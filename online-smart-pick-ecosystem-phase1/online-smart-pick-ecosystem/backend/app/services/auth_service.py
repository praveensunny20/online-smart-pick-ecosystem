"""
Auth service — business logic for user registration, login, and invites.

Keeps DB writes + password hashing + token issuance out of API route handlers.
"""
from datetime import datetime, timezone
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.models import Agency, AgencyUser, SubscriptionTier, UserRole
from app.schemas.auth import AgencySignupRequest
from app.utils.slug import random_password, unique_slug


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

    async def signup_agency(
        self, data: AgencySignupRequest
    ) -> Tuple[Agency, AgencyUser, str, str]:
        """
        Register a brand new agency AND create its owner user in a single transaction.

        Returns: (agency, user, access_token, refresh_token)
        """
        # Check if email already exists
        existing = await self.db.execute(
            select(AgencyUser).where(AgencyUser.email == data.email.lower())
        )
        if existing.scalar_one_or_none() is not None:
            raise AuthServiceError("An account with this email already exists.", 409)

        # Create agency
        agency = Agency(
            name=data.agency_name.strip(),
            slug=unique_slug(data.agency_name),
            subscription_tier=SubscriptionTier.FREE,
            is_active=True,
        )
        self.db.add(agency)
        # Flush to get agency.id without committing
        await self.db.flush()

        # Create owner user
        user = AgencyUser(
            agency_id=agency.id,
            email=data.email.lower(),
            full_name=data.full_name.strip(),
            password_hash=hash_password(data.password),
            role=UserRole.OWNER,
            is_active=True,
            is_email_verified=False,  # Email verification is Phase 2
        )
        self.db.add(user)

        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            raise AuthServiceError("Could not create account due to a conflict.", 409)

        # Refresh to load server-defaults like created_at
        await self.db.refresh(agency)
        await self.db.refresh(user)

        access_token = create_access_token(
            user_id=user.id, agency_id=agency.id, role=user.role.value
        )
        refresh_token = create_refresh_token(user_id=user.id)

        return agency, user, access_token, refresh_token

    async def authenticate(
        self, email: str, password: str
    ) -> Tuple[Agency, AgencyUser, str, str]:
        """
        Authenticate an existing user.

        Returns: (agency, user, access_token, refresh_token)
        Raises AuthServiceError if credentials are invalid.
        """
        email_normalized = email.lower().strip()
        result = await self.db.execute(
            select(AgencyUser).where(AgencyUser.email == email_normalized)
        )
        user: Optional[AgencyUser] = result.scalar_one_or_none()

        # Use the same error for "no user" and "wrong password" to prevent user enumeration
        if user is None or not verify_password(password, user.password_hash):
            raise AuthServiceError("Invalid email or password.", 401)

        if not user.is_active:
            raise AuthServiceError("This account has been disabled.", 403)

        # Update last_login_at
        user.last_login_at = datetime.now(timezone.utc)

        # Load the agency
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
        """
        Issue a new access token using a valid refresh token.
        The caller is responsible for validating the refresh token signature.
        """
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

    async def invite_user(
        self,
        agency_id: UUID,
        email: str,
        full_name: str,
        role: UserRole,
    ) -> Tuple[AgencyUser, str]:
        """
        Invite a new user to an existing agency.

        In Phase 1, this creates the user with a generated temporary password
        that is returned to the inviting admin (who must share it with the invitee).
        Phase 2 will add email delivery.

        Returns: (user, temp_password)
        """
        email_normalized = email.lower().strip()

        # Check duplicate email
        existing = await self.db.execute(
            select(AgencyUser).where(AgencyUser.email == email_normalized)
        )
        if existing.scalar_one_or_none() is not None:
            raise AuthServiceError("A user with this email already exists.", 409)

        # Don't allow inviting another OWNER — only the signup flow creates owners
        if role == UserRole.OWNER:
            raise AuthServiceError("Cannot invite another owner. Transfer ownership instead.", 400)

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
        return user, temp_password
