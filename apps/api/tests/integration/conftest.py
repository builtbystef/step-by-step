"""The integration tier's fixtures.

Every test here runs against the real Postgres from the compose stack. That
stack is long-lived shared state, so the tier never assumes a fresh one: each
run creates a database of its own, migrates it, and drops it afterwards.
"""

import os
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from step_by_step_api.db import get_engine

ALEMBIC_INI = Path(__file__).parents[2] / "alembic.ini"


@pytest.fixture
def migration_runner() -> Config:
    """The migration runner, configured exactly as the command line configures it."""
    return Config(str(ALEMBIC_INI))


@pytest.fixture(scope="session")
def run_database_url() -> Iterator[str]:
    """A database this run owns, on the shared compose Postgres."""
    admin_url = make_url(os.environ["DATABASE_URL"])
    name = f"stepbystep_test_{uuid4().hex[:12]}"
    admin_engine = create_engine(
        admin_url.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    try:
        with admin_engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
        yield admin_url.set(database=name).render_as_string(hide_password=False)
        with admin_engine.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    finally:
        admin_engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def migrated_database(run_database_url: str) -> Iterator[None]:
    """Point the app's engine at this run's database and migrate it to head."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("DATABASE_URL", run_database_url)
        get_engine.cache_clear()
        command.upgrade(Config(str(ALEMBIC_INI)), "head")
        yield
        get_engine().dispose()
    get_engine.cache_clear()
