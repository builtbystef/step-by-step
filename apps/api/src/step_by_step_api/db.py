"""The database seam: one engine per process, one session per request.

The connection URL comes only from the `DATABASE_URL` environment variable —
never from a file, a default, or a constructor argument. The engine is built
on first use rather than at import, so the no-services test tier and any tool
that merely imports the app need no database at all.
"""

from collections.abc import Iterator
from functools import lru_cache
from os import environ
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session


class Base(DeclarativeBase):
    """The base every table inherits; Alembic autogenerates from its metadata."""


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """The process-wide engine, built from the environment-supplied URL."""
    return create_engine(environ["DATABASE_URL"], pool_pre_ping=True)


def get_session() -> Iterator[Session]:
    """One session per request, closed when the request ends.

    Closing rolls back whatever the handler did not commit, so a failed
    request never leaves a half-written transaction behind.
    """
    with Session(get_engine()) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
"""The dependency route handlers declare to receive their request's session."""
