"""Postgres persistence for claims and the rows produced by execution."""

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB
from step_by_step_core.db import session_scope
from step_by_step_core.document import WorkflowDocument
from step_by_step_core.events import publish, publish_log
from step_by_step_core.objects import artifact_bucket, object_store

from step_by_step_worker.executor import RunWork, StepOutcome

CLAIM = text(
    """
    WITH claimed AS (
        UPDATE runs
        SET status = 'running',
            worker_id = :worker_id,
            worker_vnc_endpoint = :vnc_endpoint,
            started_at = :at,
            heartbeat_at = :at
        WHERE id = :run_id AND status = 'queued'
        RETURNING *
    )
    SELECT claimed.id,
           claimed.is_test,
           claimed.draft_snapshot,
           claimed.timeout_ms,
           claimed.variables,
           workflow_versions.document AS version_document,
           workflows.default_step_timeout_ms,
           workflows.takeover_timeout_ms
    FROM claimed
    JOIN workflows ON workflows.id = claimed.workflow_id
    LEFT JOIN workflow_versions
      ON workflow_versions.workflow_id = claimed.workflow_id
     AND workflow_versions.number = claimed.version_number
    """
)


class PostgresRunStore:
    """Each call is one durable unit, so a later browser failure loses no result."""

    def claim(
        self,
        run_id: UUID,
        worker_id: str,
        vnc_endpoint: str,
        at: datetime,
    ) -> RunWork | None:
        with session_scope() as session:
            claimed = (
                session.execute(
                    CLAIM,
                    {
                        "run_id": run_id,
                        "worker_id": worker_id,
                        "vnc_endpoint": vnc_endpoint,
                        "at": at,
                    },
                )
                .mappings()
                .one_or_none()
            )
            session.commit()
        return (
            work_from_claim(cast(Mapping[str, Any], claimed))
            if claimed is not None
            else None
        )

    def start_interval(self, run_id: UUID, kind: str, at: datetime) -> object:
        interval_id = uuid4()
        with session_scope() as session:
            session.execute(
                text(
                    """
                    INSERT INTO run_control_intervals
                        (id, run_id, kind, started_at, ended_at)
                    VALUES (:id, :run_id, :kind, :at, NULL)
                    """
                ),
                {"id": interval_id, "run_id": run_id, "kind": kind, "at": at},
            )
            session.commit()
        return interval_id

    def end_interval(self, handle: object, at: datetime) -> None:
        with session_scope() as session:
            session.execute(
                text("UPDATE run_control_intervals SET ended_at = :at WHERE id = :id"),
                {"id": handle, "at": at},
            )
            session.commit()

    def add_result(self, run_id: UUID, result: StepOutcome) -> None:
        statement = text(
            """
            INSERT INTO step_results (
                id, run_id, step_id, position, status, started_at, ended_at,
                matched_candidate_rank, candidate_count, completed_by_human,
                error_code, error_message, diagnostics, extracted_value
            ) VALUES (
                :id, :run_id, :step_id, :position, :status, :started_at, :ended_at,
                :rank, :candidate_count, :completed_by_human,
                :error_code, :error_message, :diagnostics, :extracted_value
            )
            """
        ).bindparams(
            bindparam("extracted_value", type_=JSONB),
            bindparam("diagnostics", type_=JSONB),
        )
        with session_scope() as session:
            session.execute(
                statement,
                {
                    "id": uuid4(),
                    "run_id": run_id,
                    "step_id": result.step_id,
                    "position": result.position,
                    "status": result.status,
                    "started_at": result.started_at,
                    "ended_at": result.ended_at,
                    "rank": result.matched_candidate_rank,
                    "candidate_count": result.candidate_count,
                    "error_code": result.error_code,
                    "error_message": result.error_message,
                    "diagnostics": result.diagnostics,
                    "extracted_value": result.extracted_value,
                    "completed_by_human": result.completed_by_human,
                },
            )
            session.commit()

    def finish_run(
        self,
        run_id: UUID,
        status: str,
        failure_reason: str | None,
        failure_detail: str | None,
        automation_ms: int,
        at: datetime,
    ) -> None:
        with session_scope() as session:
            session.execute(
                text(
                    """
                    UPDATE runs
                    SET status = :status,
                        failure_reason = :failure_reason,
                        failure_detail = :failure_detail,
                        automation_ms = :automation_ms,
                        heartbeat_at = :at,
                        ended_at = :at
                    WHERE id = :run_id AND status = 'running'
                    """
                ),
                {
                    "run_id": run_id,
                    "status": status,
                    "failure_reason": failure_reason,
                    "failure_detail": failure_detail,
                    "automation_ms": automation_ms,
                    "at": at,
                },
            )
            session.commit()

    def emit(self, run_id: UUID, event_type: str, payload: Mapping[str, Any]) -> None:
        publish(run_id, event_type, dict(payload))

    def log(
        self,
        run_id: UUID,
        level: str,
        text: str,
        step_id: UUID | None = None,
    ) -> None:
        publish_log(run_id, level=level, text=text, step_id=step_id)

    def park(self, run_id: UUID, deadline_at: datetime, at: datetime) -> None:
        with session_scope() as session:
            session.execute(
                text(
                    """
                    UPDATE runs
                    SET status = 'waiting_for_human',
                        takeover_deadline_at = :deadline_at,
                        pause_requested_at = NULL,
                        handback_requested_at = NULL,
                        auto_handback_disabled = false,
                        heartbeat_at = :at
                    WHERE id = :run_id AND status = 'running'
                    """
                ),
                {"run_id": run_id, "deadline_at": deadline_at, "at": at},
            )
            session.commit()

    def resume(self, run_id: UUID, at: datetime) -> None:
        with session_scope() as session:
            session.execute(
                text(
                    """
                    UPDATE runs
                    SET status = 'running',
                        takeover_holder_session_id = NULL,
                        handback_requested_at = NULL,
                        auto_handback_disabled = false,
                        heartbeat_at = :at
                    WHERE id = :run_id AND status = 'waiting_for_human'
                    """
                ),
                {"run_id": run_id, "at": at},
            )
            session.commit()

    def release_holder(self, run_id: UUID, at: datetime) -> None:
        with session_scope() as session:
            session.execute(
                text(
                    """
                    UPDATE runs
                    SET takeover_holder_session_id = NULL,
                        handback_requested_at = NULL,
                        auto_handback_disabled = false,
                        heartbeat_at = :at
                    WHERE id = :run_id AND status = 'waiting_for_human'
                    """
                ),
                {"run_id": run_id, "at": at},
            )
            session.commit()

    def add_artifact(
        self,
        run_id: UUID,
        *,
        kind: str,
        body: bytes,
        content_type: str,
        index: int,
        step_id: UUID | None = None,
        filename: str = "",
    ) -> UUID:
        artifact_id = uuid4()
        name = Path(filename).name or kind
        object_key = f"runs/{run_id}/{artifact_id}/{name}"
        safe_name = name.replace('"', "")
        object_store().put_object(
            Bucket=artifact_bucket(),
            Key=object_key,
            Body=body,
            ContentType=content_type,
            ContentDisposition=f'attachment; filename="{safe_name}"',
        )
        with session_scope() as session:
            session.execute(
                text(
                    """
                    INSERT INTO artifacts (
                        id, run_id, step_id, kind, object_key, content_type,
                        size_bytes, index
                    ) VALUES (
                        :id, :run_id, :step_id, :kind, :object_key, :content_type,
                        :size_bytes, :index
                    )
                    """
                ),
                {
                    "id": artifact_id,
                    "run_id": run_id,
                    "step_id": step_id,
                    "kind": kind,
                    "object_key": object_key,
                    "content_type": content_type,
                    "size_bytes": len(body),
                    "index": index,
                },
            )
            session.commit()
        publish(
            run_id,
            "artifact",
            {
                "run_id": run_id,
                "step_id": step_id,
                "artifact_id": artifact_id,
                "kind": kind,
                "at": datetime.now(UTC),
            },
        )
        return artifact_id


def work_from_claim(claimed: Mapping[str, Any]) -> RunWork:
    """Select the immutable execution document from one conditionally claimed row."""
    document = (
        claimed["draft_snapshot"] if claimed["is_test"] else claimed["version_document"]
    )
    if document is None:
        raise ValueError("a claimed Run has no executable document")
    return RunWork(
        run_id=claimed["id"],
        document=WorkflowDocument.model_validate(document),
        default_step_timeout_ms=claimed["default_step_timeout_ms"],
        timeout_ms=claimed["timeout_ms"],
        variables=claimed["variables"],
        takeover_timeout_ms=claimed.get("takeover_timeout_ms", 1_800_000),
    )
