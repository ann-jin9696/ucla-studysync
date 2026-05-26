from __future__ import annotations

from fastapi.testclient import TestClient

from app import ai, groups
from app.ai_service import AISummaryDraft
from app.main import app
from app.openai_document_qa import (
    DocumentQAAnswer,
    DocumentQASourceResult,
    IndexedDocument,
)


def make_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("STUDYSYNC_DB_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("STUDYSYNC_SECRET_KEY", "test-secret-key")
    monkeypatch.setattr(groups, "UPLOAD_DIR", tmp_path / "uploads")
    return TestClient(app)


def course_payload(course_code: str = "CS35L") -> dict[str, object]:
    return {
        "course_code": course_code,
        "course_quarter": "Spring 2026",
        "lecture_number": 1,
        "study_goals": ["project_work"],
        "pace_preference": "moderate",
        "group_size_preference": 4,
    }


def signup(
    client: TestClient,
    email: str = "ai-owner@g.ucla.edu",
    full_name: str = "AI Owner",
) -> None:
    response = client.post(
        "/api/auth/signup",
        json={
            "full_name": full_name,
            "email": email,
            "password": "classroom123",
        },
    )
    assert response.status_code == 201


def login(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "classroom123"},
    )
    assert response.status_code == 200


def update_profile(client: TestClient) -> dict:
    response = client.put(
        "/api/profile/me",
        json={"courses": [course_payload()]},
    )
    assert response.status_code == 200
    return response.json()


def create_profile_group(client: TestClient) -> int:
    profile = update_profile(client)
    response = client.post(
        "/api/groups",
        json={"user_course_id": profile["courses"][0]["user_course_id"]},
    )
    assert response.status_code == 201
    return response.json()["id"]


def upload_document(client: TestClient, group_id: int, title: str = "AI Notes") -> dict:
    response = client.post(
        f"/api/groups/{group_id}/documents",
        data={"title": title, "document_type": "notes"},
        files={"file": (f"{title}.txt", b"StudySync AI notes", "text/plain")},
    )
    assert response.status_code == 201
    return response.json()


class ReadyDocumentQA:
    def create_vector_store(self, group_id: int, group_name: str) -> str:
        return f"vs-{group_id}-{group_name}"

    def index_document(self, **_kwargs) -> IndexedDocument:
        return IndexedDocument(
            openai_file_id="file-ready",
            openai_vector_store_file_id="vsf-ready",
            status="ready",
        )

    def answer_question(self, **_kwargs) -> DocumentQAAnswer:
        return DocumentQAAnswer(
            answer="Use the notes to connect concepts before solving problems.",
            sources=[
                DocumentQASourceResult(
                    document_id=1,
                    file_name="ai-notes.txt",
                    snippet="Connect concepts before problem solving.",
                )
            ],
        )

    def summarize_document(self, **_kwargs) -> str:
        return "This document summarizes the study notes."


class ReadyAIService:
    def create_study_summary(self, **kwargs) -> AISummaryDraft:
        self.last_kwargs = kwargs
        return AISummaryDraft(
            summary_text="Graphs and invariants guide the main proof strategy.",
            key_ideas=[
                "Track invariants before each transformation.",
                "Use graph structure to organize cases.",
            ],
        )


def test_ai_summaries_require_login(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        response = client.get("/api/ai/groups/1/summaries")

    assert response.status_code == 401


def test_create_and_list_ai_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(groups, "document_qa_service", ReadyDocumentQA())
    fake_ai_service = ReadyAIService()
    monkeypatch.setattr(ai, "ai_service", fake_ai_service)

    with make_client(tmp_path, monkeypatch) as client:
        signup(client)
        group_id = create_profile_group(client)
        document = upload_document(client, group_id)

        response = client.post(
            f"/api/ai/groups/{group_id}/summaries",
            json={"topic": "  proof planning  ", "document_id": document["id"]},
        )
        listed = client.get(f"/api/ai/groups/{group_id}/summaries")

    assert response.status_code == 201
    body = response.json()
    assert body["group_id"] == group_id
    assert body["document_id"] == document["id"]
    assert body["topic"] == "proof planning"
    assert body["summary_text"] == "Graphs and invariants guide the main proof strategy."
    assert [idea["content"] for idea in body["key_ideas"]] == [
        "Track invariants before each transformation.",
        "Use graph structure to organize cases.",
    ]
    assert body["saved"] is False
    assert fake_ai_service.last_kwargs["document_id"] == document["id"]
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == body["id"]


def test_save_summary_and_list_saved_summaries(tmp_path, monkeypatch):
    monkeypatch.setattr(groups, "document_qa_service", ReadyDocumentQA())
    monkeypatch.setattr(ai, "ai_service", ReadyAIService())

    with make_client(tmp_path, monkeypatch) as client:
        signup(client)
        group_id = create_profile_group(client)
        upload_document(client, group_id)
        summary = client.post(f"/api/ai/groups/{group_id}/summaries", json={}).json()

        saved = client.post(f"/api/ai/summaries/{summary['id']}/save")
        duplicate_save = client.post(f"/api/ai/summaries/{summary['id']}/save")
        saved_list = client.get("/api/ai/saved-summaries")
        listed = client.get(f"/api/ai/groups/{group_id}/summaries")

    assert saved.status_code == 201
    assert duplicate_save.status_code == 201
    assert saved.json()["summary"]["saved"] is True
    assert saved_list.status_code == 200
    assert len(saved_list.json()) == 1
    assert saved_list.json()[0]["ai_summary_id"] == summary["id"]
    assert listed.json()[0]["saved"] is True


def test_non_member_cannot_save_ai_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(groups, "document_qa_service", ReadyDocumentQA())
    monkeypatch.setattr(ai, "ai_service", ReadyAIService())

    with make_client(tmp_path, monkeypatch) as client:
        signup(client, "owner@g.ucla.edu", "Owner Bruin")
        group_id = create_profile_group(client)
        upload_document(client, group_id)
        summary = client.post(f"/api/ai/groups/{group_id}/summaries", json={}).json()
        client.post("/api/auth/logout")

        signup(client, "outsider@g.ucla.edu", "Outside Bruin")
        response = client.post(f"/api/ai/summaries/{summary['id']}/save")

    assert response.status_code == 404


def test_create_ai_summary_requires_ready_document(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client)
        group_id = create_profile_group(client)
        response = client.post(f"/api/ai/groups/{group_id}/summaries", json={})

    assert response.status_code == 409
