"""
FastAPI dependencies — functions that can be injected into route handlers.

Main purpose: extract and verify the JWT token on every protected request,
then load the current user from the database.
"""
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_access_token
from app.db.session import get_db
from app.models import AgencyUser, UserRole


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> AgencyUser:
    """
    FastAPI dependency that returns the authenticated user.

    Expects a header: `Authorization: Bearer <jwt_access_token>`

    Raises 401 if:
        - No Authorization header
        - Header format is wrong
        - Token is expired / invalid / wrong type
        - User doesn't exist or is inactive
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Parse "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must be 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = parts[1]

    # Verify signature and expiry
    try:
        payload = verify_access_token(token)
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim",
        )

    try:
        user_id = UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user id in token",
        )

    # Load user from DB
    result = await db.execute(select(AgencyUser).where(AgencyUser.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    return user


def require_role(*allowed_roles: UserRole):
    """
    Returns a dependency that requires the current user to have one of the given roles.

    Usage:
        @router.delete("/agencies")
        async def delete_agency(
            user: AgencyUser = Depends(require_role(UserRole.OWNER))
        ):
            ...
    """

    async def _checker(
        current_user: AgencyUser = Depends(get_current_user),
    ) -> AgencyUser:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Requires one of these roles: "
                    f"{', '.join(r.value for r in allowed_roles)}"
                ),
            )
        return current_user

    return _checker


# Common role-requirement shortcuts
require_owner = require_role(UserRole.OWNER)
require_admin = require_role(UserRole.OWNER, UserRole.ADMIN)
require_manager = require_role(UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER)
