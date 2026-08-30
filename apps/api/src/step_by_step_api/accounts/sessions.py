import hashlib
import secrets
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DbSession

from step_by_step_api import clock
from step_by_step_api.accounts.models import Session, User
from step_by_step_api.db import SessionDep
from step_by_step_api.errors import ApiError

SESSION_COOKIE = "session"

TOKEN_BYTES = 32

SESSION_LIFETIME = timedelta(days=30)

TOUCH_INTERVAL = timedelta(hours=1)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def begin(db: DbSession, user: User) -> str:
    token = secrets.token_urlsafe(TOKEN_BYTES)
    now = clock.now()
    db.add(Session(token_hash=token_digest(token), user_id=user.id, last_seen_at=now))
    return token


def end(db: DbSession, token: str) -> None:
    db.execute(delete(Session).where(Session.token_hash == token_digest(token)))


def end_all(db: DbSession, user: User) -> None:
    db.execute(delete(Session).where(Session.user_id == user.id))


def carry(request: Request, response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_LIFETIME.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
    )


def drop(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def signed_in_user(request: Request, response: Response, db: DbSession) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise ApiError(401, "unauthenticated", "no session")
    found = db.execute(
        select(Session, User)
        .join(User, User.id == Session.user_id)
        .where(Session.token_hash == token_digest(token))
    ).one_or_none()
    if found is None:
        raise ApiError(401, "unauthenticated", "no session")
    session, user = found
    now = clock.now()
    if now - session.last_seen_at >= SESSION_LIFETIME:
        db.delete(session)
        db.commit()
        raise ApiError(401, "unauthenticated", "no session")
    if now - session.last_seen_at >= TOUCH_INTERVAL:
        session.last_seen_at = now
        db.commit()
        # Slide the cookie with the server-side session.
        carry(request, response, token)
    return user


def current_user(request: Request, response: Response, db: SessionDep) -> User:
    return signed_in_user(request, response, db)


CurrentUser = Annotated[User, Depends(current_user)]
