from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import SESSION_COOKIE_NAME
from app.main import app


def make_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("STUDYSYNC_DB_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("STUDYSYNC_SECRET_KEY", "test-secret-key")
    return TestClient(app)


def signup_payload(email: str = "bruin@g.ucla.edu") -> dict[str, str]:
    return {
        "full_name": "Sunny Bruin",
        "email": email,
        "password": "classroom123",
    }


def test_signup_creates_ucla_user_and_sets_cookie(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        response = client.post("/api/auth/signup", json=signup_payload())

    assert response.status_code == 201
    assert response.json()["user"]["email"] == "bruin@ucla.edu"
    assert response.json()["user"]["email_verified"] is False
    assert response.json()["user"]["notify_group_application_news"] is True
    assert SESSION_COOKIE_NAME in response.cookies


def test_signup_rejects_non_ucla_email(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        response = client.post(
            "/api/auth/signup",
            json=signup_payload(email="bruin@example.com"),
        )

    assert response.status_code == 422
    assert "UCLA" in response.json()["detail"]


def test_signup_rejects_missing_fields_and_short_password(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        response = client.post(
            "/api/auth/signup",
            json={"full_name": "", "email": "bruin@ucla.edu", "password": "short"},
        )

    assert response.status_code == 422


def test_signup_rejects_duplicate_email_case_insensitively(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        first = client.post("/api/auth/signup", json=signup_payload("bruin@ucla.edu"))
        client.post("/api/auth/logout")
        duplicate = client.post("/api/auth/signup", json=signup_payload("BRUIN@ucla.edu"))

    assert first.status_code == 201
    assert duplicate.status_code == 409


def test_g_ucla_email_is_ucla_alias_for_signup_and_login(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup = client.post("/api/auth/signup", json=signup_payload("bruin@g.ucla.edu"))
        client.post("/api/auth/logout")
        duplicate = client.post(
            "/api/auth/signup",
            json=signup_payload("bruin@ucla.edu"),
        )
        login = client.post(
            "/api/auth/login",
            json={"email": "bruin@g.ucla.edu", "password": "classroom123"},
        )

    assert signup.status_code == 201
    assert signup.json()["user"]["email"] == "bruin@ucla.edu"
    assert duplicate.status_code == 409
    assert login.status_code == 200


def test_login_succeeds_and_fails_with_expected_credentials(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        client.post("/api/auth/signup", json=signup_payload())
        client.post("/api/auth/logout")

        bad_login = client.post(
            "/api/auth/login",
            json={"email": "bruin@g.ucla.edu", "password": "wrongpassword"},
        )
        good_login = client.post(
            "/api/auth/login",
            json={"email": "bruin@g.ucla.edu", "password": "classroom123"},
        )

    assert bad_login.status_code == 401
    assert good_login.status_code == 200
    assert SESSION_COOKIE_NAME in good_login.cookies


def test_me_requires_auth_and_logout_clears_session(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        logged_out = client.get("/api/auth/me")
        signup = client.post("/api/auth/signup", json=signup_payload())
        logged_in = client.get("/api/auth/me")
        logout = client.post("/api/auth/logout")
        after_logout = client.get("/api/auth/me")

    assert logged_out.status_code == 401
    assert signup.status_code == 201
    assert logged_in.status_code == 200
    assert logged_in.json()["user"]["full_name"] == "Sunny Bruin"
    assert logout.status_code == 204
    assert after_logout.status_code == 401


def test_email_verification_confirms_user(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup = client.post("/api/auth/signup", json=signup_payload())
        db_path = tmp_path / "test.sqlite3"
        import sqlite3

        with sqlite3.connect(db_path) as connection:
            token_hash = connection.execute(
                "SELECT token_hash FROM email_verification_tokens"
            ).fetchone()[0]
            connection.execute(
                """
                UPDATE email_verification_tokens
                SET token_hash = ?
                WHERE token_hash = ?
                """,
                (
                    "46f6e828be35b9e2482ea7fc7a6a8f43f95a131098470486be3d137d408c8811",
                    token_hash,
                ),
            )
        confirm = client.post(
            "/api/auth/email-verification/confirm",
            json={"token": "verification-token"},
        )

    assert signup.status_code == 201
    assert confirm.status_code == 200
    assert confirm.json()["user"]["email_verified"] is True


def test_password_reset_updates_password_and_verifies_email(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        client.post("/api/auth/signup", json=signup_payload())
        client.post("/api/auth/password-reset/request", json={"email": "bruin@g.ucla.edu"})
        db_path = tmp_path / "test.sqlite3"
        import sqlite3

        with sqlite3.connect(db_path) as connection:
            token_hash = connection.execute(
                "SELECT token_hash FROM password_reset_tokens"
            ).fetchone()[0]
            connection.execute(
                """
                UPDATE password_reset_tokens
                SET token_hash = ?
                WHERE token_hash = ?
                """,
                (
                    "b251c3d7aec4506ef8824816dc07e2ab49c856b64de73001942c35bde191d8f8",
                    token_hash,
                ),
            )
        reset = client.post(
            "/api/auth/password-reset/confirm",
            json={"token": "reset-token-valid", "password": "newclassroom123"},
        )
        client.post("/api/auth/logout")
        old_login = client.post(
            "/api/auth/login",
            json={"email": "bruin@g.ucla.edu", "password": "classroom123"},
        )
        new_login = client.post(
            "/api/auth/login",
            json={"email": "bruin@g.ucla.edu", "password": "newclassroom123"},
        )

    assert reset.status_code == 200
    assert reset.json()["user"]["email_verified"] is True
    assert old_login.status_code == 401
    assert new_login.status_code == 200
