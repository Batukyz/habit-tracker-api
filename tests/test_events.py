def test_create_event(client):
    response = client.post("/events", json={"title": "Toplantı", "event_date": "2026-08-24"})
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Toplantı"
    assert body["event_date"] == "2026-08-24"
    assert body["is_done"] is False


def test_create_event_requires_auth(anon_client):
    response = anon_client.post("/events", json={"title": "Toplantı", "event_date": "2026-08-24"})
    assert response.status_code == 401


def test_list_events_sorted_by_date(client):
    client.post("/events", json={"title": "Sonra", "event_date": "2026-09-01"})
    client.post("/events", json={"title": "Önce", "event_date": "2026-08-20"})

    response = client.get("/events")
    assert response.status_code == 200
    titles = [e["title"] for e in response.json()]
    assert titles == ["Önce", "Sonra"]


def test_list_events_filter_by_date_range(client):
    client.post("/events", json={"title": "Ağustos", "event_date": "2026-08-24"})
    client.post("/events", json={"title": "Eylül", "event_date": "2026-09-05"})

    response = client.get("/events", params={"date_from": "2026-09-01", "date_to": "2026-09-30"})
    assert response.status_code == 200
    titles = [e["title"] for e in response.json()]
    assert titles == ["Eylül"]


def test_list_events_filter_by_is_done(client):
    e1 = client.post("/events", json={"title": "Yapıldı", "event_date": "2026-08-01"}).json()
    client.post("/events", json={"title": "Yapılmadı", "event_date": "2026-08-02"})
    client.put(f"/events/{e1['id']}", json={"is_done": True})

    response = client.get("/events", params={"is_done": True})
    assert response.status_code == 200
    titles = [e["title"] for e in response.json()]
    assert titles == ["Yapıldı"]


def test_update_event_mark_done(client):
    event = client.post("/events", json={"title": "Toplantı", "event_date": "2026-08-24"}).json()

    response = client.put(f"/events/{event['id']}", json={"is_done": True})
    assert response.status_code == 200
    assert response.json()["is_done"] is True


def test_update_event_not_found(client):
    response = client.put("/events/999", json={"is_done": True})
    assert response.status_code == 404


def test_delete_event(client):
    event = client.post("/events", json={"title": "Toplantı", "event_date": "2026-08-24"}).json()

    response = client.delete(f"/events/{event['id']}")
    assert response.status_code == 204

    response = client.get("/events")
    assert response.json() == []


def test_delete_event_not_found(client):
    response = client.delete("/events/999")
    assert response.status_code == 404


def test_events_are_scoped_to_owner(make_authed_client):
    alice = make_authed_client(email="alice_ev@example.com")
    bob = make_authed_client(email="bob_ev@example.com")

    alice_event = alice.post("/events", json={"title": "Alice", "event_date": "2026-08-24"}).json()
    bob.post("/events", json={"title": "Bob", "event_date": "2026-08-25"})

    assert [e["title"] for e in alice.get("/events").json()] == ["Alice"]
    assert [e["title"] for e in bob.get("/events").json()] == ["Bob"]
    assert bob.get(f"/events/{alice_event['id']}").status_code == 404
    assert bob.put(f"/events/{alice_event['id']}", json={"is_done": True}).status_code == 404
    assert bob.delete(f"/events/{alice_event['id']}").status_code == 404
