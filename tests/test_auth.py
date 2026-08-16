def test_register(anon_client):
    response = anon_client.post(
        "/auth/register", json={"email": "new@example.com", "password": "testpassword123"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new@example.com"
    assert "id" in body
    assert "password" not in body


def test_register_duplicate_email(anon_client):
    anon_client.post(
        "/auth/register", json={"email": "dup@example.com", "password": "testpassword123"}
    )
    response = anon_client.post(
        "/auth/register", json={"email": "dup@example.com", "password": "anotherpassword"}
    )
    assert response.status_code == 400


def test_login(anon_client):
    anon_client.post(
        "/auth/register", json={"email": "login@example.com", "password": "testpassword123"}
    )
    response = anon_client.post(
        "/auth/login", data={"username": "login@example.com", "password": "testpassword123"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_wrong_password(anon_client):
    anon_client.post(
        "/auth/register", json={"email": "wrongpw@example.com", "password": "testpassword123"}
    )
    response = anon_client.post(
        "/auth/login", data={"username": "wrongpw@example.com", "password": "nope"}
    )
    assert response.status_code == 401


def test_login_unknown_user(anon_client):
    response = anon_client.post(
        "/auth/login", data={"username": "ghost@example.com", "password": "whatever123"}
    )
    assert response.status_code == 401


def test_habits_require_auth(anon_client):
    response = anon_client.get("/habits")
    assert response.status_code == 401


def test_users_only_see_their_own_habits(make_authed_client):
    alice = make_authed_client(email="alice@example.com")
    bob = make_authed_client(email="bob@example.com")

    alice_habit = alice.post("/habits", json={"title": "Alice'in habiti"}).json()
    bob.post("/habits", json={"title": "Bob'un habiti"})

    alice_habits = alice.get("/habits").json()
    bob_habits = bob.get("/habits").json()

    assert [h["title"] for h in alice_habits] == ["Alice'in habiti"]
    assert [h["title"] for h in bob_habits] == ["Bob'un habiti"]

    response = bob.get(f"/habits/{alice_habit['id']}")
    assert response.status_code == 404


def test_read_me(client):
    response = client.get("/me")
    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"


def test_read_me_requires_auth(anon_client):
    response = anon_client.get("/me")
    assert response.status_code == 401


def test_update_me_email(client):
    response = client.put("/me", json={"email": "updated@example.com"})
    assert response.status_code == 200
    assert response.json()["email"] == "updated@example.com"


def test_update_me_password_allows_relogin(anon_client, client):
    client.put("/me", json={"password": "newpassword123"})

    old_login = anon_client.post(
        "/auth/login", data={"username": "user@example.com", "password": "testpassword123"}
    )
    assert old_login.status_code == 401

    new_login = anon_client.post(
        "/auth/login", data={"username": "user@example.com", "password": "newpassword123"}
    )
    assert new_login.status_code == 200


def test_update_me_duplicate_email(make_authed_client):
    alice = make_authed_client(email="alice2@example.com")
    make_authed_client(email="bob2@example.com")

    response = alice.put("/me", json={"email": "bob2@example.com"})
    assert response.status_code == 400
