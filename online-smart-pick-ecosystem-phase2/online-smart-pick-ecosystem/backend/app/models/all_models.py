"""
SQLAlchemy ORM models.

These Python classes map to PostgreSQL tables. SQLAlchemy handles the translation.

Tables:
    - agencies: Top-level tenant (each marketing agency)
    - agency_users: Users who belong to an agency
    - clients: Marketing clients managed by an agency
    - platform_connections: Connected marketing platforms (Meta, Google, etc.)
    - unified_metrics_cache: Normalized metric data fetched from platforms
    - smart_picks_cache: AI-generated recommendations
    - reports: Generated PowerPoint/PDF/HTML reports
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


# ============================================================
# ENUMS
# ============================================================

class SubscriptionTier(str, enum.Enum):
    """Subscription tiers for agencies."""
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class UserRole(str, enum.Enum):
    """Roles within an agency."""
    OWNER = "owner"          # Full control, can delete agency
    ADMIN = "admin"          # Can manage all users and clients
    MANAGER = "manager"      # Can manage clients but not users
    VIEWER = "viewer"        # Read-only


class PlatformType(str, enum.Enum):
    """Supported marketing platforms."""
    GOOGLE_ANALYTICS = "google_analytics"
    GOOGLE_ADS = "google_ads"
    GOOGLE_SEARCH_CONSOLE = "google_search_console"
    META_ADS = "meta_ads"
    META_ORGANIC = "meta_organic"
    X_ADS = "x_ads"
    INSTAGRAM = "instagram"
    TIKTOK_ADS = "tiktok_ads"
    PINTEREST_ADS = "pinterest_ads"
    LINKEDIN_ADS = "linkedin_ads"
    EMAIL_MARKETING = "email_marketing"


class ConnectionStatus(str, enum.Enum):
    """Status of a platform connection."""
    PENDING = "pending"          # Connection initiated but not authenticated
    ACTIVE = "active"            # Working normally
    ERROR = "error"              # Sync failed (bad token, rate limit, etc.)
    DISCONNECTED = "disconnected"  # User manually disconnected


class ReportType(str, enum.Enum):
    """Report output formats."""
    PPTX = "pptx"
    PDF = "pdf"
    HTML = "html"


# ============================================================
# HELPER — timestamped base mixin
# ============================================================

def _utcnow() -> datetime:
    """Returns current time in UTC. Used as default for timestamp columns."""
    return datetime.now(timezone.utc)


# ============================================================
# TABLE 1: AGENCIES
# ============================================================

class Agency(Base):
    """
    Top-level tenant. Each agency is completely isolated from other agencies
    via row-level security policies (see migration).
    """
    __tablename__ = "agencies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    logo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    subscription_tier: Mapped[SubscriptionTier] = mapped_column(
        Enum(SubscriptionTier, name="subscription_tier_enum",
             values_callable=lambda e: [v.value for v in e]),
        default=SubscriptionTier.FREE,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    users: Mapped[list["AgencyUser"]] = relationship(
        back_populates="agency",
        cascade="all, delete-orphan",
    )
    clients: Mapped[list["Client"]] = relationship(
        back_populates="agency",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Agency(id={self.id}, name={self.name!r})>"


# ============================================================
# TABLE 2: AGENCY_USERS
# ============================================================

class AgencyUser(Base):
    """User account belonging to an agency."""
    __tablename__ = "agency_users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    agency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role_enum",
             values_callable=lambda e: [v.value for v in e]),
        default=UserRole.VIEWER,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    agency: Mapped["Agency"] = relationship(back_populates="users")

    __table_args__ = (
        Index("ix_agency_users_agency_email", "agency_id", "email"),
    )

    def __repr__(self) -> str:
        return f"<AgencyUser(id={self.id}, email={self.email!r}, role={self.role})>"


# ============================================================
# TABLE 3: CLIENTS
# ============================================================

class Client(Base):
    """A marketing client managed by an agency."""
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    agency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    primary_contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    agency: Mapped["Agency"] = relationship(back_populates="clients")
    platform_connections: Mapped[list["PlatformConnection"]] = relationship(
        back_populates="client",
        cascade="all, delete-orphan",
    )
    metrics: Mapped[list["UnifiedMetricCache"]] = relationship(
        back_populates="client",
        cascade="all, delete-orphan",
    )
    smart_picks: Mapped[list["SmartPickCache"]] = relationship(
        back_populates="client",
        cascade="all, delete-orphan",
    )
    reports: Mapped[list["Report"]] = relationship(
        back_populates="client",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("agency_id", "slug", name="uq_client_agency_slug"),
    )

    def __repr__(self) -> str:
        return f"<Client(id={self.id}, name={self.name!r})>"


# ============================================================
# TABLE 4: PLATFORM_CONNECTIONS
# ============================================================

class PlatformConnection(Base):
    """
    Connection to a marketing platform for a specific client.
    Credentials (OAuth tokens, API keys) are AES-256 encrypted.
    """
    __tablename__ = "platform_connections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform_type: Mapped[PlatformType] = mapped_column(
        Enum(PlatformType, name="platform_type_enum",
             values_callable=lambda e: [v.value for v in e]),
        nullable=False,
    )
    account_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Holds AES-256 encrypted JSON blob (tokens, refresh tokens, account ids, etc.)
    encrypted_credentials: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ConnectionStatus] = mapped_column(
        Enum(ConnectionStatus, name="connection_status_enum",
             values_callable=lambda e: [v.value for v in e]),
        default=ConnectionStatus.PENDING,
        nullable=False,
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    client: Mapped["Client"] = relationship(back_populates="platform_connections")

    __table_args__ = (
        UniqueConstraint(
            "client_id", "platform_type", "account_name",
            name="uq_platform_connection_unique",
        ),
    )

    def __repr__(self) -> str:
        return f"<PlatformConnection(client_id={self.client_id}, platform={self.platform_type})>"


# ============================================================
# TABLE 5: UNIFIED_METRICS_CACHE
# ============================================================

class UnifiedMetricCache(Base):
    """
    Normalized metric data from platforms.

    A "metric" is a single data point: a value for a specific metric name on a
    specific date from a specific platform for a specific client.

    Example rows:
        client_id=A, platform=meta_ads, metric=impressions, value=12345, date=2026-01-01
        client_id=A, platform=google_ads, metric=impressions, value=98765, date=2026-01-01
    """
    __tablename__ = "unified_metrics_cache"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform_type: Mapped[PlatformType] = mapped_column(
        Enum(PlatformType, name="platform_type_enum",
             values_callable=lambda e: [v.value for v in e]),
        nullable=False,
    )
    # Normalized metric name: "impressions", "clicks", "spend_usd", "ctr", "roas", etc.
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    # Date this metric corresponds to (not the fetch time). Usually a daily aggregate.
    metric_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Raw response from the platform — kept for auditing and re-processing
    raw_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Optional campaign/ad-level granularity
    campaign_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    campaign_name: Mapped[str | None] = mapped_column(String(500), nullable=True)

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    # Relationships
    client: Mapped["Client"] = relationship(back_populates="metrics")

    __table_args__ = (
        Index(
            "ix_metrics_client_platform_metric_date",
            "client_id", "platform_type", "metric_name", "metric_date",
        ),
        CheckConstraint("metric_value >= 0 OR metric_name IN ('roi', 'delta')",
                        name="check_metric_value_nonneg"),
    )

    def __repr__(self) -> str:
        return (
            f"<UnifiedMetricCache(client={self.client_id}, "
            f"platform={self.platform_type}, metric={self.metric_name}={self.metric_value})>"
        )


# ============================================================
# TABLE 6: SMART_PICKS_CACHE
# ============================================================

class SmartPickCache(Base):
    """
    AI-generated recommendations (Smart Picks) for a client.
    Generated nightly by the Claude AI engine (Phase 4).
    """
    __tablename__ = "smart_picks_cache"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Slug for the public review URL: /reviews/{slug}
    slug: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    # Confidence score from 0.0 to 1.0
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    # Structured list of data points that led to this recommendation
    data_points: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Suggested action: "shift_budget", "pause_campaign", "increase_bid", etc.
    recommended_action: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Which platforms are involved in this pick
    platforms_involved: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    is_dismissed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    client: Mapped["Client"] = relationship(back_populates="smart_picks")

    __table_args__ = (
        UniqueConstraint("client_id", "slug", name="uq_smart_pick_client_slug"),
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="check_confidence_range",
        ),
    )

    def __repr__(self) -> str:
        return f"<SmartPickCache(id={self.id}, title={self.title!r})>"


# ============================================================
# TABLE 7: REPORTS
# ============================================================

class Report(Base):
    """Generated reports (PPTX/PDF/HTML) for clients."""
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    report_type: Mapped[ReportType] = mapped_column(
        Enum(ReportType, name="report_type_enum",
             values_callable=lambda e: [v.value for v in e]),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    # URL or storage path where the file lives (S3 / local / etc.)
    file_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Public share token — if set, report is accessible by /reports/shared/{token}
    share_token: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)

    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    # When the share link expires
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    client: Mapped["Client"] = relationship(back_populates="reports")

    def __repr__(self) -> str:
        return f"<Report(id={self.id}, type={self.report_type}, title={self.title!r})>"
