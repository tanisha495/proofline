"""ProofLine database engine, session factory and dependency.

The SQLAlchemy ``Base`` lives in ``app.models._base`` and is re-exported
here for backward compatibility with any code that imports ``from app.db import Base``.
"""
from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models._base import Base  # re-export for compatibility  # noqa: F401

connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine_kwargs = {
    "connect_args": connect_args,
    "echo": False,
}
if not settings.database_url.startswith("sqlite"):
    # Revalidate idle connections (important for serverless Postgres like Neon).
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_recycle"] = 300

engine = create_engine(
    settings.database_url,
    **engine_kwargs,
)

if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize all tables defined in models."""
    import app.models  # ensure all models are registered
    Base.metadata.create_all(bind=engine)
