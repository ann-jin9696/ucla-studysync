from __future__ import annotations

import sqlite3

from app import db as db_module
from app.db import init_db


def test_group_tables_are_created_without_workspaces(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDYSYNC_DB_PATH", str(tmp_path / "test.sqlite3"))

    init_db()

    connection = sqlite3.connect(tmp_path / "test.sqlite3")
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }

    assert {
        "courses",
        "user_course",
        "groups",
        "group_members",
        "join_requests",
        "documents",
        "comments",
    }.issubset(tables)
    assert "workspaces" not in tables

    join_request_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(join_requests)")
    }
    assert "expires_at" not in join_request_columns

    seeded_codes = {
        row[0]
        for row in connection.execute(
            "SELECT DISTINCT course_code FROM courses"
        ).fetchall()
    }
    assert {"CS35L", "MATH151A", "PIC10A"}.issubset(seeded_codes)


def test_documents_and_comments_reference_group_records(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDYSYNC_DB_PATH", str(tmp_path / "test.sqlite3"))

    init_db()

    connection = sqlite3.connect(tmp_path / "test.sqlite3")
    connection.execute("PRAGMA foreign_keys = ON")
    user_id = connection.execute(
        """
        INSERT INTO users (full_name, email, password_hash)
        VALUES (?, ?, ?)
        """,
        ("Group Tester", "group@g.ucla.edu", "hash"),
    ).lastrowid
    course_id = connection.execute(
        """
        INSERT INTO courses (course_code, course_quarter, lecture_number)
        VALUES (?, ?, ?)
        """,
        ("ENGR96", "Spring 2026", 1),
    ).lastrowid
    group_id = connection.execute(
        """
        INSERT INTO groups (name, course_id, created_by_user_id)
        VALUES (?, ?, ?)
        """,
        ("Review Group", course_id, user_id),
    ).lastrowid
    connection.execute(
        """
        INSERT INTO group_members (group_id, user_id)
        VALUES (?, ?)
        """,
        (group_id, user_id),
    )
    document_id = connection.execute(
        """
        INSERT INTO documents (
            group_id,
            uploader_id,
            title,
            file_name,
            file_path,
            document_type
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            group_id,
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


def test_default_mock_seed_data_is_uniform_and_cross_table_valid(
    tmp_path,
    monkeypatch,
):
    db_path = tmp_path / "seed.sqlite3"
    monkeypatch.setenv("STUDYSYNC_DB_PATH", str(db_path))
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", db_path)

    db_module.init_db()

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    expected_group_count = len(db_module.MOCK_COURSE_OFFERINGS)
    expected_seed_user_count = len(db_module.MOCK_GROUP_USERS)
    expected_document_count = (
        expected_group_count * len(db_module.MOCK_GROUP_DOCUMENTS)
    )
    expected_comment_count = expected_group_count * len(db_module.MOCK_GROUP_COMMENTS)

    seed_groups = connection.execute(
        """
        SELECT groups.id, groups.name, courses.course_code
        FROM groups
        JOIN courses ON courses.id = groups.course_id
        WHERE groups.name = courses.course_code || ' Study Hub'
        ORDER BY courses.course_code
        """
    ).fetchall()
    seed_users = connection.execute(
        """
        SELECT id, full_name
        FROM users
        WHERE email LIKE '%.seed@g.ucla.edu'
        """
    ).fetchall()
    seed_documents = connection.execute(
        """
        SELECT documents.id, documents.file_path
        FROM documents
        JOIN groups ON groups.id = documents.group_id
        JOIN courses ON courses.id = groups.course_id
        WHERE groups.name = courses.course_code || ' Study Hub'
        """
    ).fetchall()
    seed_comment_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM comments
        JOIN documents ON documents.id = comments.document_id
        JOIN groups ON groups.id = documents.group_id
        JOIN courses ON courses.id = groups.course_id
        WHERE groups.name = courses.course_code || ' Study Hub'
        """
    ).fetchone()[0]

    assert len(seed_groups) == expected_group_count
    assert len(seed_users) == expected_seed_user_count
    assert {row["full_name"] for row in seed_users} == {
        full_name for full_name, _email, *_preferences in db_module.MOCK_GROUP_USERS
    }
    assert len(seed_documents) == expected_document_count
    assert seed_comment_count == expected_comment_count
    assert (
        connection.execute(
            """
            SELECT COUNT(*)
            FROM groups
            WHERE name LIKE 'Workspace Switch%'
            """
        ).fetchone()[0]
        == 0
    )

    for group in seed_groups:
        member_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM group_members
            JOIN users ON users.id = group_members.user_id
            WHERE group_members.group_id = ?
              AND users.email LIKE '%.seed@g.ucla.edu'
            """,
            (group["id"],),
        ).fetchone()[0]
        assert member_count == expected_seed_user_count

    for document in seed_documents:
        assert db_module.resolve_seed_file_path(document["file_path"]).exists()

    upload_actor_mismatches = connection.execute(
        """
        SELECT COUNT(*)
        FROM documents
        LEFT JOIN group_members
          ON group_members.group_id = documents.group_id
         AND group_members.user_id = documents.uploader_id
        WHERE group_members.id IS NULL
        """
    ).fetchone()[0]
    comment_actor_mismatches = connection.execute(
        """
        SELECT COUNT(*)
        FROM comments
        JOIN documents ON documents.id = comments.document_id
        LEFT JOIN group_members
          ON group_members.group_id = documents.group_id
         AND group_members.user_id = comments.author_id
        WHERE group_members.id IS NULL
        """
    ).fetchone()[0]
    assert upload_actor_mismatches == 0
    assert comment_actor_mismatches == 0

    db_module.validate_seeded_group_content(
        connection,
        {
            row["email"]: row["id"]
            for row in connection.execute(
                "SELECT id, email FROM users WHERE email LIKE '%.seed@g.ucla.edu'"
            ).fetchall()
        },
    )


def test_legacy_demo_names_are_normalized_on_startup(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy-demo.sqlite3"
    monkeypatch.setenv("STUDYSYNC_DB_PATH", str(db_path))
    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", db_path)

    db_module.init_db()

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    legacy_demo_rows = (
        ("Alice", "alice.seed@g.ucla.edu"),
        ("Iris Seed", "iris.seed.demo@g.ucla.edu"),
        ("Jordan", "jordan.seed@g.ucla.edu"),
        ("Maya Seed", "maya.seed.demo@g.ucla.edu"),
        ("Neel", "neel.seed@g.ucla.edu"),
        ("Noah Seed", "noah.seed.demo@g.ucla.edu"),
    )
    for full_name, email in legacy_demo_rows:
        connection.execute(
            """
            INSERT INTO users (full_name, email, password_hash)
            VALUES (?, ?, ?)
            ON CONFLICT(email) DO UPDATE SET full_name = excluded.full_name
            """,
            (full_name, email, "hash"),
        )
    legacy_group = connection.execute(
        """
        SELECT groups.id
        FROM groups
        JOIN courses ON courses.id = groups.course_id
        WHERE courses.course_code = 'PIC10A'
          AND groups.name = 'PIC10A Study Hub'
        """
    ).fetchone()
    connection.execute(
        "UPDATE groups SET name = 'Workspace Switch 09388' WHERE id = ?",
        (legacy_group["id"],),
    )
    connection.commit()
    connection.close()

    db_module.init_db()

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    renamed_users = {
        row["email"]: row["full_name"]
        for row in connection.execute(
            """
            SELECT email, full_name
            FROM users
            WHERE email IN (
                'alice.seed@g.ucla.edu',
                'iris.seed.demo@g.ucla.edu',
                'jordan.seed@g.ucla.edu',
                'maya.seed.demo@g.ucla.edu',
                'neel.seed@g.ucla.edu',
                'noah.seed.demo@g.ucla.edu'
            )
            """
        ).fetchall()
    }
    renamed_group = connection.execute(
        """
        SELECT 1
        FROM groups
        JOIN courses ON courses.id = groups.course_id
        WHERE groups.name = 'PIC10A Review Workspace'
          AND courses.course_code = 'PIC10A'
        """
    ).fetchone()
    legacy_user_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM users
        WHERE full_name IN (
            'Alice',
            'Iris Seed',
            'Jordan',
            'Maya Seed',
            'Neel',
            'Noah Seed'
        )
        """
    ).fetchone()[0]
    legacy_group_count = connection.execute(
        "SELECT COUNT(*) FROM groups WHERE name = 'Workspace Switch 09388'"
    ).fetchone()[0]

    assert renamed_users == {
        "alice.seed@g.ucla.edu": "Ann",
        "iris.seed.demo@g.ucla.edu": "Taylor",
        "jordan.seed@g.ucla.edu": "Victor",
        "maya.seed.demo@g.ucla.edu": "Fahd",
        "neel.seed@g.ucla.edu": "Audrey",
        "noah.seed.demo@g.ucla.edu": "Tobias",
    }
    assert renamed_group is not None
    assert legacy_user_count == 0
    assert legacy_group_count == 0
