from __future__ import annotations

import re
import sqlite3

from fastapi import Cookie, Depends, HTTPException, Response, status
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner
from passlib.context import CryptContext

from .config import SESSION_COOKIE_NAME, SESSION_MAX_AGE_SECONDS, get_secret_key
from .db import get_db


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(email: str) -> str:
    return email.strip().lower()


def is_ucla_email(email: str) -> bool:
    normalized = normalize_email(email)
    if not EMAIL_PATTERN.match(normalized) or "@" not in normalized:
        return False
    domain = normalized.rsplit("@", 1)[1]
    return domain == "ucla.edu" or domain.endswith(".ucla.edu")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def _signer() -> TimestampSigner:
    return TimestampSigner(get_secret_key())


def create_session_cookie(response: Response, user_id: int) -> None:
    token = _signer().sign(str(user_id)).decode("utf-8")
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE_NAME, httponly=True, samesite="lax")


def get_current_user(
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: sqlite3.Connection = Depends(get_db),
) -> sqlite3.Row:
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
        )

    try:
        raw_user_id = _signer().unsign(
            session_token,
            max_age=SESSION_MAX_AGE_SECONDS,
        )
        user_id = int(raw_user_id.decode("utf-8"))
    except (BadSignature, SignatureExpired, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please log in again.",
        ) from None

    user = db.execute(
        "SELECT id, full_name, email, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists.",
        )
    return user
