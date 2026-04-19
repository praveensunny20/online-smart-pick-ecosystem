"""
Auth service — business logic for user registration, login, invites,
email verification, and password reset.
"""
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple
from uuid import UUID

from jose import JWTError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.email import (
    EmailServiceError,
    send_invitation_email,
    send_password_reset_email,
    send_verification_email,
)
from app.core.security import (
    create_access_token,
    create_email_verify_token,
    create_password_reset_token,
    create_refresh_token,
    hash_password,
    verify_email_verify_token,
    verify_password,
    verify_password_reset_token,
)
from app.models import Agency, AgencyUser, SubscriptionTier, UserRole
from app.schemas.auth import AgencySignupRequest
from app.utils.slug import random_password, unique_slug

logger = logging.getLogger(__name__)


class AuthServiceError(Exception):
    """Raised by AuthService for known business-logic failures."""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class AuthService:
    """Encapsulates authentication business logic."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # -----------------------------------------------------------
    # SIGNUP
    # -----------------------------------------------------------
    async def signup_agency(
        self, data: AgencySignupRequest
    ) -> Tuple[Agency, AgencyUser, str, str]:
        """
        Register a brand new agency AND create its owner user.
        Sends a verification email asynchronously (best-effort).
        Returns: (agency, user, access_token, refresh_token)
        """
        existing = await self.db.execute(
            select(AgencyUser).where(AgencyUser.email == data.email.lower())
        )
        if existing.scalar_one_or_none() is not None:
            raise AuthServiceError("An account with this email already exists.", 409)

        agency = Agency(
            name=data.agency_name.strip(),
            slug=unique_slug(data.agency_name),
            subscription_tier=SubscriptionTier.FREE,
            is_active=True,
        )
        self.db.add(agency)
        await self.db.flush()

        user = AgencyUser(
            agency_id=agency.id,
            email=data.email.lower(),
            full_name=data.full_name.strip(),
            password_hash=hash_password(data.password),
            role=UserRole.OWNER,
            is_active=True,
            is_email_verified=False,
        )
        self.db.add(user)

        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            raise AuthServiceError("Could not create account due to a conflict.", 409)

        await self.db.refresh(agency)
        await self.db.refresh(user)

        # Send verification email (best-effort — don't fail signup if email fails)
        try:
            verify_token = create_email_verify_token(user_id=user.id, email=user.email)
            await send_verification_email(
                to=user.email,
                full_name=user.full_name,
                verify_token=verify_token,
            )
        except EmailServiceError as e:
            logger.warning("Verification email failed to send: %s", e)

        access_token = create_access_token(
            user_id=user.id, agency_id=agency.id, role=user.role.value
        )
        refresh_token = create_refresh_token(user_id=user.id)
        return agency, user, access_token, refresh_token

    # -----------------------------------------------------------
    # LOGIN
    # -----------------------------------------------------------
    async def authenticate(
        self, email: str, password: str
    ) -> Tuple[Agency, AgencyUser, str, str]:
        """Authenticate an existing user."""
        email_normalized = email.lower().strip()
        result = await self.db.execute(
            select(AgencyUser).where(AgencyUser.email == email_normalized)
        )
        user: Optional[AgencyUser] = result.scalar_one_or_none()

        # Use the same error for "no user" and "wrong password" to prevent enumeration
        if user is None or not verify_password(password, user.password_hash):
            raise AuthServiceError("Invalid email or password.", 401)

        if not user.is_active:
            raise AuthServiceError("This account has been disabled.", 403)

        user.last_login_at = datetime.now(timezone.utc)

        agency_result = await self.db.execute(
            select(Agency).where(Agency.id == user.agency_id)
        )
        agency = agency_result.scalar_one()

        if not agency.is_active:
            raise AuthServiceError("Your agency account has been disabled.", 403)

        await self.db.commit()
        await self.db.refresh(user)

        access_token = create_access_token(
            user_id=user.id, agency_id=agency.id, role=user.role.value
        )
        refresh_token = create_refresh_token(user_id=user.id)
        return agency, user, access_token, refresh_token

    async def refresh_access_token(self, user_id: UUID) -> Tuple[AgencyUser, str]:
        result = await self.db.execute(
            select(AgencyUser).where(AgencyUser.id == user_id)
        )
        user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            raise AuthServiceError("User not found or inactive.", 401)

        access_token = create_access_token(
            user_id=user.id, agency_id=user.agency_id, role=user.role.value
        )
        return user, access_token

    # -----------------------------------------------------------
    # INVITE
    # -----------------------------------------------------------
    async def invite_user(
        self,
        agency_id: UUID,
        email: str,
        full_name: str,
        role: UserRole,
    ) -> Tuple[AgencyUser, str]:
        """
        Create a new user under an existing agency with a temporary password.
        Sends an invitation email (best-effort) AND returns the temp password
        so the inviting admin always has a backup channel.
        """
        email_normalized = email.lower().strip()

        existing = await self.db.execute(
            select(AgencyUser).where(AgencyUser.email == email_normalized)
        )
        if existing.scalar_one_or_none() is not None:
            raise AuthServiceError("A user with this email already exists.", 409)

        if role == UserRole.OWNER:
            raise AuthServiceError(
                "Cannot invite another owner. Transfer ownership instead.", 400
            )

        temp_password = random_password(16)

        user = AgencyUser(
            agency_id=agency_id,
            email=email_normalized,
            full_name=full_name.strip(),
            password_hash=hash_password(temp_password),
            role=role,
            is_active=True,
            is_email_verified=False,
        )
        self.db.add(user)

        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            raise AuthServiceError("Could not create user due to a conflict.", 409)

        await self.db.refresh(user)

        # Load agency name for email
        agency_result = await self.db.execute(
            select(Agency).where(Agency.id == agency_id)
        )
        agency = agency_result.scalar_one()

        try:
            await send_invitation_email(
                to=user.email,
                full_name=user.full_name,
                agency_name=agency.name,
                temp_password=temp_password,
            )
        except EmailServiceError as e:
            logger.warning("Invitation email failed to send: %s", e)

        return user, temp_password

    # -----------------------------------------------------------
    # EMAIL VERIFICATION
    # -----------------------------------------------------------
    async def verify_email(self, token: str) -> AgencyUser:
        """Mark a user's email as verified based on a signed token."""
        try:
            payload = verify_email_verify_token(token)
        except JWTError as e:
            raise AuthServiceError(f"Invalid or expired verification link: {e}", 400)

        user_id = payload.get("sub")
        if not user_id:
            raise AuthServiceError("Malformed verification token.", 400)

        try:
            user_uuid = UUID(user_id)
        except ValueError:
            raise AuthServiceError("Malformed verification token.", 400)

        result = await self.db.execute(
            select(AgencyUser).where(AgencyUser.id == user_uuid)
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise AuthServiceError("User not found.", 404)

        if not user.is_email_verified:
            user.is_email_verified = True
            await self.db.commit()
            await self.db.refresh(user)

        return user

    async def resend_verification_email(self, user: AgencyUser) -> None:
        """Re-send the verification email for a user who hasn't verified yet."""
        if user.is_email_verified:
            raise AuthServiceError("Email is already verified.", 400)

        try:
            verify_token = create_email_verify_token(user_id=user.id, email=user.email)
            await send_verification_email(
                to=user.email,
                full_name=user.full_name,
                verify_token=verify_token,
            )
        except EmailServiceError as e:
            raise AuthServiceError(f"Failed to send verification email: {e}", 502)

    # -----------------------------------------------------------
    # PASSWORD RESET
    # -----------------------------------------------------------
    async def request_password_reset(self, email: str) -> None:
        """
        Send a password-reset email if the account exists.
        Always returns success to the caller (no user-enumeration).
        """
        email_normalized = email.lower().strip()
        result = await self.db.execute(
            select(AgencyUser).where(AgencyUser.email == email_normalized)
        )
        user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            # Silently succeed — don't leak which emails exist
            return

        try:
            token = create_password_reset_token(user_id=user.id, email=user.email)
            await send_password_reset_email(
                to=user.email,
                full_name=user.full_name,
                reset_token=token,
            )
        except EmailServiceError as e:
            logger.error("Password reset email failed: %s", e)
            # Still silent to caller

    async def confirm_password_reset(self, token: str, new_password: str) -> AgencyUser:
        """Set the user's password after verifying a reset token."""
        try:
            payload = verify_password_reset_token(token)
        except JWTError as e:
            raise AuthServiceError(f"Invalid or expired reset link: {e}", 400)

        user_id = payload.get("sub")
        if not user_id:
            raise AuthServiceError("Malformed reset token.", 400)

        try:
            user_uuid = UUID(user_id)
        except ValueError:
            raise AuthServiceError("Malformed reset token.", 400)

        result = await self.db.execute(
            select(AgencyUser).where(AgencyUser.id == user_uuid)
        )
        user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            raise AuthServiceError("User not found or inactive.", 404)

        try:
            user.password_hash = hash_password(new_password)
        except ValueError as e:
            raise AuthServiceError(str(e), 400)

        await self.db.commit()
        await self.db.refresh(user)
        return user
