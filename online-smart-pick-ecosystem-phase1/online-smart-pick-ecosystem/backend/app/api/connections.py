"""
Platform connection API routes.

Connections are scoped under a client, which is scoped under an agency.
URL shape: /clients/{client_id}/connections
"""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_manager
from app.db.session import get_db
from app.models import AgencyUser
from app.schemas.clients import (
    PlatformConnectionCreateRequest,
    PlatformConnectionResponse,
)
from app.services.connection_service import ConnectionService, ConnectionServiceError

router = APIRouter(
    prefix="/clients/{client_id}/connections",
    tags=["platform-connections"],
)


@router.get(
    "",
    response_model=List[PlatformConnectionResponse],
    summary="List all platform connections for a client",
)
async def list_connections(
    client_id: UUID,
    current_user: AgencyUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ConnectionService(db)
    try:
        connections = await service.list_connections(client_id, current_user.agency_id)
    except ConnectionServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return [PlatformConnectionResponse.model_validate(c) for c in connections]


@router.post(
    "",
    response_model=PlatformConnectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Connect a new marketing platform for a client",
)
async def create_connection(
    client_id: UUID,
    data: PlatformConnectionCreateRequest,
    current_user: AgencyUser = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new platform connection. Credentials are AES-256 encrypted before storage.

    The response NEVER includes the credentials — only metadata.
    """
    service = ConnectionService(db)
    try:
        connection = await service.create_connection(
            client_id=client_id,
            agency_id=current_user.agency_id,
            data=data,
        )
    except ConnectionServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return PlatformConnectionResponse.model_validate(connection)


@router.delete(
    "/{connection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a platform connection",
)
async def delete_connection(
    client_id: UUID,
    connection_id: UUID,
    current_user: AgencyUser = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    service = ConnectionService(db)
    try:
        await service.delete_connection(
            connection_id=connection_id,
            client_id=client_id,
            agency_id=current_user.agency_id,
        )
    except ConnectionServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return None
