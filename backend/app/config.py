from __future__ import annotations

import os
from pathlib import Path
from typing import Literal


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "studysync.sqlite3"
ORACLE_CLOUD_MARKERS = (
    Path("/sys/class/dmi/id/product_name"),
    Path("/sys/class/dmi/id/sys_vendor"),
    Path("/sys/class/dmi/id/chassis_asset_tag"),
)

SESSION_COOKIE_NAME = "studysync_session"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 7
DEFAULT_OPENAI_DOC_QA_MODEL = "gpt-5.4-mini"
EMAIL_VERIFICATION_MAX_AGE_HOURS = 24
PASSWORD_RESET_MAX_AGE_HOURS = 2
DatabaseBackend = Literal["sqlite", "oracle"]


def get_database_path() -> Path:
    return Path(os.environ.get("STUDYSYNC_DB_PATH", DEFAULT_DB_PATH))


def truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def is_oci_host() -> bool:
    explicit_env = os.environ.get("STUDYSYNC_RUNTIME_ENV", "").strip().lower()
    if explicit_env in {"oci", "oracle", "production"}:
        return True
    if truthy_env("STUDYSYNC_OCI_HOST") or truthy_env("OCI_DEPLOYED"):
        return True
    for marker_path in ORACLE_CLOUD_MARKERS:
        try:
            marker = marker_path.read_text(encoding="utf-8").strip().lower()
        except OSError:
            continue
        if "oracle" in marker or "oci" in marker:
            return True
    return False


def get_database_backend() -> DatabaseBackend:
    configured_backend = os.environ.get("STUDYSYNC_DB_BACKEND", "auto").strip().lower()
    if configured_backend in {"sqlite", "oracle"}:
        return configured_backend  # type: ignore[return-value]
    if configured_backend != "auto":
        raise RuntimeError(
            "STUDYSYNC_DB_BACKEND must be one of: auto, sqlite, oracle."
        )

    debug_mode = os.environ.get("STUDYSYNC_DB_DEBUG", "").strip().lower()
    if debug_mode in {"adb", "atp", "oracle"} or truthy_env("STUDYSYNC_USE_ORACLE_ADB"):
        return "oracle"
    if is_oci_host():
        return "oracle"
    return "sqlite"


def get_oracle_user() -> str:
    return os.environ.get("STUDYSYNC_ORACLE_USER", "ADMIN")


def get_oracle_password() -> str:
    password = os.environ.get("STUDYSYNC_ORACLE_PASSWORD", "").strip()
    if not password:
        raise RuntimeError("STUDYSYNC_ORACLE_PASSWORD is required for Oracle ADB.")
    return password


def get_oracle_dsn() -> str:
    dsn = os.environ.get("STUDYSYNC_ORACLE_DSN", "").strip()
    if not dsn:
        raise RuntimeError(
            "STUDYSYNC_ORACLE_DSN is required for Oracle ADB, for example "
            "the ATP wallet service name ending in _tp."
        )
    return dsn


def get_oracle_wallet_dir() -> str | None:
    wallet_dir = os.environ.get("STUDYSYNC_ORACLE_WALLET_DIR", "").strip()
    return wallet_dir or None


def get_oracle_wallet_password() -> str | None:
    wallet_password = os.environ.get("STUDYSYNC_ORACLE_WALLET_PASSWORD", "").strip()
    return wallet_password or None


def get_secret_key() -> str:
    return os.environ.get("STUDYSYNC_SECRET_KEY", "dev-studysync-change-me")


def get_openai_api_key() -> str | None:
    return os.environ.get("OPENAI_API_KEY")


def get_openai_doc_qa_model() -> str:
    return os.environ.get("OPENAI_DOC_QA_MODEL", DEFAULT_OPENAI_DOC_QA_MODEL)


def get_openai_doc_qa_enabled() -> bool:
    raw_value = os.environ.get("OPENAI_DOC_QA_ENABLED")
    if raw_value is None:
        return get_openai_api_key() is not None
    return raw_value.strip().lower() not in {"0", "false", "no", "off"}


def get_frontend_url() -> str:
    return os.environ.get("STUDYSYNC_FRONTEND_URL", "http://localhost:5173").rstrip("/")


def get_resend_api_key() -> str | None:
    return os.environ.get("RESEND_API_KEY")


def get_resend_from_email() -> str:
    return os.environ.get(
        "RESEND_FROM_EMAIL",
        "StudySync <noreply@studysync.bruinapps.com>",
    )
