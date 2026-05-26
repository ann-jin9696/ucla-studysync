from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status

from .ai_service import AIService
from .db import get_db
from .groups import ensure_document_in_group, require_group_member
from .openai_document_qa import DocumentQAError, DocumentQAUnavailable
from .schemas import (
    AISummaryCreateRequest,
    AISummaryResponse,
    KeyIdeaResponse,
    SavedSummaryResponse,
)
from .security import get_current_user


router = APIRouter(prefix="/api/ai", tags=["ai"])
ai_service = AIService()


def clean_topic(topic: str | None) -> str | None:
    if topic is None:
        return None
    cleaned = " ".join(topic.strip().split())
    return cleaned or None


def serialize_key_idea(row: sqlite3.Row) -> KeyIdeaResponse:
    return KeyIdeaResponse(
        id=row["id"],
        ai_summary_id=row["ai_summary_id"],
        content=row["content"],
        position=row["position"],
    )


def get_key_ideas(db: sqlite3.Connection, ai_summary_id: int) -> list[KeyIdeaResponse]:
    rows = db.execute(
        """
        SELECT id, ai_summary_id, content, position
        FROM key_ideas
        WHERE ai_summary_id = ?
        ORDER BY position ASC, id ASC
        """,
        (ai_summary_id,),
    ).fetchall()
    return [serialize_key_idea(row) for row in rows]


def summary_is_saved(
    db: sqlite3.Connection,
    ai_summary_id: int,
    user_id: int,
) -> bool:
    row = db.execute(
        """
        SELECT 1
        FROM saved_summaries
        WHERE ai_summary_id = ?
          AND user_id = ?
        """,
        (ai_summary_id, user_id),
    ).fetchone()
    return row is not None


def serialize_ai_summary(
    db: sqlite3.Connection,
    row: sqlite3.Row,
    user_id: int,
) -> AISummaryResponse:
    summary_id = int(row["id"])
    return AISummaryResponse(
        id=summary_id,
        group_id=row["group_id"],
        creator_id=row["creator_id"],
        document_id=row["document_id"],
        topic=row["topic"],
        summary_text=row["summary_text"],
        key_ideas=get_key_ideas(db, summary_id),
        saved=summary_is_saved(db, summary_id, user_id),
        created_at=row["created_at"],
    )


def get_ai_summary_for_member(
    db: sqlite3.Connection,
    ai_summary_id: int,
    user_id: int,
) -> sqlite3.Row:
    row = db.execute(
        """
        SELECT
            ai_summaries.id,
            ai_summaries.group_id,
            ai_summaries.creator_id,
            ai_summaries.document_id,
            ai_summaries.topic,
            ai_summaries.summary_text,
            ai_summaries.created_at
        FROM ai_summaries
        JOIN group_members
          ON group_members.group_id = ai_summaries.group_id
         AND group_members.user_id = ?
        WHERE ai_summaries.id = ?
        """,
        (user_id, ai_summary_id),
    ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI summary not found.",
        )
    return row


def get_saved_summary_row(
    db: sqlite3.Connection,
    ai_summary_id: int,
    user_id: int,
) -> sqlite3.Row:
    row = db.execute(
        """
        SELECT id, user_id, ai_summary_id, saved_at
        FROM saved_summaries
        WHERE ai_summary_id = ?
          AND user_id = ?
        """,
        (ai_summary_id, user_id),
    ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved summary not found.",
        )
    return row


def serialize_saved_summary(
    db: sqlite3.Connection,
    saved_row: sqlite3.Row,
    user_id: int,
) -> SavedSummaryResponse:
    summary = get_ai_summary_for_member(db, int(saved_row["ai_summary_id"]), user_id)
    return SavedSummaryResponse(
        id=saved_row["id"],
        ai_summary_id=saved_row["ai_summary_id"],
        user_id=saved_row["user_id"],
        saved_at=saved_row["saved_at"],
        summary=serialize_ai_summary(db, summary, user_id),
    )


@router.post(
    "/groups/{group_id}/summaries",
    response_model=AISummaryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_ai_summary(
    group_id: int,
    payload: AISummaryCreateRequest,
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(get_current_user),
) -> AISummaryResponse:
    group = require_group_member(db, group_id, int(user["id"]))
    topic = clean_topic(payload.topic)

    if payload.document_id is not None:
        document = ensure_document_in_group(db, group_id, payload.document_id)
        if document["index_status"] != "ready":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That document is not ready for AI summaries yet.",
            )

    ready_document = db.execute(
        """
        SELECT 1
        FROM documents
        WHERE group_id = ?
          AND index_status = 'ready'
        """,
        (group_id,),
    ).fetchone()
    if ready_document is None or not group["openai_vector_store_id"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No indexed documents are ready for AI summaries yet.",
        )

    try:
        draft = ai_service.create_study_summary(
            vector_store_id=str(group["openai_vector_store_id"]),
            topic=topic,
            document_id=payload.document_id,
        )
    except DocumentQAUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except DocumentQAError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenAI study summary failed: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenAI study summary failed: {exc}",
        ) from exc

    summary_text = " ".join(draft.summary_text.strip().split())
    if not summary_text:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenAI study summary did not return summary text.",
        )

    try:
        cursor = db.execute(
            """
            INSERT INTO ai_summaries (
                group_id,
                creator_id,
                document_id,
                topic,
                summary_text
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (group_id, user["id"], payload.document_id, topic, summary_text),
        )
        ai_summary_id = int(cursor.lastrowid)
        for position, key_idea in enumerate(draft.key_ideas[:5], start=1):
            content = " ".join(key_idea.strip().split())
            if not content:
                continue
            db.execute(
                """
                INSERT INTO key_ideas (ai_summary_id, content, position)
                VALUES (?, ?, ?)
                """,
                (ai_summary_id, content[:600], position),
            )
        db.commit()
    except sqlite3.Error:
        db.rollback()
        raise

    return serialize_ai_summary(
        db,
        get_ai_summary_for_member(db, ai_summary_id, int(user["id"])),
        int(user["id"]),
    )


@router.get("/groups/{group_id}/summaries", response_model=list[AISummaryResponse])
def list_ai_summaries(
    group_id: int,
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(get_current_user),
) -> list[AISummaryResponse]:
    require_group_member(db, group_id, int(user["id"]))
    rows = db.execute(
        """
        SELECT id, group_id, creator_id, document_id, topic, summary_text, created_at
        FROM ai_summaries
        WHERE group_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (group_id,),
    ).fetchall()
    return [serialize_ai_summary(db, row, int(user["id"])) for row in rows]


@router.post(
    "/summaries/{ai_summary_id}/save",
    response_model=SavedSummaryResponse,
    status_code=status.HTTP_201_CREATED,
)
def save_ai_summary(
    ai_summary_id: int,
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(get_current_user),
) -> SavedSummaryResponse:
    user_id = int(user["id"])
    get_ai_summary_for_member(db, ai_summary_id, user_id)
    try:
        db.execute(
            """
            INSERT OR IGNORE INTO saved_summaries (user_id, ai_summary_id)
            VALUES (?, ?)
            """,
            (user_id, ai_summary_id),
        )
        db.commit()
    except sqlite3.Error:
        db.rollback()
        raise

    saved_row = get_saved_summary_row(db, ai_summary_id, user_id)
    return serialize_saved_summary(db, saved_row, user_id)


@router.get("/saved-summaries", response_model=list[SavedSummaryResponse])
def list_saved_summaries(
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(get_current_user),
) -> list[SavedSummaryResponse]:
    user_id = int(user["id"])
    rows = db.execute(
        """
        SELECT
            saved_summaries.id,
            saved_summaries.user_id,
            saved_summaries.ai_summary_id,
            saved_summaries.saved_at
        FROM saved_summaries
        JOIN ai_summaries ON ai_summaries.id = saved_summaries.ai_summary_id
        JOIN group_members
          ON group_members.group_id = ai_summaries.group_id
         AND group_members.user_id = saved_summaries.user_id
        WHERE saved_summaries.user_id = ?
        ORDER BY saved_summaries.saved_at DESC, saved_summaries.id DESC
        """,
        (user_id,),
    ).fetchall()
    return [serialize_saved_summary(db, row, user_id) for row in rows]
