from __future__ import annotations

from pydantic import BaseModel, Field


class SignupRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    notify_group_application_news: bool = True


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    id: int
    full_name: str
    email: str
    email_verified: bool
    notify_group_application_news: bool
    created_at: str


class AuthResponse(BaseModel):
    user: UserResponse


class EmailVerificationRequest(BaseModel):
    token: str = Field(min_length=16, max_length=256)


class PasswordResetRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(min_length=16, max_length=256)
    password: str = Field(min_length=8, max_length=128)


class EmailPreferencesRequest(BaseModel):
    notify_group_application_news: bool


class ProfileCourseResponse(BaseModel):
    user_course_id: int
    course_id: int
    course_code: str
    course_quarter: str
    lecture_number: int
    study_goals: list[str]
    pace_preference: str | None
    group_size_preference: int | None


class ProfileResponse(BaseModel):
    courses: list[ProfileCourseResponse]
    has_basic_profile: bool
    is_complete: bool
    created_at: str | None
    updated_at: str | None


class CourseQuarterOptionsResponse(BaseModel):
    options: list[str]


class CourseCodeOptionsResponse(BaseModel):
    options: list[str]


class GroupCreateRequest(BaseModel):
    user_course_id: int = Field(gt=0)
    name: str | None = Field(default=None, max_length=80)


class GroupResponse(BaseModel):
    id: int
    name: str
    course_id: int
    course_code: str
    course_quarter: str
    lecture_number: int
    created_by_user_id: int
    member_count: int
    created_at: str
    updated_at: str


class StudyGoalSummary(BaseModel):
    value: str
    count: int


class GroupMemberResponse(BaseModel):
    user_id: int
    full_name: str
    is_owner: bool
    study_goals: list[str]
    pace_preference: str | None
    group_size_preference: int | None
    joined_at: str


class GroupDetailResponse(GroupResponse):
    owner_name: str
    top_study_goals: list[StudyGoalSummary]
    average_pace_preference: str | None
    average_pace_score: float | None
    group_size_bucket: str
    members: list[GroupMemberResponse]


class GroupDirectoryResponse(GroupResponse):
    owner_name: str
    top_study_goals: list[StudyGoalSummary]
    average_pace_preference: str | None
    average_pace_score: float | None
    group_size_bucket: str
    matches_preferred_group_size: bool
    is_member: bool
    is_owner: bool
    pending_request_id: int | None
    pending_applicant_count: int


class JoinRequestResponse(BaseModel):
    id: int
    group_id: int
    user_id: int
    user_name: str
    status: str
    created_at: str
    decided_at: str | None


class PendingApplicationResponse(BaseModel):
    id: int
    group_id: int
    group_name: str
    course_code: str
    user_id: int
    user_name: str
    created_at: str


class DocumentResponse(BaseModel):
    id: int
    group_id: int
    uploader_id: int
    uploader_name: str
    title: str
    file_name: str
    file_path: str
    file_size_bytes: int
    document_type: str
    index_status: str
    index_error: str | None
    ai_summary: str | None
    can_delete: bool = False
    uploaded_at: str


class GroupDocumentsResponse(BaseModel):
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


class DocumentQARequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class DocumentQASource(BaseModel):
    document_id: int | None
    file_name: str
    snippet: str


class DocumentQAResponse(BaseModel):
    answer: str
    sources: list[DocumentQASource]


class AISummaryCreateRequest(BaseModel):
    topic: str | None = Field(default=None, max_length=160)
    document_id: int | None = Field(default=None, gt=0)


class KeyIdeaResponse(BaseModel):
    id: int
    ai_summary_id: int
    content: str
    position: int


class AISummaryResponse(BaseModel):
    id: int
    group_id: int
    creator_id: int
    document_id: int | None
    topic: str | None
    summary_text: str
    key_ideas: list[KeyIdeaResponse]
    saved: bool = False
    created_at: str


class SavedSummaryResponse(BaseModel):
    id: int
    ai_summary_id: int
    user_id: int
    saved_at: str
    summary: AISummaryResponse


class GroupActivityResponse(BaseModel):
    id: str
    activity_type: str
    group_id: int
    group_name: str
    course_code: str
    document_id: int
    document_title: str
    actor_id: int
    actor_name: str
    occurred_at: str
