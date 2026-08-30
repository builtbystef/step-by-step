import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text as sql_text

from step_by_step_core.bus import get_redis
from step_by_step_core.db import session_scope

LOG_LINE_CAP = 10_000
TRUNCATION_TEXT = "log truncated"
ARTIFACT_FIELDS = frozenset({"run_id", "step_id", "artifact_id", "kind", "at"})
TERMINAL_STATUSES = frozenset({"succeeded", "failed", "cancelled"})
TERMINAL_CHANNEL = "runs:terminal"


def events_channel(run_id: UUID) -> str:
    return f"run:{run_id}:events"


def batch_events_channel(batch_id: UUID) -> str:
    return f"batch:{batch_id}:events"


def publish(run_id: UUID, event_type: str, payload: dict[str, Any]) -> None:
    body = {"type": event_type, **jsonable(payload)}
    if event_type == "artifact":
        body = {
            key: value
            for key, value in body.items()
            if key in {"type", *ARTIFACT_FIELDS}
        }
    get_redis().publish(events_channel(run_id), json.dumps(body))
    if event_type == "run.status" and body.get("status") in TERMINAL_STATUSES:
        get_redis().publish(TERMINAL_CHANNEL, json.dumps(body))


def publish_batch(batch_id: UUID, event_type: str, payload: dict[str, Any]) -> None:
    body = {"type": event_type, **jsonable(payload)}
    get_redis().publish(batch_events_channel(batch_id), json.dumps(body))


def publish_log(
    run_id: UUID,
    *,
    level: str,
    text: str,
    step_id: UUID | None = None,
    at: datetime | None = None,
) -> int | None:
    stamped = at or datetime.now(UTC)
    with session_scope() as session:
        count = session.execute(
            sql_text("SELECT COUNT(*) FROM run_log_lines WHERE run_id = :run_id"),
            {"run_id": run_id},
        ).scalar_one()
        if count > LOG_LINE_CAP:
            return None
        if count == LOG_LINE_CAP:
            level = "warning"
            text = TRUNCATION_TEXT
            step_id = None
        seq = count + 1
        session.execute(
            sql_text(
                """
                INSERT INTO run_log_lines (id, run_id, seq, step_id, level, at, text)
                VALUES (:id, :run_id, :seq, :step_id, :level, :at, :text)
                """
            ),
            {
                "id": uuid4(),
                "run_id": run_id,
                "seq": seq,
                "step_id": step_id,
                "level": level,
                "at": stamped,
                "text": text,
            },
        )
        session.commit()
    publish(
        run_id,
        "log",
        {
            "run_id": run_id,
            "seq": seq,
            "step_id": step_id,
            "level": level,
            "text": text,
            "at": stamped,
        },
    )
    return seq


def jsonable(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items() if item is not None}
    if isinstance(value, (bytes, bytearray)):
        return None
    return value
