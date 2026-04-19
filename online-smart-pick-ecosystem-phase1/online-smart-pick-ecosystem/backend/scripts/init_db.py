"""
Initialize the database with sample seed data.

Run this after `alembic upgrade head`. It is idempotent — if the seed agency
already exists, it prints "already seeded" and exits cleanly.

Usage (inside docker):
    docker compose exec backend python -m scripts.init_db

Usage (local venv, with Postgres running in Docker):
    cd backend
    python -m scripts.init_db
"""
import asyncio
import sys
from pathlib import Path

# Make `app.*` importable when running this script directly
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal, engine
from app.models import (
    Agency,
    AgencyUser,
    Client,
    SubscriptionTier,
    UserRole,
)
from app.utils.slug import unique_slug


async def seed(db: AsyncSession) -> None:
    """Create the seed agency + admin + 2 sample clients."""
    # Idempotency check — if seed admin already exists, skip
    existing = await db.execute(
        select(AgencyUser).where(AgencyUser.email == settings.SEED_ADMIN_EMAIL.lower())
    )
    if existing.scalar_one_or_none() is not None:
        print(f"✅ Database already seeded (user {settings.SEED_ADMIN_EMAIL} exists).")
        return

    print(f"🌱 Seeding database...")

    # 1. Create the seed agency
    agency = Agency(
        name=settings.SEED_AGENCY_NAME,
        slug=unique_slug(settings.SEED_AGENCY_NAME),
        subscription_tier=SubscriptionTier.PROFESSIONAL,
        is_active=True,
    )
    db.add(agency)
    await db.flush()
    print(f"   Created agency: {agency.name} ({agency.id})")

    # 2. Create the owner user
    admin = AgencyUser(
        agency_id=agency.id,
        email=settings.SEED_ADMIN_EMAIL.lower(),
        full_name="Admin User",
        password_hash=hash_password(settings.SEED_ADMIN_PASSWORD),
        role=UserRole.OWNER,
        is_active=True,
        is_email_verified=True,
    )
    db.add(admin)
    await db.flush()
    print(f"   Created admin user: {admin.email}")

    # 3. Create 2 sample clients
    sample_clients = [
        {
            "name": "Acme Corp",
            "industry": "SaaS",
            "primary_contact_email": "contact@acme.example",
        },
        {
            "name": "Sarah's Boutique",
            "industry": "E-commerce",
            "primary_contact_email": "sarah@boutique.example",
        },
    ]
    for cdata in sample_clients:
        client = Client(
            agency_id=agency.id,
            name=cdata["name"],
            slug=unique_slug(cdata["name"]),
            industry=cdata["industry"],
            primary_contact_email=cdata["primary_contact_email"],
            is_active=True,
        )
        db.add(client)
        print(f"   Created client: {cdata['name']}")

    await db.commit()

    print()
    print("=" * 60)
    print("  DATABASE SEEDED SUCCESSFULLY")
    print("=" * 60)
    print(f"  Login email:    {settings.SEED_ADMIN_EMAIL}")
    print(f"  Login password: {settings.SEED_ADMIN_PASSWORD}")
    print(f"  Agency:         {agency.name}")
    print(f"  Sample clients: {len(sample_clients)}")
    print("=" * 60)
    print()
    print("  ⚠️  Change the admin password after first login!")
    print()


async def main() -> None:
    # Quick sanity check: can we connect?
    async with engine.begin() as conn:
        from sqlalchemy import text
        result = await conn.execute(text("SELECT current_database(), current_user"))
        db_name, db_user = result.one()
        print(f"📦 Connected to database: {db_name} as user: {db_user}")

    async with AsyncSessionLocal() as session:
        await seed(session)


if __name__ == "__main__":
    asyncio.run(main())
