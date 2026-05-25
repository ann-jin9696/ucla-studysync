from __future__ import annotations

import sqlite3
from collections.abc import Generator
from pathlib import Path

from .config import BASE_DIR, DEFAULT_DB_PATH, get_database_path


DEFAULT_LEGACY_QUARTER = "Spring 2026"
DEFAULT_LEGACY_LECTURE = 1
LEGACY_DEMO_USER_RENAMES = (
    ("alice.seed@g.ucla.edu", "Alice", "Ann"),
    ("iris.seed.demo@g.ucla.edu", "Iris Seed", "Taylor"),
    ("jordan.seed@g.ucla.edu", "Jordan", "Victor"),
    ("maya.seed.demo@g.ucla.edu", "Maya Seed", "Fahd"),
    ("neel.seed@g.ucla.edu", "Neel", "Audrey"),
    ("noah.seed.demo@g.ucla.edu", "Noah Seed", "Tobias"),
)
LEGACY_WORKSPACE_GROUP_PREFIX = "Workspace Switch"
MOCK_COURSE_OFFERINGS = (
    ("CS35L", "Spring 2026", 1),
    ("MATH151A", "Spring 2026", 1),
    ("PIC10A", "Spring 2026", 1),
    ("PHYSICS1A", "Spring 2026", 1),
    ("STATS100A", "Spring 2026", 1),
    ("CHEM20A", "Spring 2026", 1),
)
MOCK_USER_PASSWORD_HASH = (
    "$2b$12$KZPJPAmZ6AJqh3BTSnWbgOLa/a6DvvK.ONLsUyEXkceJpU3xG1tMi"
)
MOCK_GROUP_OWNER_EMAIL = "alice.seed@g.ucla.edu"
MOCK_GROUP_USERS = (
    (
        "Ann",
        "alice.seed@g.ucla.edu",
        '["project_work", "notes_sharing"]',
        "moderate",
        4,
    ),
    (
        "Audrey",
        "neel.seed@g.ucla.edu",
        '["homework_help", "concept_review"]',
        "relaxed",
        6,
    ),
    (
        "Victor",
        "jordan.seed@g.ucla.edu",
        '["exam_prep", "homework_help"]',
        "intensive",
        8,
    ),
)
MOCK_GROUP_DOCUMENTS = (
    {
        "title": "Midterm Review Notes",
        "file_name": "midterm-review-notes.md",
        "document_type": "notes",
        "uploader_email": "alice.seed@g.ucla.edu",
        "uploaded_at": "datetime('now', '-1 hour')",
        "content": "# Midterm Review Notes\n\nKey formulas, practice prompts, and review checkpoints for the group.\n",
    },
    {
        "title": "Week 5 Worksheet",
        "file_name": "week-5-worksheet.txt",
        "document_type": "worksheet",
        "uploader_email": "neel.seed@g.ucla.edu",
        "uploaded_at": "datetime('now', '-35 minutes')",
        "content": "Week 5 worksheet\n\n1. Compare your setup.\n2. Mark confusing steps.\n3. Bring one question to discussion.\n",
    },
)
MOCK_GROUP_COMMENTS = (
    {
        "document_title": "Midterm Review Notes",
        "author_email": "jordan.seed@g.ucla.edu",
        "content": "I added a few exam-style questions to review together.",
        "created_at": "datetime('now', '-20 minutes')",
    },
    {
        "document_title": "Week 5 Worksheet",
        "author_email": "alice.seed@g.ucla.edu",
        "content": "Let's use this as our warm-up before the next group session.",
        "created_at": "datetime('now', '-10 minutes')",
    },
)


def validate_mock_seed_configuration() -> None:
    errors: list[str] = []
    course_keys = set()
    for course_code, course_quarter, lecture_number in MOCK_COURSE_OFFERINGS:
        course_key = (course_code, course_quarter, lecture_number)
        if course_key in course_keys:
            errors.append(f"duplicate mock course offering {course_key}")
        course_keys.add(course_key)
        if lecture_number < 1:
            errors.append(f"mock lecture number must be positive for {course_code}")

    seed_emails = [email for _name, email, *_preferences in MOCK_GROUP_USERS]
    seed_email_set = set(seed_emails)
    if len(seed_emails) != len(seed_email_set):
        errors.append("mock seed user emails must be unique")
    if MOCK_GROUP_OWNER_EMAIL not in seed_email_set:
        errors.append("mock group owner email must reference a seed user")

    document_titles = [document["title"] for document in MOCK_GROUP_DOCUMENTS]
    document_title_set = set(document_titles)
    if len(document_titles) != len(document_title_set):
        errors.append("mock document titles must be unique")
    for document in MOCK_GROUP_DOCUMENTS:
        if document["uploader_email"] not in seed_email_set:
            errors.append(f"mock document uploader missing: {document['uploader_email']}")

    for comment in MOCK_GROUP_COMMENTS:
        if comment["author_email"] not in seed_email_set:
            errors.append(f"mock comment author missing: {comment['author_email']}")
        if comment["document_title"] not in document_title_set:
            errors.append(
                f"mock comment document missing: {comment['document_title']}"
            )

    if errors:
        raise RuntimeError("Mock seed configuration is invalid: " + "; ".join(errors))


def get_connection() -> sqlite3.Connection:
    db_path = get_database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    if not table_exists(connection, table_name):
        return set()
    return {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }


def create_users_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            email_verified INTEGER NOT NULL DEFAULT 0,
            email_verified_at TEXT,
            notify_group_application_news INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def ensure_user_email_columns(connection: sqlite3.Connection) -> None:
    user_columns = table_columns(connection, "users")
    if "email_verified" not in user_columns:
        connection.execute(
            "ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 0"
        )
        connection.execute("UPDATE users SET email_verified = 1")
        user_columns.add("email_verified")
    if "email_verified_at" not in user_columns:
        connection.execute("ALTER TABLE users ADD COLUMN email_verified_at TEXT")
        connection.execute(
            """
            UPDATE users
            SET email_verified_at = created_at
            WHERE email_verified = 1
              AND email_verified_at IS NULL
            """
        )
        user_columns.add("email_verified_at")
    if "notify_group_application_news" not in user_columns:
        connection.execute(
            """
            ALTER TABLE users
            ADD COLUMN notify_group_application_news INTEGER NOT NULL DEFAULT 1
            """
        )


def create_email_token_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS email_verification_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TEXT NOT NULL,
            used_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TEXT NOT NULL,
            used_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )


def collect_legacy_user_courses(
    connection: sqlite3.Connection,
) -> list[dict[str, object]]:
    legacy_courses: dict[tuple[int, str, str, int], dict[str, object]] = {}
    profile_preferences: dict[int, dict[str, object]] = {}

    if table_exists(connection, "profiles"):
        profile_columns = table_columns(connection, "profiles")
        selected_columns = ["user_id"]
        for column in ("study_goals", "pace_preference", "group_size_preference"):
            selected_columns.append(column if column in profile_columns else f"NULL AS {column}")
        for row in connection.execute(
            f"SELECT {', '.join(selected_columns)} FROM profiles"
        ).fetchall():
            profile_preferences[int(row["user_id"])] = {
                "study_goals": row["study_goals"] or "[]",
                "pace_preference": row["pace_preference"],
                "group_size_preference": row["group_size_preference"],
            }

    if table_exists(connection, "user_course") and table_exists(connection, "courses"):
        user_course_columns = table_columns(connection, "user_course")
        course_columns = table_columns(connection, "courses")
        course_quarter_expr = (
            "courses.course_quarter"
            if "course_quarter" in course_columns
            else f"'{DEFAULT_LEGACY_QUARTER}'"
        )
        lecture_number_expr = (
            "courses.lecture_number"
            if "lecture_number" in course_columns
            else str(DEFAULT_LEGACY_LECTURE)
        )
        study_goals_expr = (
            "user_course.study_goals"
            if "study_goals" in user_course_columns
            else "NULL"
        )
        pace_expr = (
            "user_course.pace_preference"
            if "pace_preference" in user_course_columns
            else "NULL"
        )
        group_size_expr = (
            "user_course.group_size_preference"
            if "group_size_preference" in user_course_columns
            else "NULL"
        )

        rows = connection.execute(
            f"""
            SELECT
                user_course.user_id,
                courses.course_code,
                {course_quarter_expr} AS course_quarter,
                {lecture_number_expr} AS lecture_number,
                {study_goals_expr} AS study_goals,
                {pace_expr} AS pace_preference,
                {group_size_expr} AS group_size_preference
            FROM user_course
            JOIN courses ON courses.id = user_course.course_id
            """
        ).fetchall()
        for row in rows:
            user_id = int(row["user_id"])
            preferences = profile_preferences.get(user_id, {})
            study_goals = row["study_goals"] or preferences.get("study_goals") or "[]"
            pace_preference = row["pace_preference"] or preferences.get("pace_preference")
            group_size_preference = (
                row["group_size_preference"]
                if row["group_size_preference"] is not None
                else preferences.get("group_size_preference")
            )
            key = (
                user_id,
                str(row["course_code"]),
                str(row["course_quarter"] or DEFAULT_LEGACY_QUARTER),
                int(row["lecture_number"] or DEFAULT_LEGACY_LECTURE),
            )
            legacy_courses[key] = {
                "user_id": user_id,
                "course_code": key[1],
                "course_quarter": key[2],
                "lecture_number": key[3],
                "study_goals": study_goals,
                "pace_preference": pace_preference,
                "group_size_preference": group_size_preference,
            }

    if table_exists(connection, "profile_courses") and table_exists(connection, "profiles"):
        rows = connection.execute(
            """
            SELECT
                profiles.user_id,
                profile_courses.course_code,
                profiles.study_goals,
                profiles.pace_preference,
                profiles.group_size_preference
            FROM profile_courses
            JOIN profiles ON profiles.id = profile_courses.profile_id
            """
        ).fetchall()
        for row in rows:
            key = (
                int(row["user_id"]),
                str(row["course_code"]),
                DEFAULT_LEGACY_QUARTER,
                DEFAULT_LEGACY_LECTURE,
            )
            legacy_courses.setdefault(
                key,
                {
                    "user_id": key[0],
                    "course_code": key[1],
                    "course_quarter": key[2],
                    "lecture_number": key[3],
                    "study_goals": row["study_goals"] or "[]",
                    "pace_preference": row["pace_preference"],
                    "group_size_preference": row["group_size_preference"],
                },
            )

    return list(legacy_courses.values())


def drop_tables(connection: sqlite3.Connection, table_names: tuple[str, ...]) -> None:
    for table_name in table_names:
        connection.execute(f"DROP TABLE IF EXISTS {table_name}")


def coerce_group_size_preference(raw_value: object) -> int | None:
    if raw_value in (None, "", "no_preference"):
        return None
    if isinstance(raw_value, int):
        return raw_value if raw_value >= 1 else None
    if isinstance(raw_value, str):
        if raw_value.isdigit():
            parsed_value = int(raw_value)
            return parsed_value if parsed_value >= 1 else None
        legacy_sizes = {
            "pair": 2,
            "small_group": 4,
            "medium_group": 8,
            "large_group": 11,
        }
        return legacy_sizes.get(raw_value)
    return None


def needs_course_schema_rebuild(connection: sqlite3.Connection) -> bool:
    course_columns = table_columns(connection, "courses")
    user_course_columns = table_columns(connection, "user_course")
    if not course_columns and not user_course_columns:
        return False
    return not {
        "course_code",
        "course_quarter",
        "lecture_number",
    }.issubset(course_columns) or not {
        "study_goals",
        "pace_preference",
        "group_size_preference",
    }.issubset(user_course_columns)


def needs_document_schema_rebuild(connection: sqlite3.Connection) -> bool:
    document_columns = table_columns(connection, "documents")
    return "workspace_id" in document_columns or table_exists(connection, "workspaces")


def needs_join_request_schema_rebuild(connection: sqlite3.Connection) -> bool:
    join_request_columns = table_columns(connection, "join_requests")
    return "expires_at" in join_request_columns


def ensure_group_columns(connection: sqlite3.Connection) -> None:
    group_columns = table_columns(connection, "groups")
    if group_columns and "name" not in group_columns:
        connection.execute("ALTER TABLE groups ADD COLUMN name TEXT")
    if group_columns and "openai_vector_store_id" not in group_columns:
        connection.execute("ALTER TABLE groups ADD COLUMN openai_vector_store_id TEXT")
    connection.execute(
        """
        UPDATE groups
        SET name = 'Group ' || id
        WHERE name IS NULL OR TRIM(name) = ''
        """
    )


def ensure_document_columns(connection: sqlite3.Connection) -> None:
    document_columns = table_columns(connection, "documents")
    if not document_columns:
        return
    if "openai_file_id" not in document_columns:
        connection.execute("ALTER TABLE documents ADD COLUMN openai_file_id TEXT")
    if "openai_vector_store_file_id" not in document_columns:
        connection.execute(
            "ALTER TABLE documents ADD COLUMN openai_vector_store_file_id TEXT"
        )
    if "index_status" not in document_columns:
        connection.execute(
            "ALTER TABLE documents ADD COLUMN index_status TEXT NOT NULL DEFAULT 'failed'"
        )
    if "index_error" not in document_columns:
        connection.execute("ALTER TABLE documents ADD COLUMN index_error TEXT")
    if "ai_summary" not in document_columns:
        connection.execute("ALTER TABLE documents ADD COLUMN ai_summary TEXT")


def create_course_group_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_code TEXT NOT NULL,
            course_quarter TEXT NOT NULL,
            lecture_number INTEGER NOT NULL CHECK (lecture_number >= 1),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (course_code, course_quarter, lecture_number)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS user_course (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            study_goals TEXT NOT NULL DEFAULT '[]',
            pace_preference TEXT,
            group_size_preference INTEGER CHECK (
                group_size_preference IS NULL OR group_size_preference >= 1
            ),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
            UNIQUE (user_id, course_id)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            course_id INTEGER NOT NULL,
            created_by_user_id INTEGER NOT NULL,
            openai_vector_store_id TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
            FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    ensure_group_columns(connection)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS group_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE (group_id, user_id)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS join_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending' CHECK (
                status IN ('pending', 'approved', 'rejected', 'withdrawn')
            ),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            decided_by_user_id INTEGER,
            decided_at TEXT,
            FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (decided_by_user_id) REFERENCES users(id) ON DELETE SET NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            uploader_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            document_type TEXT NOT NULL,
            openai_file_id TEXT,
            openai_vector_store_file_id TEXT,
            index_status TEXT NOT NULL DEFAULT 'failed',
            index_error TEXT,
            ai_summary TEXT,
            uploaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
            FOREIGN KEY (uploader_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    ensure_document_columns(connection)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            author_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
            FOREIGN KEY (author_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )


def create_indexes(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_courses_offering ON courses "
        "(course_code, course_quarter, lecture_number)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_user_course_user_id ON user_course (user_id)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_user_course_course_id ON user_course (course_id)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_groups_course_id ON groups (course_id)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_group_members_user_id ON group_members (user_id)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_group_members_group_id ON group_members (group_id)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_join_requests_user_status "
        "ON join_requests (user_id, status)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_join_requests_group_status "
        "ON join_requests (group_id, status)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_documents_group_id ON documents (group_id)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_comments_document_id ON comments (document_id)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_email_verification_tokens_hash "
        "ON email_verification_tokens (token_hash)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_hash "
        "ON password_reset_tokens (token_hash)"
    )


def seed_mock_courses(connection: sqlite3.Connection) -> None:
    connection.executemany(
        """
        INSERT OR IGNORE INTO courses (
            course_code,
            course_quarter,
            lecture_number
        )
        VALUES (?, ?, ?)
        """,
        MOCK_COURSE_OFFERINGS,
    )


def get_course_id(
    connection: sqlite3.Connection,
    course_code: str,
    course_quarter: str,
    lecture_number: int,
) -> int:
    row = connection.execute(
        """
        SELECT id
        FROM courses
        WHERE course_code = ?
          AND course_quarter = ?
          AND lecture_number = ?
        """,
        (course_code, course_quarter, lecture_number),
    ).fetchone()
    return int(row["id"])


def merge_user_rows(
    connection: sqlite3.Connection,
    source_user_id: int,
    target_user_id: int,
) -> None:
    connection.execute(
        """
        INSERT OR IGNORE INTO user_course (
            user_id,
            course_id,
            study_goals,
            pace_preference,
            group_size_preference,
            created_at,
            updated_at
        )
        SELECT
            ?,
            course_id,
            study_goals,
            pace_preference,
            group_size_preference,
            created_at,
            updated_at
        FROM user_course
        WHERE user_id = ?
        """,
        (target_user_id, source_user_id),
    )
    connection.execute("DELETE FROM user_course WHERE user_id = ?", (source_user_id,))
    connection.execute(
        """
        INSERT OR IGNORE INTO group_members (group_id, user_id, created_at)
        SELECT group_id, ?, created_at
        FROM group_members
        WHERE user_id = ?
        """,
        (target_user_id, source_user_id),
    )
    connection.execute("DELETE FROM group_members WHERE user_id = ?", (source_user_id,))
    connection.execute(
        "UPDATE groups SET created_by_user_id = ? WHERE created_by_user_id = ?",
        (target_user_id, source_user_id),
    )
    connection.execute(
        "UPDATE documents SET uploader_id = ? WHERE uploader_id = ?",
        (target_user_id, source_user_id),
    )
    connection.execute(
        "UPDATE comments SET author_id = ? WHERE author_id = ?",
        (target_user_id, source_user_id),
    )
    connection.execute(
        "UPDATE join_requests SET user_id = ? WHERE user_id = ?",
        (target_user_id, source_user_id),
    )
    connection.execute(
        "UPDATE join_requests SET decided_by_user_id = ? WHERE decided_by_user_id = ?",
        (target_user_id, source_user_id),
    )
    connection.execute("DELETE FROM users WHERE id = ?", (source_user_id,))


def normalize_legacy_demo_data(connection: sqlite3.Connection) -> None:
    for email, old_name, new_name in LEGACY_DEMO_USER_RENAMES:
        connection.execute(
            """
            UPDATE users
            SET full_name = ?
            WHERE email = ?
               OR (full_name = ? AND email LIKE '%.seed%@g.ucla.edu')
            """,
            (new_name, email, old_name),
        )

    legacy_group_rows = connection.execute(
        """
        SELECT groups.id, courses.course_code, courses.lecture_number
        FROM groups
        JOIN courses ON courses.id = groups.course_id
        WHERE groups.name LIKE ?
        """,
        (f"{LEGACY_WORKSPACE_GROUP_PREFIX}%",),
    ).fetchall()
    for row in legacy_group_rows:
        course_code = str(row["course_code"])
        lecture_number = int(row["lecture_number"])
        group_name = f"{course_code} Review Workspace"
        if lecture_number > 1:
            group_name = f"{course_code} Lecture {lecture_number} Review Workspace"
        connection.execute(
            "UPDATE groups SET name = ? WHERE id = ?",
            (group_name, int(row["id"])),
        )


def get_seed_user_ids(connection: sqlite3.Connection) -> dict[str, int]:
    user_ids: dict[str, int] = {}
    for full_name, email, *_preferences in MOCK_GROUP_USERS:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO users (full_name, email, password_hash)
            VALUES (?, ?, ?)
            """,
            (full_name, email, MOCK_USER_PASSWORD_HASH),
        )
        if cursor.lastrowid:
            user_ids[email] = int(cursor.lastrowid)
        else:
            row = connection.execute(
                "SELECT id FROM users WHERE email = ?",
                (email,),
            ).fetchone()
            user_ids[email] = int(row["id"])
        connection.execute(
            """
            UPDATE users
            SET full_name = ?,
                email_verified = 1,
                email_verified_at = COALESCE(email_verified_at, created_at)
            WHERE id = ?
            """,
            (full_name, user_ids[email]),
        )
    return user_ids


def seed_user_course_preferences(
    connection: sqlite3.Connection,
    seed_user_ids: dict[str, int],
) -> None:
    course_rows = connection.execute("SELECT id FROM courses").fetchall()
    for course_row in course_rows:
        for _name, email, study_goals, pace, group_size in MOCK_GROUP_USERS:
            connection.execute(
                """
                INSERT OR IGNORE INTO user_course (
                    user_id,
                    course_id,
                    study_goals,
                    pace_preference,
                    group_size_preference
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    seed_user_ids[email],
                    course_row["id"],
                    study_goals,
                    pace,
                    group_size,
                ),
            )


def seed_file(file_path: Path, content: str) -> str:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    try:
        return str(file_path.relative_to(BASE_DIR))
    except ValueError:
        return str(file_path)


def resolve_seed_file_path(stored_path: str) -> Path:
    path = Path(stored_path)
    if path.is_absolute():
        return path
    return BASE_DIR / path


def seed_document_file_path(group_id: int, document: dict[str, str]) -> Path:
    return (
        DEFAULT_DB_PATH.parent
        / "uploads"
        / "seed"
        / f"group-{group_id}"
        / document["file_name"]
    )


def get_or_create_seed_group(
    connection: sqlite3.Connection,
    course_id: int,
    course_code: str,
    owner_user_id: int,
) -> int:
    group_name = f"{course_code} Study Hub"
    row = connection.execute(
        """
        SELECT id
        FROM groups
        WHERE course_id = ?
          AND name = ?
        """,
        (course_id, group_name),
    ).fetchone()
    if row is not None:
        return int(row["id"])

    cursor = connection.execute(
        """
        INSERT INTO groups (name, course_id, created_by_user_id)
        VALUES (?, ?, ?)
        """,
        (group_name, course_id, owner_user_id),
    )
    return int(cursor.lastrowid)


def seed_group_members(
    connection: sqlite3.Connection,
    group_id: int,
    course_id: int,
    seed_user_ids: dict[str, int],
) -> None:
    for user_id in seed_user_ids.values():
        connection.execute(
            """
            INSERT OR IGNORE INTO group_members (group_id, user_id)
            VALUES (?, ?)
            """,
            (group_id, user_id),
        )

    enrolled_user_rows = connection.execute(
        "SELECT user_id FROM user_course WHERE course_id = ?",
        (course_id,),
    ).fetchall()
    for row in enrolled_user_rows:
        connection.execute(
            """
            INSERT OR IGNORE INTO group_members (group_id, user_id)
            VALUES (?, ?)
            """,
            (group_id, row["user_id"]),
        )


def get_or_create_seed_document(
    connection: sqlite3.Connection,
    group_id: int,
    document: dict[str, str],
    seed_user_ids: dict[str, int],
) -> int:
    row = connection.execute(
        """
        SELECT id, file_path
        FROM documents
        WHERE group_id = ?
          AND title = ?
        """,
        (group_id, document["title"]),
    ).fetchone()
    if row is not None:
        stored_path = row["file_path"]
        if stored_path:
            file_path = resolve_seed_file_path(stored_path)
        else:
            file_path = seed_document_file_path(group_id, document)
            stored_path = seed_file(file_path, document["content"])
            connection.execute(
                "UPDATE documents SET file_path = ? WHERE id = ?",
                (stored_path, row["id"]),
            )
        if not file_path.exists():
            seed_file(file_path, document["content"])
        return int(row["id"])

    file_path = seed_document_file_path(group_id, document)
    stored_path = seed_file(file_path, document["content"])
    uploaded_at = connection.execute(
        f"SELECT {document['uploaded_at']} AS uploaded_at"
    ).fetchone()["uploaded_at"]
    cursor = connection.execute(
        """
        INSERT INTO documents (
            group_id,
            uploader_id,
            title,
            file_name,
            file_path,
            document_type,
            uploaded_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            group_id,
            seed_user_ids[document["uploader_email"]],
            document["title"],
            document["file_name"],
            stored_path,
            document["document_type"],
            uploaded_at,
        ),
    )
    return int(cursor.lastrowid)


def seed_group_comments(
    connection: sqlite3.Connection,
    documents_by_title: dict[str, int],
    seed_user_ids: dict[str, int],
) -> None:
    for comment in MOCK_GROUP_COMMENTS:
        document_id = documents_by_title[comment["document_title"]]
        author_id = seed_user_ids[comment["author_email"]]
        existing_comment = connection.execute(
            """
            SELECT id
            FROM comments
            WHERE document_id = ?
              AND author_id = ?
              AND content = ?
            """,
            (document_id, author_id, comment["content"]),
        ).fetchone()
        if existing_comment is not None:
            continue

        created_at = connection.execute(
            f"SELECT {comment['created_at']} AS created_at"
        ).fetchone()["created_at"]
        connection.execute(
            """
            INSERT INTO comments (document_id, author_id, content, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (document_id, author_id, comment["content"], created_at),
        )


def seed_mock_group_content(connection: sqlite3.Connection) -> None:
    if get_database_path() != DEFAULT_DB_PATH:
        return

    validate_mock_seed_configuration()
    seed_user_ids = get_seed_user_ids(connection)
    seed_user_course_preferences(connection, seed_user_ids)

    course_rows = connection.execute(
        """
        SELECT id, course_code
        FROM courses
        ORDER BY course_code
        """
    ).fetchall()
    for course in course_rows:
        group_id = get_or_create_seed_group(
            connection,
            int(course["id"]),
            str(course["course_code"]),
            seed_user_ids["alice.seed@g.ucla.edu"],
        )
        seed_group_members(connection, group_id, int(course["id"]), seed_user_ids)
        documents_by_title = {
            document["title"]: get_or_create_seed_document(
                connection,
                group_id,
                document,
                seed_user_ids,
            )
            for document in MOCK_GROUP_DOCUMENTS
        }
        seed_group_comments(connection, documents_by_title, seed_user_ids)
    validate_seeded_group_content(connection, seed_user_ids)


def count_query(connection: sqlite3.Connection, query: str) -> int:
    row = connection.execute(query).fetchone()
    return int(row[0])


def validate_seeded_group_content(
    connection: sqlite3.Connection,
    seed_user_ids: dict[str, int],
) -> None:
    errors: list[str] = []

    orphan_documents = count_query(
        connection,
        """
        SELECT COUNT(*)
        FROM documents
        LEFT JOIN groups ON groups.id = documents.group_id
        LEFT JOIN users ON users.id = documents.uploader_id
        WHERE groups.id IS NULL OR users.id IS NULL
        """,
    )
    if orphan_documents:
        errors.append(f"{orphan_documents} document rows have missing group or uploader")

    orphan_comments = count_query(
        connection,
        """
        SELECT COUNT(*)
        FROM comments
        LEFT JOIN documents ON documents.id = comments.document_id
        LEFT JOIN users ON users.id = comments.author_id
        WHERE documents.id IS NULL OR users.id IS NULL
        """,
    )
    if orphan_comments:
        errors.append(f"{orphan_comments} comment rows have missing document or author")

    for course_code, course_quarter, lecture_number in MOCK_COURSE_OFFERINGS:
        group_name = f"{course_code} Study Hub"
        group = connection.execute(
            """
            SELECT groups.id
            FROM groups
            JOIN courses ON courses.id = groups.course_id
            WHERE groups.name = ?
              AND courses.course_code = ?
              AND courses.course_quarter = ?
              AND courses.lecture_number = ?
            """,
            (group_name, course_code, course_quarter, lecture_number),
        ).fetchone()
        if group is None:
            errors.append(f"seed group missing: {group_name}")
            continue

        group_id = int(group["id"])
        for email, user_id in seed_user_ids.items():
            membership = connection.execute(
                """
                SELECT 1
                FROM group_members
                WHERE group_id = ?
                  AND user_id = ?
                """,
                (group_id, user_id),
            ).fetchone()
            if membership is None:
                errors.append(f"seed user {email} is not a member of {group_name}")

        documents_by_title: dict[str, sqlite3.Row] = {}
        for document in MOCK_GROUP_DOCUMENTS:
            row = connection.execute(
                """
                SELECT id, uploader_id, file_path
                FROM documents
                WHERE group_id = ?
                  AND title = ?
                """,
                (group_id, document["title"]),
            ).fetchone()
            if row is None:
                errors.append(f"seed document missing in {group_name}: {document['title']}")
                continue
            documents_by_title[document["title"]] = row
            expected_uploader_id = seed_user_ids[document["uploader_email"]]
            if int(row["uploader_id"]) != expected_uploader_id:
                errors.append(
                    f"seed document uploader mismatch in {group_name}: {document['title']}"
                )
            if not resolve_seed_file_path(row["file_path"]).exists():
                errors.append(
                    f"seed document file missing in {group_name}: {document['title']}"
                )

        for comment in MOCK_GROUP_COMMENTS:
            document = documents_by_title.get(comment["document_title"])
            if document is None:
                continue
            row = connection.execute(
                """
                SELECT author_id
                FROM comments
                WHERE document_id = ?
                  AND content = ?
                """,
                (document["id"], comment["content"]),
            ).fetchone()
            if row is None:
                errors.append(
                    f"seed comment missing in {group_name}: {comment['document_title']}"
                )
                continue
            expected_author_id = seed_user_ids[comment["author_email"]]
            if int(row["author_id"]) != expected_author_id:
                errors.append(
                    f"seed comment author mismatch in {group_name}: "
                    f"{comment['document_title']}"
                )

    if errors:
        raise RuntimeError("Mock seed data validation failed: " + "; ".join(errors))


def restore_legacy_user_courses(
    connection: sqlite3.Connection,
    legacy_courses: list[dict[str, object]],
) -> None:
    for legacy_course in legacy_courses:
        user_exists = connection.execute(
            "SELECT 1 FROM users WHERE id = ?",
            (legacy_course["user_id"],),
        ).fetchone()
        if user_exists is None:
            continue

        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO courses (
                course_code,
                course_quarter,
                lecture_number
            )
            VALUES (?, ?, ?)
            """,
            (
                legacy_course["course_code"],
                legacy_course["course_quarter"],
                legacy_course["lecture_number"],
            ),
        )
        if cursor.lastrowid:
            course_id = int(cursor.lastrowid)
        else:
            course_row = connection.execute(
                """
                SELECT id
                FROM courses
                WHERE course_code = ?
                  AND course_quarter = ?
                  AND lecture_number = ?
                """,
                (
                    legacy_course["course_code"],
                    legacy_course["course_quarter"],
                    legacy_course["lecture_number"],
                ),
            ).fetchone()
            course_id = int(course_row["id"])

        connection.execute(
            """
            INSERT OR IGNORE INTO user_course (
                user_id,
                course_id,
                study_goals,
                pace_preference,
                group_size_preference
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                legacy_course["user_id"],
                course_id,
                legacy_course["study_goals"],
                legacy_course["pace_preference"],
                coerce_group_size_preference(legacy_course["group_size_preference"]),
            ),
        )


def init_db() -> None:
    with get_connection() as connection:
        create_users_table(connection)
        ensure_user_email_columns(connection)
        create_email_token_tables(connection)

        rebuild_courses = needs_course_schema_rebuild(connection)
        rebuild_documents = needs_document_schema_rebuild(connection)
        rebuild_join_requests = needs_join_request_schema_rebuild(connection)
        legacy_courses = collect_legacy_user_courses(connection) if rebuild_courses else []

        if rebuild_courses or rebuild_documents:
            drop_tables(
                connection,
                (
                    "comments",
                    "documents",
                    "join_requests",
                    "group_members",
                    "groups",
                    "workspaces",
                ),
            )
        elif rebuild_join_requests:
            drop_tables(connection, ("join_requests",))

        if rebuild_courses:
            drop_tables(
                connection,
                (
                    "user_course",
                    "courses",
                    "profile_courses",
                    "profiles",
                ),
            )
        else:
            drop_tables(connection, ("profile_courses", "profiles", "workspaces"))

        create_course_group_tables(connection)
        create_indexes(connection)
        seed_mock_courses(connection)
        restore_legacy_user_courses(connection, legacy_courses)
        normalize_legacy_demo_data(connection)
        seed_mock_group_content(connection)


def get_db() -> Generator[sqlite3.Connection, None, None]:
    connection = get_connection()
    try:
        yield connection
    finally:
        connection.close()
