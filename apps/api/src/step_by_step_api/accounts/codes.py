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
from enum import StrEnum

from sqlalchemy import case, delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session as DbSession

from step_by_step_api import clock
from step_by_step_api.accounts.models import CodeIssuance, SigninCode

CODE_DIGITS = 6
"""Short enough to read out of an email and type; the caps make it enough."""

CODE_LIFETIME = timedelta(minutes=10)
"""Long enough to switch to a mail client, short enough that a guess is stale."""

ATTEMPT_CAP = 5
"""Wrong guesses one code survives.

Five is what turns a million possible codes into a defence: a guesser gets
five of them per code, and asking for a code of their own to guess at is what
the issuance limit meets. Generous enough that nobody mistyping their own
code runs out of it.
"""

ISSUANCE_LIMIT = 5
"""Codes one address is sent per window.

The cap and this are one defence between them: five guesses at a code is only
a limit while codes are scarce, and this is what makes them scarce. Five an
hour is more than anybody who mislaid an email needs and far less than a
mailbox being used as a doorbell.
"""

ISSUANCE_WINDOW = timedelta(hours=1)
"""How long those five are counted for, from the first of them."""


def mint() -> str:
    """A fresh code: six digits from the CSPRNG, leading zeros kept.

    `randbelow` rather than `randint` on a shuffled range, because a uniform
    draw over the whole space is the only property that matters here.
    """
    return f"{secrets.randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}"


def digest(code: str) -> str:
    """What the table stores in place of the code."""
    return hashlib.sha256(code.encode()).hexdigest()


def count_issuance(db: DbSession, email: str) -> int:
    """Count one request against the address's window, and say where it lands.

    A fixed window: the first request of an hour opens it, and the request
    that arrives after it has closed opens the next one. One statement, so
    that two requests at once cannot both read four and both write five —
    Postgres settles the order, and the row is the only place the count lives.

    The number comes back rather than a verdict, so the caller decides what
    being over the limit means; here it is only arithmetic.
    """
    now = clock.now()
    opened_within_the_window = CodeIssuance.window_started_at > now - ISSUANCE_WINDOW
    counted = (
        insert(CodeIssuance)
        .values(email=email, issued=1, window_started_at=now)
        .on_conflict_do_update(
            index_elements=[CodeIssuance.email],
            set_={
                "issued": case(
                    (opened_within_the_window, CodeIssuance.issued + 1), else_=1
                ),
                "window_started_at": case(
                    (opened_within_the_window, CodeIssuance.window_started_at),
                    else_=now,
                ),
            },
        )
        .returning(CodeIssuance.issued)
    )
    return db.execute(counted).scalar_one()


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


class Attempt(StrEnum):
    """How an entered code came out, which is what the caller answers with."""

    ACCEPTED = "accepted"
    """Right, live, and now spent."""

    WRONG = "wrong"
    """Wrong, expired, already spent, or never issued — one outcome for all
    four, because telling them apart tells a guesser how close they are."""

    EXHAUSTED = "exhausted"
    """This code has taken its wrong guesses and no longer answers to any."""


def claim(db: DbSession, email: str, code: str) -> Attempt:
    """Spend the address's code, and say how the attempt came out.

    Success deletes the row, which is what makes a code single-use: the second
    attempt with the same digits finds nothing and is refused exactly like a
    wrong one. A wrong guess is counted instead, and once the count reaches the
    cap the row stops answering — to the right code as much as to a wrong one,
    because a guesser who has spent five tries must not be handed the sixth by
    finally getting it right. The row stays where it is, refusing, until it
    expires or the next request replaces it: that request is the recovery, and
    it is the one the person who owns the address can ask for.
    """
    outstanding = db.execute(
        select(SigninCode).where(SigninCode.email == email)
    ).scalar_one_or_none()
    if outstanding is None or outstanding.expires_at <= clock.now():
        return Attempt.WRONG
    if outstanding.attempts >= ATTEMPT_CAP:
        return Attempt.EXHAUSTED
    if not secrets.compare_digest(outstanding.code_hash, digest(code)):
        db.execute(
            update(SigninCode)
            .where(SigninCode.id == outstanding.id)
            .values(attempts=SigninCode.attempts + 1)
        )
        return Attempt.WRONG
    db.delete(outstanding)
    return Attempt.ACCEPTED
