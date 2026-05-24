from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query, status

from .db import get_db
from .group_metrics import (
    average_pace,
    get_group_member_courses,
    group_size_bucket,
    pace_from_average,
    top_study_goals,
)
from .schemas import GroupDirectoryResponse
from .security import get_current_user


router = APIRouter(prefix="/api/matching", tags=["matching"])


def get_owned_user_course(
    db: sqlite3.Connection,
    user_id: int,
    user_course_id: int,
) -> sqlite3.Row:
    user_course = db.execute(
        """
        SELECT
            user_course.id,
            user_course.user_id,
            user_course.course_id,
            user_course.study_goals,
            user_course.pace_preference,
            user_course.group_size_preference,
            courses.course_code,
            courses.course_quarter,
            courses.lecture_number
        FROM user_course
        JOIN courses ON courses.id = user_course.course_id
        WHERE user_course.id = ?
          AND user_course.user_id = ?
        """,
        (user_course_id, user_id),
    ).fetchone()
    if user_course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course preference not found.",
        )
    return user_course


def get_pending_request(
    db: sqlite3.Connection,
    group_id: int,
    user_id: int,
) -> sqlite3.Row | None:
    return db.execute(
        """
        SELECT id
        FROM join_requests
        WHERE group_id = ?
          AND user_id = ?
          AND status = 'pending'
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (group_id, user_id),
    ).fetchone()


def get_pending_applicant_count(db: sqlite3.Connection, group_id: int) -> int:
    row = db.execute(
        """
        SELECT COUNT(*) AS applicant_count
        FROM join_requests
        WHERE group_id = ?
          AND status = 'pending'
        """,
        (group_id,),
    ).fetchone()
    return int(row["applicant_count"])


@router.get("/groups", response_model=list[GroupDirectoryResponse])
def list_course_groups(
    user_course_id: int = Query(gt=0),
    study_goal: list[str] = Query(default=[]),
    pace_preference: str | None = None,
    group_size: str | None = None,
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(get_current_user),
) -> list[GroupDirectoryResponse]:
    user_id = int(user["id"])
    user_course = get_owned_user_course(db, user_id, user_course_id)
    preferred_bucket = group_size_bucket(user_course["group_size_preference"])

    groups = db.execute(
        """
        SELECT
            groups.id,
            groups.name,
            groups.course_id,
            courses.course_code,
            courses.course_quarter,
            courses.lecture_number,
            groups.created_by_user_id,
            owner.full_name AS owner_name,
            groups.created_at,
            groups.updated_at,
            COUNT(group_members.id) AS member_count,
            MAX(CASE WHEN group_members.user_id = ? THEN 1 ELSE 0 END) AS is_member
        FROM groups
        JOIN courses ON courses.id = groups.course_id
        JOIN users owner ON owner.id = groups.created_by_user_id
        LEFT JOIN group_members ON group_members.group_id = groups.id
        WHERE groups.course_id = ?
        GROUP BY groups.id
        """,
        (user_id, user_course["course_id"]),
    ).fetchall()

    directory = []
    selected_goals = set(study_goal)
    for group in groups:
        member_courses = get_group_member_courses(db, int(group["id"]), int(group["course_id"]))
        goal_summary = top_study_goals(member_courses)
        average_pace_preference, average_pace_score = average_pace(member_courses)
        size_bucket = group_size_bucket(group["member_count"])
        matches_preferred_size = (
            preferred_bucket == "unknown" or preferred_bucket == size_bucket
        )

        group_goal_values = {goal.value for goal in goal_summary}
        if selected_goals and not selected_goals.issubset(group_goal_values):
            continue
        if pace_preference and average_pace_preference != pace_preference:
            continue
        if group_size and size_bucket != group_size:
            continue

        pending_request = get_pending_request(db, int(group["id"]), user_id)
        directory.append(
            GroupDirectoryResponse(
                id=group["id"],
                name=group["name"],
                course_id=group["course_id"],
                course_code=group["course_code"],
                course_quarter=group["course_quarter"],
                lecture_number=group["lecture_number"],
                created_by_user_id=group["created_by_user_id"],
                owner_name=group["owner_name"],
                member_count=group["member_count"],
                created_at=group["created_at"],
                updated_at=group["updated_at"],
                top_study_goals=goal_summary,
                average_pace_preference=average_pace_preference,
                average_pace_score=average_pace_score,
                group_size_bucket=size_bucket,
                matches_preferred_group_size=matches_preferred_size,
                is_member=bool(group["is_member"]),
                is_owner=int(group["created_by_user_id"]) == user_id,
                pending_request_id=(
                    int(pending_request["id"]) if pending_request is not None else None
                ),
                pending_applicant_count=get_pending_applicant_count(db, int(group["id"])),
            )
        )

    return sorted(
        directory,
        key=lambda group: (
            not group.matches_preferred_group_size,
            group.name.lower(),
        ),
    )
