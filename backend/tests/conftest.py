"""
Shared pytest fixtures for the innovo_backend test suite.

IMPORTANT: JWT_SECRET_KEY must be set before any innovo_backend import.
This module is loaded by pytest before all test files, ensuring the env var
is present when jwt_utils.py executes its module-level validation.
"""
import os

# Must come before ANY innovo_backend import
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-testing-purposes-only")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-not-real")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("POSTHOG_API_KEY", "")

# SQLite (used in tests) does not understand PostgreSQL-specific column types.
# Patch JSONB → JSON before any innovo_backend module imports so that
# SQLAlchemy renders a SQLite-compatible column type when create_all() runs.
import sqlalchemy.dialects.postgresql as _pg_dialect  # noqa: E402
from sqlalchemy import JSON as _JSON_TYPE  # noqa: E402
_pg_dialect.JSONB = _JSON_TYPE  # type: ignore[assignment]

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from innovo_backend.shared.database import Base, get_db
from innovo_backend.main import app

_TEST_DB_URL = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def test_engine():
    """Session-scoped engine backed by an in-memory SQLite database."""
    engine = create_engine(
        _TEST_DB_URL,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db(test_engine):
    """
    Function-scoped database session with transactional rollback isolation.

    Each test gets a clean slate: all writes are rolled back after the test
    without touching any other test's data.
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=connection)
    session = SessionLocal()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db):
    """
    Function-scoped TestClient that overrides the DB dependency to use the
    transactional test session.
    """
    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------

TEST_USER_EMAIL = "testuser@innovo-consulting.de"
TEST_USER_PASSWORD = "securepass123"


@pytest.fixture()
def registered_user(client):
    """Register a test user and return its email."""
    resp = client.post(
        "/auth/register",
        json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD},
    )
    assert resp.status_code in (201, 409), resp.text  # 409 if already exists in session
    return TEST_USER_EMAIL


@pytest.fixture()
def auth_headers(client, registered_user):
    """Login the test user and return bearer auth headers."""
    resp = client.post(
        "/auth/login",
        json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
