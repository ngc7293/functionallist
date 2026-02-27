from collections.abc import Generator
from contextlib import contextmanager

from pydantic import PostgresDsn
from sqlalchemy import Engine
from sqlmodel import Session, create_engine

from .settings import settings


class Database:
    def __init__(self, database_url: PostgresDsn):
        self._engine = create_engine(
            str(database_url).replace("postgresql://", "postgresql+psycopg://"),
        )

    @contextmanager
    def engine(self) -> Generator[Engine, None, None]:
        yield self._engine

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        with Session(self._engine) as session:
            yield session

    def session_depends(self) -> Generator[Session, None, None]:
        """Plain generator for use with FastAPI Depends()."""
        with Session(self._engine) as session:
            yield session


database = Database(settings.database_url)
