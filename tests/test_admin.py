from datetime import date, timedelta

TODAY = date.today().isoformat()
YESTERDAY = (date.today() - timedelta(days=1)).isoformat()


def test_admin_endpoints_require_auth(anon_client):
    assert anon_client.get("/admin/ecosystem/overview").status_code == 401
    assert anon_client.get("/admin/ecosystem/milestones").status_code == 401
    assert anon_client.get("/admin/users").status_code == 401


def test_admin_endpoints_forbidden_for_regular_user(client):
    assert client.get("/admin/ecosystem/overview").status_code == 403
    assert client.get("/admin/ecosystem/milestones").status_code == 403
    assert client.post("/admin/ecosystem/milestones", json={
        "threshold": 5, "stage_key": "x", "name": "X",
    }).status_code == 403
    assert client.get("/admin/users").status_code == 403
    assert client.get("/admin/ecosystem/preview?streak=10").status_code == 403


def test_admin_overview_counts_users_with_active_habits(make_admin_client, make_authed_client):
    admin = make_admin_client()
    other = make_authed_client(email="regular_ov@example.com")
    habit = other.post("/habits", json={"title": "Read"}).json()
    other.post(f"/habits/{habit['id']}/logs", json={"completed_on": TODAY})

    response = admin.get("/admin/ecosystem/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["total_users"] >= 2
    assert body["users_with_active_habits"] >= 1
    assert body["milestone_count"] == 9  # DEFAULT_MILESTONES fallback (no DB seed in test DB)


def test_admin_milestone_crud(make_admin_client):
    admin = make_admin_client()

    created = admin.post("/admin/ecosystem/milestones", json={
        "threshold": 500, "stage_key": "legendary", "name": "Efsanevi", "description": "test",
    })
    assert created.status_code == 201
    milestone_id = created.json()["id"]

    listed = admin.get("/admin/ecosystem/milestones").json()
    assert any(m["id"] == milestone_id for m in listed)

    updated = admin.put(f"/admin/ecosystem/milestones/{milestone_id}", json={"name": "Yeni İsim"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Yeni İsim"

    deleted = admin.delete(f"/admin/ecosystem/milestones/{milestone_id}")
    assert deleted.status_code == 204
    listed_after = admin.get("/admin/ecosystem/milestones").json()
    assert not any(m["id"] == milestone_id for m in listed_after)


def test_admin_milestone_duplicate_threshold_rejected(make_admin_client):
    admin = make_admin_client()
    admin.post("/admin/ecosystem/milestones", json={
        "threshold": 42, "stage_key": "a", "name": "A",
    })
    dup = admin.post("/admin/ecosystem/milestones", json={
        "threshold": 42, "stage_key": "b", "name": "B",
    })
    assert dup.status_code == 409


def test_admin_preview_uses_streak_query_param(make_admin_client):
    admin = make_admin_client()
    response = admin.get("/admin/ecosystem/preview?streak=30")
    assert response.status_code == 200
    body = response.json()
    assert body["best_current_streak"] == 30
    assert body["is_simulated"] is True


def test_admin_list_users_includes_summary(make_admin_client, make_authed_client):
    admin = make_admin_client()
    other = make_authed_client(email="regular_list@example.com")
    habit = other.post("/habits", json={"title": "Read"}).json()
    other.post(f"/habits/{habit['id']}/logs", json={"completed_on": TODAY})

    response = admin.get("/admin/users")
    assert response.status_code == 200
    emails = [u["email"] for u in response.json()]
    assert "regular_list@example.com" in emails
    other_summary = next(u for u in response.json() if u["email"] == "regular_list@example.com")
    assert other_summary["active_habits"] == 1
    assert other_summary["has_override"] is False


def test_admin_set_and_clear_user_override(make_admin_client, make_authed_client):
    admin = make_admin_client()
    other = make_authed_client(email="regular_override@example.com")
    other_id = other.get("/me").json()["id"]

    real_state = other.get("/ecosystem").json()
    assert real_state["is_simulated"] is False
    assert real_state["best_current_streak"] == 0

    set_response = admin.put(f"/admin/users/{other_id}/ecosystem/override", json={"simulated_streak": 100})
    assert set_response.status_code == 200
    assert set_response.json()["is_simulated"] is True
    assert set_response.json()["best_current_streak"] == 100
    assert set_response.json()["stage_key"] == "mature"

    as_seen_by_owner = other.get("/ecosystem").json()
    assert as_seen_by_owner["is_simulated"] is True
    assert as_seen_by_owner["best_current_streak"] == 100

    cleared = admin.delete(f"/admin/users/{other_id}/ecosystem/override")
    assert cleared.status_code == 200
    assert cleared.json()["is_simulated"] is False
    assert cleared.json()["best_current_streak"] == 0

    after_clear = other.get("/ecosystem").json()
    assert after_clear["is_simulated"] is False
    assert after_clear["best_current_streak"] == 0


def test_admin_override_requires_existing_user(make_admin_client):
    admin = make_admin_client()
    response = admin.put("/admin/users/999999/ecosystem/override", json={"simulated_streak": 10})
    assert response.status_code == 404


def test_admin_regular_user_cannot_override_others(client, make_authed_client):
    victim = make_authed_client(email="victim@example.com")
    victim_id = victim.get("/me").json()["id"]
    response = client.put(f"/admin/users/{victim_id}/ecosystem/override", json={"simulated_streak": 10})
    assert response.status_code == 403
