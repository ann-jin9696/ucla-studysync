from __future__ import annotations

from fastapi.testclient import TestClient

from app import workspace
from app.main import app


def make_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("STUDYSYNC_DB_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("STUDYSYNC_SECRET_KEY", "test-secret-key")
    monkeypatch.setattr(workspace, "UPLOAD_DIR", tmp_path / "uploads")
    return TestClient(app)


def signup(client: TestClient) -> None:
    response = client.post(
        "/api/auth/signup",
        json={
            "full_name": "Workspace Bruin",
            "email": "workspace@g.ucla.edu",
            "password": "classroom123",
        },
    )
    assert response.status_code == 201


def test_workspace_documents_require_login(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        response = client.get("/api/workspace/documents")

    assert response.status_code == 401


def test_user_can_upload_search_and_comment_on_document(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client)

        upload = client.post(
            "/api/workspace/documents",
            data={"title": "Week 1 Notes", "document_type": "pdf"},
            files={
                "file": (
                    "week 1 notes.pdf",
                    b"StudySync workspace notes",
                    "application/pdf",
                )
            },
        )
        assert upload.status_code == 201
        document = upload.json()
        assert document["title"] == "Week 1 Notes"
        assert document["file_name"] == "week-1-notes.pdf"
        assert document["document_type"] == "pdf"
        assert document["uploader_name"] == "Workspace Bruin"

        saved_file = tmp_path / "uploads" / "1-week-1-notes.pdf"
        assert saved_file.read_bytes() == b"StudySync workspace notes"

        file_response = client.get(
            f"/api/workspace/documents/{document['id']}/file"
        )

        assert file_response.status_code == 200
        assert file_response.content == b"StudySync workspace notes"
        assert file_response.headers["content-type"] == "application/pdf"
        assert "inline" in file_response.headers["content-disposition"]

        matching_search = client.get("/api/workspace/documents?search=week")
        empty_search = client.get("/api/workspace/documents?search=slides")

        assert matching_search.status_code == 200
        assert [row["id"] for row in matching_search.json()["documents"]] == [
            document["id"]
        ]
        assert empty_search.status_code == 200
        assert empty_search.json()["documents"] == []

        created_comment = client.post(
            f"/api/workspace/documents/{document['id']}/comments",
            json={"content": "This will help us review for the quiz."},
        )
        comments = client.get(f"/api/workspace/documents/{document['id']}/comments")

        assert created_comment.status_code == 201
        assert created_comment.json()["author_name"] == "Workspace Bruin"
        assert comments.status_code == 200
        assert comments.json()[0]["content"] == "This will help us review for the quiz."
