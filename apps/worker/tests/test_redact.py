"""The Worker redacts secret values before anything is published."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from step_by_step_worker.executor import StepOutcome
from step_by_step_worker.redact import MASK, RedactingStore

SECRET = "s3cret-zx9q2m"
SHORT = "qz"


@dataclass
class RecordingStore:
    logs: list[tuple[str, str, UUID | None]] = field(default_factory=list)
    results: list[StepOutcome] = field(default_factory=list)
    finished: list[tuple[str, str | None, str | None]] = field(default_factory=list)
    events: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    artifacts: list[tuple[str, bytes]] = field(default_factory=list)

    def start_interval(self, run_id: UUID, kind: str, at: datetime) -> object:
        return kind

    def end_interval(self, handle: object, at: datetime) -> None:
        return None

    def add_result(self, run_id: UUID, result: StepOutcome) -> None:
        self.results.append(result)

    def finish_run(
        self,
        run_id: UUID,
        status: str,
        failure_reason: str | None,
        failure_detail: str | None,
        automation_ms: int,
        at: datetime,
    ) -> None:
        self.finished.append((status, failure_reason, failure_detail))

    def emit(self, run_id: UUID, event_type: str, payload: dict[str, Any]) -> None:
        self.events.append((event_type, dict(payload)))

    def log(
        self,
        run_id: UUID,
        level: str,
        text: str,
        step_id: UUID | None = None,
    ) -> None:
        self.logs.append((level, text, step_id))

    def park(self, run_id: UUID, deadline_at: datetime, at: datetime) -> None:
        return None

    def resume(self, run_id: UUID, at: datetime) -> None:
        return None

    def release_holder(self, run_id: UUID, at: datetime) -> None:
        return None

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
        self.artifacts.append((kind, body))
        return uuid4()


def helper(secrets: list[str]) -> tuple[RedactingStore, RecordingStore]:
    inner = RecordingStore()
    return RedactingStore(inner, secrets), inner


def test_a_log_line_containing_a_secret_is_redacted_before_publish() -> None:
    store, inner = helper([SECRET])
    run_id = uuid4()

    store.log(run_id, "info", f"typed {SECRET} into the field")

    assert inner.logs == [("info", f"typed {MASK} into the field", None)]
    assert SECRET not in inner.logs[0][1]


def test_a_two_character_secret_is_redacted_too() -> None:
    store, inner = helper([SHORT])

    store.log(uuid4(), "info", f"code={SHORT} end")

    assert inner.logs[0][1] == f"code={MASK} end"
    assert SHORT not in inner.logs[0][1]


def test_an_error_string_embedding_the_secret_is_redacted_before_publish() -> None:
    store, inner = helper([SECRET])
    run_id = uuid4()
    failed = StepOutcome(
        step_id=uuid4(),
        position=0,
        status="failed",
        started_at=None,
        ended_at=datetime.now(UTC),
        error_code="action_failed",
        error_message=f"fill({SECRET}) timed out",
    )

    store.add_result(run_id, failed)
    store.finish_run(
        run_id,
        "failed",
        "step_failed",
        f"locator.fill: {SECRET} not found",
        10,
        datetime.now(UTC),
    )
    store.emit(
        run_id,
        "run.status",
        {"status": "failed", "failure_detail": f"saw {SECRET}"},
    )

    assert inner.results[0].error_message == f"fill({MASK}) timed out"
    assert SECRET not in (inner.results[0].error_message or "")
    assert inner.finished[0][2] == f"locator.fill: {MASK} not found"
    assert inner.events[0][1]["failure_detail"] == f"saw {MASK}"
