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
