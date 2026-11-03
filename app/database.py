import os
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, SQLModel, create_engine

load_dotenv()

_engine = None


def normalize_database_url(raw_url: str) -> str:
    """Normalize a database URL to use the postgresql+psycopg:// driver scheme.

    Raises ValueError if raw_url is empty or None.
    Converts:
      - postgres://...         -> postgresql+psycopg://...
      - postgresql://...       -> postgresql+psycopg://...
      - postgresql+psycopg://  -> unchanged
      - sqlite://...           -> unchanged
    """
    if not raw_url:
        raise ValueError("DATABASE_URL must not be empty")

    if raw_url.startswith("postgres://"):
        return "postgresql+psycopg://" + raw_url[len("postgres://"):]

    if raw_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + raw_url[len("postgresql://"):]

    # Already has a driver (e.g. postgresql+psycopg://) or is sqlite://
    return raw_url


def get_engine():
    """Return the singleton SQLAlchemy engine, creating it if needed."""
    global _engine
    if _engine is None:
        raw_url = os.getenv("DATABASE_URL")
        if not raw_url:
            raise RuntimeError(
                "DATABASE_URL environment variable is not set. "
                "Set it before calling get_engine()."
            )
        url = normalize_database_url(raw_url)

        # pool_pre_ping keeps Postgres connections healthy after restarts.
        # SQLite does not support pool_pre_ping, so omit it for sqlite:// URLs.
        if url.startswith("sqlite"):
            _engine = create_engine(url)
        else:
            _engine = create_engine(url, pool_pre_ping=True)

    return _engine


def reset_engine():
    """Dispose and clear the singleton engine (used in tests to simulate a container restart)."""
    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None


def init_db():
    """Create all tables defined in SQLModel.metadata."""
    # Import models so their table definitions are registered on SQLModel.metadata
    import app.models  # noqa: F401

    SQLModel.metadata.create_all(get_engine())


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session with automatic rollback on error."""
    session = Session(get_engine())
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
