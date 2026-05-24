from __future__ import annotations

import sqlite3
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.profile import generate_course_quarter_options


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


def course(
    course_code: str,
    course_quarter: str = "Spring 2026",
    lecture_number: int = 1,
    study_goals: list[str] | None = None,
    pace_preference: str | None = None,
    group_size_preference: int | None = None,
) -> dict[str, object]:
    return {
        "course_code": course_code,
        "course_quarter": course_quarter,
        "lecture_number": lecture_number,
        "study_goals": study_goals or [],
        "pace_preference": pace_preference,
        "group_size_preference": group_size_preference,
    }


def profile_payload(**overrides):
    payload = {"courses": [course("cs 35l")]}
    payload.update(overrides)
    return payload


def simplify_courses(response_json: dict) -> list[dict[str, object]]:
    return [
        {
            "course_code": row["course_code"],
            "course_quarter": row["course_quarter"],
            "lecture_number": row["lecture_number"],
            "study_goals": row["study_goals"],
            "pace_preference": row["pace_preference"],
            "group_size_preference": row["group_size_preference"],
        }
        for row in response_json["courses"]
    ]


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
    assert simplify_courses(response.json()) == [
        {
            "course_code": "CS35L",
            "course_quarter": "Spring 2026",
            "lecture_number": 1,
            "study_goals": [],
            "pace_preference": None,
            "group_size_preference": None,
        }
    ]
    assert response.json()["courses"][0]["user_course_id"] > 0
    assert response.json()["courses"][0]["course_id"] > 0
    assert response.json()["has_basic_profile"] is True
    assert response.json()["is_complete"] is False


def test_course_code_search_returns_seeded_and_saved_codes(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client)
        seeded_response = client.get("/api/profile/course-codes?search=cs")
        client.put(
            "/api/profile/me",
            json=profile_payload(courses=[course("Ling20")]),
        )
        saved_response = client.get("/api/profile/course-codes?search=lin")

    assert seeded_response.status_code == 200
    assert "CS35L" in seeded_response.json()["options"]
    assert saved_response.status_code == 200
    assert saved_response.json()["options"] == ["LING20"]


def test_per_course_required_fields_make_profile_complete(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client)

        response = client.put(
            "/api/profile/me",
            json=profile_payload(
                courses=[
                    course(
                        "cs 35l",
                        study_goals=["exam_prep"],
                        pace_preference="moderate",
                    )
                ],
            ),
        )

    assert response.status_code == 200
    assert response.json()["is_complete"] is True
    assert response.json()["courses"][0]["group_size_preference"] is None


def test_duplicate_course_offerings_are_normalized_and_deduplicated(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client)

        response = client.put(
            "/api/profile/me",
            json=profile_payload(
                courses=[
                    course("cs 35l", "Spring 2026", 1),
                    course("CS35L", "Spring 2026", 1, pace_preference="moderate"),
                    course("CS35L", "Spring 2026", 2),
                    course("Math151a", "Fall 2026", 1),
                ],
            ),
        )

    assert response.status_code == 200
    assert simplify_courses(response.json()) == [
        {
            "course_code": "CS35L",
            "course_quarter": "Spring 2026",
            "lecture_number": 1,
            "study_goals": [],
            "pace_preference": None,
            "group_size_preference": None,
        },
        {
            "course_code": "CS35L",
            "course_quarter": "Spring 2026",
            "lecture_number": 2,
            "study_goals": [],
            "pace_preference": None,
            "group_size_preference": None,
        },
        {
            "course_code": "MATH151A",
            "course_quarter": "Fall 2026",
            "lecture_number": 1,
            "study_goals": [],
            "pace_preference": None,
            "group_size_preference": None,
        },
    ]


def test_get_returns_saved_normalized_profile_after_put(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client)
        put_response = client.put(
            "/api/profile/me",
            json=profile_payload(
                courses=[
                    course(
                        "Physics 1a",
                        "Summer 2026",
                        3,
                        ["homework_help", "notes_sharing"],
                        "relaxed",
                        4,
                    )
                ],
            ),
        )
        get_response = client.get("/api/profile/me")

    assert put_response.status_code == 200
    assert get_response.status_code == 200
    assert get_response.json() == put_response.json()
    assert simplify_courses(get_response.json()) == [
        {
            "course_code": "PHYSICS1A",
            "course_quarter": "Summer 2026",
            "lecture_number": 3,
            "study_goals": ["homework_help", "notes_sharing"],
            "pace_preference": "relaxed",
            "group_size_preference": 4,
        }
    ]


def test_profile_put_replaces_old_courses(tmp_path, monkeypatch):
    db_path = tmp_path / "test.sqlite3"
    with make_client(tmp_path, monkeypatch) as client:
        signup(client)
        first = client.put(
            "/api/profile/me",
            json=profile_payload(courses=[course("CS35L"), course("MATH151A")]),
        )
        second = client.put(
            "/api/profile/me",
            json=profile_payload(courses=[course("CS35L", "Fall 2026", 2)]),
        )
        get_response = client.get("/api/profile/me")

    connection = sqlite3.connect(db_path)
    saved_course_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM courses
        WHERE course_code IN ('CS35L', 'MATH151A')
        """
    ).fetchone()[0]
    user_course_count = connection.execute("SELECT COUNT(*) FROM user_course").fetchone()[0]

    assert first.status_code == 200
    assert second.status_code == 200
    assert simplify_courses(get_response.json()) == [
        {
            "course_code": "CS35L",
            "course_quarter": "Fall 2026",
            "lecture_number": 2,
            "study_goals": [],
            "pace_preference": None,
            "group_size_preference": None,
        }
    ]
    assert saved_course_count >= 2
    assert user_course_count == 1


def test_profile_put_only_updates_authenticated_user(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client, "user-a@g.ucla.edu")
        client.put("/api/profile/me", json=profile_payload(courses=[course("CS35L")]))
        client.post("/api/auth/logout")

        signup(client, "user-b@g.ucla.edu")
        user_b_update = client.put(
            "/api/profile/me",
            json=profile_payload(courses=[course("MATH151A", "Fall 2026", 1)]),
        )
        user_b_profile = client.get("/api/profile/me")
        client.post("/api/auth/logout")

        login(client, "user-a@g.ucla.edu")
        user_a_profile = client.get("/api/profile/me")

    assert user_b_update.status_code == 200
    assert simplify_courses(user_b_profile.json())[0]["course_code"] == "MATH151A"
    assert simplify_courses(user_a_profile.json())[0]["course_code"] == "CS35L"


def test_profile_put_rejects_top_level_preference_fields(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client)

        response = client.put(
            "/api/profile/me",
            json=profile_payload(study_goals=["exam_prep"], user_id=999),
        )

    assert response.status_code == 400
    assert "Unsupported profile field" in response.json()["detail"]


def test_profile_put_rejects_removed_course_time_and_study_style_fields(
    tmp_path,
    monkeypatch,
):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client)

        course_time_response = client.put(
            "/api/profile/me",
            json=profile_payload(courses=[{**course("CS35L"), "course_time": "MWF 10"}]),
        )
        study_style_response = client.put(
            "/api/profile/me",
            json=profile_payload(courses=[{**course("CS35L"), "study_style": "quiet"}]),
        )

    assert course_time_response.status_code == 400
    assert study_style_response.status_code == 400


@pytest.mark.parametrize("course_code", ["hello", "35L", "CS", "CS!!!35L"])
def test_profile_put_rejects_invalid_course_codes(tmp_path, monkeypatch, course_code):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client)

        response = client.put(
            "/api/profile/me",
            json=profile_payload(courses=[course(course_code)]),
        )

    assert response.status_code == 400
    assert "Invalid course code" in response.json()["detail"]


def test_profile_put_validates_quarter_and_lecture_number(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client)

        winter_2026 = client.put(
            "/api/profile/me",
            json=profile_payload(courses=[course("CS35L", "Winter 2026", 1)]),
        )
        bad_lecture = client.put(
            "/api/profile/me",
            json=profile_payload(courses=[course("CS35L", "Spring 2026", 0)]),
        )

    assert winter_2026.status_code == 400
    assert bad_lecture.status_code == 400


def test_profile_put_rejects_malformed_arrays_and_unknown_enums(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client)

        malformed = client.put(
            "/api/profile/me",
            json=profile_payload(courses=[{**course("CS35L"), "study_goals": "exam_prep"}]),
        )
        unknown = client.put(
            "/api/profile/me",
            json=profile_payload(courses=[course("CS35L", pace_preference="extra_fast")]),
        )
        bad_group_size = client.put(
            "/api/profile/me",
            json=profile_payload(
                courses=[{**course("CS35L"), "group_size_preference": "small_group"}],
            ),
        )

    assert malformed.status_code == 400
    assert unknown.status_code == 400
    assert bad_group_size.status_code == 400


def test_course_quarter_options_start_at_spring_2026_and_extend_two_years():
    options = generate_course_quarter_options(date(2026, 5, 23))

    assert options[0] == "Spring 2026"
    assert "Winter 2026" not in options
    assert options[-1] == "Fall 2028"
