import pytest
from app.matching import calculate_matching_score

def test_perfect_match():
    user_a  = ["CS35L", "MATH131A"]
    user_b  = ["CS35L", "MATH131A"]
    assert calculate_matching_score(user_a, user_b) == 100.0

def test_partial_match():
    user_a  = [ "MATH131A", "MATH170E"]
    user_b  = ["CS35L", "MATH131A"]
    assert calculate_matching_score(user_a, user_b) == 33.33

def test_no_match():
    user_a  = ["Math168"]
    user_b  = ["MATH131A"]
    assert calculate_matching_score(user_a, user_b) == 0.0

def test_no_data():
    assert calculate_matching_score([], []) == 0.0
    assert calculate_matching_score(["CS35L"], []) == 0.0