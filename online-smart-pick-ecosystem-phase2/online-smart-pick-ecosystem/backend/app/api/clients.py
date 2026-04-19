"""
Client API routes.

Endpoints:
    GET     /clients             — List all clients for the current agency
    POST    /clients             — Create a new client
    GET     /clients/{client_id} — Get one client
    PATCH   /clients/{client_id} — Update a client
    DELETE  /clients/{client_id} — Delete a client

All endpoints are scoped to the authenticated user's agency.
"""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_manager
from app.db.session import get_db
from app.models import AgencyUser
from app.schemas.clients import (
    ClientCreateRequest,
    ClientResponse,
    ClientUpdateRequest,
)
from app.services.client_service import ClientService, ClientServiceError

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get(
    "",
    response_model=List[ClientResponse],
    summary="List all clients for your agency",
)
async def list_clients(
    current_user: AgencyUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all clients under the current user's agency."""
    service = ClientService(db)
    clients = await service.list_clients(current_user.agency_id)
    return [ClientResponse.model_validate(c) for c in clients]


@router.post(
    "",
    response_model=ClientResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new client",
)
async def create_client(
    data: ClientCreateRequest,
    current_user: AgencyUser = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    """Create a new client under the current user's agency (manager+ role only)."""
    service = ClientService(db)
    try:
        client = await service.create_client(current_user.agency_id, data)
    except ClientServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return ClientResponse.model_validate(client)


@router.get(
    "/{client_id}",
    response_model=ClientResponse,
    summary="Get a single client by id",
)
async def get_client(
    client_id: UUID,
    current_user: AgencyUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ClientService(db)
    try:
        client = await service.get_client(client_id, current_user.agency_id)
    except ClientServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return ClientResponse.model_validate(client)


@router.patch(
    "/{client_id}",
    response_model=ClientResponse,
    summary="Update a client's details",
)
async def update_client(
    client_id: UUID,
    data: ClientUpdateRequest,
    current_user: AgencyUser = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    service = ClientService(db)
    try:
        client = await service.update_client(client_id, current_user.agency_id, data)
    except ClientServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return ClientResponse.model_validate(client)


@router.delete(
    "/{client_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a client (cascades to connections, metrics, reports)",
)
async def delete_client(
    client_id: UUID,
    current_user: AgencyUser = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    service = ClientService(db)
    try:
        await service.delete_client(client_id, current_user.agency_id)
    except ClientServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return None
