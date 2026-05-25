from __future__ import annotations

from app import config
from app.oracle_db import (
    _prepare_oracle_statement,
    _rewrite_datetime_now,
    _rewrite_limit_clause,
)


def test_database_backend_defaults_to_sqlite(monkeypatch):
    monkeypatch.delenv("STUDYSYNC_DB_BACKEND", raising=False)
    monkeypatch.delenv("STUDYSYNC_DB_DEBUG", raising=False)
    monkeypatch.delenv("STUDYSYNC_USE_ORACLE_ADB", raising=False)
    monkeypatch.delenv("STUDYSYNC_RUNTIME_ENV", raising=False)
    monkeypatch.delenv("STUDYSYNC_OCI_HOST", raising=False)
    monkeypatch.delenv("OCI_DEPLOYED", raising=False)
    monkeypatch.setattr(config, "ORACLE_CLOUD_MARKERS", ())

    assert config.get_database_backend() == "sqlite"


def test_database_backend_uses_oracle_for_oci_host(monkeypatch):
    monkeypatch.setenv("STUDYSYNC_RUNTIME_ENV", "oci")
    monkeypatch.delenv("STUDYSYNC_DB_BACKEND", raising=False)

    assert config.get_database_backend() == "oracle"


def test_database_backend_uses_oracle_for_desktop_adb_debug(monkeypatch):
    monkeypatch.setenv("STUDYSYNC_DB_DEBUG", "atp")
    monkeypatch.delenv("STUDYSYNC_DB_BACKEND", raising=False)
    monkeypatch.setattr(config, "ORACLE_CLOUD_MARKERS", ())

    assert config.get_database_backend() == "oracle"


def test_database_backend_explicit_sqlite_overrides_oci(monkeypatch):
    monkeypatch.setenv("STUDYSYNC_DB_BACKEND", "sqlite")
    monkeypatch.setenv("STUDYSYNC_RUNTIME_ENV", "oci")

    assert config.get_database_backend() == "sqlite"


def test_oracle_statement_converter_uses_named_binds():
    sql, params = _prepare_oracle_statement(
        "SELECT '?' AS literal, id FROM users WHERE email = ? AND id = ?",
        ("bruin@g.ucla.edu", 12),
    )

    assert sql == "SELECT '?' AS literal, id FROM users WHERE email = :p0 AND id = :p1"
    assert params == {"p0": "bruin@g.ucla.edu", "p1": 12}


def test_oracle_limit_rewrite_consumes_limit_parameter():
    sql, params = _rewrite_limit_clause(
        "SELECT id FROM groups WHERE course_id = ? LIMIT ?",
        (7, 8),
    )

    assert sql == "SELECT id FROM groups WHERE course_id = ? FETCH FIRST 8 ROWS ONLY"
    assert params == (7,)


def test_oracle_datetime_rewrite_consumes_datetime_parameter_only():
    sql, params = _rewrite_datetime_now(
        "INSERT INTO email_verification_tokens (user_id, token_hash, expires_at) "
        "VALUES (?, ?, datetime('now', ?))",
        (7, "hash", "+24 hours"),
    )

    assert "TO_CHAR(SYSTIMESTAMP + INTERVAL '24' HOUR" in sql
    assert params == (7, "hash")
