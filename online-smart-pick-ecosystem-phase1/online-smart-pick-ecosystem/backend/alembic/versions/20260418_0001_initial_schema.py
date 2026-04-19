"""Initial schema - all tables + row-level security

Revision ID: 20260418_0001
Revises:
Create Date: 2026-04-18

This migration creates all 7 tables for the Online Smart Pick Ecosystem:
    - agencies, agency_users, clients, platform_connections,
      unified_metrics_cache, smart_picks_cache, reports

It also enables Row-Level Security (RLS) on tenant-scoped tables to guarantee
that one agency can never accidentally read another agency's data, even if the
application layer has a bug.

HOW RLS WORKS:
    - We enable RLS on each tenant table.
    - Each RLS policy checks a session variable `app.current_agency_id`.
    - The API layer sets this variable via `SET LOCAL app.current_agency_id = '<uuid>'`
      at the start of each request (Phase 2+). For Phase 1, we also keep app-layer
      filtering (WHERE agency_id = :x) so protection is layered.
    - The DB-level superuser / migration user has BYPASSRLS, so migrations and
      maintenance still work.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260418_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============================================================
    # ENUMS
    # ============================================================
    subscription_tier_enum = postgresql.ENUM(
        "free", "starter", "professional", "enterprise",
        name="subscription_tier_enum",
        create_type=False,
    )
    subscription_tier_enum.create(op.get_bind(), checkfirst=True)

    user_role_enum = postgresql.ENUM(
        "owner", "admin", "manager", "viewer",
        name="user_role_enum",
        create_type=False,
    )
    user_role_enum.create(op.get_bind(), checkfirst=True)

    platform_type_enum = postgresql.ENUM(
        "google_analytics",
        "google_ads",
        "google_search_console",
        "meta_ads",
        "meta_organic",
        "x_ads",
        "instagram",
        "tiktok_ads",
        "pinterest_ads",
        "linkedin_ads",
        "email_marketing",
        name="platform_type_enum",
        create_type=False,
    )
    platform_type_enum.create(op.get_bind(), checkfirst=True)

    connection_status_enum = postgresql.ENUM(
        "pending", "active", "error", "disconnected",
        name="connection_status_enum",
        create_type=False,
    )
    connection_status_enum.create(op.get_bind(), checkfirst=True)

    report_type_enum = postgresql.ENUM(
        "pptx", "pdf", "html",
        name="report_type_enum",
        create_type=False,
    )
    report_type_enum.create(op.get_bind(), checkfirst=True)

    # ============================================================
    # AGENCIES
    # ============================================================
    op.create_table(
        "agencies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("logo_url", sa.String(512), nullable=True),
        sa.Column("subscription_tier", subscription_tier_enum,
                  nullable=False, server_default="free"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_agencies_slug", "agencies", ["slug"], unique=True)

    # ============================================================
    # AGENCY_USERS
    # ============================================================
    op.create_table(
        "agency_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", user_role_enum, nullable=False, server_default="viewer"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_email_verified", sa.Boolean(), nullable=False,
                  server_default=sa.text("false")),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_agency_users_agency_id", "agency_users", ["agency_id"])
    op.create_index("ix_agency_users_email", "agency_users", ["email"], unique=True)
    op.create_index("ix_agency_users_agency_email", "agency_users", ["agency_id", "email"])

    # ============================================================
    # CLIENTS
    # ============================================================
    op.create_table(
        "clients",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("agency_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("industry", sa.String(100), nullable=True),
        sa.Column("logo_url", sa.String(512), nullable=True),
        sa.Column("primary_contact_email", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["agency_id"], ["agencies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agency_id", "slug", name="uq_client_agency_slug"),
    )
    op.create_index("ix_clients_agency_id", "clients", ["agency_id"])
    op.create_index("ix_clients_slug", "clients", ["slug"])

    # ============================================================
    # PLATFORM_CONNECTIONS
    # ============================================================
    op.create_table(
        "platform_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform_type", platform_type_enum, nullable=False),
        sa.Column("account_name", sa.String(255), nullable=True),
        sa.Column("encrypted_credentials", sa.Text(), nullable=False),
        sa.Column("status", connection_status_enum, nullable=False, server_default="pending"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "client_id", "platform_type", "account_name",
            name="uq_platform_connection_unique",
        ),
    )
    op.create_index("ix_platform_connections_client_id", "platform_connections", ["client_id"])

    # ============================================================
    # UNIFIED_METRICS_CACHE
    # ============================================================
    op.create_table(
        "unified_metrics_cache",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform_type", platform_type_enum, nullable=False),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=False),
        sa.Column("metric_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("campaign_id", sa.String(255), nullable=True),
        sa.Column("campaign_name", sa.String(500), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "metric_value >= 0 OR metric_name IN ('roi', 'delta')",
            name="check_metric_value_nonneg",
        ),
    )
    op.create_index("ix_unified_metrics_cache_client_id", "unified_metrics_cache", ["client_id"])
    op.create_index("ix_unified_metrics_cache_metric_name", "unified_metrics_cache", ["metric_name"])
    op.create_index("ix_unified_metrics_cache_campaign_id", "unified_metrics_cache", ["campaign_id"])
    op.create_index(
        "ix_metrics_client_platform_metric_date",
        "unified_metrics_cache",
        ["client_id", "platform_type", "metric_name", "metric_date"],
    )

    # ============================================================
    # SMART_PICKS_CACHE
    # ============================================================
    op.create_table(
        "smart_picks_cache",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("data_points", postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("recommended_action", sa.String(100), nullable=True),
        sa.Column("platforms_involved", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_dismissed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id", "slug", name="uq_smart_pick_client_slug"),
        sa.CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="check_confidence_range",
        ),
    )
    op.create_index("ix_smart_picks_cache_client_id", "smart_picks_cache", ["client_id"])
    op.create_index("ix_smart_picks_cache_slug", "smart_picks_cache", ["slug"])

    # ============================================================
    # REPORTS
    # ============================================================
    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("report_type", report_type_enum, nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("file_url", sa.String(1024), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("share_token", sa.String(64), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("share_token"),
    )
    op.create_index("ix_reports_client_id", "reports", ["client_id"])
    op.create_index("ix_reports_share_token", "reports", ["share_token"], unique=True)

    # ============================================================
    # ROW-LEVEL SECURITY
    # ============================================================
    # We use a session variable "app.current_agency_id" that the application
    # sets at the start of each authenticated request. Policies check that
    # agency_id = current_setting('app.current_agency_id')::uuid.
    #
    # For clients-adjacent tables (platform_connections, metrics, smart_picks,
    # reports), the policy joins through clients.agency_id.
    #
    # NOTE: The app's DB user needs to NOT be a superuser for RLS to apply.
    # In docker-compose, we create a non-superuser "smartpick" role. The
    # migration runs as superuser "postgres" — see init_db.py.

    # Enable RLS
    op.execute("ALTER TABLE agencies ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE agency_users ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE clients ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE platform_connections ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE unified_metrics_cache ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE smart_picks_cache ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE reports ENABLE ROW LEVEL SECURITY;")

    # Helper function: returns the current agency UUID from session variable,
    # or NULL if not set (which means "not in tenant context — see nothing").
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_current_agency_id()
        RETURNS uuid
        LANGUAGE plpgsql
        STABLE
        AS $$
        BEGIN
            RETURN NULLIF(current_setting('app.current_agency_id', true), '')::uuid;
        EXCEPTION WHEN others THEN
            RETURN NULL;
        END;
        $$;
        """
    )

    # --- AGENCIES: user can see their own agency row only ---
    op.execute(
        """
        CREATE POLICY agencies_tenant_isolation ON agencies
        USING (id = app_current_agency_id())
        WITH CHECK (id = app_current_agency_id());
        """
    )

    # --- AGENCY_USERS ---
    op.execute(
        """
        CREATE POLICY agency_users_tenant_isolation ON agency_users
        USING (agency_id = app_current_agency_id())
        WITH CHECK (agency_id = app_current_agency_id());
        """
    )

    # --- CLIENTS ---
    op.execute(
        """
        CREATE POLICY clients_tenant_isolation ON clients
        USING (agency_id = app_current_agency_id())
        WITH CHECK (agency_id = app_current_agency_id());
        """
    )

    # --- PLATFORM_CONNECTIONS: join through clients ---
    op.execute(
        """
        CREATE POLICY platform_connections_tenant_isolation ON platform_connections
        USING (
            client_id IN (
                SELECT id FROM clients WHERE agency_id = app_current_agency_id()
            )
        )
        WITH CHECK (
            client_id IN (
                SELECT id FROM clients WHERE agency_id = app_current_agency_id()
            )
        );
        """
    )

    # --- UNIFIED_METRICS_CACHE ---
    op.execute(
        """
        CREATE POLICY unified_metrics_tenant_isolation ON unified_metrics_cache
        USING (
            client_id IN (
                SELECT id FROM clients WHERE agency_id = app_current_agency_id()
            )
        )
        WITH CHECK (
            client_id IN (
                SELECT id FROM clients WHERE agency_id = app_current_agency_id()
            )
        );
        """
    )

    # --- SMART_PICKS_CACHE ---
    op.execute(
        """
        CREATE POLICY smart_picks_tenant_isolation ON smart_picks_cache
        USING (
            client_id IN (
                SELECT id FROM clients WHERE agency_id = app_current_agency_id()
            )
        )
        WITH CHECK (
            client_id IN (
                SELECT id FROM clients WHERE agency_id = app_current_agency_id()
            )
        );
        """
    )

    # --- REPORTS ---
    op.execute(
        """
        CREATE POLICY reports_tenant_isolation ON reports
        USING (
            client_id IN (
                SELECT id FROM clients WHERE agency_id = app_current_agency_id()
            )
        )
        WITH CHECK (
            client_id IN (
                SELECT id FROM clients WHERE agency_id = app_current_agency_id()
            )
        );
        """
    )


def downgrade() -> None:
    # Drop policies first, then tables, then enums
    for table in [
        "agencies", "agency_users", "clients", "platform_connections",
        "unified_metrics_cache", "smart_picks_cache", "reports",
    ]:
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
        op.execute(f"DROP POLICY IF EXISTS {table.replace('_cache', '').replace('agency_users', 'agency_users').replace('platform_connections', 'platform_connections').replace('unified_metrics_cache', 'unified_metrics')}_tenant_isolation ON {table};")

    op.execute("DROP FUNCTION IF EXISTS app_current_agency_id();")

    op.drop_table("reports")
    op.drop_table("smart_picks_cache")
    op.drop_table("unified_metrics_cache")
    op.drop_table("platform_connections")
    op.drop_table("clients")
    op.drop_table("agency_users")
    op.drop_table("agencies")

    for enum_name in [
        "report_type_enum",
        "connection_status_enum",
        "platform_type_enum",
        "user_role_enum",
        "subscription_tier_enum",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name};")
