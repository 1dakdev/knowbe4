from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


def sqlite_connect_args(url: str) -> dict:
    return {"check_same_thread": False} if url.startswith("sqlite") else {}


def enable_sqlite_foreign_keys(engine: Engine, url: str) -> None:
    if not url.startswith("sqlite"):
        return

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


settings = get_settings()
engine = create_engine(settings.database_url, connect_args=sqlite_connect_args(settings.database_url))
enable_sqlite_foreign_keys(engine, settings.database_url)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
