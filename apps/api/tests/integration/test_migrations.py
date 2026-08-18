"""The migration runner against a real Postgres."""

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from step_by_step_api.db import get_engine

pytestmark = pytest.mark.integration


def head_revision(runner: Config) -> str | None:
    return ScriptDirectory.from_config(runner).get_current_head()


def stamped_revision() -> str:
    with get_engine().connect() as connection:
        version = connection.execute(text("SELECT version_num FROM alembic_version"))
        return version.scalar_one()


def test_migrating_a_fresh_database_reaches_head(migration_runner: Config) -> None:
    assert stamped_revision() == head_revision(migration_runner)


def test_migrating_again_changes_nothing(migration_runner: Config) -> None:
    command.upgrade(migration_runner, "head")

    assert stamped_revision() == head_revision(migration_runner)
