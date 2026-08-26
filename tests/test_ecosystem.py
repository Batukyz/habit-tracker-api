from datetime import date, timedelta

import pytest

from app.ecosystem import (
    DEFAULT_MILESTONES,
    EcosystemInput,
    Milestone,
    compute_ecosystem_state,
)

TODAY = date.today().isoformat()
YESTERDAY = (date.today() - timedelta(days=1)).isoformat()


def _inputs(**overrides):
    base = dict(
        total_habits=0,
        total_logs=0,
        best_current_streak=0,
        best_longest_streak=0,
        avg_completion_rate=0.0,
    )
    base.update(overrides)
    return EcosystemInput(**base)


def test_compute_ecosystem_state_requires_milestones():
    with pytest.raises(ValueError):
        compute_ecosystem_state(_inputs(), [])


def test_compute_ecosystem_state_starts_at_first_stage():
    state = compute_ecosystem_state(_inputs(best_current_streak=0), DEFAULT_MILESTONES)
    assert state.stage_key == "empty"
    assert state.growth_level == 0
    assert state.next_milestone.stage_key == "seed"


def test_compute_ecosystem_state_picks_highest_reached_stage():
    state = compute_ecosystem_state(_inputs(best_current_streak=7), DEFAULT_MILESTONES)
    assert state.stage_key == "young_plant"
    assert state.next_milestone.stage_key == "growing"


def test_compute_ecosystem_state_exact_threshold_match():
    state = compute_ecosystem_state(_inputs(best_current_streak=30), DEFAULT_MILESTONES)
    assert state.stage_key == "garden"


def test_compute_ecosystem_state_final_stage_has_no_next_milestone():
    state = compute_ecosystem_state(_inputs(best_current_streak=365), DEFAULT_MILESTONES)
    assert state.stage_key == "ancient"
    assert state.next_milestone is None
    assert state.progress_to_next == 100.0


def test_compute_ecosystem_state_beyond_final_stage_stays_capped():
    state = compute_ecosystem_state(_inputs(best_current_streak=9999), DEFAULT_MILESTONES)
    assert state.stage_key == "ancient"
    assert state.progress_to_next == 100.0


def test_compute_ecosystem_state_progress_to_next_midpoint():
    milestones = [Milestone(0, "empty", "Empty"), Milestone(10, "seed", "Seed")]
    state = compute_ecosystem_state(_inputs(best_current_streak=5), milestones)
    assert state.progress_to_next == 50.0


def test_compute_ecosystem_state_is_deterministic():
    first = compute_ecosystem_state(_inputs(best_current_streak=14, total_habits=3), DEFAULT_MILESTONES)
    second = compute_ecosystem_state(_inputs(best_current_streak=14, total_habits=3), DEFAULT_MILESTONES)
    assert first == second


# --- endpoint tests ---


def test_ecosystem_requires_auth(anon_client):
    response = anon_client.get("/ecosystem")
    assert response.status_code == 401


def test_ecosystem_empty_state(client):
    response = client.get("/ecosystem")
    assert response.status_code == 200
    body = response.json()
    assert body["stage_key"] == "empty"
    assert body["growth_level"] == 0
    assert body["total_habits"] == 0
    assert body["best_current_streak"] == 0
    assert body["next_milestone"]["stage_key"] == "seed"


def test_ecosystem_reflects_best_current_streak(client):
    habit = client.post("/habits", json={"title": "Read"}).json()
    client.post(f"/habits/{habit['id']}/logs", json={"completed_on": YESTERDAY})
    client.post(f"/habits/{habit['id']}/logs", json={"completed_on": TODAY})

    response = client.get("/ecosystem")
    body = response.json()
    assert body["best_current_streak"] == 2
    assert body["stage_key"] == "seed"


def test_ecosystem_excludes_archived_habits(client):
    habit = client.post("/habits", json={"title": "Read"}).json()
    client.post(f"/habits/{habit['id']}/logs", json={"completed_on": TODAY})
    client.delete(f"/habits/{habit['id']}")  # archive

    response = client.get("/ecosystem")
    body = response.json()
    assert body["total_habits"] == 0
    assert body["best_current_streak"] == 0


def test_ecosystem_scoped_to_owner(make_authed_client):
    alice = make_authed_client(email="alice_eco@example.com")
    bob = make_authed_client(email="bob_eco@example.com")

    habit = alice.post("/habits", json={"title": "Alice habit"}).json()
    alice.post(f"/habits/{habit['id']}/logs", json={"completed_on": TODAY})

    assert alice.get("/ecosystem").json()["total_habits"] == 1
    assert bob.get("/ecosystem").json()["total_habits"] == 0
