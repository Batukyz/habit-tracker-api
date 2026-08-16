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


def test_get_habit_streak(client):
    habit = client.post("/habits", json={"title": "Read"}).json()
    client.post(f"/habits/{habit['id']}/logs", json={"completed_on": "2026-01-01"})
    client.post(f"/habits/{habit['id']}/logs", json={"completed_on": "2026-01-02"})
    client.post(f"/habits/{habit['id']}/logs", json={"completed_on": "2026-01-03"})

    response = client.get(f"/habits/{habit['id']}/streak")
    assert response.status_code == 200
    assert response.json() == {"habit_id": habit["id"], "current_streak": 3}


def test_get_habit_streak_no_logs(client):
    habit = client.post("/habits", json={"title": "Read"}).json()

    response = client.get(f"/habits/{habit['id']}/streak")
    assert response.status_code == 200
    assert response.json() == {"habit_id": habit["id"], "current_streak": 0}


def test_get_habit_streak_not_found(client):
    response = client.get("/habits/999/streak")
    assert response.status_code == 404


def test_get_habit_stats(client):
    habit = client.post("/habits", json={"title": "Read"}).json()
    client.post(f"/habits/{habit['id']}/logs", json={"completed_on": "2026-08-01"})
    client.post(f"/habits/{habit['id']}/logs", json={"completed_on": "2026-08-02"})
    client.post(f"/habits/{habit['id']}/logs", json={"completed_on": "2026-08-10"})

    response = client.get(f"/habits/{habit['id']}/stats")
    assert response.status_code == 200
    body = response.json()
    assert body["habit_id"] == habit["id"]
    assert body["total_completions"] == 3
    assert body["current_streak"] == 1
    assert body["longest_streak"] == 2


def test_get_habit_stats_not_found(client):
    response = client.get("/habits/999/stats")
    assert response.status_code == 404


def test_list_habits_filter_by_frequency(client):
    client.post("/habits", json={"title": "Read", "frequency": "daily"})
    client.post("/habits", json={"title": "Gym", "frequency": "weekly"})

    response = client.get("/habits", params={"frequency": "weekly"})
    assert response.status_code == 200
    titles = [h["title"] for h in response.json()]
    assert titles == ["Gym"]


def test_list_habits_filter_by_is_completed(client):
    client.post("/habits", json={"title": "Read", "is_completed": False})
    client.post("/habits", json={"title": "Gym", "is_completed": True})

    response = client.get("/habits", params={"is_completed": True})
    assert response.status_code == 200
    titles = [h["title"] for h in response.json()]
    assert titles == ["Gym"]


def test_list_habits_search(client):
    client.post("/habits", json={"title": "Read a book"})
    client.post("/habits", json={"title": "Gym"})

    response = client.get("/habits", params={"search": "book"})
    assert response.status_code == 200
    titles = [h["title"] for h in response.json()]
    assert titles == ["Read a book"]


def test_list_habits_pagination(client):
    for i in range(5):
        client.post("/habits", json={"title": f"Habit {i}"})

    response = client.get("/habits", params={"skip": 2, "limit": 2})
    assert response.status_code == 200
    titles = [h["title"] for h in response.json()]
    assert titles == ["Habit 2", "Habit 3"]
