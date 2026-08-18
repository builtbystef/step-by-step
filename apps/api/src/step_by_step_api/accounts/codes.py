"""Sign-in Codes: minting them, storing what proves them, and spending them.

Six decimal digits from a CSPRNG, valid ten minutes, single-use, and one per
address at a time — requesting a code replaces the last one, so the newest is
the only one that works.

The table holds a SHA-256 of the code and never the code itself. A digest is
not a defence against guessing a six-digit number offline, and it is not meant
to be: the code's protection is its ten minutes, its single use, and the
attempt cap the throttling slice adds. What the digest buys is that a leaked
backup, a replicated table, or a query in a log hands nobody a working code.
"""

import hashlib
import secrets
from datetime import timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session as DbSession

from step_by_step_api import clock
from step_by_step_api.accounts.models import SigninCode

CODE_DIGITS = 6
"""Short enough to read out of an email and type; the caps make it enough."""

CODE_LIFETIME = timedelta(minutes=10)
"""Long enough to switch to a mail client, short enough that a guess is stale."""


def mint() -> str:
    """A fresh code: six digits from the CSPRNG, leading zeros kept.

    `randbelow` rather than `randint` on a shuffled range, because a uniform
    draw over the whole space is the only property that matters here.
    """
    return f"{secrets.randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}"


def digest(code: str) -> str:
    """What the table stores in place of the code."""
    return hashlib.sha256(code.encode()).hexdigest()


def issue(db: DbSession, email: str) -> str:
    """Replace whatever code that address had, and return the new one to send.

    `email` is the normalized address: codes are looked up by it, and the
    person who typed `Ada@Example.com` must get the code that `ada@example.com`
    was issued.
    """
    db.execute(delete(SigninCode).where(SigninCode.email == email))
    code = mint()
    db.add(
        SigninCode(
            email=email,
            code_hash=digest(code),
            expires_at=clock.now() + CODE_LIFETIME,
        )
    )
    return code


def claim(db: DbSession, email: str, code: str) -> bool:
    """Spend the address's code, and say whether it was the right live one.

    Success deletes the row, which is what makes a code single-use: the second
    attempt with the same digits finds nothing and is refused exactly like a
    wrong one. A wrong guess is counted instead — the counter is the throttling
    slice's to act on.
    """
    outstanding = db.execute(
        select(SigninCode).where(SigninCode.email == email)
    ).scalar_one_or_none()
    if outstanding is None or outstanding.expires_at <= clock.now():
        return False
    if not secrets.compare_digest(outstanding.code_hash, digest(code)):
        db.execute(
            update(SigninCode)
            .where(SigninCode.id == outstanding.id)
            .values(attempts=SigninCode.attempts + 1)
        )
        return False
    db.delete(outstanding)
    return True
