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
"""How long a session may go unused before it is over.

Sliding rather than fixed: being used is what buys the next thirty days, so
somebody who visits weekly never signs in again and somebody who walks away
from a borrowed machine is signed out of it within the month.
"""

TOUCH_INTERVAL = timedelta(hours=1)
"""How stale `last_seen_at` may get before a request writes it again.

Every request would otherwise write a row, which is a write per read of every
screen for no gain: what the column is for is measuring silence in days, and
an hour of resolution measures that exactly as well.
"""


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


def end_all(db: DbSession, user: User) -> None:
    """Revoke every session this user has, including the one asking.

    Signing out everywhere is for a browser somebody no longer has, so it must
    reach the sessions this request cannot see. Keeping the current one would
    make the action a lie on the one machine that can read it.
    """
    db.execute(delete(Session).where(Session.user_id == user.id))


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


def signed_in_user(request: Request, response: Response, db: DbSession) -> User:
    """The user this request is acting as, or a refusal.

    One code for every way a request can fail to be signed in — no cookie, a
    token that matches no row, a session that was revoked, a session nobody
    used for a month — because a client does the same thing about all of them,
    and telling them apart would say which tokens once existed.

    This commits, which no other dependency does. Both writes it can make —
    the slide and the reaping of an expired row — are the session layer's own
    bookkeeping rather than the handler's work, and both must survive an answer
    the handler then refuses to give.
    """
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
        # Deleted rather than merely refused: the row is dead weight from here
        # on, and reaping it where it is found is the whole of the cleanup this
        # table needs.
        db.delete(session)
        db.commit()
        raise ApiError(401, "unauthenticated", "no session")
    if now - session.last_seen_at >= TOUCH_INTERVAL:
        session.last_seen_at = now
        db.commit()
        # And the cookie slides with the row. It carries a 30-day lifetime of
        # its own, so a browser told nothing more would drop it 30 days after
        # signing in and leave a live session nobody could reach — extending
        # in the store alone extends nothing anybody can use.
        carry(request, response, token)
    return user


def current_user(request: Request, response: Response, db: SessionDep) -> User:
    """The dependency a route declares to be signed-in-only.

    The `Response` is FastAPI's own for this request, and what a dependency
    writes on it reaches a handler's answer — for the handlers that answer with
    a model, which is every read the app makes. A handler returning a `Response`
    of its own replaces it wholesale, and the two that do are `logout` and
    `logout-all`, which are taking the cookie away rather than renewing it.
    """
    return signed_in_user(request, response, db)


CurrentUser = Annotated[User, Depends(current_user)]
"""A route parameter of this type is a route no signed-out visitor reaches."""
