"""Single-use takeover tickets. The VNC path spends them; this slice mints them."""

import hashlib
import secrets
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session as DbSession

from step_by_step_api import clock
from step_by_step_api.runs.models import RunTakeoverTicket

TICKET_TTL = timedelta(seconds=60)
"""Long enough to open the socket, short enough a leaked ticket rots."""


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def mint_ticket(db: DbSession, run_id: UUID, session_id: str) -> tuple[str, datetime]:
    """A fresh ticket for this Run and holding session, and when it expires."""
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


def redeem_ticket(db: DbSession, presented: str) -> UUID | None:
    """Spend a ticket. Returns its Run id, or None if it is no good.

    Missing, expired, and already-spent are the same answer: a second redeem
    must not confirm that a ticket once existed.
    """
    row = db.get(RunTakeoverTicket, digest(presented))
    if row is None or row.redeemed_at is not None or row.expires_at <= clock.now():
        return None
    row.redeemed_at = clock.now()
    return row.run_id
