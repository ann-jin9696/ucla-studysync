from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status

from .db import get_db
from .profile import STUDY_GOALS
from .schemas import GroupMemberResponse, GroupResponse, createGroupRequest
from .security import get_current_user


router = APIRouter(prefix="/api/groups", tags=["groups"])

GROUP_SIZE_CAPS: dict[str, int | None] = {
    "pair": 2,
    "small": 5,
    "medium": 10,
    "large": None,
}


def serialize_group(row: sqlite3.Row, member_count: int) -> GroupResponse:
    return GroupResponse(
        id=row["id"],
        name=row["name"],
        course=row["course"],
        study_goals=json.loads(row["study_goals"]),
        group_size=row["group_size"],
        member_count=member_count,
        created_at=row["created_at"],
    )


def serialize_member(row: sqlite3.Row) -> GroupMemberResponse:
    return GroupMemberResponse(
        user_id=row["user_id"],
        full_name=row["full_name"],
        joined_at=row["joined_at"],
    )


@router.post("", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
def create_group(
    payload: createGroupRequest,
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(get_current_user),
) -> GroupResponse:
    if payload.group_size not in GROUP_SIZE_CAPS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"group_size must be one of: {', '.join(GROUP_SIZE_CAPS)}",
        )

    invalid_goals = [g for g in payload.study_goals if g not in STUDY_GOALS]
    if invalid_goals:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid study goals: {', '.join(invalid_goals)}",
        )

    name = " ".join(payload.name.strip().split())
    cursor = db.execute(
        "INSERT INTO groups (name, course, study_goals, group_size) VALUES (?, ?, ?, ?)",
        (name, payload.course.strip(), json.dumps(payload.study_goals), payload.group_size),
    )
    group_id = cursor.lastrowid

    db.execute(
        "INSERT INTO group_member (group_id, user_id, role) VALUES (?, ?, 'owner')",
        (group_id, user["id"]),
    )
    db.commit()

    row = db.execute(
        "SELECT id, name, course, study_goals, group_size, created_at FROM groups WHERE id = ?",
        (group_id,),
    ).fetchone()

    return serialize_group(row, member_count=1)


@router.post("/{group_id}/join", response_model=GroupResponse, status_code=status.HTTP_200_OK)
def join_group(
    group_id: int,
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(get_current_user),
) -> GroupResponse:
    group = db.execute(
        "SELECT id, name, course, study_goals, group_size, created_at FROM groups WHERE id = ?",
        (group_id,),
    ).fetchone()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found.")

    existing = db.execute(
        "SELECT id FROM group_member WHERE group_id = ? AND user_id = ?",
        (group_id, user["id"]),
    ).fetchone()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already a member of this group.")

    cap = GROUP_SIZE_CAPS[group["group_size"]]
    member_count = db.execute(
        "SELECT COUNT(*) FROM group_member WHERE group_id = ?",
        (group_id,),
    ).fetchone()[0]
    if cap is not None and member_count >= cap:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Group is full.")

    db.execute(
        "INSERT INTO group_member (group_id, user_id, role) VALUES (?, ?, 'member')",
        (group_id, user["id"]),
    )
    db.commit()

    return serialize_group(group, member_count=member_count + 1)


@router.delete("/{group_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
def leave_group(
    group_id: int,
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(get_current_user),
) -> None:
    group = db.execute(
        "SELECT id FROM groups WHERE id = ?",
        (group_id,),
    ).fetchone()
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found.")

    member = db.execute(
        "SELECT id, role FROM group_member WHERE group_id = ? AND user_id = ?",
        (group_id, user["id"]),
    ).fetchone()
    if member is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You are not a member of this group.")

    if member["role"] == "owner":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Owner cannot leave the group.")

    db.execute(
        "DELETE FROM group_member WHERE id = ?",
        (member["id"],),
    )
    db.commit()
