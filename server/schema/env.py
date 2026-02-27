from sqlmodel import SQLModel

from server.settings import settings
from server.database import database
from server.logging import configure_logging
from server.model import *  # noqa: F403

from alembic import context


def migrate() -> None:
    with database.engine() as engine:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=SQLModel.metadata)

            with context.begin_transaction():
                context.run_migrations()

configure_logging(settings.log_level)
migrate()
