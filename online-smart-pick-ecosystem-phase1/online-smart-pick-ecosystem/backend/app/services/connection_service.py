"""
Platform connection service.

When connecting a platform (Meta, Google Ads, etc.) for a client, the raw
credentials are AES-256 encrypted before being stored in the database.
The plaintext credentials never leave this service.
"""
from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import get_encryption_service
from app.models import ConnectionStatus, PlatformConnection, Client
from app.schemas.clients import PlatformConnectionCreateRequest


class ConnectionServiceError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ConnectionService:
    """Manage platform connections for a client's marketing platforms."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.encryption = get_encryption_service()

    async def _verify_client_access(self, client_id: UUID, agency_id: UUID) -> Client:
        """Check that the client exists and belongs to this agency."""
        result = await self.db.execute(
            select(Client).where(
                Client.id == client_id,
                Client.agency_id == agency_id,
            )
        )
        client = result.scalar_one_or_none()
        if client is None:
            raise ConnectionServiceError("Client not found.", 404)
        return client

    async def list_connections(
        self, client_id: UUID, agency_id: UUID
    ) -> List[PlatformConnection]:
        """List all platform connections for a client."""
        await self._verify_client_access(client_id, agency_id)

        result = await self.db.execute(
            select(PlatformConnection)
            .where(PlatformConnection.client_id == client_id)
            .order_by(PlatformConnection.created_at.desc())
        )
        return list(result.scalars().all())

    async def create_connection(
        self,
        client_id: UUID,
        agency_id: UUID,
        data: PlatformConnectionCreateRequest,
    ) -> PlatformConnection:
        """
        Create a new platform connection. Encrypts credentials before storing.
        """
        await self._verify_client_access(client_id, agency_id)

        if not data.credentials:
            raise ConnectionServiceError("Credentials cannot be empty.", 400)

        # Encrypt the entire credentials dict as a single blob
        encrypted_blob = self.encryption.encrypt_dict(data.credentials)

        connection = PlatformConnection(
            client_id=client_id,
            platform_type=data.platform_type,
            account_name=data.account_name,
            encrypted_credentials=encrypted_blob,
            status=ConnectionStatus.PENDING,
        )
        self.db.add(connection)

        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            raise ConnectionServiceError(
                "A connection for this platform + account already exists for this client.",
                409,
            )
        await self.db.refresh(connection)
        return connection

    async def get_decrypted_credentials(
        self, connection_id: UUID, agency_id: UUID
    ) -> dict:
        """
        Return the plaintext credentials for a connection.

        This method is used by the background sync worker (Phase 3) to actually
        fetch data from the external platforms. It should NEVER be exposed
        directly via an API endpoint.
        """
        result = await self.db.execute(
            select(PlatformConnection, Client)
            .join(Client, Client.id == PlatformConnection.client_id)
            .where(
                PlatformConnection.id == connection_id,
                Client.agency_id == agency_id,
            )
        )
        row = result.first()
        if row is None:
            raise ConnectionServiceError("Connection not found.", 404)

        connection, _ = row
        return self.encryption.decrypt_dict(connection.encrypted_credentials)

    async def delete_connection(
        self, connection_id: UUID, client_id: UUID, agency_id: UUID
    ) -> None:
        """Delete a platform connection."""
        await self._verify_client_access(client_id, agency_id)

        result = await self.db.execute(
            select(PlatformConnection).where(
                PlatformConnection.id == connection_id,
                PlatformConnection.client_id == client_id,
            )
        )
        connection = result.scalar_one_or_none()
        if connection is None:
            raise ConnectionServiceError("Connection not found.", 404)

        await self.db.delete(connection)
        await self.db.commit()
