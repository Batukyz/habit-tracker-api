def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_habit(client):
    response = client.post("/habits", json={"title": "Read"})
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Read"
    assert body["frequency"] == "daily"
    assert body["is_completed"] is False
    assert "id" in body


def test_list_habits(client):
    client.post("/habits", json={"title": "Read"})
    client.post("/habits", json={"title": "Exercise"})

    response = client.get("/habits")
    assert response.status_code == 200
    titles = [habit["title"] for habit in response.json()]
    assert titles == ["Read", "Exercise"]


def test_get_habit(client):
    created = client.post("/habits", json={"title": "Read"}).json()

    response = client.get(f"/habits/{created['id']}")
    assert response.status_code == 200
    assert response.json()["title"] == "Read"


def test_get_habit_not_found(client):
    response = client.get("/habits/999")
    assert response.status_code == 404


def test_update_habit(client):
    created = client.post("/habits", json={"title": "Read"}).json()

    response = client.put(f"/habits/{created['id']}", json={"is_completed": True})
    assert response.status_code == 200
    body = response.json()
    assert body["is_completed"] is True
    assert body["title"] == "Read"


def test_update_habit_not_found(client):
    response = client.put("/habits/999", json={"is_completed": True})
    assert response.status_code == 404


def test_delete_habit(client):
    created = client.post("/habits", json={"title": "Read"}).json()

    response = client.delete(f"/habits/{created['id']}")
    assert response.status_code == 204

    response = client.get(f"/habits/{created['id']}")
    assert response.status_code == 404


def test_delete_habit_not_found(client):
    response = client.delete("/habits/999")
    assert response.status_code == 404
