"""
Pydantic schemas for authentication flows.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import UserRole


class AgencySignupRequest(BaseModel):
    """Request body for POST /auth/signup — creates new agency + owner user."""
    agency_name: str = Field(..., min_length=2, max_length=255, description="Your agency's name")
    full_name: str = Field(..., min_length=2, max_length=255, description="Your full name")
    email: EmailStr = Field(..., description="Login email")
    password: str = Field(..., min_length=8, max_length=72, description="Password (8-72 chars)")

    @field_validator("password")
    @classmethod
    def password_must_have_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class LoginRequest(BaseModel):
    """Request body for POST /auth/login."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Response body for signup and login — contains JWT tokens."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user: "CurrentUser"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int


class CurrentUser(BaseModel):
    """Current authenticated user info (returned by /auth/me)."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    full_name: str
    role: UserRole
    agency_id: UUID
    agency_name: Optional[str] = None
    is_active: bool
    is_email_verified: bool
    created_at: datetime


class AgencyPublicInfo(BaseModel):
    """Public-facing agency information."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    logo_url: Optional[str] = None
    subscription_tier: str


class InviteUserRequest(BaseModel):
    """Request to invite a new user to an existing agency."""
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)
    role: UserRole = UserRole.VIEWER


class InviteUserResponse(BaseModel):
    user_id: UUID
    email: EmailStr
    role: UserRole
    temp_password: str = Field(
        ...,
        description="Temporary password the invited user should change on first login.",
    )
    message: str


# ---------------------------------------------------------------
# PHASE 2: Email verification + password reset
# ---------------------------------------------------------------

class VerifyEmailRequest(BaseModel):
    """Request to confirm an email verification token."""
    token: str


class PasswordResetRequest(BaseModel):
    """Request to START a password reset (sends email)."""
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    """Confirm a password reset using a token + new password."""
    token: str
    new_password: str = Field(..., min_length=8, max_length=72)

    @field_validator("new_password")
    @classmethod
    def strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class SimpleMessageResponse(BaseModel):
    message: str


# Rebuild forward reference
TokenResponse.model_rebuild()
