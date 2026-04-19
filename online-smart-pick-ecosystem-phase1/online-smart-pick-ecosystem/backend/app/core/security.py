"""
Security module - handles password hashing and JWT tokens.

- Passwords are hashed with bcrypt (one-way, cannot be reversed)
- JWT tokens are signed with HS256 (symmetric signing)
- Access tokens expire in 60 minutes; refresh tokens in 7 days
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# Bcrypt context for password hashing. bcrypt is the gold standard.
# It automatically handles salting and is slow by design (resistant to brute force).
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ============================================================
# PASSWORD HASHING
# ============================================================

def hash_password(plain_password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        plain_password: The plaintext password to hash.

    Returns:
        A bcrypt hash string safe to store in the database.
    """
    if not plain_password or len(plain_password) < 8:
        raise ValueError("Password must be at least 8 characters long")
    # bcrypt has a 72-byte limit; longer passwords get silently truncated.
    # Enforce limit explicitly to avoid confusing behavior.
    if len(plain_password.encode("utf-8")) > 72:
        raise ValueError("Password must be at most 72 bytes")
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plaintext password against a bcrypt hash.

    Args:
        plain_password: Password provided by user at login.
        hashed_password: Hash stored in the database.

    Returns:
        True if the password matches, False otherwise.
    """
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        # Don't leak whether the hash is malformed vs just wrong password
        return False


# ============================================================
# JWT TOKENS
# ============================================================

def _create_token(
    subject: str,
    expires_delta: timedelta,
    token_type: str,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Internal helper to create a JWT token.

    Args:
        subject: The main claim — typically user id as string.
        expires_delta: How long before this token expires.
        token_type: "access" or "refresh".
        extra_claims: Additional key-value pairs to include in token payload.
    """
    now = datetime.now(timezone.utc)
    expire = now + expires_delta

    to_encode: Dict[str, Any] = {
        "sub": str(subject),       # Subject (user id)
        "iat": int(now.timestamp()),      # Issued at
        "exp": int(expire.timestamp()),   # Expires at
        "type": token_type,         # Helps prevent using refresh tokens as access tokens
    }

    if extra_claims:
        to_encode.update(extra_claims)

    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def create_access_token(
    user_id: UUID | str,
    agency_id: UUID | str,
    role: str,
) -> str:
    """
    Create a short-lived access token (60 minutes by default).
    Used for authenticating API requests.
    """
    return _create_token(
        subject=str(user_id),
        expires_delta=timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
        token_type="access",
        extra_claims={
            "agency_id": str(agency_id),
            "role": role,
        },
    )


def create_refresh_token(user_id: UUID | str) -> str:
    """
    Create a long-lived refresh token (7 days by default).
    Used only to obtain new access tokens; never sent on normal requests.
    """
    return _create_token(
        subject=str(user_id),
        expires_delta=timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
        token_type="refresh",
    )


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode and verify a JWT token.

    Raises:
        JWTError: If token is invalid, expired, or signature doesn't match.

    Returns:
        The decoded claims dict.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError as e:
        raise JWTError(f"Invalid or expired token: {e}")


def verify_access_token(token: str) -> Dict[str, Any]:
    """
    Verify an access token specifically and return its payload.
    Rejects refresh tokens (prevents them being used on protected endpoints).
    """
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise JWTError("Not an access token")
    return payload


def verify_refresh_token(token: str) -> Dict[str, Any]:
    """Verify a refresh token specifically and return its payload."""
    payload = decode_token(token)
    if payload.get("type") != "refresh":
        raise JWTError("Not a refresh token")
    return payload
