import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.database import Base, get_db
from app.main import app
from app.rate_limit import limiter

limiter.enabled = False

SQLALCHEMY_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _register_and_login(test_client, email, password="testpassword123"):
    test_client.post("/auth/register", json={"email": email, "password": password})
    response = test_client.post("/auth/login", data={"username": email, "password": password})
    return response.json()["access_token"]


@pytest.fixture
def anon_client():
    """An unauthenticated client, for testing auth flows and access control."""
    return TestClient(app)


@pytest.fixture
def make_authed_client():
    """Factory for a logged-in TestClient with its own dedicated user."""

    def _make(email="user@example.com", password="testpassword123"):
        test_client = TestClient(app)
        token = _register_and_login(test_client, email, password)
        test_client.headers.update({"Authorization": f"Bearer {token}"})
        return test_client

    return _make


@pytest.fixture
def client(make_authed_client):
    """Default authenticated client used by most tests."""
    return make_authed_client()


@pytest.fixture
def make_admin_client(make_authed_client):
    """Factory for a logged-in TestClient whose user has is_admin=True.

    There is no user-facing way to become an admin, so tests promote the user
    directly in the database - the same one-time-DB-manipulation path used
    to grant the first real admin in production.
    """

    def _make(email="admin@example.com", password="testpassword123"):
        test_client = make_authed_client(email=email, password=password)
        db = TestingSessionLocal()
        try:
            user = db.query(models.User).filter(models.User.email == email).first()
            user.is_admin = True
            db.commit()
        finally:
            db.close()
        return test_client

    return _make
