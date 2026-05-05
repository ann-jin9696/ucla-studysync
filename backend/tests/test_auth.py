from __future__ import annotations

import os

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
    assert response.json()["user"]["email"] == "bruin@g.ucla.edu"
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
