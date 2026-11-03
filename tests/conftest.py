"""
Shared pytest fixtures for the E190 prototyping assistant backend tests.

All tests run against a real PostgreSQL instance. The DATABASE_URL must be set
to a dedicated test database before running pytest, e.g.:

    DATABASE_URL=postgresql+psycopg://postgres@localhost:5432/prototyping_assistant_test \
        /Users/nathannoronha/E190BO-FINAL-PROJECT/.venv/bin/pytest -v
"""
import os

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel

import app.models  # noqa: F401 — registers all table metadata
from app.database import get_engine, get_session, reset_engine
from app.main import app

TEST_DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres@localhost:5432/prototyping_assistant_test",
)


@pytest.fixture(scope="session", autouse=True)
def set_test_database_url():
    """Ensure DATABASE_URL points at the test database for the entire session."""
    os.environ["DATABASE_URL"] = TEST_DB_URL
    yield
    # Leave the env var set; teardown handled per-test via reset_engine


@pytest.fixture(autouse=True)
def clean_tables():
    """
    Truncate all application tables before each test so tests are fully isolated.
    Does NOT drop the database or other unrelated tables.
    """
    # Ensure the engine is fresh and tables exist
    reset_engine()
    engine = get_engine()
    SQLModel.metadata.create_all(engine)

    yield

    # Truncate in reverse dependency order to avoid FK violations
    with engine.connect() as conn:
        conn.execute(
            __import__("sqlalchemy").text(
                "TRUNCATE TABLE project_bom_items, project_steps, inventory_items, "
                "projects, users RESTART IDENTITY CASCADE"
            )
        )
        conn.commit()
    reset_engine()


@pytest.fixture
def session():
    """Yield a fresh SQLModel session for direct DB manipulation in tests."""
    engine = get_engine()
    with Session(engine) as s:
        yield s


@pytest.fixture
def client():
    """Yield a FastAPI TestClient backed by the test Postgres database."""
    # Override the get_session dependency so the app uses the test DB
    def override_get_session():
        engine = get_engine()
        with Session(engine) as s:
            try:
                yield s
            except Exception:
                s.rollback()
                raise

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
