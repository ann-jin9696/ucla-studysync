import pytest
from app.matching import get_final_score, search_rooms


@pytest.fixture
def base_user():
    return {
        "courses": ["Math131A"],
        "availability": ["weekday_mornings", "weekday_evenings"],
        "study_styles": ["quiet_parallel"],
        "study_goals": ["homework_help"],
        "pace": "moderate",
        "size_preference": "small_group"
    }


@pytest.fixture
def perfect_match_room():
    return {
        "id": 1,
        "course": "Math131A",
        "availability": ["weekday_mornings", "weekday_evenings"],
        "study_styles": ["quiet_parallel"],
        "study_goals": ["homework_help"],
        "pace": "moderate",
        "size": "small_group"
    }


def test_perfect_match_score(base_user, perfect_match_room):
    """Verifies that identical criteria yield a perfect 100% score."""
    score = get_final_score(base_user, perfect_match_room)
    assert score == 100.0


def test_course_hard_filter(base_user, perfect_match_room):
    """Verifies that an unrequested course acts as a hard filter."""
    perfect_match_room["course"] = "CS35L"
    score = get_final_score(base_user, perfect_match_room)
    assert score == 0.0


def test_partial_match_jaccard(base_user, perfect_match_room):
    """Verifies that half array overlaps deduct correct weighted proportions."""
    # Intersection = 1, Union = 2 -> Jaccard similarity is 50.0%
    perfect_match_room["availability"] = ["weekday_mornings"]
    score = get_final_score(base_user, perfect_match_room)
    # Availability is worth 40 max points. Losing 50% drops score from 100 to 80.
    assert score == 92.5


def test_pace_binary_mismatch(base_user, perfect_match_room):
    """Verifies that a string value mismatch completely voids the pace category."""
    perfect_match_room["pace"] = "intensive"
    score = get_final_score(base_user, perfect_match_room)
    # Pace is worth 10 points. Losing it drops score from 100 to 90.
    assert score == 85.0


def test_size_no_preference_safety_valve(base_user, perfect_match_room):
    """Verifies that selecting 'no_preference' provides automated max size value."""
    base_user["size_preference"] = "no_preference"
    perfect_match_room["size"] = "large_group"
    score = get_final_score(base_user, perfect_match_room)
    assert score == 100.0


def test_search_rooms_sorting(base_user):
    """Verifies that final search collection groups output by maximum rank ordering."""
    all_rooms = [
        {
            "id": 101,
            "course": "Math131A",
            "availability": ["weekday_mornings"],
            "study_styles": ["discussion_based"],
            "study_goals": ["homework_help"],
            "pace": "relaxed",
            "size": "large_group"
        },
        {
            "id": 102,
            "course": "Math131A",
            "availability": ["weekday_mornings", "weekday_evenings"],
            "study_styles": ["quiet_parallel"],
            "study_goals": ["homework_help"],
            "pace": "moderate",
            "size": "small_group"
        }
    ]
    results = search_rooms(base_user, all_rooms)
    assert len(results) == 2
    assert results[0]["id"] == 102  # Higher rank element must bubble to index 0
    assert results[0]["match_score"] > results[1]["match_score"]