# Alembic environment configuration
import asyncio
from logging.config import fileConfig

from alembic import context
from alembic.script import ScriptDirectory

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import settings
from app.models.base import Base

# IMPORTANT:
# імпорт усіх моделей для autogenerate
import app.models  # noqa


config = context.config

config.set_main_option(
    "sqlalchemy.url",
    settings.db.url,
)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def process_revision_directives(
    context,
    revision,
    directives,
):
    """
    Автоматична нумерація міграцій:

    00001
    00002
    00003
    """

    if not directives:
        return

    migration_script = directives[0]

    head_revision = (
        ScriptDirectory
        .from_config(context.config)
        .get_current_head()
    )

    if head_revision is None:
        new_revision = 1
    else:
        new_revision = int(head_revision.lstrip("0")) + 1

    migration_script.rev_id = f"{new_revision:05}"


def run_migrations_offline() -> None:
    """
    Offline migrations.
    """

    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named",
        },
        compare_type=True,
        compare_server_default=True,
        process_revision_directives=process_revision_directives,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(
    connection: Connection,
) -> None:

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        process_revision_directives=process_revision_directives,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:

    connectable = async_engine_from_config(
        config.get_section(
            config.config_ini_section,
            {},
        ),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(
            do_run_migrations,
        )

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(
        run_async_migrations(),
    )


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()