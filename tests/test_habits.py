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


def test_create_habit_log(client):
    habit = client.post("/habits", json={"title": "Read"}).json()

    response = client.post(f"/habits/{habit['id']}/logs", json={})
    assert response.status_code == 201
    body = response.json()
    assert body["habit_id"] == habit["id"]
    assert "completed_on" in body


def test_create_habit_log_with_date(client):
    habit = client.post("/habits", json={"title": "Read"}).json()

    response = client.post(f"/habits/{habit['id']}/logs", json={"completed_on": "2026-01-01"})
    assert response.status_code == 201
    assert response.json()["completed_on"] == "2026-01-01"


def test_create_habit_log_not_found(client):
    response = client.post("/habits/999/logs", json={})
    assert response.status_code == 404


def test_list_habit_logs(client):
    habit = client.post("/habits", json={"title": "Read"}).json()
    client.post(f"/habits/{habit['id']}/logs", json={"completed_on": "2026-01-01"})
    client.post(f"/habits/{habit['id']}/logs", json={"completed_on": "2026-01-02"})

    response = client.get(f"/habits/{habit['id']}/logs")
    assert response.status_code == 200
    dates = [log["completed_on"] for log in response.json()]
    assert dates == ["2026-01-01", "2026-01-02"]


def test_list_habit_logs_not_found(client):
    response = client.get("/habits/999/logs")
    assert response.status_code == 404


def test_delete_habit_log(client):
    habit = client.post("/habits", json={"title": "Read"}).json()
    log = client.post(f"/habits/{habit['id']}/logs", json={}).json()

    response = client.delete(f"/habits/{habit['id']}/logs/{log['id']}")
    assert response.status_code == 204

    response = client.get(f"/habits/{habit['id']}/logs")
    assert response.json() == []


def test_delete_habit_log_habit_not_found(client):
    response = client.delete("/habits/999/logs/1")
    assert response.status_code == 404


def test_delete_habit_log_log_not_found(client):
    habit = client.post("/habits", json={"title": "Read"}).json()

    response = client.delete(f"/habits/{habit['id']}/logs/999")
    assert response.status_code == 404
