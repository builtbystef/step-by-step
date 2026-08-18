"""The database seam: one engine per process, one session per unit of work.

Backend and Workers both write through this module — Workers write Step
Results, log lines, control intervals, and Run status straight to Postgres
rather than routing them through the backend.

The connection URL comes only from the `DATABASE_URL` environment variable —
never from a file, a default, or a constructor argument. The engine is built
on first use rather than at import, so the no-services test tier and any tool
that merely imports a process need no database at all.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from os import environ

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session


class Base(DeclarativeBase):
    """The base every table inherits; Alembic autogenerates from its metadata."""


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """The process-wide engine, built from the environment-supplied URL."""
    return create_engine(environ["DATABASE_URL"], pool_pre_ping=True)


@contextmanager
def session_scope() -> Iterator[Session]:
    """One session for one unit of work, closed when the block ends.

    Closing rolls back whatever the caller did not commit, so a failure never
    leaves a half-written transaction behind. This is the form a Worker uses;
    the backend reaches the same session through its request dependency.
    """
    with Session(get_engine()) as session:
        yield session


def get_session() -> Iterator[Session]:
    """One session per request — the generator FastAPI resolves as a dependency."""
    with session_scope() as session:
        yield session
