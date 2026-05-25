from __future__ import annotations

import re
import shutil
import sqlite3
from mimetypes import guess_type
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse

from .db import get_db
from .email import (
    send_group_application_decision_email,
    send_group_application_reviewer_email,
)
from .group_metrics import (
    as_list,
    average_pace,
    get_group_member_courses,
    group_size_bucket,
    top_study_goals,
)
from .openai_document_qa import (
    DocumentQAError,
    DocumentQAUnavailable,
    OpenAIDocumentQA,
)
from .schemas import (
    CommentCreateRequest,
    CommentResponse,
    DocumentQARequest,
    DocumentQAResponse,
    DocumentQASource,
    DocumentResponse,
    GroupActivityResponse,
    GroupCreateRequest,
    GroupDetailResponse,
    GroupDocumentsResponse,
    GroupMemberResponse,
    JoinRequestResponse,
    GroupResponse,
    PendingApplicationResponse,
)
from .security import get_current_user


router = APIRouter(prefix="/api/groups", tags=["groups"])
document_qa_service = OpenAIDocumentQA()

BACKEND_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BACKEND_DIR / "data" / "uploads"
SUPPORTED_DOCUMENT_EXTENSIONS = {".pdf", ".png", ".jpg", ".txt", ".md"}
SUPPORTED_DOCUMENT_EXTENSION_LABEL = "PDF, PNG, JPG, TXT, or MD"


def clean_file_name(file_name: str) -> str:
    name = Path(file_name).name.strip()
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", name)
    return name or "uploaded-file"


def get_file_extension(file_name: str) -> str:
    return Path(file_name).suffix.lower()


def require_supported_document_file(file_name: str) -> None:
    if get_file_extension(file_name) not in SUPPORTED_DOCUMENT_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Please upload a {SUPPORTED_DOCUMENT_EXTENSION_LABEL} file.",
        )


def stored_file_path(path: Path) -> str:
    try:
        return str(path.relative_to(BACKEND_DIR))
    except ValueError:
        return str(path)


def resolve_stored_file_path(file_path: str) -> Path:
    path = Path(file_path)
    if path.is_absolute():
        return path
    return BACKEND_DIR / path


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


def clean_group_name(raw_name: str | None) -> str | None:
    if raw_name is None:
        return None
    name = " ".join(raw_name.strip().split())
    return name or None


def default_group_name(db: sqlite3.Connection, user_course: sqlite3.Row) -> str:
    row = db.execute(
        "SELECT COUNT(*) AS group_count FROM groups WHERE course_id = ?",
        (user_course["course_id"],),
    ).fetchone()
    next_count = int(row["group_count"]) + 1
    return (
        f"{user_course['course_code']} Lec {user_course['lecture_number']} "
        f"Group {next_count}"
    )


def get_group(db: sqlite3.Connection, group_id: int) -> sqlite3.Row:
    group = db.execute(
        """
        SELECT
            groups.id,
            groups.name,
            groups.course_id,
            courses.course_code,
            courses.course_quarter,
            courses.lecture_number,
            groups.created_by_user_id,
            groups.openai_vector_store_id,
            groups.created_at,
            groups.updated_at,
            COUNT(group_members.id) AS member_count
        FROM groups
        JOIN courses ON courses.id = groups.course_id
        LEFT JOIN group_members ON group_members.group_id = groups.id
        WHERE groups.id = ?
        GROUP BY groups.id
        """,
        (group_id,),
    ).fetchone()
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found.",
        )
    return group


def get_group_with_owner(db: sqlite3.Connection, group_id: int) -> sqlite3.Row:
    group = db.execute(
        """
        SELECT
            groups.id,
            groups.name,
            groups.course_id,
            courses.course_code,
            courses.course_quarter,
            courses.lecture_number,
            groups.created_by_user_id,
            groups.openai_vector_store_id,
            owner.full_name AS owner_name,
            groups.created_at,
            groups.updated_at,
            COUNT(group_members.id) AS member_count
        FROM groups
        JOIN courses ON courses.id = groups.course_id
        JOIN users owner ON owner.id = groups.created_by_user_id
        LEFT JOIN group_members ON group_members.group_id = groups.id
        WHERE groups.id = ?
        GROUP BY groups.id
        """,
        (group_id,),
    ).fetchone()
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found.",
        )
    return group


def require_group_member(
    db: sqlite3.Connection,
    group_id: int,
    user_id: int,
) -> sqlite3.Row:
    group = get_group(db, group_id)
    membership = db.execute(
        """
        SELECT 1
        FROM group_members
        WHERE group_id = ?
          AND user_id = ?
        """,
        (group_id, user_id),
    ).fetchone()
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Join this group before using its shared materials.",
        )
    return group


def ensure_group_vector_store(db: sqlite3.Connection, group: sqlite3.Row) -> str:
    vector_store_id = group["openai_vector_store_id"]
    if vector_store_id:
        return str(vector_store_id)

    vector_store_id = document_qa_service.create_vector_store(
        int(group["id"]),
        str(group["name"]),
    )
    db.execute(
        "UPDATE groups SET openai_vector_store_id = ? WHERE id = ?",
        (vector_store_id, group["id"]),
    )
    db.commit()
    return vector_store_id


def mark_document_index_failed(
    db: sqlite3.Connection,
    document_id: int,
    error: str,
) -> None:
    db.execute(
        """
        UPDATE documents
        SET index_status = 'failed',
            index_error = ?
        WHERE id = ?
        """,
        (error[:500], document_id),
    )
    db.commit()


def index_saved_document(
    db: sqlite3.Connection,
    group_id: int,
    document_id: int,
    file_name: str,
    saved_path: Path,
) -> None:
    try:
        group = get_group(db, group_id)
        vector_store_id = ensure_group_vector_store(db, group)
        indexed_document = document_qa_service.index_document(
            vector_store_id=vector_store_id,
            file_path=saved_path,
            group_id=group_id,
            document_id=document_id,
            file_name=file_name,
        )
    except DocumentQAUnavailable as exc:
        mark_document_index_failed(db, document_id, str(exc))
        return
    except DocumentQAError as exc:
        mark_document_index_failed(db, document_id, str(exc))
        return
    except Exception as exc:
        mark_document_index_failed(db, document_id, f"OpenAI indexing failed: {exc}")
        return

    ai_summary: str | None = None
    if indexed_document.status == "ready":
        try:
            ai_summary = document_qa_service.summarize_document(
                vector_store_id=vector_store_id,
                document_id=document_id,
                file_name=file_name,
            )
        except (DocumentQAUnavailable, DocumentQAError):
            ai_summary = None
        except Exception:
            ai_summary = None

    db.execute(
        """
        UPDATE documents
        SET openai_file_id = ?,
            openai_vector_store_file_id = ?,
            index_status = ?,
            index_error = NULL,
            ai_summary = ?
        WHERE id = ?
        """,
        (
            indexed_document.openai_file_id,
            indexed_document.openai_vector_store_file_id,
            indexed_document.status,
            ai_summary,
            document_id,
        ),
    )
    db.commit()


def ensure_document_in_group(
    db: sqlite3.Connection,
    group_id: int,
    document_id: int,
) -> sqlite3.Row:
    document = db.execute(
        """
        SELECT
            documents.id,
            documents.group_id,
            documents.uploader_id,
            documents.title,
            documents.file_name,
            documents.file_path,
            documents.document_type,
            documents.openai_file_id,
            documents.openai_vector_store_file_id,
            documents.index_status,
            documents.index_error,
            documents.ai_summary,
            documents.uploaded_at
        FROM documents
        WHERE documents.id = ?
          AND documents.group_id = ?
        """,
        (document_id, group_id),
    ).fetchone()
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )
    return document


def serialize_group(row: sqlite3.Row) -> GroupResponse:
    return GroupResponse(
        id=row["id"],
        name=row["name"],
        course_id=row["course_id"],
        course_code=row["course_code"],
        course_quarter=row["course_quarter"],
        lecture_number=row["lecture_number"],
        created_by_user_id=row["created_by_user_id"],
        member_count=row["member_count"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def serialize_group_member(
    row: sqlite3.Row,
    owner_user_id: int,
) -> GroupMemberResponse:
    return GroupMemberResponse(
        user_id=row["user_id"],
        full_name=row["full_name"],
        is_owner=int(row["user_id"]) == owner_user_id,
        study_goals=as_list(row["study_goals"]),
        pace_preference=row["pace_preference"],
        group_size_preference=row["group_size_preference"],
        joined_at=row["joined_at"],
    )


def serialize_group_detail(
    row: sqlite3.Row,
    member_courses: list[sqlite3.Row],
) -> GroupDetailResponse:
    average_pace_preference, average_pace_score = average_pace(member_courses)
    owner_user_id = int(row["created_by_user_id"])
    return GroupDetailResponse(
        id=row["id"],
        name=row["name"],
        course_id=row["course_id"],
        course_code=row["course_code"],
        course_quarter=row["course_quarter"],
        lecture_number=row["lecture_number"],
        created_by_user_id=row["created_by_user_id"],
        owner_name=row["owner_name"],
        member_count=row["member_count"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        top_study_goals=top_study_goals(member_courses),
        average_pace_preference=average_pace_preference,
        average_pace_score=average_pace_score,
        group_size_bucket=group_size_bucket(row["member_count"]),
        members=[
            serialize_group_member(member_course, owner_user_id)
            for member_course in member_courses
        ],
    )


def serialize_join_request(row: sqlite3.Row) -> JoinRequestResponse:
    return JoinRequestResponse(
        id=row["id"],
        group_id=row["group_id"],
        user_id=row["user_id"],
        user_name=row["user_name"],
        status=row["status"],
        created_at=row["created_at"],
        decided_at=row["decided_at"],
    )


def serialize_document(row: sqlite3.Row) -> DocumentResponse:
    return DocumentResponse(
        id=row["id"],
        group_id=row["group_id"],
        uploader_id=row["uploader_id"],
        uploader_name=row["uploader_name"],
        title=row["title"],
        file_name=row["file_name"],
        file_path=row["file_path"],
        document_type=row["document_type"],
        index_status=row["index_status"],
        index_error=row["index_error"],
        ai_summary=row["ai_summary"],
        uploaded_at=row["uploaded_at"],
    )


def serialize_comment(row: sqlite3.Row) -> CommentResponse:
    return CommentResponse(
        id=row["id"],
        document_id=row["document_id"],
        author_id=row["author_id"],
        author_name=row["author_name"],
        content=row["content"],
        created_at=row["created_at"],
    )


def serialize_activity(row: sqlite3.Row) -> GroupActivityResponse:
    return GroupActivityResponse(
        id=row["id"],
        activity_type=row["activity_type"],
        group_id=row["group_id"],
        group_name=row["group_name"],
        course_code=row["course_code"],
        document_id=row["document_id"],
        document_title=row["document_title"],
        actor_id=row["actor_id"],
        actor_name=row["actor_name"],
        occurred_at=row["occurred_at"],
    )


def serialize_pending_application(row: sqlite3.Row) -> PendingApplicationResponse:
    return PendingApplicationResponse(
        id=row["id"],
        group_id=row["group_id"],
        group_name=row["group_name"],
        course_code=row["course_code"],
        user_id=row["user_id"],
        user_name=row["user_name"],
        created_at=row["created_at"],
    )


def get_user_for_email(db: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    return db.execute(
        """
        SELECT
            id,
            full_name,
            email,
            notify_group_application_news
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()


def user_allows_group_application_email(user: sqlite3.Row | None) -> bool:
    return bool(user is not None and user["notify_group_application_news"])


@router.get("/join-requests/pending", response_model=list[PendingApplicationResponse])
def list_pending_applications(
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(get_current_user),
) -> list[PendingApplicationResponse]:
    rows = db.execute(
        """
        SELECT
            join_requests.id,
            join_requests.group_id,
            groups.name AS group_name,
            courses.course_code,
            join_requests.user_id,
            users.full_name AS user_name,
            join_requests.created_at
        FROM join_requests
        JOIN groups ON groups.id = join_requests.group_id
        JOIN courses ON courses.id = groups.course_id
        JOIN users ON users.id = join_requests.user_id
        WHERE groups.created_by_user_id = ?
          AND join_requests.status = 'pending'
        ORDER BY join_requests.created_at ASC
        """,
        (user["id"],),
    ).fetchall()
    return [serialize_pending_application(row) for row in rows]


@router.get("", response_model=list[GroupResponse])
def list_my_groups(
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(get_current_user),
) -> list[GroupResponse]:
    rows = db.execute(
        """
        SELECT
            groups.id,
            groups.name,
            groups.course_id,
            courses.course_code,
            courses.course_quarter,
            courses.lecture_number,
            groups.created_by_user_id,
            groups.created_at,
            groups.updated_at,
            COUNT(all_members.id) AS member_count
        FROM groups
        JOIN courses ON courses.id = groups.course_id
        JOIN group_members current_membership
          ON current_membership.group_id = groups.id
         AND current_membership.user_id = ?
        LEFT JOIN group_members all_members ON all_members.group_id = groups.id
        GROUP BY groups.id
        ORDER BY groups.updated_at DESC, groups.id DESC
        """,
        (user["id"],),
    ).fetchall()
    return [serialize_group(row) for row in rows]


@router.get("/activity", response_model=list[GroupActivityResponse])
def list_group_activity(
    limit: int = Query(default=8, ge=1, le=30),
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(get_current_user),
) -> list[GroupActivityResponse]:
    rows = db.execute(
        """
        SELECT *
        FROM (
            SELECT
                'document-' || documents.id AS id,
                'document_uploaded' AS activity_type,
                documents.group_id,
                groups.name AS group_name,
                courses.course_code,
                documents.id AS document_id,
                documents.title AS document_title,
                users.id AS actor_id,
                users.full_name AS actor_name,
                documents.uploaded_at AS occurred_at
            FROM documents
            JOIN groups ON groups.id = documents.group_id
            JOIN courses ON courses.id = groups.course_id
            JOIN users ON users.id = documents.uploader_id
            JOIN group_members viewer_membership
              ON viewer_membership.group_id = groups.id
             AND viewer_membership.user_id = ?
            JOIN group_members actor_membership
              ON actor_membership.group_id = groups.id
             AND actor_membership.user_id = documents.uploader_id

            UNION ALL

            SELECT
                'comment-' || comments.id AS id,
                'comment_added' AS activity_type,
                documents.group_id,
                groups.name AS group_name,
                courses.course_code,
                documents.id AS document_id,
                documents.title AS document_title,
                users.id AS actor_id,
                users.full_name AS actor_name,
                comments.created_at AS occurred_at
            FROM comments
            JOIN documents ON documents.id = comments.document_id
            JOIN groups ON groups.id = documents.group_id
            JOIN courses ON courses.id = groups.course_id
            JOIN users ON users.id = comments.author_id
            JOIN group_members viewer_membership
              ON viewer_membership.group_id = groups.id
             AND viewer_membership.user_id = ?
            JOIN group_members actor_membership
              ON actor_membership.group_id = groups.id
             AND actor_membership.user_id = comments.author_id
        )
        ORDER BY occurred_at DESC, id DESC
        LIMIT ?
        """,
        (user["id"], user["id"], limit),
    ).fetchall()
    return [serialize_activity(row) for row in rows]


@router.get("/{group_id}", response_model=GroupDetailResponse)
def get_group_detail(
    group_id: int,
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(get_current_user),
) -> GroupDetailResponse:
    group = require_group_member(db, group_id, int(user["id"]))
    group_with_owner = get_group_with_owner(db, int(group["id"]))
    member_courses = get_group_member_courses(
        db,
        int(group_with_owner["id"]),
        int(group_with_owner["course_id"]),
    )
    return serialize_group_detail(group_with_owner, member_courses)


@router.post("", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
def create_group(
    payload: GroupCreateRequest,
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(get_current_user),
) -> GroupResponse:
    user_course = get_owned_user_course(db, int(user["id"]), payload.user_course_id)
    group_name = clean_group_name(payload.name) or default_group_name(db, user_course)

    try:
        db.execute("BEGIN")
        cursor = db.execute(
            """
            INSERT INTO groups (name, course_id, created_by_user_id)
            VALUES (?, ?, ?)
            """,
            (group_name, user_course["course_id"], user["id"]),
        )
        group_id = int(cursor.lastrowid)
        db.execute(
            """
            INSERT INTO group_members (group_id, user_id)
            VALUES (?, ?)
            """,
            (group_id, user["id"]),
        )
        db.commit()
    except sqlite3.Error:
        db.rollback()
        raise

    return serialize_group(get_group(db, group_id))


def ensure_same_course_enrollment(
    db: sqlite3.Connection,
    user_id: int,
    course_id: int,
) -> sqlite3.Row:
    user_course = db.execute(
        """
        SELECT id
        FROM user_course
        WHERE user_id = ?
          AND course_id = ?
        """,
        (user_id, course_id),
    ).fetchone()
    if user_course is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only apply to groups for your enrolled course offerings.",
        )
    return user_course


def require_group_owner(
    db: sqlite3.Connection,
    group_id: int,
    user_id: int,
) -> sqlite3.Row:
    group = get_group(db, group_id)
    if int(group["created_by_user_id"]) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the group owner can manage join requests.",
        )
    return group


@router.post(
    "/{group_id}/join-requests",
    response_model=JoinRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def apply_to_group(
    group_id: int,
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(get_current_user),
) -> JoinRequestResponse:
    group = get_group(db, group_id)
    user_id = int(user["id"])
    ensure_same_course_enrollment(db, user_id, int(group["course_id"]))

    if db.execute(
        """
        SELECT 1
        FROM group_members
        WHERE group_id = ?
          AND user_id = ?
        """,
        (group_id, user_id),
    ).fetchone():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You are already in this group.",
        )

    active_request = db.execute(
        """
        SELECT join_requests.id
        FROM join_requests
        JOIN groups ON groups.id = join_requests.group_id
        WHERE join_requests.user_id = ?
          AND join_requests.status = 'pending'
          AND groups.course_id = ?
        """,
        (user_id, int(group["course_id"])),
    ).fetchone()
    if active_request is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a pending group application for this course.",
        )

    try:
        cursor = db.execute(
            """
            INSERT INTO join_requests (group_id, user_id)
            VALUES (?, ?)
            """,
            (group_id, user_id),
        )
        db.commit()
    except sqlite3.Error:
        db.rollback()
        raise

    row = db.execute(
        """
        SELECT
            join_requests.id,
            join_requests.group_id,
            join_requests.user_id,
            users.full_name AS user_name,
            join_requests.status,
            join_requests.created_at,
            join_requests.decided_at
        FROM join_requests
        JOIN users ON users.id = join_requests.user_id
        WHERE join_requests.id = ?
        """,
        (cursor.lastrowid,),
    ).fetchone()
    reviewer = get_user_for_email(db, int(group["created_by_user_id"]))
    if user_allows_group_application_email(reviewer):
        send_group_application_reviewer_email(
            reviewer["email"],
            reviewer["full_name"],
            user["full_name"],
            group["name"],
        )
    return serialize_join_request(row)


@router.post("/{group_id}/join", response_model=JoinRequestResponse)
def join_group(
    group_id: int,
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(get_current_user),
) -> JoinRequestResponse:
    return apply_to_group(group_id, db, user)


@router.delete("/{group_id}/membership", response_model=GroupResponse)
def leave_group(
    group_id: int,
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(get_current_user),
) -> GroupResponse:
    membership = db.execute(
        """
        SELECT 1
        FROM group_members
        WHERE group_id = ?
          AND user_id = ?
        """,
        (group_id, user["id"]),
    ).fetchone()
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You are not a member of this group.",
        )

    group = get_group(db, group_id)
    db.execute(
        """
        DELETE FROM group_members
        WHERE group_id = ?
          AND user_id = ?
        """,
        (group_id, user["id"]),
    )

    remaining = db.execute(
        "SELECT COUNT(*) FROM group_members WHERE group_id = ?",
        (group_id,),
    ).fetchone()[0]

    if remaining == 0:
        db.execute("DELETE FROM groups WHERE id = ?", (group_id,))
        db.commit()
        return serialize_group(group)

    if int(group["created_by_user_id"]) == int(user["id"]):
        next_owner = db.execute(
            """
            SELECT user_id
            FROM group_members
            WHERE group_id = ?
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (group_id,),
        ).fetchone()
        db.execute(
            "UPDATE groups SET created_by_user_id = ? WHERE id = ?",
            (next_owner["user_id"], group_id),
        )

    db.execute(
        "UPDATE groups SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (group_id,),
    )
    db.commit()
    return serialize_group(get_group(db, int(group["id"])))


@router.get("/{group_id}/join-requests", response_model=list[JoinRequestResponse])
def list_join_requests(
    group_id: int,
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(get_current_user),
) -> list[JoinRequestResponse]:
    require_group_owner(db, group_id, int(user["id"]))
    rows = db.execute(
        """
        SELECT
            join_requests.id,
            join_requests.group_id,
            join_requests.user_id,
            users.full_name AS user_name,
            join_requests.status,
            join_requests.created_at,
            join_requests.decided_at
        FROM join_requests
        JOIN users ON users.id = join_requests.user_id
        WHERE join_requests.group_id = ?
          AND join_requests.status = 'pending'
        ORDER BY join_requests.created_at ASC
        """,
        (group_id,),
    ).fetchall()
    return [serialize_join_request(row) for row in rows]


def get_pending_join_request(
    db: sqlite3.Connection,
    group_id: int,
    request_id: int,
) -> sqlite3.Row:
    join_request = db.execute(
        """
        SELECT
            join_requests.id,
            join_requests.group_id,
            join_requests.user_id,
            users.full_name AS user_name,
            join_requests.status,
            join_requests.created_at,
            join_requests.decided_at
        FROM join_requests
        JOIN users ON users.id = join_requests.user_id
        WHERE join_requests.id = ?
          AND join_requests.group_id = ?
        """,
        (request_id, group_id),
    ).fetchone()
    if join_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Join request not found.",
        )
    if join_request["status"] != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Join request is no longer pending.",
        )
    return join_request


@router.delete(
    "/{group_id}/join-requests/{request_id}",
    response_model=JoinRequestResponse,
)
def withdraw_join_request(
    group_id: int,
    request_id: int,
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(get_current_user),
) -> JoinRequestResponse:
    join_request = get_pending_join_request(db, group_id, request_id)
    if int(join_request["user_id"]) != int(user["id"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the applicant can withdraw this join request.",
        )

    db.execute(
        """
        UPDATE join_requests
        SET status = 'withdrawn',
            decided_by_user_id = ?,
            decided_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (user["id"], request_id),
    )
    db.commit()
    row = db.execute(
        """
        SELECT
            join_requests.id,
            join_requests.group_id,
            join_requests.user_id,
            users.full_name AS user_name,
            join_requests.status,
            join_requests.created_at,
            join_requests.decided_at
        FROM join_requests
        JOIN users ON users.id = join_requests.user_id
        WHERE join_requests.id = ?
        """,
        (join_request["id"],),
    ).fetchone()
    return serialize_join_request(row)


@router.post(
    "/{group_id}/join-requests/{request_id}/approve",
    response_model=JoinRequestResponse,
)
def approve_join_request(
    group_id: int,
    request_id: int,
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(get_current_user),
) -> JoinRequestResponse:
    group = require_group_owner(db, group_id, int(user["id"]))
    join_request = get_pending_join_request(db, group_id, request_id)
    ensure_same_course_enrollment(db, int(join_request["user_id"]), int(group["course_id"]))

    try:
        db.execute("BEGIN")
        db.execute(
            """
            INSERT OR IGNORE INTO group_members (group_id, user_id)
            VALUES (?, ?)
            """,
            (group_id, join_request["user_id"]),
        )
        db.execute(
            """
            UPDATE join_requests
            SET status = 'approved',
                decided_by_user_id = ?,
                decided_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (user["id"], request_id),
        )
        db.execute(
            """
            UPDATE join_requests
            SET status = 'withdrawn',
                decided_by_user_id = ?,
                decided_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
              AND status = 'pending'
              AND id != ?
            """,
            (join_request["user_id"], join_request["user_id"], request_id),
        )
        db.execute(
            "UPDATE groups SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (group_id,),
        )
        db.commit()
    except sqlite3.Error:
        db.rollback()
        raise

    row = db.execute(
        """
        SELECT
            join_requests.id,
            join_requests.group_id,
            join_requests.user_id,
            users.full_name AS user_name,
            join_requests.status,
            join_requests.created_at,
            join_requests.decided_at
        FROM join_requests
        JOIN users ON users.id = join_requests.user_id
        WHERE join_requests.id = ?
        """,
        (request_id,),
    ).fetchone()
    applicant = get_user_for_email(db, int(join_request["user_id"]))
    if user_allows_group_application_email(applicant):
        send_group_application_decision_email(
            applicant["email"],
            applicant["full_name"],
            group["name"],
            "approved",
        )
    return serialize_join_request(row)


@router.post(
    "/{group_id}/join-requests/{request_id}/reject",
    response_model=JoinRequestResponse,
)
def reject_join_request(
    group_id: int,
    request_id: int,
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(get_current_user),
) -> JoinRequestResponse:
    require_group_owner(db, group_id, int(user["id"]))
    join_request = get_pending_join_request(db, group_id, request_id)
    db.execute(
        """
        UPDATE join_requests
        SET status = 'rejected',
            decided_by_user_id = ?,
            decided_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (user["id"], request_id),
    )
    db.commit()
    row = db.execute(
        """
        SELECT
            join_requests.id,
            join_requests.group_id,
            join_requests.user_id,
            users.full_name AS user_name,
            join_requests.status,
            join_requests.created_at,
            join_requests.decided_at
        FROM join_requests
        JOIN users ON users.id = join_requests.user_id
        WHERE join_requests.id = ?
        """,
        (join_request["id"],),
    ).fetchone()
    group = get_group(db, group_id)
    applicant = get_user_for_email(db, int(join_request["user_id"]))
    if user_allows_group_application_email(applicant):
        send_group_application_decision_email(
            applicant["email"],
            applicant["full_name"],
            group["name"],
            "rejected",
        )
    return serialize_join_request(row)


@router.get("/{group_id}/documents", response_model=GroupDocumentsResponse)
def list_documents(
    group_id: int,
    search: str = "",
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(get_current_user),
) -> GroupDocumentsResponse:
    require_group_member(db, group_id, int(user["id"]))
    search_term = f"%{search.strip()}%"

    rows = db.execute(
        """
        SELECT
            documents.id,
            documents.group_id,
            documents.uploader_id,
            users.full_name AS uploader_name,
            documents.title,
            documents.file_name,
            documents.file_path,
            documents.document_type,
            documents.openai_file_id,
            documents.openai_vector_store_file_id,
            documents.index_status,
            documents.index_error,
            documents.ai_summary,
            documents.uploaded_at
        FROM documents
        JOIN users ON users.id = documents.uploader_id
        WHERE documents.group_id = ?
          AND (
            ? = '%%'
            OR documents.title LIKE ?
            OR documents.file_name LIKE ?
            OR documents.document_type LIKE ?
          )
        ORDER BY documents.uploaded_at DESC
        """,
        (group_id, search_term, search_term, search_term, search_term),
    ).fetchall()

    return GroupDocumentsResponse(
        group_id=group_id,
        documents=[serialize_document(row) for row in rows],
    )


@router.post(
    "/{group_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(
    group_id: int,
    title: str = Form(..., min_length=1, max_length=160),
    document_type: str = Form(..., min_length=1, max_length=40),
    file: UploadFile = File(...),
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(get_current_user),
) -> DocumentResponse:
    require_group_member(db, group_id, int(user["id"]))
    clean_name = clean_file_name(file.filename or "uploaded-file")
    require_supported_document_file(clean_name)
    group_upload_dir = UPLOAD_DIR / f"group-{group_id}"
    group_upload_dir.mkdir(parents=True, exist_ok=True)

    cursor = db.execute(
        """
        INSERT INTO documents (
            group_id,
            uploader_id,
            title,
            file_name,
            file_path,
            document_type,
            index_status
        )
        VALUES (?, ?, ?, ?, ?, ?, 'indexing')
        """,
        (
            group_id,
            user["id"],
            " ".join(title.strip().split()),
            clean_name,
            "",
            document_type.strip().lower(),
        ),
    )
    document_id = int(cursor.lastrowid)
    saved_name = f"{document_id}-{clean_name}"
    saved_path = group_upload_dir / saved_name

    with saved_path.open("wb") as output:
        shutil.copyfileobj(file.file, output)

    db.execute(
        "UPDATE documents SET file_path = ? WHERE id = ?",
        (stored_file_path(saved_path), document_id),
    )
    db.execute(
        "UPDATE groups SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (group_id,),
    )
    db.commit()
    index_saved_document(db, group_id, document_id, clean_name, saved_path)

    row = db.execute(
        """
        SELECT
            documents.id,
            documents.group_id,
            documents.uploader_id,
            users.full_name AS uploader_name,
            documents.title,
            documents.file_name,
            documents.file_path,
            documents.document_type,
            documents.openai_file_id,
            documents.openai_vector_store_file_id,
            documents.index_status,
            documents.index_error,
            documents.ai_summary,
            documents.uploaded_at
        FROM documents
        JOIN users ON users.id = documents.uploader_id
        WHERE documents.id = ?
        """,
        (document_id,),
    ).fetchone()

    return serialize_document(row)


@router.post("/{group_id}/qa", response_model=DocumentQAResponse)
def ask_group_documents(
    group_id: int,
    payload: DocumentQARequest,
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(get_current_user),
) -> DocumentQAResponse:
    group = require_group_member(db, group_id, int(user["id"]))
    question = " ".join(payload.question.strip().split())
    if not question:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Question is required.",
        )

    ready_documents = db.execute(
        """
        SELECT id
        FROM documents
        WHERE group_id = ?
          AND index_status = 'ready'
        """,
        (group_id,),
    ).fetchall()
    if not ready_documents or not group["openai_vector_store_id"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No indexed documents are ready for Q&A yet.",
        )

    try:
        answer = document_qa_service.answer_question(
            vector_store_id=str(group["openai_vector_store_id"]),
            question=question,
        )
    except DocumentQAUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except DocumentQAError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenAI document Q&A failed: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenAI document Q&A failed: {exc}",
        ) from exc

    response_text = answer.answer or (
        "The shared documents do not include enough information to answer that."
    )
    return DocumentQAResponse(
        answer=response_text,
        sources=[
            DocumentQASource(
                document_id=source.document_id,
                file_name=source.file_name,
                snippet=source.snippet[:800],
            )
            for source in answer.sources
        ],
    )


@router.get("/{group_id}/documents/{document_id}/file")
def download_document(
    group_id: int,
    document_id: int,
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(get_current_user),
) -> FileResponse:
    require_group_member(db, group_id, int(user["id"]))
    document = ensure_document_in_group(db, group_id, document_id)

    file_path = resolve_stored_file_path(document["file_path"])
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Uploaded file not found.",
        )

    media_type, _ = guess_type(document["file_name"])
    return FileResponse(
        file_path,
        filename=document["file_name"],
        media_type=media_type or "application/octet-stream",
        content_disposition_type="inline",
    )


@router.get(
    "/{group_id}/documents/{document_id}/comments",
    response_model=list[CommentResponse],
)
def list_comments(
    group_id: int,
    document_id: int,
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(get_current_user),
) -> list[CommentResponse]:
    require_group_member(db, group_id, int(user["id"]))
    ensure_document_in_group(db, group_id, document_id)
    rows = db.execute(
        """
        SELECT
            comments.id,
            comments.document_id,
            comments.author_id,
            users.full_name AS author_name,
            comments.content,
            comments.created_at
        FROM comments
        JOIN users ON users.id = comments.author_id
        WHERE comments.document_id = ?
        ORDER BY comments.created_at ASC
        """,
        (document_id,),
    ).fetchall()

    return [serialize_comment(row) for row in rows]


@router.post(
    "/{group_id}/documents/{document_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_comment(
    group_id: int,
    document_id: int,
    payload: CommentCreateRequest,
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(get_current_user),
) -> CommentResponse:
    require_group_member(db, group_id, int(user["id"]))
    ensure_document_in_group(db, group_id, document_id)

    content = " ".join(payload.content.strip().split())
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Comment content is required.",
        )

    cursor = db.execute(
        """
        INSERT INTO comments (document_id, author_id, content)
        VALUES (?, ?, ?)
        """,
        (document_id, user["id"], content),
    )
    db.execute(
        "UPDATE groups SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (group_id,),
    )
    db.commit()

    row = db.execute(
        """
        SELECT
            comments.id,
            comments.document_id,
            comments.author_id,
            users.full_name AS author_name,
            comments.content,
            comments.created_at
        FROM comments
        JOIN users ON users.id = comments.author_id
        WHERE comments.id = ?
        """,
        (cursor.lastrowid,),
    ).fetchone()

    return serialize_comment(row)
