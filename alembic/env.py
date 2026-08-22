from logging.config import fileConfig

from alembic import context

from trd_bot.core.config import get_settings
from trd_bot.db import DatabaseBase, create_database_engine
from trd_bot.db import models as database_models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = DatabaseBase.metadata


def get_database_url() -> str:
    """Use an explicit Alembic URL or fall back to application settings."""

    configured_url = config.get_main_option("sqlalchemy.url")
    return configured_url or get_settings().database_url


def run_migrations_offline() -> None:
    """Run migrations without creating a database connection."""

    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against the configured database connection."""

    engine = create_database_engine(get_database_url())
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
            )

            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
