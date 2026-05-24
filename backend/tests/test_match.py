from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.matching import group_size_bucket, pace_from_average


def make_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("STUDYSYNC_DB_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("STUDYSYNC_SECRET_KEY", "test-secret-key")
    return TestClient(app)


def course_payload(
    course_code: str = "CS35L",
    study_goals: list[str] | None = None,
    pace_preference: str | None = "moderate",
    group_size_preference: int | None = 4,
) -> dict[str, object]:
    return {
        "course_code": course_code,
        "course_quarter": "Spring 2026",
        "lecture_number": 1,
        "study_goals": study_goals or ["project_work"],
        "pace_preference": pace_preference,
        "group_size_preference": group_size_preference,
    }


def signup_with_profile(
    client: TestClient,
    email: str,
    full_name: str,
    course: dict[str, object],
) -> dict:
    response = client.post(
        "/api/auth/signup",
        json={
            "full_name": full_name,
            "email": email,
            "password": "classroom123",
        },
    )
    assert response.status_code == 201
    profile = client.put("/api/profile/me", json={"courses": [course]})
    assert profile.status_code == 200
    return profile.json()


def login(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "classroom123"},
    )
    assert response.status_code == 200


def create_group_for_current_user(
    client: TestClient,
    profile: dict,
    name: str = "Review Crew",
) -> dict:
    response = client.post(
        "/api/groups",
        json={
            "user_course_id": profile["courses"][0]["user_course_id"],
            "name": name,
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.parametrize(
    ("size", "bucket"),
    [(4, "small"), (5, "medium"), (10, "medium"), (11, "large")],
)
def test_group_size_buckets(size, bucket):
    assert group_size_bucket(size) == bucket


@pytest.mark.parametrize(
    ("score", "pace"),
    [(1.2, "relaxed"), (2.0, "moderate"), (2.6, "intensive"), (None, None)],
)
def test_average_pace_label(score, pace):
    assert pace_from_average(score) == pace


def test_create_group_adds_name_owner_and_current_user(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        profile = signup_with_profile(
            client,
            "owner@g.ucla.edu",
            "Owner Bruin",
            course_payload(),
        )
        created_group = create_group_for_current_user(client, profile, "Midterm Crew")
        my_groups = client.get("/api/groups")

    assert created_group["name"] == "Midterm Crew"
    assert created_group["course_code"] == "CS35L"
    assert created_group["created_by_user_id"] == 1
    assert created_group["member_count"] == 1
    assert my_groups.status_code == 200
    assert [group["name"] for group in my_groups.json()] == ["Midterm Crew"]


def test_course_group_directory_shows_live_properties_sorting_and_filters(
    tmp_path,
    monkeypatch,
):
    with make_client(tmp_path, monkeypatch) as client:
        alice_profile = signup_with_profile(
            client,
            "alice@g.ucla.edu",
            "Alice Bruin",
            course_payload(
                "CS35L",
                study_goals=["exam_prep", "project_work"],
                pace_preference="moderate",
                group_size_preference=4,
            ),
        )
        small_group = create_group_for_current_user(client, alice_profile, "Exam Crew")
        client.post("/api/auth/logout")

        bob_profile = signup_with_profile(
            client,
            "bob@g.ucla.edu",
            "Bob Bruin",
            course_payload(
                "CS35L",
                study_goals=["notes_sharing"],
                pace_preference="intensive",
                group_size_preference=11,
            ),
        )
        large_group = create_group_for_current_user(client, bob_profile, "Notes Lab")
        client.post("/api/auth/logout")

        carol_profile = signup_with_profile(
            client,
            "carol@g.ucla.edu",
            "Carol Bruin",
            course_payload(
                "CS35L",
                study_goals=["exam_prep"],
                pace_preference="moderate",
                group_size_preference=3,
            ),
        )
        user_course_id = carol_profile["courses"][0]["user_course_id"]

        directory = client.get(f"/api/matching/groups?user_course_id={user_course_id}")
        goal_filter = client.get(
            f"/api/matching/groups?user_course_id={user_course_id}&study_goal=notes_sharing"
        )
        pace_filter = client.get(
            f"/api/matching/groups?user_course_id={user_course_id}&pace_preference=intensive"
        )

    assert directory.status_code == 200
    assert [group["id"] for group in directory.json()] == [
        small_group["id"],
        large_group["id"],
    ]
    first_group = directory.json()[0]
    assert first_group["name"] == "Exam Crew"
    assert first_group["top_study_goals"][0] == {"value": "exam_prep", "count": 1}
    assert first_group["average_pace_preference"] == "moderate"
    assert first_group["group_size_bucket"] == "small"
    assert first_group["matches_preferred_group_size"] is True
    assert first_group["is_member"] is False
    assert first_group["is_owner"] is False
    assert goal_filter.status_code == 200
    assert [group["name"] for group in goal_filter.json()] == ["Notes Lab"]
    assert pace_filter.status_code == 200
    assert [group["name"] for group in pace_filter.json()] == ["Notes Lab"]


def test_join_requests_are_one_at_a_time_and_owner_can_approve(tmp_path, monkeypatch):
    db_path = tmp_path / "test.sqlite3"
    with make_client(tmp_path, monkeypatch) as client:
        owner_profile = signup_with_profile(
            client,
            "owner@g.ucla.edu",
            "Owner Bruin",
            course_payload("CS35L"),
        )
        group = create_group_for_current_user(client, owner_profile, "Owner Group")
        client.post("/api/auth/logout")

        applicant_profile = signup_with_profile(
            client,
            "applicant@g.ucla.edu",
            "Applicant Bruin",
            course_payload("CS35L"),
        )
        applicant_user_course_id = applicant_profile["courses"][0]["user_course_id"]
        apply = client.post(f"/api/groups/{group['id']}/join-requests")
        second_apply = client.post(f"/api/groups/{group['id']}/join-requests")
        directory = client.get(
            f"/api/matching/groups?user_course_id={applicant_user_course_id}"
        )
        client.post("/api/auth/logout")

        login(client, "owner@g.ucla.edu")
        requests = client.get(f"/api/groups/{group['id']}/join-requests")
        approved = client.post(
            f"/api/groups/{group['id']}/join-requests/{apply.json()['id']}/approve"
        )
        requests_after = client.get(f"/api/groups/{group['id']}/join-requests")
        my_groups = client.get("/api/groups")

    assert apply.status_code == 201
    assert apply.json()["status"] == "pending"
    assert "expires_at" not in apply.json()
    assert second_apply.status_code == 409
    assert directory.json()[0]["pending_request_id"] == apply.json()["id"]
    assert "pending_request_expires_at" not in directory.json()[0]
    assert requests.status_code == 200
    assert [request["user_name"] for request in requests.json()] == ["Applicant Bruin"]
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert requests_after.json() == []
    assert my_groups.json()[0]["member_count"] == 2

    connection = sqlite3.connect(db_path)
    member_count = connection.execute(
        "SELECT COUNT(*) FROM group_members WHERE group_id = ?",
        (group["id"],),
    ).fetchone()[0]
    assert member_count == 2


def test_user_can_belong_to_multiple_groups_after_approved_requests(
    tmp_path,
    monkeypatch,
):
    with make_client(tmp_path, monkeypatch) as client:
        owner_one_profile = signup_with_profile(
            client,
            "owner-one@g.ucla.edu",
            "Owner One",
            course_payload("CS35L"),
        )
        group_one = create_group_for_current_user(
            client,
            owner_one_profile,
            "Project Crew",
        )
        client.post("/api/auth/logout")

        owner_two_profile = signup_with_profile(
            client,
            "owner-two@g.ucla.edu",
            "Owner Two",
            course_payload("CS35L"),
        )
        group_two = create_group_for_current_user(
            client,
            owner_two_profile,
            "Exam Crew",
        )
        client.post("/api/auth/logout")

        applicant_profile = signup_with_profile(
            client,
            "multi-member@g.ucla.edu",
            "Multi Member",
            course_payload("CS35L"),
        )
        applicant_user_course_id = applicant_profile["courses"][0]["user_course_id"]
        first_application = client.post(
            f"/api/groups/{group_one['id']}/join-requests"
        )
        client.post("/api/auth/logout")

        login(client, "owner-one@g.ucla.edu")
        first_approval = client.post(
            f"/api/groups/{group_one['id']}/join-requests/"
            f"{first_application.json()['id']}/approve"
        )
        client.post("/api/auth/logout")

        login(client, "multi-member@g.ucla.edu")
        second_application = client.post(
            f"/api/groups/{group_two['id']}/join-requests"
        )
        client.post("/api/auth/logout")

        login(client, "owner-two@g.ucla.edu")
        second_approval = client.post(
            f"/api/groups/{group_two['id']}/join-requests/"
            f"{second_application.json()['id']}/approve"
        )
        client.post("/api/auth/logout")

        login(client, "multi-member@g.ucla.edu")
        my_groups = client.get("/api/groups")
        directory = client.get(
            f"/api/matching/groups?user_course_id={applicant_user_course_id}"
        )

    assert first_application.status_code == 201
    assert first_approval.status_code == 200
    assert first_approval.json()["status"] == "approved"
    assert second_application.status_code == 201
    assert second_approval.status_code == 200
    assert second_approval.json()["status"] == "approved"
    assert my_groups.status_code == 200
    assert sorted(group["name"] for group in my_groups.json()) == [
        "Exam Crew",
        "Project Crew",
    ]

    member_state_by_name = {
        group["name"]: group["is_member"]
        for group in directory.json()
        if group["name"] in {"Exam Crew", "Project Crew"}
    }
    assert member_state_by_name == {
        "Exam Crew": True,
        "Project Crew": True,
    }


def test_member_can_leave_group_without_deleting_group(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        owner_profile = signup_with_profile(
            client,
            "owner@g.ucla.edu",
            "Owner Bruin",
            course_payload("CS35L"),
        )
        group = create_group_for_current_user(client, owner_profile, "Owner Group")
        directory_before = client.get(
            f"/api/matching/groups?user_course_id={owner_profile['courses'][0]['user_course_id']}"
        )
        leave = client.delete(f"/api/groups/{group['id']}/membership")
        directory_after = client.get(
            f"/api/matching/groups?user_course_id={owner_profile['courses'][0]['user_course_id']}"
        )
        my_groups = client.get("/api/groups")

    assert directory_before.json()[0]["is_member"] is True
    assert leave.status_code == 200
    assert leave.json()["member_count"] == 0
    assert directory_after.json()[0]["is_member"] is False
    assert directory_after.json()[0]["is_owner"] is True
    assert my_groups.json() == []


def test_owner_can_reject_and_applicant_can_withdraw_request(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        owner_profile = signup_with_profile(
            client,
            "owner@g.ucla.edu",
            "Owner Bruin",
            course_payload("CS35L"),
        )
        group = create_group_for_current_user(client, owner_profile, "Owner Group")
        client.post("/api/auth/logout")

        applicant_profile = signup_with_profile(
            client,
            "applicant@g.ucla.edu",
            "Applicant Bruin",
            course_payload("CS35L"),
        )
        user_course_id = applicant_profile["courses"][0]["user_course_id"]
        pending = client.post(f"/api/groups/{group['id']}/join-requests")
        client.post("/api/auth/logout")

        login(client, "owner@g.ucla.edu")
        rejected = client.post(
            f"/api/groups/{group['id']}/join-requests/{pending.json()['id']}/reject"
        )
        client.post("/api/auth/logout")

        login(client, "applicant@g.ucla.edu")
        replacement = client.post(f"/api/groups/{group['id']}/join-requests")
        pending_directory = client.get(
            f"/api/matching/groups?user_course_id={user_course_id}"
        )
        withdrawn = client.delete(
            f"/api/groups/{group['id']}/join-requests/{replacement.json()['id']}"
        )
        after_withdraw = client.get(f"/api/matching/groups?user_course_id={user_course_id}")
        reapply = client.post(f"/api/groups/{group['id']}/join-requests")

    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert replacement.status_code == 201
    assert pending_directory.json()[0]["pending_request_id"] == replacement.json()["id"]
    assert withdrawn.status_code == 200
    assert withdrawn.json()["status"] == "withdrawn"
    assert after_withdraw.status_code == 200
    assert after_withdraw.json()[0]["pending_request_id"] is None
    assert reapply.status_code == 201


def test_applications_require_same_course_and_owned_user_course(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        owner_profile = signup_with_profile(
            client,
            "owner@g.ucla.edu",
            "Owner Bruin",
            course_payload("CS35L"),
        )
        group = create_group_for_current_user(client, owner_profile, "CS Group")
        owner_user_course_id = owner_profile["courses"][0]["user_course_id"]
        client.post("/api/auth/logout")

        applicant_profile = signup_with_profile(
            client,
            "applicant@g.ucla.edu",
            "Applicant Bruin",
            course_payload("MATH151A"),
        )
        wrong_course = client.post(f"/api/groups/{group['id']}/join-requests")
        owned_course = client.get(
            f"/api/matching/groups?user_course_id={owner_user_course_id}"
        )

    assert wrong_course.status_code == 403
    assert owned_course.status_code == 404
    assert applicant_profile["courses"][0]["course_code"] == "MATH151A"
