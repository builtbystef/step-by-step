"""Sessions: an opaque token in a cookie, and a row that can be deleted.

Server-side sessions rather than JWTs, deliberately (ADR 0005). Signing out
everywhere, removing a member, and deleting an account all have to end access
*now*, and a token the server does not store cannot be taken back. The row is
the truth; the cookie only carries the key to it.

The token is 256 bits from the CSPRNG, and the table holds only its SHA-256 —
so a reader of the table, or of a backup, holds nothing they can present.
"""

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
"""The cookie the browser carries. One origin, so no domain and no prefix."""

TOKEN_BYTES = 32
"""256 bits — comfortably past the 128 the design calls for, and free."""

SESSION_LIFETIME = timedelta(days=30)
"""How long a session may go unused. Sliding it is the session-expiry slice's."""


def token_digest(token: str) -> str:
    """What the table stores in place of the token."""
    return hashlib.sha256(token.encode()).hexdigest()


def begin(db: DbSession, user: User) -> str:
    """Open a session for a user and return the token to hand the browser."""
    token = secrets.token_urlsafe(TOKEN_BYTES)
    now = clock.now()
    db.add(Session(token_hash=token_digest(token), user_id=user.id, last_seen_at=now))
    return token


def end(db: DbSession, token: str) -> None:
    """Revoke one session, which is deleting its row and nothing else."""
    db.execute(delete(Session).where(Session.token_hash == token_digest(token)))


def carry(request: Request, response: Response, token: str) -> None:
    """Put the token in the cookie the browser will send back.

    `httponly` keeps it away from scripts, `samesite=lax` is the whole CSRF
    story for an app served from one origin, and `secure` follows the scheme
    the request arrived on — a development instance on plain HTTP would drop a
    Secure cookie on the floor and never sign anyone in.
    """
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
    """Take the cookie back, so a signed-out browser stops sending a dead key."""
    response.delete_cookie(SESSION_COOKIE, path="/")


def signed_in_user(request: Request, db: DbSession) -> User:
    """The user this request is acting as, or a refusal.

    One code for every way a request can fail to be signed in — no cookie, a
    token that matches no row, a session that was revoked — because a client
    does the same thing about all of them, and telling them apart would say
    which tokens once existed.
    """
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise ApiError(401, "unauthenticated", "no session")
    user = db.execute(
        select(User)
        .join(Session, Session.user_id == User.id)
        .where(Session.token_hash == token_digest(token))
    ).scalar_one_or_none()
    if user is None:
        raise ApiError(401, "unauthenticated", "no session")
    return user


def current_user(request: Request, db: SessionDep) -> User:
    """The dependency a route declares to be signed-in-only."""
    return signed_in_user(request, db)


CurrentUser = Annotated[User, Depends(current_user)]
"""A route parameter of this type is a route no signed-out visitor reaches."""
