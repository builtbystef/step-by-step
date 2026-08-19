"""Connect codes: minting them, storing what proves them, and spending them.

The fallback half of the connect flow. When the extension cannot be handed the
handshake on the app's connect page, the app shows one of these and the person
pastes it into the popup; spending it tells the extension that the address they
typed is a live instance whose signed-in user authorized the pairing.

Twelve characters rather than the Sign-in Code's six digits, because this one
is not sent to an address only its owner reads — it is on a screen, and its
protection is its own length. The alphabet leaves out the characters people
mistake for each other, and the code is shown in groups because it is copied by
hand as often as it is pasted.
"""

import hashlib
from datetime import datetime, timedelta
from secrets import choice

from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DbSession

from step_by_step_api import clock
from step_by_step_api.accounts.models import User
from step_by_step_api.extension.models import ExtensionConnectCode

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
"""Uppercase and digits, without I, L, O, 0, and 1."""

GROUPS = 3
GROUP_LENGTH = 4
CODE_LENGTH = GROUPS * GROUP_LENGTH

CODE_LIFETIME = timedelta(minutes=10)
"""Long enough to reach the popup with it, short enough that a screenshot rots."""


def mint() -> str:
    """A fresh code, in the groups it is shown in."""
    drawn = "".join(choice(ALPHABET) for _ in range(CODE_LENGTH))
    return "-".join(
        drawn[at : at + GROUP_LENGTH] for at in range(0, CODE_LENGTH, GROUP_LENGTH)
    )


def normalize(entered: str) -> str:
    """The code inside whatever was pasted.

    A selection drags spaces along, a person retypes it without the dashes, and
    a phone capitalizes nothing. None of that is a different code, so none of it
    is a refusal.
    """
    return "".join(character for character in entered.upper() if character in ALPHABET)


def digest(code: str) -> str:
    """What the table stores in place of the code."""
    return hashlib.sha256(normalize(code).encode()).hexdigest()


def issue(db: DbSession, user: User) -> tuple[str, datetime]:
    """Take a code for this user, and say when it stops working.

    Codes that ran out are swept here rather than by anything scheduled: the
    table is only ever written on this path, so this is the one moment it is
    known to be worth looking at.
    """
    db.execute(
        delete(ExtensionConnectCode).where(
            ExtensionConnectCode.expires_at <= clock.now()
        )
    )
    code = mint()
    expires_at = clock.now() + CODE_LIFETIME
    db.add(
        ExtensionConnectCode(
            user_id=user.id, code_hash=digest(code), expires_at=expires_at
        )
    )
    return code, expires_at


def claim(db: DbSession, entered: str) -> bool:
    """Spend a code, and say whether it was a live one.

    Success deletes the row, which is the whole of "single-use": a second
    attempt with the same characters finds nothing and is refused exactly like
    a code nobody ever issued.
    """
    if len(normalize(entered)) != CODE_LENGTH:
        return False
    outstanding = db.execute(
        select(ExtensionConnectCode).where(
            ExtensionConnectCode.code_hash == digest(entered)
        )
    ).scalar_one_or_none()
    if outstanding is None or outstanding.expires_at <= clock.now():
        return False
    db.delete(outstanding)
    return True
