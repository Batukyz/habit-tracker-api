import app.main as main_module


def _capture_reset_email(monkeypatch):
    captured = {}

    def fake_send_password_reset_email(to, token):
        captured["to"] = to
        captured["token"] = token

    monkeypatch.setattr(main_module, "send_password_reset_email", fake_send_password_reset_email)
    return captured


def test_forgot_password_existing_user(anon_client, monkeypatch):
    captured = _capture_reset_email(monkeypatch)
    anon_client.post(
        "/auth/register", json={"email": "forgot@example.com", "password": "testpassword123"}
    )

    response = anon_client.post("/auth/forgot-password", json={"email": "forgot@example.com"})
    assert response.status_code == 202
    assert captured["to"] == "forgot@example.com"
    assert captured["token"]


def test_forgot_password_unknown_user_returns_same_response(anon_client, monkeypatch):
    captured = _capture_reset_email(monkeypatch)

    response = anon_client.post("/auth/forgot-password", json={"email": "ghost@example.com"})
    assert response.status_code == 202
    assert "token" not in captured


def test_reset_password_changes_password(anon_client, monkeypatch):
    captured = _capture_reset_email(monkeypatch)
    anon_client.post(
        "/auth/register", json={"email": "reset@example.com", "password": "oldpassword123"}
    )
    anon_client.post("/auth/forgot-password", json={"email": "reset@example.com"})

    response = anon_client.post(
        "/auth/reset-password",
        json={"token": captured["token"], "new_password": "newpassword123"},
    )
    assert response.status_code == 204

    old_login = anon_client.post(
        "/auth/login", data={"username": "reset@example.com", "password": "oldpassword123"}
    )
    assert old_login.status_code == 401

    new_login = anon_client.post(
        "/auth/login", data={"username": "reset@example.com", "password": "newpassword123"}
    )
    assert new_login.status_code == 200


def test_reset_password_token_is_single_use(anon_client, monkeypatch):
    captured = _capture_reset_email(monkeypatch)
    anon_client.post(
        "/auth/register", json={"email": "singleuse@example.com", "password": "oldpassword123"}
    )
    anon_client.post("/auth/forgot-password", json={"email": "singleuse@example.com"})

    first = anon_client.post(
        "/auth/reset-password",
        json={"token": captured["token"], "new_password": "newpassword123"},
    )
    assert first.status_code == 204

    reused = anon_client.post(
        "/auth/reset-password",
        json={"token": captured["token"], "new_password": "anotherpassword"},
    )
    assert reused.status_code == 400


def test_reset_password_with_invalid_token(anon_client):
    response = anon_client.post(
        "/auth/reset-password", json={"token": "not-a-real-token", "new_password": "newpassword123"}
    )
    assert response.status_code == 400


def test_reset_password_revokes_existing_refresh_tokens(anon_client, monkeypatch):
    captured = _capture_reset_email(monkeypatch)
    anon_client.post(
        "/auth/register", json={"email": "revoke@example.com", "password": "oldpassword123"}
    )
    login = anon_client.post(
        "/auth/login", data={"username": "revoke@example.com", "password": "oldpassword123"}
    ).json()

    anon_client.post("/auth/forgot-password", json={"email": "revoke@example.com"})
    anon_client.post(
        "/auth/reset-password",
        json={"token": captured["token"], "new_password": "newpassword123"},
    )

    refresh_response = anon_client.post(
        "/auth/refresh", json={"refresh_token": login["refresh_token"]}
    )
    assert refresh_response.status_code == 401
