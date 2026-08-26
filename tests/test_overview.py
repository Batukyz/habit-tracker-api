from datetime import date, timedelta

TODAY = date.today().isoformat()
YESTERDAY = (date.today() - timedelta(days=1)).isoformat()
TOMORROW = (date.today() + timedelta(days=1)).isoformat()


def test_overview_requires_auth(anon_client):
    response = anon_client.get("/overview")
    assert response.status_code == 401


def test_overview_empty_state(client):
    response = client.get("/overview")
    assert response.status_code == 200
    assert response.json() == {
        "active_habits": 0,
        "checked_in_today": 0,
        "best_current_streak": 0,
        "events_today_total": 0,
        "events_today_done": 0,
        "overdue_events": 0,
    }


def test_overview_counts_active_habits_and_checkins(client):
    habit1 = client.post("/habits", json={"title": "Read"}).json()
    client.post("/habits", json={"title": "Run"})
    client.post(f"/habits/{habit1['id']}/logs", json={"completed_on": TODAY})

    response = client.get("/overview")
    body = response.json()
    assert body["active_habits"] == 2
    assert body["checked_in_today"] == 1


def test_overview_excludes_archived_habits(client):
    habit = client.post("/habits", json={"title": "Read"}).json()
    client.delete(f"/habits/{habit['id']}")  # archive

    response = client.get("/overview")
    assert response.json()["active_habits"] == 0


def test_overview_best_current_streak(client):
    habit = client.post("/habits", json={"title": "Read"}).json()
    client.post(f"/habits/{habit['id']}/logs", json={"completed_on": YESTERDAY})
    client.post(f"/habits/{habit['id']}/logs", json={"completed_on": TODAY})

    response = client.get("/overview")
    assert response.json()["best_current_streak"] == 2


def test_overview_events_today(client):
    e1 = client.post("/events", json={"title": "A", "event_date": TODAY}).json()
    client.post("/events", json={"title": "B", "event_date": TODAY})
    client.put(f"/events/{e1['id']}", json={"is_done": True})

    response = client.get("/overview")
    body = response.json()
    assert body["events_today_total"] == 2
    assert body["events_today_done"] == 1


def test_overview_overdue_events(client):
    client.post("/events", json={"title": "Geçmiş", "event_date": YESTERDAY})
    done = client.post("/events", json={"title": "Bitmiş geçmiş", "event_date": YESTERDAY}).json()
    client.put(f"/events/{done['id']}", json={"is_done": True})
    client.post("/events", json={"title": "Gelecek", "event_date": TOMORROW})

    response = client.get("/overview")
    assert response.json()["overdue_events"] == 1


def test_overview_scoped_to_owner(make_authed_client):
    alice = make_authed_client(email="alice_ov@example.com")
    bob = make_authed_client(email="bob_ov@example.com")

    alice.post("/habits", json={"title": "Alice habit"})
    bob.post("/habits", json={"title": "Bob habit 1"})
    bob.post("/habits", json={"title": "Bob habit 2"})

    assert alice.get("/overview").json()["active_habits"] == 1
    assert bob.get("/overview").json()["active_habits"] == 2
