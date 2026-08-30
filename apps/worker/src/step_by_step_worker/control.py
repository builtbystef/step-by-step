import json
from dataclasses import dataclass
from threading import Event, Thread
from uuid import UUID

from sqlalchemy import text
from step_by_step_core.bus import control_channel, get_redis
from step_by_step_core.db import session_scope


@dataclass(frozen=True, slots=True)
class ControlFlags:
    cancel_requested: bool = False
    pause_requested: bool = False
    takeover_phase: str | None = None
    auto_handback_disabled: bool = False
    holder_present: bool = False
    handback_requested: bool = False


class RunCancelled(Exception):
    pass


class RunPaused(Exception):
    pass


def flags_from_row(run_id: UUID) -> ControlFlags:
    with session_scope() as session:
        row = (
            session.execute(
                text(
                    """
                    SELECT cancel_requested_at, pause_requested_at,
                           auto_handback_disabled, takeover_holder_session_id,
                           handback_requested_at
                    FROM runs WHERE id = :run_id
                    """
                ),
                {"run_id": run_id},
            )
            .mappings()
            .one_or_none()
        )
    if row is None:
        return ControlFlags()
    return ControlFlags(
        cancel_requested=row["cancel_requested_at"] is not None,
        pause_requested=row["pause_requested_at"] is not None,
        auto_handback_disabled=bool(row["auto_handback_disabled"]),
        holder_present=row["takeover_holder_session_id"] is not None,
        handback_requested=row["handback_requested_at"] is not None,
    )


class ControlWatch:
    def __init__(self, run_id: UUID) -> None:
        self.run_id = run_id
        self._heard_cancel = False
        self._heard_pause = False
        self._heard_handback = False
        self._stop = Event()
        self._ready = Event()
        self._thread = Thread(target=self._listen, name="run-control", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=1)

    def _listen(self) -> None:
        pubsub = None
        try:
            pubsub = get_redis().pubsub(ignore_subscribe_messages=True)
            pubsub.subscribe(control_channel(self.run_id))
            self._ready.set()
            while not self._stop.is_set():
                message = pubsub.get_message(timeout=0.1)
                if message is None or message.get("type") != "message":
                    continue
                raw = message["data"]
                if isinstance(raw, bytes):
                    raw = raw.decode()
                body = json.loads(raw)
                if body.get("cancel_requested"):
                    self._heard_cancel = True
                if body.get("pause_requested"):
                    self._heard_pause = True
                if body.get("handback"):
                    self._heard_handback = True
        finally:
            self._ready.set()
            if pubsub is not None:
                pubsub.close()

    def poll(self) -> ControlFlags:
        flags = flags_from_row(self.run_id)
        if flags.handback_requested or not flags.holder_present:
            self._heard_handback = False
        return ControlFlags(
            cancel_requested=flags.cancel_requested or self._heard_cancel,
            pause_requested=flags.pause_requested or self._heard_pause,
            takeover_phase=flags.takeover_phase,
            auto_handback_disabled=flags.auto_handback_disabled,
            holder_present=flags.holder_present,
            handback_requested=flags.handback_requested or self._heard_handback,
        )

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=1)
