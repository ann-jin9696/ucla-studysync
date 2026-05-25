from __future__ import annotations

import sqlite3
from hashlib import sha256
from secrets import token_urlsafe

from fastapi import APIRouter, Depends, HTTPException, Response, status

from .config import EMAIL_VERIFICATION_MAX_AGE_HOURS, PASSWORD_RESET_MAX_AGE_HOURS
from .db import get_db
from .email import (
    send_password_reset_email,
    send_verification_email,
)
from .schemas import (
    AuthResponse,
    EmailPreferencesRequest,
    EmailVerificationRequest,
    LoginRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    SignupRequest,
    UserResponse,
)
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


USER_FIELDS = """
        id,
        full_name,
        email,
        email_verified,
        notify_group_application_news,
        created_at
"""

USER_SELECT = f"""
    SELECT
        {USER_FIELDS}
    FROM users
"""


def serialize_user(user: sqlite3.Row) -> UserResponse:
    return UserResponse(
        id=user["id"],
        full_name=user["full_name"],
        email=user["email"],
        email_verified=bool(user["email_verified"]),
        notify_group_application_news=bool(user["notify_group_application_news"]),
        created_at=user["created_at"],
    )


def hash_token(raw_token: str) -> str:
    return sha256(raw_token.encode("utf-8")).hexdigest()


def create_one_time_token(
    db: sqlite3.Connection,
    table_name: str,
    user_id: int,
    expires_in_hours: int,
) -> str:
    raw_token = token_urlsafe(32)
    db.execute(
        f"""
        INSERT INTO {table_name} (user_id, token_hash, expires_at)
        VALUES (?, ?, datetime('now', ?))
        """,
        (user_id, hash_token(raw_token), f"+{expires_in_hours} hours"),
    )
    return raw_token


def get_valid_token_row(
    db: sqlite3.Connection,
    table_name: str,
    raw_token: str,
) -> sqlite3.Row:
    token_row = db.execute(
        f"""
        SELECT id, user_id
        FROM {table_name}
        WHERE token_hash = ?
          AND used_at IS NULL
          AND expires_at >= CURRENT_TIMESTAMP
        """,
        (hash_token(raw_token),),
    ).fetchone()
    if token_row is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This link is invalid or has expired.",
        )
    return token_row


def get_user_by_id(db: sqlite3.Connection, user_id: int) -> sqlite3.Row:
    user = db.execute(f"{USER_SELECT} WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found.",
        )
    return user


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
            INSERT INTO users (
                full_name,
                email,
                password_hash,
                email_verified,
                notify_group_application_news
            )
            VALUES (?, ?, ?, 0, ?)
            """,
            (
                full_name,
                email,
                hash_password(payload.password),
                int(payload.notify_group_application_news),
            ),
        )
        user_id = int(cursor.lastrowid)
        verification_token = create_one_time_token(
            db,
            "email_verification_tokens",
            user_id,
            EMAIL_VERIFICATION_MAX_AGE_HOURS,
        )
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists.",
        ) from None
    except sqlite3.Error:
        db.rollback()
        raise

    user = get_user_by_id(db, user_id)
    send_verification_email(user["email"], user["full_name"], verification_token)
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
        f"SELECT {USER_FIELDS}, password_hash FROM users WHERE email = ?",
        (email,),
    ).fetchone()

    if user is None or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is incorrect.",
        )

    create_session_cookie(response, int(user["id"]))
    return AuthResponse(user=serialize_user(user))


@router.post(
    "/email-verification/resend",
    response_class=Response,
    status_code=status.HTTP_204_NO_CONTENT,
)
def resend_email_verification(
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(get_current_user),
) -> Response:
    if not bool(user["email_verified"]):
        token = create_one_time_token(
            db,
            "email_verification_tokens",
            int(user["id"]),
            EMAIL_VERIFICATION_MAX_AGE_HOURS,
        )
        db.commit()
        send_verification_email(user["email"], user["full_name"], token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/email-verification/confirm", response_model=AuthResponse)
def confirm_email_verification(
    payload: EmailVerificationRequest,
    response: Response,
    db: sqlite3.Connection = Depends(get_db),
) -> AuthResponse:
    token_row = get_valid_token_row(
        db,
        "email_verification_tokens",
        payload.token,
    )
    user_id = int(token_row["user_id"])
    try:
        db.execute("BEGIN")
        db.execute(
            """
            UPDATE email_verification_tokens
            SET used_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (token_row["id"],),
        )
        db.execute(
            """
            UPDATE users
            SET email_verified = 1,
                email_verified_at = COALESCE(email_verified_at, CURRENT_TIMESTAMP)
            WHERE id = ?
            """,
            (user_id,),
        )
        db.commit()
    except sqlite3.Error:
        db.rollback()
        raise

    user = get_user_by_id(db, user_id)
    create_session_cookie(response, user_id)
    return AuthResponse(user=serialize_user(user))


@router.post(
    "/password-reset/request",
    response_class=Response,
    status_code=status.HTTP_204_NO_CONTENT,
)
def request_password_reset(
    payload: PasswordResetRequest,
    db: sqlite3.Connection = Depends(get_db),
) -> Response:
    email = normalize_email(payload.email)
    user = db.execute(f"{USER_SELECT} WHERE email = ?", (email,)).fetchone()
    if user is not None:
        token = create_one_time_token(
            db,
            "password_reset_tokens",
            int(user["id"]),
            PASSWORD_RESET_MAX_AGE_HOURS,
        )
        db.commit()
        send_password_reset_email(user["email"], user["full_name"], token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/password-reset/confirm", response_model=AuthResponse)
def confirm_password_reset(
    payload: PasswordResetConfirmRequest,
    response: Response,
    db: sqlite3.Connection = Depends(get_db),
) -> AuthResponse:
    token_row = get_valid_token_row(db, "password_reset_tokens", payload.token)
    user_id = int(token_row["user_id"])
    try:
        db.execute("BEGIN")
        db.execute(
            """
            UPDATE password_reset_tokens
            SET used_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (token_row["id"],),
        )
        db.execute(
            """
            UPDATE users
            SET password_hash = ?,
                email_verified = 1,
                email_verified_at = COALESCE(email_verified_at, CURRENT_TIMESTAMP)
            WHERE id = ?
            """,
            (hash_password(payload.password), user_id),
        )
        db.commit()
    except sqlite3.Error:
        db.rollback()
        raise

    user = get_user_by_id(db, user_id)
    create_session_cookie(response, user_id)
    return AuthResponse(user=serialize_user(user))


@router.put("/email-preferences", response_model=AuthResponse)
def update_email_preferences(
    payload: EmailPreferencesRequest,
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(get_current_user),
) -> AuthResponse:
    db.execute(
        """
        UPDATE users
        SET notify_group_application_news = ?
        WHERE id = ?
        """,
        (int(payload.notify_group_application_news), user["id"]),
    )
    db.commit()
    updated_user = get_user_by_id(db, int(user["id"]))
    return AuthResponse(user=serialize_user(updated_user))


@router.post("/logout", response_class=Response, status_code=status.HTTP_204_NO_CONTENT)
def logout() -> Response:
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_session_cookie(response)
    return response


@router.get("/me", response_model=AuthResponse)
def me(user: sqlite3.Row = Depends(get_current_user)) -> AuthResponse:
    return AuthResponse(user=serialize_user(user))
