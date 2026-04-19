"""
Authentication API routes.

Endpoints:
    POST   /auth/signup      — Create a new agency + owner user
    POST   /auth/login       — Authenticate, get access + refresh tokens
    POST   /auth/refresh     — Exchange refresh token for a new access token
    GET    /auth/me          — Get info about currently logged-in user
    POST   /auth/invite      — Invite a new user to the current agency (admin only)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api.deps import get_current_user, require_admin
from app.core.config import settings
from app.core.security import verify_refresh_token
from app.db.session import get_db
from app.models import Agency, AgencyUser
from app.schemas.auth import (
    AgencyPublicInfo,
    AgencySignupRequest,
    CurrentUser,
    InviteUserRequest,
    InviteUserResponse,
    LoginRequest,
    RefreshTokenRequest,
    RefreshTokenResponse,
    TokenResponse,
)
from app.services.auth_service import AuthService, AuthServiceError

router = APIRouter(prefix="/auth", tags=["auth"])


def _to_current_user(user: AgencyUser, agency_name: str | None = None) -> CurrentUser:
    """Build the CurrentUser response object from an AgencyUser model."""
    return CurrentUser(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        agency_id=user.agency_id,
        agency_name=agency_name,
        is_active=user.is_active,
        is_email_verified=user.is_email_verified,
        created_at=user.created_at,
    )


@router.post(
    "/signup",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new agency and owner account",
)
async def signup(
    data: AgencySignupRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new agency and its owner user.

    Returns access + refresh tokens so the client can start calling protected routes
    immediately.
    """
    service = AuthService(db)
    try:
        agency, user, access_token, refresh_token = await service.signup_agency(data)
    except AuthServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in_minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
        user=_to_current_user(user, agency_name=agency.name),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and receive JWT tokens",
)
async def login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate with email + password, get access + refresh tokens."""
    service = AuthService(db)
    try:
        agency, user, access_token, refresh_token = await service.authenticate(
            data.email, data.password
        )
    except AuthServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in_minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
        user=_to_current_user(user, agency_name=agency.name),
    )


@router.post(
    "/refresh",
    response_model=RefreshTokenResponse,
    summary="Get a new access token using a refresh token",
)
async def refresh(
    data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Exchange a valid refresh token for a fresh access token.
    Refresh tokens are long-lived (7 days), access tokens are short-lived (60 min).
    """
    try:
        payload = verify_refresh_token(data.refresh_token)
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)
        )

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing subject in refresh token",
        )

    try:
        user_id = UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user id in refresh token",
        )

    service = AuthService(db)
    try:
        _, access_token = await service.refresh_access_token(user_id)
    except AuthServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    return RefreshTokenResponse(
        access_token=access_token,
        expires_in_minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    )


@router.get(
    "/me",
    response_model=CurrentUser,
    summary="Get info about the currently authenticated user",
)
async def me(
    current_user: AgencyUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the currently logged-in user's profile."""
    agency_result = await db.execute(
        select(Agency).where(Agency.id == current_user.agency_id)
    )
    agency = agency_result.scalar_one_or_none()
    return _to_current_user(current_user, agency_name=agency.name if agency else None)


@router.get(
    "/agency",
    response_model=AgencyPublicInfo,
    summary="Get the currently authenticated user's agency info",
)
async def my_agency(
    current_user: AgencyUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    agency_result = await db.execute(
        select(Agency).where(Agency.id == current_user.agency_id)
    )
    agency = agency_result.scalar_one_or_none()
    if agency is None:
        raise HTTPException(status_code=404, detail="Agency not found")
    return AgencyPublicInfo(
        id=agency.id,
        name=agency.name,
        slug=agency.slug,
        logo_url=agency.logo_url,
        subscription_tier=agency.subscription_tier.value,
    )


@router.post(
    "/invite",
    response_model=InviteUserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Invite a new user to your agency (admin/owner only)",
)
async def invite_user(
    data: InviteUserRequest,
    current_user: AgencyUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new user in the current user's agency with a temporary password.

    In Phase 1, the temp password is returned in the response so the inviting
    admin can share it with the invitee. Phase 2 will add email delivery.
    """
    service = AuthService(db)
    try:
        user, temp_password = await service.invite_user(
            agency_id=current_user.agency_id,
            email=data.email,
            full_name=data.full_name,
            role=data.role,
        )
    except AuthServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    return InviteUserResponse(
        user_id=user.id,
        email=user.email,
        role=user.role,
        temp_password=temp_password,
        message=(
            "User created. Share the temporary password securely with the invitee. "
            "They should change it on first login."
        ),
    )
