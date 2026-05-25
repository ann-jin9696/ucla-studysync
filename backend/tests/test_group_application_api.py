from __future__ import annotations

from fastapi.testclient import TestClient

from app import groups
from app.main import app


def make_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("STUDYSYNC_DB_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("STUDYSYNC_SECRET_KEY", "test-secret-key")
    monkeypatch.setattr(groups, "UPLOAD_DIR", tmp_path / "uploads")
    return TestClient(app)


def course_payload(course_code: str = "CS35L") -> dict[str, object]:
    return {
        "course_code": course_code,
        "course_quarter": "Spring 2026",
        "lecture_number": 1,
        "study_goals": ["project_work"],
        "pace_preference": "moderate",
        "group_size_preference": 4,
    }


def signup(
    client: TestClient,
    email: str = "workspace@g.ucla.edu",
    full_name: str = "Workspace Bruin",
    password: str = "classroom123",
) -> None:
    response = client.post(
        "/api/auth/signup",
        json={"full_name": full_name, "email": email, "password": password},
    )
    assert response.status_code == 201


def login(client: TestClient, email: str, password: str = "classroom123") -> None:
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200


def enroll_in_course(client: TestClient, course: dict | None = None) -> dict:
    profile = client.put(
        "/api/profile/me",
        json={"courses": [course or course_payload()]},
    )
    assert profile.status_code == 200
    return profile.json()


def create_group(client: TestClient, name: str | None = None) -> int:
    profile = enroll_in_course(client)
    payload: dict = {"user_course_id": profile["courses"][0]["user_course_id"]}
    if name:
        payload["name"] = name
    response = client.post("/api/groups", json=payload)
    assert response.status_code == 201
    return response.json()["id"]


# apply to join group

def test_applicant_can_submit_join_request(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client, "owner@g.ucla.edu", "Owner Bruin")
        group_id = create_group(client)
        client.post("/api/auth/logout")

        signup(client, "applicant@g.ucla.edu", "Applicant Bruin")
        enroll_in_course(client)
        response = client.post(f"/api/groups/{group_id}/join-requests")

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["group_id"] == group_id
    assert body["user_name"] == "Applicant Bruin"


def test_apply_requires_login(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client, "owner@g.ucla.edu")
        group_id = create_group(client)
        client.post("/api/auth/logout")

        response = client.post(f"/api/groups/{group_id}/join-requests")

    assert response.status_code == 401


def test_apply_rejected_if_not_enrolled_in_same_course(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client, "owner@g.ucla.edu")
        group_id = create_group(client)
        client.post("/api/auth/logout")

        signup(client, "outsider@g.ucla.edu")
        enroll_in_course(client, course_payload("MATH151A"))
        response = client.post(f"/api/groups/{group_id}/join-requests")

    assert response.status_code == 403


def test_existing_member_cannot_apply(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client, "owner@g.ucla.edu")
        group_id = create_group(client)
        response = client.post(f"/api/groups/{group_id}/join-requests")

    assert response.status_code == 409


def test_duplicate_pending_request_is_rejected(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client, "owner@g.ucla.edu")
        group_id = create_group(client)
        client.post("/api/auth/logout")

        signup(client, "applicant@g.ucla.edu")
        enroll_in_course(client)
        first = client.post(f"/api/groups/{group_id}/join-requests")
        second = client.post(f"/api/groups/{group_id}/join-requests")

    assert first.status_code == 201
    assert second.status_code == 409

# owner views pending requests

def test_owner_can_list_pending_requests(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client, "owner@g.ucla.edu", "Owner Bruin")
        group_id = create_group(client)
        client.post("/api/auth/logout")

        signup(client, "applicant@g.ucla.edu", "Applicant Bruin")
        enroll_in_course(client)
        client.post(f"/api/groups/{group_id}/join-requests")
        client.post("/api/auth/logout")

        login(client, "owner@g.ucla.edu")
        response = client.get(f"/api/groups/{group_id}/join-requests")

    assert response.status_code == 200
    pending = response.json()
    assert len(pending) == 1
    assert pending[0]["user_name"] == "Applicant Bruin"
    assert pending[0]["status"] == "pending"


def test_non_owner_cannot_list_join_requests(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client, "owner@g.ucla.edu")
        group_id = create_group(client)
        client.post("/api/auth/logout")

        signup(client, "someone@g.ucla.edu")
        enroll_in_course(client)
        response = client.get(f"/api/groups/{group_id}/join-requests")

    assert response.status_code == 403


# approve join request

def test_owner_can_approve_join_request(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client, "owner@g.ucla.edu")
        group_id = create_group(client)
        client.post("/api/auth/logout")

        signup(client, "applicant@g.ucla.edu")
        enroll_in_course(client)
        join_req = client.post(f"/api/groups/{group_id}/join-requests").json()
        client.post("/api/auth/logout")

        login(client, "owner@g.ucla.edu")
        approve = client.post(
            f"/api/groups/{group_id}/join-requests/{join_req['id']}/approve"
        )
        members_response = client.get(f"/api/groups/{group_id}")

    assert approve.status_code == 200
    assert approve.json()["status"] == "approved"
    assert members_response.json()["member_count"] == 2


def test_approved_applicant_can_access_group(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client, "owner@g.ucla.edu")
        group_id = create_group(client)
        client.post("/api/auth/logout")

        signup(client, "applicant@g.ucla.edu")
        enroll_in_course(client)
        join_req = client.post(f"/api/groups/{group_id}/join-requests").json()
        client.post("/api/auth/logout")

        login(client, "owner@g.ucla.edu")
        client.post(
            f"/api/groups/{group_id}/join-requests/{join_req['id']}/approve"
        )
        client.post("/api/auth/logout")

        login(client, "applicant@g.ucla.edu")
        my_groups = client.get("/api/groups")
        group_detail = client.get(f"/api/groups/{group_id}")

    assert my_groups.status_code == 200
    assert any(g["id"] == group_id for g in my_groups.json())
    assert group_detail.status_code == 200


def test_non_owner_cannot_approve_join_request(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client, "owner@g.ucla.edu")
        group_id = create_group(client)
        client.post("/api/auth/logout")

        signup(client, "applicant@g.ucla.edu")
        enroll_in_course(client)
        join_req = client.post(f"/api/groups/{group_id}/join-requests").json()

        approve = client.post(
            f"/api/groups/{group_id}/join-requests/{join_req['id']}/approve"
        )

    assert approve.status_code == 403


# reject join request

def test_owner_can_reject_join_request(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client, "owner@g.ucla.edu")
        group_id = create_group(client)
        client.post("/api/auth/logout")

        signup(client, "applicant@g.ucla.edu")
        enroll_in_course(client)
        join_req = client.post(f"/api/groups/{group_id}/join-requests").json()
        client.post("/api/auth/logout")

        login(client, "owner@g.ucla.edu")
        reject = client.post(
            f"/api/groups/{group_id}/join-requests/{join_req['id']}/reject"
        )
        pending_after = client.get(f"/api/groups/{group_id}/join-requests")

    assert reject.status_code == 200
    assert reject.json()["status"] == "rejected"
    assert pending_after.json() == []


def test_rejected_applicant_cannot_access_group(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client, "owner@g.ucla.edu")
        group_id = create_group(client)
        client.post("/api/auth/logout")

        signup(client, "applicant@g.ucla.edu")
        enroll_in_course(client)
        join_req = client.post(f"/api/groups/{group_id}/join-requests").json()
        client.post("/api/auth/logout")

        login(client, "owner@g.ucla.edu")
        client.post(
            f"/api/groups/{group_id}/join-requests/{join_req['id']}/reject"
        )
        client.post("/api/auth/logout")

        login(client, "applicant@g.ucla.edu")
        group_detail = client.get(f"/api/groups/{group_id}")
        my_groups = client.get("/api/groups")

    assert group_detail.status_code == 403
    assert not any(g["id"] == group_id for g in my_groups.json())


def test_already_decided_request_cannot_be_approved_again(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client, "owner@g.ucla.edu")
        group_id = create_group(client)
        client.post("/api/auth/logout")

        signup(client, "applicant@g.ucla.edu")
        enroll_in_course(client)
        join_req = client.post(f"/api/groups/{group_id}/join-requests").json()
        client.post("/api/auth/logout")

        login(client, "owner@g.ucla.edu")
        client.post(
            f"/api/groups/{group_id}/join-requests/{join_req['id']}/reject"
        )
        second_approve = client.post(
            f"/api/groups/{group_id}/join-requests/{join_req['id']}/approve"
        )

    assert second_approve.status_code == 409


# withdraw join request 

def test_applicant_can_withdraw_pending_request(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client, "owner@g.ucla.edu")
        group_id = create_group(client)
        client.post("/api/auth/logout")

        signup(client, "applicant@g.ucla.edu")
        enroll_in_course(client)
        join_req = client.post(f"/api/groups/{group_id}/join-requests").json()
        withdraw = client.delete(
            f"/api/groups/{group_id}/join-requests/{join_req['id']}"
        )

    assert withdraw.status_code == 200
    assert withdraw.json()["status"] == "withdrawn"


def test_other_user_cannot_withdraw_someone_elses_request(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client, "owner@g.ucla.edu")
        group_id = create_group(client)
        client.post("/api/auth/logout")

        signup(client, "applicant@g.ucla.edu")
        enroll_in_course(client)
        join_req = client.post(f"/api/groups/{group_id}/join-requests").json()
        client.post("/api/auth/logout")

        signup(client, "interloper@g.ucla.edu")
        enroll_in_course(client)
        withdraw = client.delete(
            f"/api/groups/{group_id}/join-requests/{join_req['id']}"
        )

    assert withdraw.status_code == 403


# approve clears other pending requests 

def test_approved_applicant_can_still_apply_to_other_groups(tmp_path, monkeypatch):
    """Approving into group A auto-withdraws any pending request to group B."""
    with make_client(tmp_path, monkeypatch) as client:
        signup(client, "owner_a@g.ucla.edu", "Owner A")
        group_a = create_group(client, "Group A")
        client.post("/api/auth/logout")

        signup(client, "owner_b@g.ucla.edu", "Owner B")
        enroll_in_course(client)
        group_b_response = client.post(
            "/api/groups",
            json={
                "user_course_id": client.get("/api/profile/me").json()["courses"][0]["user_course_id"],
                "name": "Group B",
            },
        )
        assert group_b_response.status_code == 201
        group_b = group_b_response.json()["id"]
        client.post("/api/auth/logout")

        signup(client, "applicant@g.ucla.edu")
        enroll_in_course(client)
        req_a = client.post(f"/api/groups/{group_a}/join-requests").json()
        client.post("/api/auth/logout")

        login(client, "owner_a@g.ucla.edu")
        client.post(
            f"/api/groups/{group_a}/join-requests/{req_a['id']}/approve"
        )
        client.post("/api/auth/logout")

        login(client, "applicant@g.ucla.edu")
        second_request = client.post(f"/api/groups/{group_b}/join-requests")

    assert second_request.status_code == 201


# one pending request at a time 

def test_user_cannot_apply_to_two_groups_in_same_course(tmp_path, monkeypatch):
    """One pending request allowed at a time — second apply to same course is blocked."""
    with make_client(tmp_path, monkeypatch) as client:
        signup(client, "owner_a@g.ucla.edu", "Owner A")
        group_a = create_group(client, "Group A")
        client.post("/api/auth/logout")

        signup(client, "owner_b@g.ucla.edu", "Owner B")
        enroll_in_course(client)
        group_b_response = client.post(
            "/api/groups",
            json={
                "user_course_id": client.get("/api/profile/me").json()["courses"][0]["user_course_id"],
                "name": "Group B",
            },
        )
        assert group_b_response.status_code == 201
        group_b = group_b_response.json()["id"]
        client.post("/api/auth/logout")

        signup(client, "applicant@g.ucla.edu")
        enroll_in_course(client)
        first = client.post(f"/api/groups/{group_a}/join-requests")
        second = client.post(f"/api/groups/{group_b}/join-requests")

    assert first.status_code == 201
    assert second.status_code == 409


def test_user_can_apply_to_groups_in_different_courses_simultaneously(tmp_path, monkeypatch):
    """Pending-request limit is per course — one pending per course is allowed."""
    with make_client(tmp_path, monkeypatch) as client:
        signup(client, "owner_a@g.ucla.edu", "Owner A")
        group_a = create_group(client, "Group A")
        client.post("/api/auth/logout")

        signup(client, "owner_b@g.ucla.edu", "Owner B")
        enroll_in_course(client, course_payload("MATH151A"))
        group_b_response = client.post(
            "/api/groups",
            json={
                "user_course_id": client.get("/api/profile/me").json()["courses"][0]["user_course_id"],
                "name": "Group B",
            },
        )
        assert group_b_response.status_code == 201
        group_b = group_b_response.json()["id"]
        client.post("/api/auth/logout")

        signup(client, "applicant@g.ucla.edu")
        client.put(
            "/api/profile/me",
            json={"courses": [course_payload("CS35L"), course_payload("MATH151A")]},
        )
        first = client.post(f"/api/groups/{group_a}/join-requests")
        second = client.post(f"/api/groups/{group_b}/join-requests")

    assert first.status_code == 201
    assert second.status_code == 201


# leave group

def test_owner_leaving_empty_group_deletes_it(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client, "owner@g.ucla.edu")
        group_id = create_group(client)

        leave = client.delete(f"/api/groups/{group_id}/membership")
        fetch = client.get(f"/api/groups/{group_id}")
        my_groups = client.get("/api/groups")

    assert leave.status_code == 200
    assert fetch.status_code == 404
    assert not any(g["id"] == group_id for g in my_groups.json())


def test_group_stays_when_owner_leaves_with_other_members(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client, "owner@g.ucla.edu")
        group_id = create_group(client)
        client.post("/api/auth/logout")

        signup(client, "member@g.ucla.edu")
        enroll_in_course(client)
        join_req = client.post(f"/api/groups/{group_id}/join-requests").json()
        client.post("/api/auth/logout")

        login(client, "owner@g.ucla.edu")
        client.post(f"/api/groups/{group_id}/join-requests/{join_req['id']}/approve")
        leave = client.delete(f"/api/groups/{group_id}/membership")
        client.post("/api/auth/logout")

        login(client, "member@g.ucla.edu")
        fetch = client.get(f"/api/groups/{group_id}")

    assert leave.status_code == 200
    assert fetch.status_code == 200
    assert fetch.json()["member_count"] == 1


def test_second_member_becomes_owner_when_owner_leaves(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client, "owner@g.ucla.edu", "Owner Bruin")
        group_id = create_group(client)
        client.post("/api/auth/logout")

        signup(client, "member@g.ucla.edu", "Member Bruin")
        enroll_in_course(client)
        join_req = client.post(f"/api/groups/{group_id}/join-requests").json()
        client.post("/api/auth/logout")

        login(client, "owner@g.ucla.edu")
        client.post(f"/api/groups/{group_id}/join-requests/{join_req['id']}/approve")
        client.delete(f"/api/groups/{group_id}/membership")
        client.post("/api/auth/logout")

        login(client, "member@g.ucla.edu")
        detail = client.get(f"/api/groups/{group_id}")

    assert detail.status_code == 200
    assert detail.json()["owner_name"] == "Member Bruin"


def test_pending_applications_cleared_when_empty_group_deleted(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client, "owner@g.ucla.edu")
        group_id = create_group(client)
        client.post("/api/auth/logout")

        signup(client, "applicant@g.ucla.edu")
        enroll_in_course(client)
        client.post(f"/api/groups/{group_id}/join-requests")
        client.post("/api/auth/logout")

        login(client, "owner@g.ucla.edu")
        client.delete(f"/api/groups/{group_id}/membership")

        pending = client.get("/api/groups/join-requests/pending")

    assert pending.status_code == 200
    assert pending.json() == []
