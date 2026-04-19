"""
Client service — business logic for creating and managing clients.
All operations enforce agency scoping (a user can only touch their own agency's clients).
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Client
from app.schemas.clients import ClientCreateRequest, ClientUpdateRequest
from app.utils.slug import unique_slug


class ClientServiceError(Exception):
    """Raised by ClientService for known failures."""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ClientService:
    """Create, read, update, delete clients — always scoped to an agency."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_clients(self, agency_id: UUID) -> List[Client]:
        """Return all clients belonging to the given agency."""
        result = await self.db.execute(
            select(Client)
            .where(Client.agency_id == agency_id)
            .order_by(Client.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_client(self, client_id: UUID, agency_id: UUID) -> Client:
        """
        Fetch one client by id, checking that it belongs to the given agency.
        Raises 404 if not found (we don't leak whether the id exists in another agency).
        """
        result = await self.db.execute(
            select(Client).where(
                Client.id == client_id,
                Client.agency_id == agency_id,
            )
        )
        client = result.scalar_one_or_none()
        if client is None:
            raise ClientServiceError("Client not found.", 404)
        return client

    async def create_client(
        self, agency_id: UUID, data: ClientCreateRequest
    ) -> Client:
        """Create a new client under the given agency."""
        client = Client(
            agency_id=agency_id,
            name=data.name.strip(),
            slug=unique_slug(data.name),
            industry=data.industry.strip() if data.industry else None,
            logo_url=data.logo_url,
            primary_contact_email=(
                data.primary_contact_email.lower() if data.primary_contact_email else None
            ),
            is_active=True,
        )
        self.db.add(client)
        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            raise ClientServiceError("Could not create client due to a conflict.", 409)
        await self.db.refresh(client)
        return client

    async def update_client(
        self, client_id: UUID, agency_id: UUID, data: ClientUpdateRequest
    ) -> Client:
        """Update a client — only the fields that were provided in the request."""
        client = await self.get_client(client_id, agency_id)

        # Pydantic's model_dump(exclude_unset=True) gives us only the fields the
        # user actually sent — not defaults for missing ones
        updates = data.model_dump(exclude_unset=True)

        for field, value in updates.items():
            if field == "name" and value:
                setattr(client, field, value.strip())
            elif field == "industry" and value:
                setattr(client, field, value.strip())
            elif field == "primary_contact_email" and value:
                setattr(client, field, value.lower())
            else:
                setattr(client, field, value)

        await self.db.commit()
        await self.db.refresh(client)
        return client

    async def delete_client(self, client_id: UUID, agency_id: UUID) -> None:
        """
        Delete a client. Cascade deletes platform connections, metrics, smart picks,
        and reports because of ON DELETE CASCADE in the schema.
        """
        client = await self.get_client(client_id, agency_id)
        await self.db.delete(client)
        await self.db.commit()
