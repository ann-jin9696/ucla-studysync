from __future__ import annotations

import re
import shutil
import sqlite3
from mimetypes import guess_type
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from .db import get_db
from .schemas import (
    CommentCreateRequest,
    CommentResponse,
    DocumentResponse,
    WorkspaceDocumentsResponse,
)
from .security import get_current_user


router = APIRouter(prefix="/api/workspace", tags=["workspace"])

DEFAULT_GROUP_ID = 1
BACKEND_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BACKEND_DIR / "data" / "uploads"


def ensure_workspace(db: sqlite3.Connection) -> sqlite3.Row:
    workspace = db.execute(
        "SELECT id, group_id, created_at FROM workspaces WHERE group_id = ?",
        (DEFAULT_GROUP_ID,),
    ).fetchone()
    if workspace is not None:
        return workspace

    cursor = db.execute(
        "INSERT INTO workspaces (group_id) VALUES (?)",
        (DEFAULT_GROUP_ID,),
    )
    db.commit()
    return db.execute(
        "SELECT id, group_id, created_at FROM workspaces WHERE id = ?",
        (cursor.lastrowid,),
    ).fetchone()


def clean_file_name(file_name: str) -> str:
    name = Path(file_name).name.strip()
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", name)
    return name or "uploaded-file"


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


def serialize_document(row: sqlite3.Row) -> DocumentResponse:
    return DocumentResponse(
        id=row["id"],
        workspace_id=row["workspace_id"],
        uploader_id=row["uploader_id"],
        uploader_name=row["uploader_name"],
        title=row["title"],
        file_name=row["file_name"],
        file_path=row["file_path"],
        document_type=row["document_type"],
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


@router.get("/documents", response_model=WorkspaceDocumentsResponse)
def list_documents(
    search: str = "",
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(get_current_user),
) -> WorkspaceDocumentsResponse:
    workspace = ensure_workspace(db)
    search_term = f"%{search.strip()}%"

    rows = db.execute(
        """
        SELECT
            documents.id,
            documents.workspace_id,
            documents.uploader_id,
            users.full_name AS uploader_name,
            documents.title,
            documents.file_name,
            documents.file_path,
            documents.document_type,
            documents.uploaded_at
        FROM documents
        JOIN users ON users.id = documents.uploader_id
        WHERE documents.workspace_id = ?
          AND (
            ? = '%%'
            OR documents.title LIKE ?
            OR documents.file_name LIKE ?
            OR documents.document_type LIKE ?
          )
        ORDER BY documents.uploaded_at DESC
        """,
        (workspace["id"], search_term, search_term, search_term, search_term),
    ).fetchall()

    return WorkspaceDocumentsResponse(
        workspace_id=workspace["id"],
        group_id=workspace["group_id"],
        documents=[serialize_document(row) for row in rows],
    )


@router.post(
    "/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(
    title: str = Form(..., min_length=1, max_length=160),
    document_type: str = Form(..., min_length=1, max_length=40),
    file: UploadFile = File(...),
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(get_current_user),
) -> DocumentResponse:
    workspace = ensure_workspace(db)
    clean_name = clean_file_name(file.filename or "uploaded-file")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    cursor = db.execute(
        """
        INSERT INTO documents (
            workspace_id,
            uploader_id,
            title,
            file_name,
            file_path,
            document_type
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            workspace["id"],
            user["id"],
            " ".join(title.strip().split()),
            clean_name,
            "",
            document_type.strip().lower(),
        ),
    )
    document_id = cursor.lastrowid
    saved_name = f"{document_id}-{clean_name}"
    saved_path = UPLOAD_DIR / saved_name

    with saved_path.open("wb") as output:
        shutil.copyfileobj(file.file, output)

    db.execute(
        "UPDATE documents SET file_path = ? WHERE id = ?",
        (stored_file_path(saved_path), document_id),
    )
    db.commit()

    row = db.execute(
        """
        SELECT
            documents.id,
            documents.workspace_id,
            documents.uploader_id,
            users.full_name AS uploader_name,
            documents.title,
            documents.file_name,
            documents.file_path,
            documents.document_type,
            documents.uploaded_at
        FROM documents
        JOIN users ON users.id = documents.uploader_id
        WHERE documents.id = ?
        """,
        (document_id,),
    ).fetchone()

    return serialize_document(row)


@router.get("/documents/{document_id}/file")
def download_document(
    document_id: int,
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(get_current_user),
) -> FileResponse:
    document = db.execute(
        "SELECT file_name, file_path FROM documents WHERE id = ?",
        (document_id,),
    ).fetchone()
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

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


@router.get("/documents/{document_id}/comments", response_model=list[CommentResponse])
def list_comments(
    document_id: int,
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(get_current_user),
) -> list[CommentResponse]:
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
    "/documents/{document_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_comment(
    document_id: int,
    payload: CommentCreateRequest,
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(get_current_user),
) -> CommentResponse:
    document = db.execute(
        "SELECT id FROM documents WHERE id = ?",
        (document_id,),
    ).fetchone()
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

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
