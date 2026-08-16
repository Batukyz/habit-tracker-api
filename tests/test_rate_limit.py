import pytest

from app.rate_limit import limiter


@pytest.fixture
def enabled_limiter():
    limiter.enabled = True
    limiter.reset()
    yield
    limiter.enabled = False


def test_login_is_rate_limited(anon_client, enabled_limiter):
    anon_client.post(
        "/auth/register", json={"email": "ratelimit@example.com", "password": "testpassword123"}
    )

    responses = [
        anon_client.post(
            "/auth/login", data={"username": "ratelimit@example.com", "password": "wrong"}
        )
        for _ in range(10)
    ]

    assert any(r.status_code == 429 for r in responses)
    assert all(r.status_code in (401, 429) for r in responses)


def test_register_is_rate_limited(anon_client, enabled_limiter):
    responses = [
        anon_client.post(
            "/auth/register", json={"email": f"spam{i}@example.com", "password": "testpassword123"}
        )
        for i in range(10)
    ]

    assert any(r.status_code == 429 for r in responses)
