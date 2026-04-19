"""
Alembic environment configuration.

This file runs whenever you invoke `alembic upgrade head` or `alembic revision`.
It hooks Alembic into our app's settings (so we don't hardcode DB URLs)
and into our SQLAlchemy Base (so autogenerate works).
"""
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# --- Make `app.*` importable from this script ---
# env.py lives at backend/alembic/env.py; the app is at backend/app/...
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from app.db.session import Base  # noqa: E402

# Import all models so Alembic's autogenerate sees them
from app.models import all_models  # noqa: E402, F401

# This is the Alembic Config object; provides access to the .ini values
config = context.config

# Override the sqlalchemy.url from alembic.ini with our real URL (sync driver)
config.set_main_option("sqlalchemy.url", settings.sync_database_url)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata object that Alembic compares against the DB to autogenerate migrations
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode — emits SQL to a file without a live DB.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode — connects to the database and executes."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
