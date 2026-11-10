"""Shared test fixtures for ProofLine backend tests.

IMPORTANT — Database requirements
----------------------------------
DB-dependent tests require the PostgreSQL container from docker-compose.yml to
be running.  If it is not reachable the test session **fails** (not skips) with
a clear error message telling the user what to do.

Start the database with:
    docker compose up -d db

The tests run against the **proofline_test** database, which is isolated from
the development database (proofline).  Create it once inside the container:
    docker exec proofline-db-1 psql -U proofline -c "CREATE DATABASE proofline_test OWNER proofline"

Environment variables:
    TEST_DATABASE_URL   Override the test DB URL (optional).
                        Default: postgresql+psycopg://proofline:proofline@localhost:5432/proofline_test

Fixtures provided:
    client       : FastAPI TestClient (no DB required)
    db_engine    : Session-scoped SQLAlchemy engine — FAILS session if no PG
    alembic_cfg  : Alembic Config pointed at alembic.ini with test URL
    migrated_db  : Runs `alembic upgrade head` once per session, `downgrade base` at teardown
    db_conn      : Per-test connection; wraps each test in a SAVEPOINT that is
                   always rolled back so constraint tests cannot bleed.
"""
from __future__ import annotations

import os
import pathlib

import pytest
from fastapi.testclient import TestClient

from app.main import app

# ---------------------------------------------------------------------------
# Non-DB fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client(migrated_db):
    """Create a FastAPI test client configured to use the proofline_test database."""
    from sqlalchemy.orm import sessionmaker
    from app.db import get_db

    TestSession = sessionmaker(bind=migrated_db, expire_on_commit=False)

    def _get_test_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _get_test_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def db_session(migrated_db):
    """Provide a database session against proofline_test for test setup/inspection."""
    from sqlalchemy.orm import sessionmaker
    TestSession = sessionmaker(bind=migrated_db, expire_on_commit=False)
    session = TestSession()
    yield session
    session.close()


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

DEFAULT_TEST_DB_URL = (
    "postgresql+psycopg://proofline:proofline@localhost:5432/proofline_test"
)

_UNREACHABLE_MSG = """
╔══════════════════════════════════════════════════════════════════════╗
║  ProofLine test database is not reachable.                           ║
║                                                                      ║
║  Start the database container and re-run the tests:                  ║
║    docker compose up -d db                                           ║
║                                                                      ║
║  If the container is running but the port differs, set:              ║
║    $env:TEST_DATABASE_URL = "postgresql+psycopg://..."               ║
╚══════════════════════════════════════════════════════════════════════╝
"""


@pytest.fixture(scope="session")
def db_url() -> str:
    """Return the database URL for the test session."""
    url = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_DB_URL)
    os.environ["TEST_DATABASE_URL"] = url
    return url


@pytest.fixture(scope="session")
def db_engine(db_url: str):
    """Session-scoped SQLAlchemy engine.

    Supports sqlite:// URLs for local no-Docker testing, or connects to PostgreSQL
    (failing fast if PG is unreachable).
    """
    from sqlalchemy import create_engine, event
    from sqlalchemy import text as sa_text
    from sqlalchemy.exc import OperationalError

    if db_url.startswith("sqlite"):
        engine = create_engine(db_url, connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record):
            from datetime import datetime, timezone
            dbapi_connection.create_function(
                "now", 0, lambda: datetime.now(timezone.utc).isoformat()
            )
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        yield engine
        engine.dispose()
        return

    # Short TCP connect timeout so the error fires quickly instead of waiting
    # for the OS-level TCP timeout (~2 minutes).
    _url = db_url
    if "connect_timeout" not in _url:
        sep = "&" if "?" in _url else "?"
        _url = f"{_url}{sep}connect_timeout=5"

    engine = create_engine(_url, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            conn.execute(sa_text("SELECT 1"))
    except (OperationalError, Exception) as exc:
        pytest.fail(
            f"{_UNREACHABLE_MSG}\n"
            f"Original error: {exc}"
        )

    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def alembic_cfg(db_url: str):
    """Return an Alembic Config object pointed at this project's alembic.ini."""
    from alembic.config import Config

    # alembic.ini lives at backend/ (two directories above tests/).
    ini_path = pathlib.Path(__file__).parent.parent / "alembic.ini"
    cfg = Config(str(ini_path))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


@pytest.fixture(scope="session")
def migrated_db(db_engine, alembic_cfg):
    """Apply `alembic upgrade head` once for PG, or create_all for SQLite."""
    if db_engine.dialect.name == "sqlite":
        import app.models  # noqa: F401
        from app.models._base import Base

        Base.metadata.drop_all(bind=db_engine)
        Base.metadata.create_all(bind=db_engine)
        yield db_engine
        Base.metadata.drop_all(bind=db_engine)
        return

    from alembic import command

    # Always start from a clean state (handles leftover state from a crashed run)
    command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "head")
    yield db_engine
    command.downgrade(alembic_cfg, "base")


@pytest.fixture
def db_conn(migrated_db):
    """Per-test database connection with automatic SAVEPOINT rollback.

    Wraps each test inside a SAVEPOINT so:
    - Constraint violations abort only the inner savepoint, not the outer txn.
    - Each test always sees a clean state (rollback on exit).
    - Tests are fully isolated from each other.
    """
    with migrated_db.connect() as conn:
        # Outer transaction
        outer = conn.begin()
        # Savepoint so that failed constraint checks can be caught without
        # killing the whole connection.
        conn.execute(__import__("sqlalchemy").text("SAVEPOINT test_sp"))
        yield conn
        # Always roll back to the savepoint, then the outer transaction.
        try:
            conn.execute(__import__("sqlalchemy").text("ROLLBACK TO SAVEPOINT test_sp"))
        except Exception:
            pass
        outer.rollback()
