import os
import sys
from pathlib import Path
from logging.config import fileConfig
from sqlmodel import SQLModel
from alembic import context

# Add project root (where src/ is) to PYTHONPATH
BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = os.path.join(BASE_DIR.__str__(), 'src')
sys.path.append(SRC_DIR)


# Import engine and models from your FastAPI project
from src.db.session import engine  # 👈 use your FastAPI engine
from src.models import *  # import all models so Alembic sees them


# This is Alembic Config object
config = context.config

# Interpret logging config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = str(engine.url)   # 👈 pull the URL from your app engine
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine  # 👈 use your app engine directly

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
