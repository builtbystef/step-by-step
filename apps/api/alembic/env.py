import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Enum, engine_from_config, pool
from sqlalchemy.schema import CheckConstraint, SchemaItem
from step_by_step_core.db import Base

config = context.config

config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"].replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

import step_by_step_api.accounts.models  # noqa: E402
import step_by_step_api.auth_states.models  # noqa: E402
import step_by_step_api.batches.models  # noqa: E402
import step_by_step_api.extension.models  # noqa: E402
import step_by_step_api.runs.models  # noqa: E402
import step_by_step_api.schedules.models  # noqa: E402
import step_by_step_api.secrets.models  # noqa: E402
import step_by_step_api.workflows.models  # noqa: E402, F401

target_metadata = Base.metadata

TYPE_BOUND_CHECKS = {
    (table.name, column.type.name)
    for table in target_metadata.tables.values()
    for column in table.columns
    if isinstance(column.type, Enum)
    and not column.type.native_enum
    and column.type.create_constraint
}


def include_object(
    obj: SchemaItem,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: SchemaItem | None,
) -> bool:
    if reflected and isinstance(obj, CheckConstraint):
        return (obj.table.name, name) not in TYPE_BOUND_CHECKS
    return True


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        include_object=include_object,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
