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


def test_delete_habit_archives_instead_of_removing(client):
    created = client.post("/habits", json={"title": "Read"}).json()

    response = client.delete(f"/habits/{created['id']}")
    assert response.status_code == 204

    response = client.get(f"/habits/{created['id']}")
    assert response.status_code == 200
    assert response.json()["is_archived"] is True


def test_delete_habit_not_found(client):
    response = client.delete("/habits/999")
    assert response.status_code == 404


def test_archived_habits_hidden_from_default_list(client):
    kept = client.post("/habits", json={"title": "Kept"}).json()
    archived = client.post("/habits", json={"title": "Archived"}).json()
    client.delete(f"/habits/{archived['id']}")

    response = client.get("/habits")
    titles = [h["title"] for h in response.json()]
    assert titles == ["Kept"]

    response = client.get("/habits", params={"include_archived": True})
    titles = [h["title"] for h in response.json()]
    assert set(titles) == {"Kept", "Archived"}


def test_restore_archived_habit(client):
    created = client.post("/habits", json={"title": "Read"}).json()
    client.delete(f"/habits/{created['id']}")

    response = client.put(f"/habits/{created['id']}", json={"is_archived": False})
    assert response.status_code == 200
    assert response.json()["is_archived"] is False

    titles = [h["title"] for h in client.get("/habits").json()]
    assert titles == ["Read"]


def test_archived_habit_logs_and_stats_still_accessible(client):
    created = client.post("/habits", json={"title": "Read"}).json()
    client.post(f"/habits/{created['id']}/logs", json={"completed_on": "2026-01-01"})
    client.delete(f"/habits/{created['id']}")

    logs_response = client.get(f"/habits/{created['id']}/logs")
    assert logs_response.status_code == 200
    assert len(logs_response.json()) == 1

    stats_response = client.get(f"/habits/{created['id']}/stats")
    assert stats_response.status_code == 200
    assert stats_response.json()["total_completions"] == 1


def test_permanent_delete_requires_archiving_first(client):
    habit = client.post("/habits", json={"title": "Read"}).json()

    response = client.delete(f"/habits/{habit['id']}/permanent")
    assert response.status_code == 400

    # habit should still exist
    assert client.get(f"/habits/{habit['id']}").status_code == 200


def test_permanent_delete_removes_habit_and_logs(client):
    habit = client.post("/habits", json={"title": "Read"}).json()
    client.post(f"/habits/{habit['id']}/logs", json={"completed_on": "2026-01-01"})
    client.delete(f"/habits/{habit['id']}")  # archive first

    response = client.delete(f"/habits/{habit['id']}/permanent")
    assert response.status_code == 204

    assert client.get(f"/habits/{habit['id']}").status_code == 404
    assert client.get("/habits", params={"include_archived": True}).json() == []


def test_permanent_delete_not_found(client):
    response = client.delete("/habits/999/permanent")
    assert response.status_code == 404


def test_restore_via_put_then_permanent_delete_still_requires_rearchive(client):
    habit = client.post("/habits", json={"title": "Read"}).json()
    client.delete(f"/habits/{habit['id']}")  # archive
    client.put(f"/habits/{habit['id']}", json={"is_archived": False})  # restore

    response = client.delete(f"/habits/{habit['id']}/permanent")
    assert response.status_code == 400


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


def test_create_habit_with_tracking_unit(client):
    response = client.post("/habits", json={"title": "Su iç", "tracking_unit": "litre"})
    assert response.status_code == 201
    assert response.json()["tracking_unit"] == "litre"


def test_create_habit_without_tracking_unit_defaults_to_none(client):
    response = client.post("/habits", json={"title": "Read"})
    assert response.status_code == 201
    assert response.json()["tracking_unit"] is None


def test_create_habit_log_with_amount(client):
    habit = client.post("/habits", json={"title": "Su iç", "tracking_unit": "litre"}).json()

    response = client.post(f"/habits/{habit['id']}/logs", json={"amount": 0.5})
    assert response.status_code == 201
    assert response.json()["amount"] == 0.5


def test_create_habit_log_without_amount_defaults_to_none(client):
    habit = client.post("/habits", json={"title": "Read"}).json()

    response = client.post(f"/habits/{habit['id']}/logs", json={})
    assert response.status_code == 201
    assert response.json()["amount"] is None


def test_habit_stats_total_amount_for_tracked_habit(client):
    habit = client.post("/habits", json={"title": "Su iç", "tracking_unit": "litre"}).json()
    client.post(f"/habits/{habit['id']}/logs", json={"completed_on": "2026-01-01", "amount": 0.5})
    client.post(f"/habits/{habit['id']}/logs", json={"completed_on": "2026-01-02", "amount": 1.5})

    response = client.get(f"/habits/{habit['id']}/stats")
    assert response.status_code == 200
    assert response.json()["total_amount"] == 2.0


def test_habit_stats_total_amount_none_for_untracked_habit(client):
    habit = client.post("/habits", json={"title": "Read"}).json()
    client.post(f"/habits/{habit['id']}/logs", json={"completed_on": "2026-01-01"})

    response = client.get(f"/habits/{habit['id']}/stats")
    assert response.status_code == 200
    assert response.json()["total_amount"] is None


def test_update_habit_tracking_unit(client):
    habit = client.post("/habits", json={"title": "Read"}).json()

    response = client.put(f"/habits/{habit['id']}", json={"tracking_unit": "sayfa"})
    assert response.status_code == 200
    assert response.json()["tracking_unit"] == "sayfa"


def test_create_habit_with_category(client):
    response = client.post("/habits", json={"title": "Su iç", "category": "Sağlık"})
    assert response.status_code == 201
    assert response.json()["category"] == "Sağlık"


def test_create_habit_without_category_defaults_to_none(client):
    response = client.post("/habits", json={"title": "Read"})
    assert response.status_code == 201
    assert response.json()["category"] is None


def test_update_habit_category(client):
    habit = client.post("/habits", json={"title": "Read"}).json()

    response = client.put(f"/habits/{habit['id']}", json={"category": "Öğrenme & Gelişim"})
    assert response.status_code == 200
    assert response.json()["category"] == "Öğrenme & Gelişim"


def test_list_habits_filter_by_category(client):
    client.post("/habits", json={"title": "Su iç", "category": "Sağlık"})
    client.post("/habits", json={"title": "Kitap oku", "category": "Öğrenme & Gelişim"})

    response = client.get("/habits", params={"category": "Sağlık"})
    assert response.status_code == 200
    titles = [h["title"] for h in response.json()]
    assert titles == ["Su iç"]


def test_create_habit_log_with_note(client):
    habit = client.post("/habits", json={"title": "Araç bakımı", "tracking_unit": "km"}).json()

    response = client.post(
        f"/habits/{habit['id']}/logs",
        json={"amount": 15230, "note": "Yağ değişimi yapıldı"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["amount"] == 15230
    assert body["note"] == "Yağ değişimi yapıldı"


def test_create_habit_log_without_note_defaults_to_none(client):
    habit = client.post("/habits", json={"title": "Read"}).json()

    response = client.post(f"/habits/{habit['id']}/logs", json={})
    assert response.status_code == 201
    assert response.json()["note"] is None


def test_create_habit_log_rejects_negative_amount(client):
    habit = client.post("/habits", json={"title": "Kitap oku", "tracking_unit": "sayfa"}).json()

    response = client.post(f"/habits/{habit['id']}/logs", json={"amount": -14})
    assert response.status_code == 422


def test_create_habit_log_allows_zero_amount(client):
    habit = client.post("/habits", json={"title": "Kitap oku", "tracking_unit": "sayfa"}).json()

    response = client.post(f"/habits/{habit['id']}/logs", json={"amount": 0})
    assert response.status_code == 201
    assert response.json()["amount"] == 0
