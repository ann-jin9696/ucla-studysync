import pytest
from app.matching import get_final_score

def test_perfect_match():
    user_a = {
        "courses": ["CS35L", "MATH131A"],
        "availability": ["M12", "W14"],
        "preferences": ["Quiet"]
    }

    user_b = {
        "courses": ["CS35L", "MATH131A"],
        "availability": ["M12", "W14"],
        "preferences": ["Quiet"]
    }

    assert get_final_score(user_a, user_b) == 100.0

def test_partial_match():
    user_a = {
        "courses": ["CS35L"],
        "availability": ["W14"],
        "preferences": ["Quiet"]
    }

    user_b = {
        "courses": ["CS35L"],
        "availability": ["M12"],
        "preferences": ["Quiet"]
    }
    
    assert get_final_score(user_a, user_b) == 70.0

def test_no_match():
    user_a = {
        "courses" : ["CS35L"],
        "availability": ["M10"],
        "preferences": ["Quiet"]
    }

    user_b = {
        "courses" : ["Math116"],
        "availability": ["W10"],
        "preferences": ["Coffee Shop"]
    }
    assert get_final_score(user_a, user_b) == 0.0

def test_no_data():
    user_a = {
        "courses" : [],
        "availability": [],
        "preferences": []
    }

    user_b = {
        "courses" : [],
        "availability": [],
        "preferences": []
    }
    assert get_final_score(user_a, user_b) == 0.0