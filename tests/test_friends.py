from datetime import date, timedelta

TODAY = date.today().isoformat()


def test_friend_endpoints_require_auth(anon_client):
    assert anon_client.get("/friends").status_code == 401
    assert anon_client.get("/friends/requests/incoming").status_code == 401
    assert anon_client.post("/friends/requests", json={"email": "x@example.com"}).status_code == 401


def test_send_friend_request(make_authed_client):
    alice = make_authed_client(email="alice_fr@example.com")
    make_authed_client(email="bob_fr@example.com")

    response = alice.post("/friends/requests", json={"email": "bob_fr@example.com"})
    assert response.status_code == 201
    body = response.json()
    assert body["requester_email"] == "alice_fr@example.com"


def test_cannot_friend_request_self(make_authed_client):
    alice = make_authed_client(email="alice_self@example.com")
    response = alice.post("/friends/requests", json={"email": "alice_self@example.com"})
    assert response.status_code == 400


def test_friend_request_unknown_email(make_authed_client):
    alice = make_authed_client(email="alice_unknown@example.com")
    response = alice.post("/friends/requests", json={"email": "nobody@example.com"})
    assert response.status_code == 404


def test_duplicate_friend_request_rejected(make_authed_client):
    alice = make_authed_client(email="alice_dup@example.com")
    make_authed_client(email="bob_dup@example.com")
    alice.post("/friends/requests", json={"email": "bob_dup@example.com"})
    response = alice.post("/friends/requests", json={"email": "bob_dup@example.com"})
    assert response.status_code == 409


def test_incoming_requests_and_accept(make_authed_client):
    alice = make_authed_client(email="alice_acc@example.com")
    bob = make_authed_client(email="bob_acc@example.com")
    alice.post("/friends/requests", json={"email": "bob_acc@example.com"})

    incoming = bob.get("/friends/requests/incoming").json()
    assert len(incoming) == 1
    assert incoming[0]["requester_email"] == "alice_acc@example.com"
    requester_id = incoming[0]["requester_id"]

    accept = bob.post(f"/friends/requests/{requester_id}/accept")
    assert accept.status_code == 200
    assert accept.json()["email"] == "alice_acc@example.com"

    # now both should see each other as an accepted friend
    assert any(f["email"] == "bob_acc@example.com" for f in alice.get("/friends").json())
    assert any(f["email"] == "alice_acc@example.com" for f in bob.get("/friends").json())
    # the request is resolved, no longer incoming
    assert bob.get("/friends/requests/incoming").json() == []


def test_accept_nonexistent_request_404(make_authed_client):
    bob = make_authed_client(email="bob_noreq@example.com")
    response = bob.post("/friends/requests/999999/accept")
    assert response.status_code == 404


def test_decline_via_delete(make_authed_client):
    alice = make_authed_client(email="alice_decline@example.com")
    bob = make_authed_client(email="bob_decline@example.com")
    alice.post("/friends/requests", json={"email": "bob_decline@example.com"})
    alice_id = alice.get("/me").json()["id"]

    response = bob.delete(f"/friends/{alice_id}")
    assert response.status_code == 204
    assert bob.get("/friends/requests/incoming").json() == []
    assert alice.get("/friends").json() == []

    # after declining, a new request can be sent again
    retry = alice.post("/friends/requests", json={"email": "bob_decline@example.com"})
    assert retry.status_code == 201


def test_unfriend(make_authed_client):
    alice = make_authed_client(email="alice_unfriend@example.com")
    bob = make_authed_client(email="bob_unfriend@example.com")
    alice.post("/friends/requests", json={"email": "bob_unfriend@example.com"})
    bob_id = bob.get("/me").json()["id"]
    alice_id = alice.get("/me").json()["id"]

    # only the addressee (bob) can accept; the requester trying to "accept"
    # their own outgoing request should not find a matching pending row
    wrong_direction = alice.post(f"/friends/requests/{alice_id}/accept")
    assert wrong_direction.status_code == 404

    bob.post(f"/friends/requests/{alice_id}/accept")

    assert len(alice.get("/friends").json()) == 1
    unfriend = alice.delete(f"/friends/{bob_id}")
    assert unfriend.status_code == 204
    assert alice.get("/friends").json() == []
    assert bob.get("/friends").json() == []


def test_remove_nonexistent_friendship_404(make_authed_client):
    alice = make_authed_client(email="alice_noremove@example.com")
    response = alice.delete("/friends/999999")
    assert response.status_code == 404


def test_leaderboard_sorted_by_streak(make_authed_client):
    alice = make_authed_client(email="alice_board@example.com")
    bob = make_authed_client(email="bob_board@example.com")
    carol = make_authed_client(email="carol_board@example.com")

    alice.post("/friends/requests", json={"email": "bob_board@example.com"})
    alice_id = alice.get("/me").json()["id"]
    bob.post(f"/friends/requests/{alice_id}/accept")

    alice.post("/friends/requests", json={"email": "carol_board@example.com"})
    carol_id = carol.get("/me").json()["id"]
    carol.post(f"/friends/requests/{alice_id}/accept")

    bob_habit = bob.post("/habits", json={"title": "Read"}).json()
    bob.post(f"/habits/{bob_habit['id']}/logs", json={"completed_on": TODAY})

    carol_habit = carol.post("/habits", json={"title": "Run"}).json()
    y = (date.today() - timedelta(days=1)).isoformat()
    carol.post(f"/habits/{carol_habit['id']}/logs", json={"completed_on": y})
    carol.post(f"/habits/{carol_habit['id']}/logs", json={"completed_on": TODAY})

    leaderboard = alice.get("/friends").json()
    assert [f["email"] for f in leaderboard] == ["carol_board@example.com", "bob_board@example.com"]
    assert leaderboard[0]["best_current_streak"] == 2
    assert leaderboard[1]["best_current_streak"] == 1


def test_friends_scoped_to_relationship(make_authed_client):
    alice = make_authed_client(email="alice_scope@example.com")
    make_authed_client(email="bob_scope@example.com")
    dave = make_authed_client(email="dave_scope@example.com")

    alice.post("/friends/requests", json={"email": "bob_scope@example.com"})

    # dave is unrelated, should see nobody
    assert dave.get("/friends").json() == []
    assert dave.get("/friends/requests/incoming").json() == []
