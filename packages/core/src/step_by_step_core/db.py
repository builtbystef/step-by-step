from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from os import environ

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session


class Base(DeclarativeBase):
    pass


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(environ["DATABASE_URL"], pool_pre_ping=True)


@contextmanager
def session_scope() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session


def get_session() -> Iterator[Session]:
    with session_scope() as session:
        yield session
