import pytest
from fastapi.testclient import TestClient

from app.matching import get_final_score, search_rooms
from app.main import app


@pytest.fixture
def base_user():
    return {
        "courses": ["MATH131A"],
        "preferred_study_time_tags": ["weekday_mornings", "weekday_evenings"],
        "study_style_preference": "quiet_parallel",
        "study_goals": ["homework_help"],
        "pace_preference": "moderate",
        "group_size_preference": "small_group",
    }


@pytest.fixture
def perfect_match_room():
    return {
        "id": 1,
        "course": "Math131A",
        "preferred_study_time_tags": ["weekday_mornings", "weekday_evenings"],
        "study_style_preference": "quiet_parallel",
        "study_goals": ["homework_help"],
        "pace_preference": "moderate",
        "group_size_preference": "small_group",
    }


def test_perfect_match_score(base_user, perfect_match_room):
    score = get_final_score(base_user, perfect_match_room)
    assert score == 100.0


def test_course_hard_filter(base_user, perfect_match_room):
    perfect_match_room["course"] = "CS35L"
    score = get_final_score(base_user, perfect_match_room)
    assert score == 0.0


def test_course_codes_are_normalized_for_matching(base_user, perfect_match_room):
    base_user["courses"] = ["math 131a"]
    perfect_match_room["course"] = "MATH131A"
    score = get_final_score(base_user, perfect_match_room)
    assert score == 100.0


def test_partial_match_jaccard(base_user, perfect_match_room):
    perfect_match_room["preferred_study_time_tags"] = ["weekday_mornings"]
    score = get_final_score(base_user, perfect_match_room)
    assert score == 92.5


def test_pace_binary_mismatch(base_user, perfect_match_room):
    perfect_match_room["pace_preference"] = "intensive"
    score = get_final_score(base_user, perfect_match_room)
    assert score == 85.0


def test_size_no_preference_safety_valve(base_user, perfect_match_room):
    base_user["group_size_preference"] = "no_preference"
    perfect_match_room["group_size_preference"] = "large_group"
    score = get_final_score(base_user, perfect_match_room)
    assert score == 100.0


def test_missing_optional_group_size_does_not_penalize(base_user, perfect_match_room):
    base_user["group_size_preference"] = None
    perfect_match_room["group_size_preference"] = "large_group"
    score = get_final_score(base_user, perfect_match_room)
    assert score == 100.0


def test_legacy_payload_keys_still_work(base_user, perfect_match_room):
    legacy_user = {
        "courses": base_user["courses"],
        "availability": base_user["preferred_study_time_tags"],
        "study_styles": [base_user["study_style_preference"]],
        "study_goals": base_user["study_goals"],
        "pace": base_user["pace_preference"],
        "size_preference": base_user["group_size_preference"],
    }
    legacy_room = {
        "course": perfect_match_room["course"],
        "availability": perfect_match_room["preferred_study_time_tags"],
        "study_styles": [perfect_match_room["study_style_preference"]],
        "study_goals": perfect_match_room["study_goals"],
        "pace": perfect_match_room["pace_preference"],
        "size": perfect_match_room["group_size_preference"],
    }
    score = get_final_score(legacy_user, legacy_room)
    assert score == 100.0


def test_search_rooms_sorting(base_user):
    all_rooms = [
        {
            "id": 101,
            "course": "Math131A",
            "preferred_study_time_tags": ["weekday_mornings"],
            "study_style_preference": "discussion_based",
            "study_goals": ["homework_help"],
            "pace_preference": "relaxed",
            "group_size_preference": "large_group",
        },
        {
            "id": 102,
            "course": "Math131A",
            "preferred_study_time_tags": ["weekday_mornings", "weekday_evenings"],
            "study_style_preference": "quiet_parallel",
            "study_goals": ["homework_help"],
            "pace_preference": "moderate",
            "group_size_preference": "small_group",
        },
    ]
    results = search_rooms(base_user, all_rooms)
    assert len(results) == 2
    assert results[0]["id"] == 102
    assert results[0]["match_score"] > results[1]["match_score"]


def test_matching_api_accepts_profile_shaped_payload(base_user, tmp_path, monkeypatch):
    monkeypatch.setenv("STUDYSYNC_DB_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("STUDYSYNC_SECRET_KEY", "test-secret-key")

    with TestClient(app) as client:
        response = client.post("/api/matching/search", json=base_user)

    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["course"] == "MATH131A"
    assert results[0]["match_score"] == 92.5
