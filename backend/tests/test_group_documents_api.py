from __future__ import annotations

from fastapi.testclient import TestClient

from app import groups
from app.main import app


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
