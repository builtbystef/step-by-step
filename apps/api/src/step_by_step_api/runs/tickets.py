import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session as DbSession

from step_by_step_api import clock
from step_by_step_api.runs.models import RunTakeoverTicket

TICKET_TTL = timedelta(seconds=60)


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def mint_ticket(db: DbSession, run_id: UUID, session_id: str) -> tuple[str, datetime]:
    token = secrets.token_urlsafe(32)
    expires_at = clock.now() + TICKET_TTL
    db.add(
        RunTakeoverTicket(
            token_hash=digest(token),
            run_id=run_id,
            session_id=session_id,
            expires_at=expires_at,
        )
    )
    return token, expires_at


@dataclass(frozen=True, slots=True)
class RedeemedTicket:
    run_id: UUID
    session_id: str


def redeem_ticket(db: DbSession, presented: str) -> RedeemedTicket | None:
    row = db.get(RunTakeoverTicket, digest(presented))
    if row is None or row.redeemed_at is not None or row.expires_at <= clock.now():
        return None
    row.redeemed_at = clock.now()
    return RedeemedTicket(run_id=row.run_id, session_id=row.session_id)
