from __future__ import annotations

import json
import sqlite3
from collections import Counter
from collections.abc import Iterable

from .schemas import StudyGoalSummary


PACE_VALUES = {
    "relaxed": 1,
    "moderate": 2,
    "intensive": 3,
}


def as_list(value: object) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        try:
            parsed_value = json.loads(value)
        except json.JSONDecodeError:
            return [value]
        if isinstance(parsed_value, list):
            return [item for item in parsed_value if isinstance(item, str)]
        return [value]
    if isinstance(value, Iterable) and not isinstance(value, dict):
        return [item for item in value if isinstance(item, str)]
    return []


def parse_group_size(value: object) -> int | None:
    if value in (None, "", "no_preference"):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 1 else None
    if isinstance(value, str) and value.isdigit():
        parsed_value = int(value)
        return parsed_value if parsed_value >= 1 else None
    return None


def group_size_bucket(value: object) -> str:
    size = parse_group_size(value)
    if size is None:
        return "unknown"
    if size < 5:
        return "small"
    if size <= 10:
        return "medium"
    return "large"


def pace_from_average(score: float | None) -> str | None:
    if score is None:
        return None
    if score < 1.5:
        return "relaxed"
    if score < 2.5:
        return "moderate"
    return "intensive"


def top_study_goals(member_courses: list[sqlite3.Row]) -> list[StudyGoalSummary]:
    counter: Counter[str] = Counter()
    for member_course in member_courses:
        counter.update(as_list(member_course["study_goals"]))
    return [
        StudyGoalSummary(value=value, count=count)
        for value, count in counter.most_common(3)
    ]


def average_pace(member_courses: list[sqlite3.Row]) -> tuple[str | None, float | None]:
    pace_scores = [
        PACE_VALUES[member_course["pace_preference"]]
        for member_course in member_courses
        if member_course["pace_preference"] in PACE_VALUES
    ]
    if not pace_scores:
        return None, None
    average_score = round(sum(pace_scores) / len(pace_scores), 2)
    return pace_from_average(average_score), average_score


def get_group_member_courses(
    db: sqlite3.Connection,
    group_id: int,
    course_id: int,
) -> list[sqlite3.Row]:
    return db.execute(
        """
        SELECT
            users.id AS user_id,
            users.full_name,
            group_members.created_at AS joined_at,
            user_course.study_goals,
            user_course.pace_preference,
            user_course.group_size_preference
        FROM group_members
        JOIN users ON users.id = group_members.user_id
        LEFT JOIN user_course
          ON user_course.user_id = group_members.user_id
         AND user_course.course_id = ?
        WHERE group_members.group_id = ?
        ORDER BY users.full_name
        """,
        (course_id, group_id),
    ).fetchall()
