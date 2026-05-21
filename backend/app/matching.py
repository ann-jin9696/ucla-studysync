from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from .db import get_db
from .schemas import ActivityItemResponse, MatchResultResponse
from .security import get_current_user


router = APIRouter(prefix="/api/matching", tags=["matching"])


def load_json_list(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []

    try:
        value = json.loads(raw_value)
    except json.JSONDecodeError:
        return []

    if isinstance(value, list):
        return value

    return []


def format_preference_label(value: str | None) -> str:
    if not value:
        return "Flexible study style"

    return value.replace("_", " ").title()


def get_user_profile(db: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    return db.execute(
        """
        SELECT
            profiles.id,
            profiles.study_goals,
            profiles.pace_preference,
            profiles.study_style_preference,
            profiles.group_size_preference,
            profiles.preferred_study_time_tags
        FROM profiles
        WHERE profiles.user_id = ?
        """,
        (user_id,),
    ).fetchone()


def get_user_courses(db: sqlite3.Connection, profile_id: int | None) -> list[str]:
    if profile_id is None:
        return []

    rows = db.execute(
        """
        SELECT course_code
        FROM profile_courses
        WHERE profile_id = ?
        ORDER BY course_code ASC
        """,
        (profile_id,),
    ).fetchall()

    return [row["course_code"] for row in rows]


def build_match_results(
    courses: list[str],
    schedule_tags: list[str],
    study_style: str | None,
) -> list[MatchResultResponse]:
    if not courses:
        courses = ["CS35L"]

    if not schedule_tags:
        schedule_tags = ["flexible"]

    matched_schedule = ", ".join(
        tag.replace("_", " ").title() for tag in schedule_tags[:2]
    )
    matched_preference = format_preference_label(study_style)

    results: list[MatchResultResponse] = []

    for index, course in enumerate(courses[:3]):
        results.append(
            MatchResultResponse(
                matchScore=max(72, 96 - index * 7),
                matchedCourse=course,
                matchedSchedule=matched_schedule,
                matchedPreference=matched_preference,
            )
        )

    return results


@router.get("/results", response_model=list[MatchResultResponse])
def list_match_results(
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(get_current_user),
) -> list[MatchResultResponse]:
    profile = get_user_profile(db, int(user["id"]))

    if profile:
        courses = get_user_courses(db, int(profile["id"]))
        schedule_tags = load_json_list(profile["preferred_study_time_tags"])
        study_style = profile["study_style_preference"]
    else:
        courses = []
        schedule_tags = []
        study_style = None

    return build_match_results(courses, schedule_tags, study_style)


@router.get("/activity", response_model=list[ActivityItemResponse])
def list_activity_items(
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(get_current_user),
) -> list[ActivityItemResponse]:
    activity_items: list[ActivityItemResponse] = []
    next_id = 1

    document_rows = db.execute(
        """
        SELECT title, uploaded_at
        FROM documents
        ORDER BY uploaded_at DESC
        LIMIT 3
        """
    ).fetchall()

    for row in document_rows:
        activity_items.append(
            ActivityItemResponse(
                activityId=next_id,
                activityType="document_upload",
                timestamp=row["uploaded_at"],
                description=f'New document uploaded: {row["title"]}',
            )
        )
        next_id += 1

    comment_rows = db.execute(
        """
        SELECT comments.created_at, documents.title
        FROM comments
        JOIN documents ON documents.id = comments.document_id
        ORDER BY comments.created_at DESC
        LIMIT 3
        """
    ).fetchall()

    for row in comment_rows:
        activity_items.append(
            ActivityItemResponse(
                activityId=next_id,
                activityType="comment",
                timestamp=row["created_at"],
                description=f'New comment on {row["title"]}',
            )
        )
        next_id += 1

    profile = get_user_profile(db, int(user["id"]))

    if profile is not None:
        activity_items.append(
            ActivityItemResponse(
                activityId=next_id,
                activityType="profile",
                timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                description="Your profile is ready for study group matching.",
            )
        )

    if not activity_items:
        activity_items.append(
            ActivityItemResponse(
                activityId=next_id,
                activityType="welcome",
                timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                description="Welcome to StudySync. Complete your profile to start matching.",
            )
        )

    return sorted(activity_items, key=lambda item: item.timestamp, reverse=True)[:5]