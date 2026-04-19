"""
FastAPI dependencies — functions that can be injected into route handlers.

Main purpose: extract and verify the JWT token on every protected request,
then load the current user from the database.

Phase 2 addition: set the `app.current_agency_id` Postgres GUC (Grand Unified
Configuration) so the RLS policies defined in the initial migration can enforce
tenant isolation at the database level. This is defense-in-depth: even if an
application-layer query forgot to filter by agency_id, the database would still
block cross-tenant reads.
"""
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_access_token
from app.db.session import get_db
from app.models import AgencyUser, UserRole


async def set_rls_context(db: AsyncSession, agency_id: UUID) -> None:
    """
    Set the Postgres session variable `app.current_agency_id` for the current
    transaction so RLS policies can reference it.

    Implementation note: we use `set_config(name, value, is_local=true)` instead
    of `SET LOCAL app.current_agency_id = '<uuid>'` because SET cannot use
    parameter binding. set_config() accepts binds cleanly and does the same
    thing (session setting scoped to the current transaction).
    """
    await db.execute(
        text("SELECT set_config('app.current_agency_id', :aid, true)").bindparams(
            aid=str(agency_id)
        )
    )


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

    Also sets the RLS GUC for the current DB transaction so tenant isolation
    applies at the database layer for every subsequent query in this request.
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

    # Defense-in-depth: set the RLS context for this request's DB session.
    # After this call, any query on tenant-scoped tables is also filtered
    # at the Postgres layer.
    await set_rls_context(db, user.agency_id)

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
