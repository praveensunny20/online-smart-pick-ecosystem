"""Pydantic schemas for client and platform-connection routes."""
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import ConnectionStatus, PlatformType


# ============================================================
# CLIENTS
# ============================================================

class ClientCreateRequest(BaseModel):
    """Request to create a new client under an agency."""
    name: str = Field(..., min_length=2, max_length=255)
    industry: Optional[str] = Field(None, max_length=100)
    logo_url: Optional[str] = Field(None, max_length=512)
    primary_contact_email: Optional[EmailStr] = None


class ClientUpdateRequest(BaseModel):
    """Request to update an existing client — all fields optional."""
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    industry: Optional[str] = Field(None, max_length=100)
    logo_url: Optional[str] = Field(None, max_length=512)
    primary_contact_email: Optional[EmailStr] = None
    is_active: Optional[bool] = None


class ClientResponse(BaseModel):
    """Full client data returned from API."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agency_id: UUID
    name: str
    slug: str
    industry: Optional[str]
    logo_url: Optional[str]
    primary_contact_email: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ============================================================
# PLATFORM CONNECTIONS
# ============================================================

class PlatformConnectionCreateRequest(BaseModel):
    """Request to connect a new platform for a client."""
    platform_type: PlatformType
    account_name: Optional[str] = Field(None, max_length=255)
    # Plaintext credentials — will be encrypted before storing
    credentials: Dict[str, Any] = Field(
        ...,
        description="Platform credentials (OAuth tokens, API keys, etc.) — will be encrypted.",
        examples=[{"api_key": "xxx", "account_id": "12345"}],
    )


class PlatformConnectionResponse(BaseModel):
    """Platform connection info — credentials are NEVER returned."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    client_id: UUID
    platform_type: PlatformType
    account_name: Optional[str]
    status: ConnectionStatus
    last_synced_at: Optional[datetime]
    last_error_message: Optional[str]
    created_at: datetime
    updated_at: datetime
