from __future__ import annotations

from pydantic import BaseModel, Field


class SignupRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    id: int
    full_name: str
    email: str
    created_at: str


class AuthResponse(BaseModel):
    user: UserResponse


class ProfileResponse(BaseModel):
    courses: list[str]
    study_goals: list[str]
    pace_preference: str | None
    study_style_preference: str | None
    group_size_preference: str | None
    preferred_study_time_tags: list[str]
    has_basic_profile: bool
    is_complete: bool
    created_at: str | None
    updated_at: str | None


class DocumentResponse(BaseModel):
    id: int
    workspace_id: int
    uploader_id: int
    uploader_name: str
    title: str
    file_name: str
    file_path: str
    document_type: str
    uploaded_at: str


class WorkspaceDocumentsResponse(BaseModel):
    workspace_id: int
    group_id: int
    documents: list[DocumentResponse]


class CommentCreateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=600)


class CommentResponse(BaseModel):
    id: int
    document_id: int
    author_id: int
    author_name: str
    content: str
    created_at: str


class MatchResultResponse(BaseModel):
    matchScore: int
    matchedCourse: str
    matchedSchedule: str
    matchedPreference: str


class ActivityItemResponse(BaseModel):
    activityId: int
    activityType: str
    timestamp: str
    description: str