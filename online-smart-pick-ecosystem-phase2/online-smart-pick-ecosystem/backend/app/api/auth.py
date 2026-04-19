"""
Authentication API routes.

Endpoints:
    POST   /auth/signup                     — Create a new agency + owner user
    POST   /auth/login                      — Authenticate, get tokens
    POST   /auth/refresh                    — Exchange refresh token for access
    GET    /auth/me                         — Get current user info
    GET    /auth/agency                     — Get current user's agency
    POST   /auth/invite                     — Invite a new user (admin only)
    POST   /auth/verify-email               — Confirm email via token        [Phase 2]
    POST   /auth/resend-verification        — Resend verification email      [Phase 2]
    POST   /auth/password-reset/request     — Request reset email            [Phase 2]
    POST   /auth/password-reset/confirm     — Reset password with token      [Phase 2]
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api.deps import get_current_user, require_admin
from app.core.config import settings
from app.core.security import verify_refresh_token
from app.db.session import get_db
from app.main_limiter import limiter
from app.models import Agency, AgencyUser
from app.schemas.auth import (
    AgencyPublicInfo,
    AgencySignupRequest,
    CurrentUser,
    InviteUserRequest,
    InviteUserResponse,
    LoginRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RefreshTokenRequest,
    RefreshTokenResponse,
    SimpleMessageResponse,
    TokenResponse,
    VerifyEmailRequest,
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


# ============================================================
# SIGNUP / LOGIN / REFRESH
# ============================================================

@router.post(
    "/signup",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new agency and owner account",
)
@limiter.limit(settings.RATE_LIMIT_SIGNUP_PER_HOUR)
async def signup(
    request: Request,  # required positional arg for slowapi
    data: AgencySignupRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new agency and its owner user.

    Returns access + refresh tokens so the client can start calling protected
    routes immediately. Also sends a verification email (best-effort).
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
@limiter.limit(settings.RATE_LIMIT_LOGIN_PER_MINUTE)
async def login(
    request: Request,
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


# ============================================================
# CURRENT USER
# ============================================================

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


# ============================================================
# INVITE
# ============================================================

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
    Create a new user in the current user's agency with a temporary password,
    and send them an invitation email. The temp password is also returned in
    the API response so the inviting admin has a backup channel.
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
            "User created and invitation email sent. Share the temporary "
            "password securely as a backup — they should change it on first login."
        ),
    )


# ============================================================
# PHASE 2: EMAIL VERIFICATION
# ============================================================

@router.post(
    "/verify-email",
    response_model=SimpleMessageResponse,
    summary="Confirm a user's email address using a verification token",
)
async def verify_email(
    data: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Public endpoint — the token in the request body is the proof of identity.
    Called when a user clicks the link in their verification email.
    """
    service = AuthService(db)
    try:
        user = await service.verify_email(data.token)
    except AuthServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    if user.is_email_verified:
        return SimpleMessageResponse(message="Email verified successfully.")
    return SimpleMessageResponse(message="Email could not be verified.")


@router.post(
    "/resend-verification",
    response_model=SimpleMessageResponse,
    summary="Resend the verification email for the currently authenticated user",
)
async def resend_verification(
    current_user: AgencyUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Auth required — we only resend to the logged-in user's own email."""
    service = AuthService(db)
    try:
        await service.resend_verification_email(current_user)
    except AuthServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return SimpleMessageResponse(
        message="Verification email sent. Please check your inbox."
    )


# ============================================================
# PHASE 2: PASSWORD RESET
# ============================================================

@router.post(
    "/password-reset/request",
    response_model=SimpleMessageResponse,
    summary="Request a password reset email",
)
@limiter.limit("5/hour")
async def request_password_reset(
    request: Request,
    data: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Always returns the same success message, whether or not the email exists,
    to prevent user enumeration.
    """
    service = AuthService(db)
    await service.request_password_reset(data.email)
    return SimpleMessageResponse(
        message=(
            "If an account exists for that email, a password-reset link has been sent. "
            "Please check your inbox."
        )
    )


@router.post(
    "/password-reset/confirm",
    response_model=SimpleMessageResponse,
    summary="Complete a password reset using the token from the email",
)
async def confirm_password_reset(
    data: PasswordResetConfirmRequest,
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint — the token proves identity."""
    service = AuthService(db)
    try:
        await service.confirm_password_reset(data.token, data.new_password)
    except AuthServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return SimpleMessageResponse(
        message="Password updated. Please log in with your new password."
    )
