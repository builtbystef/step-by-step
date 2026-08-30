import hashlib
from datetime import datetime, timedelta
from secrets import choice

from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DbSession

from step_by_step_api import clock
from step_by_step_api.accounts.models import User
from step_by_step_api.extension.models import ExtensionConnectCode

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

GROUPS = 3
GROUP_LENGTH = 4
CODE_LENGTH = GROUPS * GROUP_LENGTH

CODE_LIFETIME = timedelta(minutes=10)


def mint() -> str:
    drawn = "".join(choice(ALPHABET) for _ in range(CODE_LENGTH))
    return "-".join(
        drawn[at : at + GROUP_LENGTH] for at in range(0, CODE_LENGTH, GROUP_LENGTH)
    )


def normalize(entered: str) -> str:
    return "".join(character for character in entered.upper() if character in ALPHABET)


def digest(code: str) -> str:
    return hashlib.sha256(normalize(code).encode()).hexdigest()


def issue(db: DbSession, user: User) -> tuple[str, datetime]:
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
