import pytest
from app.matching import search_rooms

def test_single_room_match():
    user = {
        "courses": ["Math131A"],
        "availability": ["M10", "W10"],
        "preferences": ["Quiet"]
    }
    
    all_rooms = [
        {"id": 1, "course": "CS35L", "availability": ["M10"], "preferences": ["Quiet"]},
        {"id": 2, "course": "Math131A", "availability": ["M10"], "preferences": ["Quiet"]},
        {"id": 3, "course": "Math116", "availability": ["M10"], "preferences": ["Quiet"]}
    ]
    
    results = search_rooms(user, all_rooms)
    
    assert len(results) == 1
    assert results[0]["course"] == "Math131A"
    assert results[0]["match_score"] == 65.0

def test_sorting_and_ranking():
    user = {
        "courses": ["CS35L"],
        "availability": ["M10", "M11", "M12"],
        "preferences": ["Quiet"]
    }
    
    all_rooms = [
        {
            "id": "bad_schedule", 
            "course": "CS35L", 
            "availability": ["M10"],
            "preferences": ["Quiet"]
        },
        {
            "id": "perfect_schedule", 
            "course": "CS35L", 
            "availability": ["M10", "M11", "M12"],
            "preferences": ["Quiet"]
        }
    ]
    
    results = search_rooms(user, all_rooms)
    
    assert len(results) == 2
    assert results[0]["id"] == "perfect_schedule"
    assert results[0]["match_score"] > results[1]["match_score"]

def test_multiple_course_search():
    user = {"courses": ["CS35L", "Math131A"], "availability": ["M10"], "preferences": ["Quiet"]}
    all_rooms = [
        {"id": 1, "course": "CS35L", "availability": ["M10"], "preferences": ["Quiet"]},
        {"id": 2, "course": "Math131A", "availability": ["M10"], "preferences": ["Quiet"]},
        {"id": 3, "course": "PHYSICS1A", "availability": ["M10"], "preferences": ["Quiet"]}
    ]
    
    results = search_rooms(user, all_rooms)
    assert len(results) == 2

    for r in results:
        assert r["course"] in ["CS35L", "Math131A"]

def test_no_matches_found():
    user = {"courses": ["CS181"], "availability": ["M10"], "preferences": ["Quiet"]}
    all_rooms = [{"course": "CS35L"}, {"course": "MATH61"}]
    
    results = search_rooms(user, all_rooms)
    assert results == []