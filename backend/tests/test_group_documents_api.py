from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import groups
from app.main import app
from app.openai_document_qa import (
    DocumentQAAnswer,
    DocumentQAError,
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
    email: str = "workspace@g.ucla.edu",
    full_name: str = "Workspace Bruin",
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


def update_profile(
    client: TestClient,
    course: dict[str, object] | None = None,
) -> dict:
    profile = client.put(
        "/api/profile/me",
        json={"courses": [course or course_payload()]},
    )
    assert profile.status_code == 200
    return profile.json()


def create_profile_group(client: TestClient) -> int:
    profile = update_profile(client)
    group = client.post(
        "/api/groups",
        json={"user_course_id": profile["courses"][0]["user_course_id"]},
    )
    assert group.status_code == 201
    return group.json()["id"]


def upload_document(client: TestClient, group_id: int, title: str) -> dict[str, object]:
    response = client.post(
        f"/api/groups/{group_id}/documents",
        data={"title": title, "document_type": "notes"},
        files={"file": (f"{title}.txt", b"StudySync notes", "text/plain")},
    )
    assert response.status_code == 201
    return response.json()


def add_member_to_group(
    client: TestClient,
    group_id: int,
    email: str = "member@g.ucla.edu",
    full_name: str = "Member Bruin",
) -> None:
    client.post("/api/auth/logout")
    signup(client, email, full_name)
    update_profile(client)
    join_request = client.post(f"/api/groups/{group_id}/join-requests")
    assert join_request.status_code == 201
    client.post("/api/auth/logout")
    login(client, "owner@g.ucla.edu")
    approve = client.post(
        f"/api/groups/{group_id}/join-requests/{join_request.json()['id']}/approve"
    )
    assert approve.status_code == 200
    client.post("/api/auth/logout")
    login(client, email)


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
            answer="Use the worksheet to compare setup steps.",
            sources=[
                DocumentQASourceResult(
                    document_id=1,
                    file_name="week-1-notes.txt",
                    snippet="Compare setup steps before discussion.",
                )
            ],
        )

    def summarize_document(self, **_kwargs) -> str:
        return "This document summarizes the setup steps for the study group."


class FailingIndexDocumentQA(ReadyDocumentQA):
    def index_document(self, **_kwargs) -> IndexedDocument:
        raise DocumentQAError("indexing exploded")


def test_group_documents_require_login(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        response = client.get("/api/groups/1/documents")

    assert response.status_code == 401


def test_non_members_cannot_use_group_documents(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client, "owner@g.ucla.edu")
        group_id = create_profile_group(client)
        client.post("/api/auth/logout")

        signup(client, "outsider@g.ucla.edu")
        response = client.get(f"/api/groups/{group_id}/documents")

    assert response.status_code == 403


def test_group_detail_shows_live_properties_and_members(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client, "owner@g.ucla.edu", "Owner Bruin")
        owner_profile = update_profile(client)
        group = client.post(
            "/api/groups",
            json={
                "user_course_id": owner_profile["courses"][0]["user_course_id"],
                "name": "Detail Crew",
            },
        )
        assert group.status_code == 201
        group_id = group.json()["id"]
        client.post("/api/auth/logout")

        signup(client, "neel@g.ucla.edu", "Neel Member")
        update_profile(
            client,
            {
                **course_payload(),
                "study_goals": ["concept_review", "project_work"],
                "pace_preference": "intensive",
                "group_size_preference": 8,
            },
        )
        join_request = client.post(f"/api/groups/{group_id}/join-requests")
        assert join_request.status_code == 201
        client.post("/api/auth/logout")

        login(client, "owner@g.ucla.edu")
        approve = client.post(
            f"/api/groups/{group_id}/join-requests/{join_request.json()['id']}/approve"
        )
        detail = client.get(f"/api/groups/{group_id}")

        client.post("/api/auth/logout")
        signup(client, "outside@g.ucla.edu", "Outside Bruin")
        outsider_detail = client.get(f"/api/groups/{group_id}")

    assert approve.status_code == 200
    assert detail.status_code == 200
    body = detail.json()
    assert body["name"] == "Detail Crew"
    assert body["owner_name"] == "Owner Bruin"
    assert body["member_count"] == 2
    assert body["group_size_bucket"] == "small"
    assert body["average_pace_preference"] == "intensive"
    assert {member["full_name"] for member in body["members"]} == {
        "Owner Bruin",
        "Neel Member",
    }
    assert [member["is_owner"] for member in body["members"] if member["full_name"] == "Owner Bruin"] == [True]
    assert {goal["value"] for goal in body["top_study_goals"]} == {
        "project_work",
        "concept_review",
    }
    assert outsider_detail.status_code == 403


def test_user_can_upload_search_and_comment_on_group_document(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client)
        group_id = create_profile_group(client)

        upload = client.post(
            f"/api/groups/{group_id}/documents",
            data={"title": "Week 1 Notes", "document_type": "pdf"},
            files={
                "file": (
                    "week 1 notes.pdf",
                    b"StudySync group notes",
                    "application/pdf",
                )
            },
        )
        assert upload.status_code == 201
        document = upload.json()
        assert document["group_id"] == group_id
        assert document["title"] == "Week 1 Notes"
        assert document["file_name"] == "week-1-notes.pdf"
        assert document["document_type"] == "pdf"
        assert document["uploader_name"] == "Workspace Bruin"
        assert document["file_size_bytes"] == len(b"StudySync group notes")
        assert document["ai_summary"] is None

        saved_file = tmp_path / "uploads" / f"group-{group_id}" / "1-week-1-notes.pdf"
        assert saved_file.read_bytes() == b"StudySync group notes"

        file_response = client.get(
            f"/api/groups/{group_id}/documents/{document['id']}/file"
        )

        assert file_response.status_code == 200
        assert file_response.content == b"StudySync group notes"
        assert file_response.headers["content-type"] == "application/pdf"
        assert "inline" in file_response.headers["content-disposition"]

        matching_search = client.get(f"/api/groups/{group_id}/documents?search=week")
        empty_search = client.get(f"/api/groups/{group_id}/documents?search=slides")

        assert matching_search.status_code == 200
        assert [row["id"] for row in matching_search.json()["documents"]] == [
            document["id"]
        ]
        assert empty_search.status_code == 200
        assert empty_search.json()["documents"] == []

        created_comment = client.post(
            f"/api/groups/{group_id}/documents/{document['id']}/comments",
            json={"content": "This will help us review for the quiz."},
        )
        comments = client.get(
            f"/api/groups/{group_id}/documents/{document['id']}/comments"
        )

        assert created_comment.status_code == 201
        assert created_comment.json()["author_name"] == "Workspace Bruin"
        assert comments.status_code == 200
        assert comments.json()[0]["content"] == "This will help us review for the quiz."


def test_upload_keeps_document_when_openai_indexing_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(groups, "document_qa_service", FailingIndexDocumentQA())
    with make_client(tmp_path, monkeypatch) as client:
        signup(client)
        group_id = create_profile_group(client)

        document = upload_document(client, group_id, "Index Failure Notes")

    assert document["index_status"] == "failed"
    assert "indexing exploded" in document["index_error"]
    assert document["ai_summary"] is None


def test_upload_stores_ai_document_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(groups, "document_qa_service", ReadyDocumentQA())
    with make_client(tmp_path, monkeypatch) as client:
        signup(client)
        group_id = create_profile_group(client)

        document = upload_document(client, group_id, "Summary Notes")
        listed = client.get(f"/api/groups/{group_id}/documents")

    assert document["index_status"] == "ready"
    assert (
        document["ai_summary"]
        == "This document summarizes the setup steps for the study group."
    )
    assert listed.status_code == 200
    assert listed.json()["documents"][0]["ai_summary"] == document["ai_summary"]


def test_group_document_qa_requires_membership(tmp_path, monkeypatch):
    monkeypatch.setattr(groups, "document_qa_service", ReadyDocumentQA())
    with make_client(tmp_path, monkeypatch) as client:
        signup(client, "owner@g.ucla.edu")
        group_id = create_profile_group(client)
        upload_document(client, group_id, "Owner Notes")
        client.post("/api/auth/logout")

        signup(client, "outsider@g.ucla.edu")
        response = client.post(
            f"/api/groups/{group_id}/qa",
            json={"question": "What should we review?"},
        )

    assert response.status_code == 403


def test_group_document_qa_requires_indexed_documents(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client)
        group_id = create_profile_group(client)

        response = client.post(
            f"/api/groups/{group_id}/qa",
            json={"question": "What should we review?"},
        )

    assert response.status_code == 409
    assert response.json()["detail"] == "No indexed documents are ready for Q&A yet."


def test_group_document_qa_returns_answer_and_sources(tmp_path, monkeypatch):
    monkeypatch.setattr(groups, "document_qa_service", ReadyDocumentQA())
    with make_client(tmp_path, monkeypatch) as client:
        signup(client)
        group_id = create_profile_group(client)
        upload_document(client, group_id, "Week 1 Notes")

        response = client.post(
            f"/api/groups/{group_id}/qa",
            json={"question": "What should we compare?"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Use the worksheet to compare setup steps."
    assert body["sources"] == [
        {
            "document_id": 1,
            "file_name": "week-1-notes.txt",
            "snippet": "Compare setup steps before discussion.",
        }
    ]


def test_group_activity_is_scoped_to_current_users_groups(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client, "owner@g.ucla.edu", "Owner Bruin")
        owner_group_id = create_profile_group(client)
        owner_document = upload_document(client, owner_group_id, "Owner Notes")
        comment = client.post(
            f"/api/groups/{owner_group_id}/documents/{owner_document['id']}/comments",
            json={"content": "I marked the review questions."},
        )
        assert comment.status_code == 201

        client.post("/api/auth/logout")

        signup(client, "outside@g.ucla.edu", "Outside Bruin")
        outside_group_id = create_profile_group(client)
        upload_document(client, outside_group_id, "Outside Notes")

        client.post("/api/auth/logout")
        login(client, "owner@g.ucla.edu")

        response = client.get("/api/groups/activity")

    assert response.status_code == 200
    activities = response.json()
    assert {activity["activity_type"] for activity in activities} == {
        "comment_added",
        "document_uploaded",
    }
    assert {activity["document_title"] for activity in activities} == {"Owner Notes"}
    assert {activity["group_id"] for activity in activities} == {owner_group_id}
    assert {activity["actor_name"] for activity in activities} == {"Owner Bruin"}


def test_file_preview_requires_authentication(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client)
        group_id = create_profile_group(client)
        document = upload_document(client, group_id, "Preview Notes")
        client.post("/api/auth/logout")

        response = client.get(f"/api/groups/{group_id}/documents/{document['id']}/file")

    assert response.status_code == 401


def test_non_member_cannot_preview_file(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client, "owner@g.ucla.edu")
        group_id = create_profile_group(client)
        document = upload_document(client, group_id, "Preview Notes")
        client.post("/api/auth/logout")

        signup(client, "outsider@g.ucla.edu")
        response = client.get(f"/api/groups/{group_id}/documents/{document['id']}/file")

    assert response.status_code == 403


def test_member_can_preview_file_with_correct_content_type(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client)
        group_id = create_profile_group(client)

        response = client.post(
            f"/api/groups/{group_id}/documents",
            data={"title": "Lecture Slides", "document_type": "slides"},
            files={"file": ("lecture.pdf", b"PDF content here", "application/pdf")},
        )
        assert response.status_code == 201
        document = response.json()

        file_response = client.get(
            f"/api/groups/{group_id}/documents/{document['id']}/file"
        )

    assert file_response.status_code == 200
    assert file_response.content == b"PDF content here"
    assert file_response.headers["content-type"] == "application/pdf"
    assert "inline" in file_response.headers["content-disposition"]


@pytest.mark.parametrize(
    ("file_name", "content_type"),
    [
        ("lecture.pdf", "application/pdf"),
        ("diagram.png", "image/png"),
        ("photo.jpg", "image/jpeg"),
        ("notes.txt", "text/plain"),
        ("outline.md", "text/markdown"),
    ],
)
def test_member_can_upload_supported_preview_file_types(
    tmp_path,
    monkeypatch,
    file_name,
    content_type,
):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client)
        group_id = create_profile_group(client)

        response = client.post(
            f"/api/groups/{group_id}/documents",
            data={"title": "Supported File", "document_type": "notes"},
            files={"file": (file_name, b"StudySync preview content", content_type)},
        )

    assert response.status_code == 201
    assert response.json()["file_name"] == file_name


def test_upload_rejects_unsupported_file_type(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client)
        group_id = create_profile_group(client)

        response = client.post(
            f"/api/groups/{group_id}/documents",
            data={"title": "Unsupported File", "document_type": "notes"},
            files={
                "file": (
                    "archive.zip",
                    b"not a previewable classroom file",
                    "application/zip",
                )
            },
        )

    assert response.status_code == 422
    assert "PDF, PNG, JPG, TXT, or MD" in response.json()["detail"]


def test_upload_rejects_files_over_per_file_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(groups, "MAX_DOCUMENT_FILE_BYTES", 10)
    with make_client(tmp_path, monkeypatch) as client:
        signup(client)
        group_id = create_profile_group(client)

        response = client.post(
            f"/api/groups/{group_id}/documents",
            data={"title": "Large File", "document_type": "notes"},
            files={"file": ("large.txt", b"x" * 11, "text/plain")},
        )
        listed = client.get(f"/api/groups/{group_id}/documents")

    assert response.status_code == 413
    assert "per-file limit" in response.json()["detail"]
    assert listed.json()["documents"] == []
    assert list((tmp_path / "uploads" / f"group-{group_id}").iterdir()) == []


def test_upload_rejects_when_group_storage_limit_would_be_exceeded(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(groups, "MAX_DOCUMENT_FILE_BYTES", 100)
    monkeypatch.setattr(groups, "MAX_GROUP_STORAGE_BYTES", 20)
    with make_client(tmp_path, monkeypatch) as client:
        signup(client)
        group_id = create_profile_group(client)

        first = client.post(
            f"/api/groups/{group_id}/documents",
            data={"title": "First", "document_type": "notes"},
            files={"file": ("first.txt", b"x" * 12, "text/plain")},
        )
        second = client.post(
            f"/api/groups/{group_id}/documents",
            data={"title": "Second", "document_type": "notes"},
            files={"file": ("second.txt", b"x" * 9, "text/plain")},
        )
        listed = client.get(f"/api/groups/{group_id}/documents")

    assert first.status_code == 201
    assert second.status_code == 413
    assert [document["title"] for document in listed.json()["documents"]] == ["First"]


def test_file_owner_can_delete_group_document(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client)
        group_id = create_profile_group(client)
        document = upload_document(client, group_id, "Delete Me")
        comment = client.post(
            f"/api/groups/{group_id}/documents/{document['id']}/comments",
            json={"content": "Remove this with the file."},
        )
        delete = client.delete(f"/api/groups/{group_id}/documents/{document['id']}")
        listed = client.get(f"/api/groups/{group_id}/documents")
        comments = client.get(
            f"/api/groups/{group_id}/documents/{document['id']}/comments"
        )

    assert comment.status_code == 201
    assert delete.status_code == 204
    assert listed.json()["documents"] == []
    assert comments.status_code == 404
    assert not Path(str(document["file_path"])).exists()


def test_group_owner_can_delete_member_document(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client, "owner@g.ucla.edu", "Owner Bruin")
        group_id = create_profile_group(client)
        add_member_to_group(client, group_id)
        member_document = upload_document(client, group_id, "Member Notes")

        client.post("/api/auth/logout")
        login(client, "owner@g.ucla.edu")
        delete = client.delete(
            f"/api/groups/{group_id}/documents/{member_document['id']}"
        )
        listed = client.get(f"/api/groups/{group_id}/documents")

    assert delete.status_code == 204
    assert listed.json()["documents"] == []


def test_member_cannot_delete_someone_elses_document(tmp_path, monkeypatch):
    with make_client(tmp_path, monkeypatch) as client:
        signup(client, "owner@g.ucla.edu", "Owner Bruin")
        group_id = create_profile_group(client)
        owner_document = upload_document(client, group_id, "Owner Notes")

        add_member_to_group(client, group_id)
        delete = client.delete(
            f"/api/groups/{group_id}/documents/{owner_document['id']}"
        )

    assert delete.status_code == 403
