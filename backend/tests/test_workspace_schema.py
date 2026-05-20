from __future__ import annotations

import sqlite3

from app.db import init_db


def test_workspace_tables_are_created(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDYSYNC_DB_PATH", str(tmp_path / "test.sqlite3"))

    init_db()

    connection = sqlite3.connect(tmp_path / "test.sqlite3")
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }

    assert {"workspaces", "documents", "comments"}.issubset(tables)


def test_documents_and_comments_reference_existing_records(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDYSYNC_DB_PATH", str(tmp_path / "test.sqlite3"))

    init_db()

    connection = sqlite3.connect(tmp_path / "test.sqlite3")
    connection.execute("PRAGMA foreign_keys = ON")
    user_id = connection.execute(
        """
        INSERT INTO users (full_name, email, password_hash)
        VALUES (?, ?, ?)
        """,
        ("Workspace Tester", "workspace@g.ucla.edu", "hash"),
    ).lastrowid
    workspace_id = connection.execute(
        "INSERT INTO workspaces (group_id) VALUES (?)",
        (101,),
    ).lastrowid
    document_id = connection.execute(
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
            workspace_id,
            user_id,
            "Week 1 Notes",
            "week-1-notes.pdf",
            "uploads/week-1-notes.pdf",
            "pdf",
        ),
    ).lastrowid
    connection.execute(
        """
        INSERT INTO comments (document_id, author_id, content)
        VALUES (?, ?, ?)
        """,
        (document_id, user_id, "This section is useful for review."),
    )

    saved_comment = connection.execute(
        "SELECT content FROM comments WHERE document_id = ?",
        (document_id,),
    ).fetchone()

    assert saved_comment[0] == "This section is useful for review."
