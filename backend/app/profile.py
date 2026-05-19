from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Iterable

from fastapi import APIRouter, Body, Depends, HTTPException, status

from .db import get_db
from .schemas import ProfileResponse
from .security import get_current_user


router = APIRouter(prefix="/api/profile", tags=["profile"])

COURSE_PATTERN = re.compile(r"^([A-Z]+)\s*([0-9]+[A-Z]?)$")
PROFILE_FIELDS = {
    "courses",
    "study_goals",
    "pace_preference",
    "study_style_preference",
    "group_size_preference",
    "preferred_study_time_tags",
}
STUDY_GOALS = {
    "homework_help",
    "exam_prep",
    "project_work",
    "concept_review",
    "notes_sharing",
}
PACE_PREFERENCES = {"relaxed", "moderate", "intensive"}
STUDY_STYLE_PREFERENCES = {
    "quiet_parallel",
    "discussion_based",
    "problem_solving",
    "teaching_each_other",
}
GROUP_SIZE_PREFERENCES = {
    "pair",
    "small_group",
    "large_group",
    "no_preference",
}
PREFERRED_STUDY_TIME_TAGS = {
    "weekday_mornings",
    "weekday_afternoons",
    "weekday_evenings",
    "weekend_mornings",
    "weekend_afternoons",
    "weekend_evenings",
    "late_nights",
    "flexible",
}


def bad_request(detail: str) -> None:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


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


def normalize_courses(raw_courses: object) -> list[str]:
    if not isinstance(raw_courses, list):
        bad_request("Courses must be an array of course codes.")

    normalized_courses = []
    seen_courses = set()
    for raw_course in raw_courses:
        course = normalize_course_code(raw_course)
        if course not in seen_courses:
            normalized_courses.append(course)
            seen_courses.add(course)

    if not normalized_courses:
        bad_request("At least one course is required.")

    return normalized_courses


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


def loads_list(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    value = json.loads(raw_value)
    return value if isinstance(value, list) else []


def dumps_list(values: Iterable[str]) -> str:
    return json.dumps(list(values))


def validate_payload(payload: dict[str, object]) -> dict[str, object]:
    extra_fields = sorted(set(payload) - PROFILE_FIELDS)
    if extra_fields:
        bad_request(f"Unsupported profile field: {extra_fields[0]}.")

    return {
        "courses": normalize_courses(payload.get("courses")),
        "study_goals": validate_enum_list(
            payload.get("study_goals", []),
            "study_goals",
            STUDY_GOALS,
        ),
        "pace_preference": validate_optional_enum(
            payload.get("pace_preference"),
            "pace_preference",
            PACE_PREFERENCES,
        ),
        "study_style_preference": validate_optional_enum(
            payload.get("study_style_preference"),
            "study_style_preference",
            STUDY_STYLE_PREFERENCES,
        ),
        "group_size_preference": validate_optional_enum(
            payload.get("group_size_preference"),
            "group_size_preference",
            GROUP_SIZE_PREFERENCES,
        ),
        "preferred_study_time_tags": validate_enum_list(
            payload.get("preferred_study_time_tags", []),
            "preferred_study_time_tags",
            PREFERRED_STUDY_TIME_TAGS,
        ),
    }


def build_profile_response(
    profile: sqlite3.Row | None,
    courses: list[str],
) -> ProfileResponse:
    if profile is None:
        study_goals = []
        pace_preference = None
        study_style_preference = None
        group_size_preference = None
        preferred_study_time_tags = []
        created_at = None
        updated_at = None
    else:
        study_goals = loads_list(profile["study_goals"])
        pace_preference = profile["pace_preference"]
        study_style_preference = profile["study_style_preference"]
        group_size_preference = profile["group_size_preference"]
        preferred_study_time_tags = loads_list(profile["preferred_study_time_tags"])
        created_at = profile["created_at"]
        updated_at = profile["updated_at"]

    has_basic_profile = len(courses) >= 1
    is_complete = (
        has_basic_profile
        and len(study_goals) >= 1
        and pace_preference is not None
        and study_style_preference is not None
    )

    return ProfileResponse(
        courses=courses,
        study_goals=study_goals,
        pace_preference=pace_preference,
        study_style_preference=study_style_preference,
        group_size_preference=group_size_preference,
        preferred_study_time_tags=preferred_study_time_tags,
        has_basic_profile=has_basic_profile,
        is_complete=is_complete,
        created_at=created_at,
        updated_at=updated_at,
    )


def get_profile_with_courses(
    db: sqlite3.Connection,
    user_id: int,
) -> tuple[sqlite3.Row | None, list[str]]:
    profile = db.execute(
        """
        SELECT
            id,
            user_id,
            study_goals,
            pace_preference,
            study_style_preference,
            group_size_preference,
            preferred_study_time_tags,
            created_at,
            updated_at
        FROM profiles
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()
    if profile is None:
        return None, []

    rows = db.execute(
        """
        SELECT course_code
        FROM profile_courses
        WHERE profile_id = ?
        ORDER BY course_code
        """,
        (profile["id"],),
    ).fetchall()
    return profile, [row["course_code"] for row in rows]


@router.get("/me", response_model=ProfileResponse)
def get_my_profile(
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(get_current_user),
) -> ProfileResponse:
    profile, courses = get_profile_with_courses(db, int(user["id"]))
    return build_profile_response(profile, courses)


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
        profile = db.execute(
            "SELECT id FROM profiles WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if profile is None:
            cursor = db.execute(
                """
                INSERT INTO profiles (
                    user_id,
                    study_goals,
                    pace_preference,
                    study_style_preference,
                    group_size_preference,
                    preferred_study_time_tags
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    dumps_list(values["study_goals"]),
                    values["pace_preference"],
                    values["study_style_preference"],
                    values["group_size_preference"],
                    dumps_list(values["preferred_study_time_tags"]),
                ),
            )
            profile_id = cursor.lastrowid
        else:
            profile_id = int(profile["id"])
            db.execute(
                """
                UPDATE profiles
                SET
                    study_goals = ?,
                    pace_preference = ?,
                    study_style_preference = ?,
                    group_size_preference = ?,
                    preferred_study_time_tags = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    dumps_list(values["study_goals"]),
                    values["pace_preference"],
                    values["study_style_preference"],
                    values["group_size_preference"],
                    dumps_list(values["preferred_study_time_tags"]),
                    profile_id,
                ),
            )

        db.execute("DELETE FROM profile_courses WHERE profile_id = ?", (profile_id,))
        db.executemany(
            """
            INSERT INTO profile_courses (profile_id, course_code)
            VALUES (?, ?)
            """,
            [(profile_id, course) for course in values["courses"]],
        )
        db.commit()
    except sqlite3.Error:
        db.rollback()
        raise

    profile, courses = get_profile_with_courses(db, user_id)
    return build_profile_response(profile, courses)
