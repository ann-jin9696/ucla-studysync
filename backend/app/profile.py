from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Iterable
from datetime import date

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from .db import get_db
from .schemas import (
    CourseCodeOptionsResponse,
    CourseQuarterOptionsResponse,
    ProfileResponse,
)
from .security import get_current_user


router = APIRouter(prefix="/api/profile", tags=["profile"])

COURSE_PATTERN = re.compile(r"^([A-Z]+)\s*([0-9]+[A-Z]?)$")
PROFILE_FIELDS = {"courses"}
COURSE_FIELDS = {
    "course_code",
    "course_quarter",
    "lecture_number",
    "study_goals",
    "pace_preference",
    "group_size_preference",
}
STUDY_GOALS = {
    "homework_help",
    "exam_prep",
    "project_work",
    "concept_review",
    "notes_sharing",
}
PACE_PREFERENCES = {"relaxed", "moderate", "intensive"}
TERMS = ("Winter", "Spring", "Summer", "Fall")
FIRST_QUARTER = ("Spring", 2026)


def bad_request(detail: str) -> None:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def generate_course_quarter_options(today: date | None = None) -> list[str]:
    current_year = (today or date.today()).year
    final_year = current_year + 2
    options = []
    for year in range(FIRST_QUARTER[1], final_year + 1):
        for term in TERMS:
            if year == FIRST_QUARTER[1] and TERMS.index(term) < TERMS.index(FIRST_QUARTER[0]):
                continue
            options.append(f"{term} {year}")
    return options


def normalize_course_code(raw_code: object) -> str:
    if not isinstance(raw_code, str):
        bad_request("Course codes must be text values.")

    compact_code = " ".join(raw_code.strip().upper().split())
    match = COURSE_PATTERN.fullmatch(compact_code)
    if match is None:
        bad_request(
            f"Invalid course code: {raw_code}. Use department letters, course number, "
            "and optional letter suffix, like CS35L or MATH151A."
        )

    return f"{match.group(1)}{match.group(2)}"


def normalize_course_code_search(raw_search: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", raw_search.upper())


def validate_course_quarter(raw_quarter: object) -> str:
    if not isinstance(raw_quarter, str):
        bad_request("course_quarter must be a text value.")
    quarter = " ".join(raw_quarter.strip().split())
    if quarter not in set(generate_course_quarter_options()):
        bad_request(f"Unsupported course_quarter: {raw_quarter}.")
    return quarter


def validate_lecture_number(raw_value: object) -> int:
    if isinstance(raw_value, bool) or not isinstance(raw_value, int):
        bad_request("lecture_number must be an integer.")
    if raw_value < 1:
        bad_request("lecture_number must be at least 1.")
    return raw_value


def validate_enum_list(
    raw_values: object,
    field_name: str,
    allowed_values: set[str],
) -> list[str]:
    if raw_values is None:
        return []
    if not isinstance(raw_values, list):
        bad_request(f"{field_name} must be an array.")

    validated_values = []
    seen_values = set()
    for raw_value in raw_values:
        if not isinstance(raw_value, str):
            bad_request(f"{field_name} values must be text.")
        if raw_value not in allowed_values:
            bad_request(f"Unknown {field_name} value: {raw_value}.")
        if raw_value not in seen_values:
            validated_values.append(raw_value)
            seen_values.add(raw_value)

    return validated_values


def validate_optional_enum(
    raw_value: object,
    field_name: str,
    allowed_values: set[str],
) -> str | None:
    if raw_value is None or raw_value == "":
        return None
    if not isinstance(raw_value, str):
        bad_request(f"{field_name} must be a text value.")
    if raw_value not in allowed_values:
        bad_request(f"Unknown {field_name} value: {raw_value}.")
    return raw_value


def validate_group_size_preference(raw_value: object) -> int | None:
    if raw_value is None or raw_value == "":
        return None
    if isinstance(raw_value, bool) or not isinstance(raw_value, int):
        bad_request("group_size_preference must be an integer.")
    if raw_value < 1:
        bad_request("group_size_preference must be at least 1.")
    return raw_value


def coerce_stored_group_size(raw_value: object) -> int | None:
    if raw_value in (None, "", "no_preference"):
        return None
    if isinstance(raw_value, int):
        return raw_value if raw_value >= 1 else None
    if isinstance(raw_value, str):
        if raw_value.isdigit():
            size = int(raw_value)
            return size if size >= 1 else None
        legacy_sizes = {
            "pair": 2,
            "small_group": 4,
            "medium_group": 8,
            "large_group": 11,
        }
        return legacy_sizes.get(raw_value)
    return None


def loads_list(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    try:
        value = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def dumps_list(values: Iterable[str]) -> str:
    return json.dumps(list(values))


def normalize_course_entry(raw_course: object) -> dict[str, object]:
    if not isinstance(raw_course, dict):
        bad_request("Courses must be course objects.")

    extra_fields = sorted(set(raw_course) - COURSE_FIELDS)
    if extra_fields:
        bad_request(f"Unsupported course field: {extra_fields[0]}.")

    return {
        "course_code": normalize_course_code(raw_course.get("course_code")),
        "course_quarter": validate_course_quarter(raw_course.get("course_quarter")),
        "lecture_number": validate_lecture_number(raw_course.get("lecture_number")),
        "study_goals": validate_enum_list(
            raw_course.get("study_goals", []),
            "study_goals",
            STUDY_GOALS,
        ),
        "pace_preference": validate_optional_enum(
            raw_course.get("pace_preference"),
            "pace_preference",
            PACE_PREFERENCES,
        ),
        "group_size_preference": validate_group_size_preference(
            raw_course.get("group_size_preference"),
        ),
    }


def normalize_courses(raw_courses: object) -> list[dict[str, object]]:
    if not isinstance(raw_courses, list):
        bad_request("Courses must be an array.")

    normalized_courses = []
    seen_courses = set()
    for raw_course in raw_courses:
        course = normalize_course_entry(raw_course)
        course_key = (
            course["course_code"],
            course["course_quarter"],
            course["lecture_number"],
        )
        if course_key not in seen_courses:
            normalized_courses.append(course)
            seen_courses.add(course_key)

    if not normalized_courses:
        bad_request("At least one course is required.")

    return normalized_courses


def validate_payload(payload: dict[str, object]) -> dict[str, object]:
    extra_fields = sorted(set(payload) - PROFILE_FIELDS)
    if extra_fields:
        bad_request(f"Unsupported profile field: {extra_fields[0]}.")

    return {
        "courses": normalize_courses(payload.get("courses")),
    }


def serialize_course(row: sqlite3.Row) -> dict[str, object]:
    return {
        "user_course_id": row["user_course_id"],
        "course_id": row["course_id"],
        "course_code": row["course_code"],
        "course_quarter": row["course_quarter"],
        "lecture_number": row["lecture_number"],
        "study_goals": loads_list(row["study_goals"]),
        "pace_preference": row["pace_preference"],
        "group_size_preference": coerce_stored_group_size(row["group_size_preference"]),
    }


def build_profile_response(rows: list[sqlite3.Row]) -> ProfileResponse:
    courses = [serialize_course(row) for row in rows]
    has_basic_profile = len(courses) >= 1
    is_complete = has_basic_profile and all(
        course["study_goals"] and course["pace_preference"] for course in courses
    )

    return ProfileResponse(
        courses=courses,
        has_basic_profile=has_basic_profile,
        is_complete=is_complete,
        created_at=min((row["created_at"] for row in rows), default=None),
        updated_at=max((row["updated_at"] for row in rows), default=None),
    )


def get_profile_courses(db: sqlite3.Connection, user_id: int) -> list[sqlite3.Row]:
    return db.execute(
        """
        SELECT
            user_course.id AS user_course_id,
            user_course.course_id,
            courses.course_code,
            courses.course_quarter,
            courses.lecture_number,
            user_course.study_goals,
            user_course.pace_preference,
            user_course.group_size_preference,
            user_course.created_at,
            user_course.updated_at
        FROM user_course
        JOIN courses ON courses.id = user_course.course_id
        WHERE user_course.user_id = ?
        ORDER BY courses.course_code, courses.course_quarter, courses.lecture_number
        """,
        (user_id,),
    ).fetchall()


def get_or_create_course(
    db: sqlite3.Connection,
    course: dict[str, object],
) -> int:
    db.execute(
        """
        INSERT OR IGNORE INTO courses (
            course_code,
            course_quarter,
            lecture_number
        )
        VALUES (?, ?, ?)
        """,
        (
            course["course_code"],
            course["course_quarter"],
            course["lecture_number"],
        ),
    )
    row = db.execute(
        """
        SELECT id
        FROM courses
        WHERE course_code = ?
          AND course_quarter = ?
          AND lecture_number = ?
        """,
        (
            course["course_code"],
            course["course_quarter"],
            course["lecture_number"],
        ),
    ).fetchone()
    return int(row["id"])


@router.get("/course-quarters", response_model=CourseQuarterOptionsResponse)
def list_course_quarters() -> CourseQuarterOptionsResponse:
    return CourseQuarterOptionsResponse(options=generate_course_quarter_options())


@router.get("/course-codes", response_model=CourseCodeOptionsResponse)
def list_course_codes(
    search: str = Query(default="", max_length=40),
    db: sqlite3.Connection = Depends(get_db),
    _user: sqlite3.Row = Depends(get_current_user),
) -> CourseCodeOptionsResponse:
    normalized_search = normalize_course_code_search(search)
    if normalized_search:
        rows = db.execute(
            """
            SELECT DISTINCT course_code
            FROM courses
            WHERE course_code LIKE ?
            ORDER BY course_code
            LIMIT 8
            """,
            (f"{normalized_search}%",),
        ).fetchall()
    else:
        rows = db.execute(
            """
            SELECT DISTINCT course_code
            FROM courses
            ORDER BY course_code
            LIMIT 8
            """
        ).fetchall()

    return CourseCodeOptionsResponse(options=[row["course_code"] for row in rows])


@router.get("/me", response_model=ProfileResponse)
def get_my_profile(
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(get_current_user),
) -> ProfileResponse:
    return build_profile_response(get_profile_courses(db, int(user["id"])))


@router.put("/me", response_model=ProfileResponse)
def update_my_profile(
    payload: dict[str, object] = Body(...),
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(get_current_user),
) -> ProfileResponse:
    values = validate_payload(payload)
    user_id = int(user["id"])

    try:
        db.execute("BEGIN")
        course_ids = []
        for course in values["courses"]:
            course_ids.append(get_or_create_course(db, course))

        if course_ids:
            placeholders = ", ".join("?" for _ in course_ids)
            db.execute(
                f"""
                DELETE FROM group_members
                WHERE user_id = ?
                  AND group_id IN (
                    SELECT id
                    FROM groups
                    WHERE course_id NOT IN ({placeholders})
                  )
                """,
                (user_id, *course_ids),
            )
            db.execute(
                f"""
                UPDATE join_requests
                SET status = 'withdrawn',
                    decided_by_user_id = ?,
                    decided_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                  AND status = 'pending'
                  AND group_id IN (
                    SELECT id
                    FROM groups
                    WHERE course_id NOT IN ({placeholders})
                  )
                """,
                (user_id, user_id, *course_ids),
            )

        db.execute("DELETE FROM user_course WHERE user_id = ?", (user_id,))
        for course, course_id in zip(values["courses"], course_ids, strict=True):
            db.execute(
                """
                INSERT INTO user_course (
                    user_id,
                    course_id,
                    study_goals,
                    pace_preference,
                    group_size_preference
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    course_id,
                    dumps_list(course["study_goals"]),
                    course["pace_preference"],
                    course["group_size_preference"],
                ),
            )
        db.commit()
    except sqlite3.Error:
        db.rollback()
        raise

    return build_profile_response(get_profile_courses(db, user_id))
