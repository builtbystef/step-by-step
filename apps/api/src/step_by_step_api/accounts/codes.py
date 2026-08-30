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

CODE_LIFETIME = timedelta(minutes=10)

ATTEMPT_CAP = 5

ISSUANCE_LIMIT = 5

ISSUANCE_WINDOW = timedelta(hours=1)


def mint() -> str:
    return f"{secrets.randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}"


def digest(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def count_issuance(db: DbSession, email: str) -> int:
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


def sweep_closed_windows(db: DbSession) -> None:
    db.execute(
        delete(CodeIssuance).where(
            CodeIssuance.window_started_at <= clock.now() - ISSUANCE_WINDOW
        )
    )


def issue(db: DbSession, email: str) -> str:
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
    ACCEPTED = "accepted"

    WRONG = "wrong"

    EXHAUSTED = "exhausted"


def claim(db: DbSession, email: str, code: str) -> Attempt:
    outstanding = db.execute(
        select(SigninCode).where(SigninCode.email == email)
    ).scalar_one_or_none()
    if outstanding is None:
        return Attempt.WRONG
    if outstanding.expires_at <= clock.now():
        db.delete(outstanding)
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
