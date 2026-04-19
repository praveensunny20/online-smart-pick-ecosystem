"""
Pydantic schemas for authentication flows.

These are the shapes of JSON that go IN and OUT of API endpoints.
Pydantic validates them automatically.
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
        """Enforce basic password strength rules."""
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
    """Request body for POST /auth/refresh."""
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    """Response for token refresh — only new access token, not new refresh."""
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
    """Response after creating an invite — includes temp password for demo."""
    user_id: UUID
    email: EmailStr
    role: UserRole
    temp_password: str = Field(
        ...,
        description="Temporary password the invited user should change on first login.",
    )
    message: str


# Rebuild forward reference
TokenResponse.model_rebuild()
