from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "studysync.sqlite3"

SESSION_COOKIE_NAME = "studysync_session"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 7
EMAIL_VERIFICATION_MAX_AGE_HOURS = 24
PASSWORD_RESET_MAX_AGE_HOURS = 2


def get_database_path() -> Path:
    return Path(os.environ.get("STUDYSYNC_DB_PATH", DEFAULT_DB_PATH))


def get_secret_key() -> str:
    return os.environ.get("STUDYSYNC_SECRET_KEY", "dev-studysync-change-me")


def get_frontend_url() -> str:
    return os.environ.get("STUDYSYNC_FRONTEND_URL", "http://localhost:5173").rstrip("/")


def get_resend_api_key() -> str | None:
    return os.environ.get("RESEND_API_KEY")


def get_resend_from_email() -> str:
    return os.environ.get(
        "RESEND_FROM_EMAIL",
        "StudySync <noreply@studysync.bruinapps.com>",
    )
