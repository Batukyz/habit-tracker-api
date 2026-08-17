from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from tests.conftest import override_get_db


def test_unhandled_exception_returns_generic_500(client):
    def broken_get_db():
        raise RuntimeError("boom")
        yield  # pragma: no cover - unreachable, keeps this a generator

    app.dependency_overrides[get_db] = broken_get_db
    try:
        raw_client = TestClient(app, raise_server_exceptions=False)
        raw_client.headers.update(client.headers)
        response = raw_client.get("/habits")
        assert response.status_code == 500
        assert response.json() == {"detail": "Internal server error"}
    finally:
        app.dependency_overrides[get_db] = override_get_db
