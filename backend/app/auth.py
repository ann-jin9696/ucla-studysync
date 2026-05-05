from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Response, status

from .db import get_db
from .schemas import AuthResponse, LoginRequest, SignupRequest, UserResponse
from .security import (
    clear_session_cookie,
    create_session_cookie,
    get_current_user,
    hash_password,
    is_ucla_email,
    normalize_email,
    verify_password,
)


router = APIRouter(prefix="/api/auth", tags=["auth"])


def serialize_user(user: sqlite3.Row) -> UserResponse:
    return UserResponse(
        id=user["id"],
        full_name=user["full_name"],
        email=user["email"],
        created_at=user["created_at"],
    )


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(
    payload: SignupRequest,
    response: Response,
    db: sqlite3.Connection = Depends(get_db),
) -> AuthResponse:
    full_name = " ".join(payload.full_name.strip().split())
    email = normalize_email(payload.email)

    if not full_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Full name is required.",
        )
    if not is_ucla_email(email):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Please use a UCLA email address.",
        )

    try:
        cursor = db.execute(
            """
            INSERT INTO users (full_name, email, password_hash)
            VALUES (?, ?, ?)
            """,
            (full_name, email, hash_password(payload.password)),
        )
        db.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists.",
        ) from None

    user = db.execute(
        "SELECT id, full_name, email, created_at FROM users WHERE id = ?",
        (cursor.lastrowid,),
    ).fetchone()
    create_session_cookie(response, int(user["id"]))
    return AuthResponse(user=serialize_user(user))


@router.post("/login", response_model=AuthResponse)
def login(
    payload: LoginRequest,
    response: Response,
    db: sqlite3.Connection = Depends(get_db),
) -> AuthResponse:
    email = normalize_email(payload.email)
    user = db.execute(
        "SELECT id, full_name, email, password_hash, created_at FROM users WHERE email = ?",
        (email,),
    ).fetchone()

    if user is None or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is incorrect.",
        )

    create_session_cookie(response, int(user["id"]))
    return AuthResponse(user=serialize_user(user))


@router.post("/logout", response_class=Response, status_code=status.HTTP_204_NO_CONTENT)
def logout() -> Response:
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_session_cookie(response)
    return response


@router.get("/me", response_model=AuthResponse)
def me(user: sqlite3.Row = Depends(get_current_user)) -> AuthResponse:
    return AuthResponse(user=serialize_user(user))
