from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.main import app


def make_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("STUDYSYNC_DB_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("STUDYSYNC_SECRET_KEY", "test-secret-key")
    return TestClient(app)


def signup(client: TestClient, email: str = "profile@g.ucla.edu") -> None:
    response = client.post(
        "/api/auth/signup",
        json={
            "full_name": "Profile Bruin",
            "email": email,
            "password": "classroom123",
        },
    )
    assert response.status_code == 201


def login(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "classroom123"},
    )
    assert response.status_code == 200


def profile_payload(**overrides):
    payload = {
        "courses": ["cs 35l"],
        "study_goals": [],
        "pace_preference": None,
        "study_style_preference": None,
        "group_size_preference": None,
        "preferred_study_time_tags": [],
    }
    payload.update(overrides)
    return payload


def test_profile_routes_require_login(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        get_response = client.get("/api/profile/me")
        put_response = client.put("/api/profile/me", json=profile_payload())

    assert get_response.status_code == 401
    assert put_response.status_code == 401


def test_new_user_gets_empty_incomplete_profile(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client)

        response = client.get("/api/profile/me")

    assert response.status_code == 200
    assert response.json() == {
        "courses": [],
        "study_goals": [],
        "pace_preference": None,
        "study_style_preference": None,
        "group_size_preference": None,
        "preferred_study_time_tags": [],
        "has_basic_profile": False,
        "is_complete": False,
        "created_at": None,
        "updated_at": None,
    }


def test_courses_only_profile_is_basic_but_incomplete(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client)

        response = client.put("/api/profile/me", json=profile_payload())

    assert response.status_code == 200
    assert response.json()["courses"] == ["CS35L"]
    assert response.json()["has_basic_profile"] is True
    assert response.json()["is_complete"] is False


def test_required_profile_fields_make_profile_complete(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client)

        response = client.put(
            "/api/profile/me",
            json=profile_payload(
                study_goals=["exam_prep"],
                pace_preference="moderate",
                study_style_preference="problem_solving",
            ),
        )

    assert response.status_code == 200
    assert response.json()["is_complete"] is True
    assert response.json()["group_size_preference"] is None
    assert response.json()["preferred_study_time_tags"] == []


def test_duplicate_courses_are_normalized_and_deduplicated(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client)

        response = client.put(
            "/api/profile/me",
            json=profile_payload(courses=["cs 35l", "CS35L", "Math151a"]),
        )

    assert response.status_code == 200
    assert response.json()["courses"] == ["CS35L", "MATH151A"]


def test_get_returns_saved_normalized_profile_after_put(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client)
        put_response = client.put(
            "/api/profile/me",
            json=profile_payload(
                courses=["Physics 1a"],
                study_goals=["homework_help", "notes_sharing"],
                pace_preference="relaxed",
                study_style_preference="discussion_based",
                group_size_preference="small_group",
                preferred_study_time_tags=["weekday_evenings", "flexible"],
            ),
        )
        get_response = client.get("/api/profile/me")

    assert put_response.status_code == 200
    assert get_response.status_code == 200
    assert get_response.json() == put_response.json()
    assert get_response.json()["courses"] == ["PHYSICS1A"]


def test_profile_put_replaces_old_courses(tmp_path, monkeypatch):
    db_path = tmp_path / "test.sqlite3"
    with make_client(tmp_path, monkeypatch) as client:
        signup(client)
        first = client.put(
            "/api/profile/me",
            json=profile_payload(courses=["CS35L", "MATH151A"]),
        )
        second = client.put(
            "/api/profile/me",
            json=profile_payload(courses=["CS35L"]),
        )
        get_response = client.get("/api/profile/me")

    connection = sqlite3.connect(db_path)
    profile_count = connection.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]
    course_count = connection.execute("SELECT COUNT(*) FROM profile_courses").fetchone()[0]

    assert first.status_code == 200
    assert second.status_code == 200
    assert get_response.json()["courses"] == ["CS35L"]
    assert profile_count == 1
    assert course_count == 1


def test_profile_put_only_updates_authenticated_user(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client, "user-a@g.ucla.edu")
        client.put("/api/profile/me", json=profile_payload(courses=["CS35L"]))
        client.post("/api/auth/logout")

        signup(client, "user-b@g.ucla.edu")
        user_b_update = client.put(
            "/api/profile/me",
            json=profile_payload(courses=["MATH151A"]),
        )
        user_b_profile = client.get("/api/profile/me")
        client.post("/api/auth/logout")

        login(client, "user-a@g.ucla.edu")
        user_a_profile = client.get("/api/profile/me")

    assert user_b_update.status_code == 200
    assert user_b_profile.json()["courses"] == ["MATH151A"]
    assert user_a_profile.json()["courses"] == ["CS35L"]


def test_profile_put_rejects_ownership_fields(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client)

        response = client.put(
            "/api/profile/me",
            json=profile_payload(user_id=999, profile_id=999),
        )

    assert response.status_code == 400
    assert "Unsupported profile field" in response.json()["detail"]


@pytest.mark.parametrize("course_code", ["hello", "35L", "CS", "CS!!!35L"])
def test_profile_put_rejects_invalid_course_codes(tmp_path, monkeypatch, course_code):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client)

        response = client.put(
            "/api/profile/me",
            json=profile_payload(courses=[course_code]),
        )

    assert response.status_code == 400
    assert "Invalid course code" in response.json()["detail"]


def test_profile_put_rejects_malformed_arrays_and_unknown_enums(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client)

        malformed = client.put(
            "/api/profile/me",
            json=profile_payload(study_goals="exam_prep"),
        )
        unknown = client.put(
            "/api/profile/me",
            json=profile_payload(pace_preference="extra_fast"),
        )

    assert malformed.status_code == 400
    assert unknown.status_code == 400
