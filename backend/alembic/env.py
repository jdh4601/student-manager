from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

from app.database import Base
from app.config import settings
from app import models  # noqa: F401  # ensure models are imported for metadata

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config


def _syncify_url(url: str) -> str:
    if "+asyncpg" in url:
        return url.replace("+asyncpg", "")
    if "+aiosqlite" in url:
        return url.replace("+aiosqlite", "")
    return url


# Ensure sqlalchemy.url is set from runtime settings (DATABASE_URL) and use sync driver for Alembic
url_opt = config.get_main_option("sqlalchemy.url")
if not url_opt:
    try:
        url_opt = settings.database_url
    except Exception:
        url_opt = "sqlite:///./test.db"
config.set_main_option("sqlalchemy.url", _syncify_url(url_opt))

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
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
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
