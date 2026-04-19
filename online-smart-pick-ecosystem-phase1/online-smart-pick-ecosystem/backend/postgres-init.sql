-- =============================================================
-- Online Smart Pick Ecosystem — Postgres init script
-- =============================================================
-- Runs ONCE when the postgres Docker container is first created.
-- Lives at /docker-entrypoint-initdb.d/ inside the container.
--
-- What this does:
--   1. Install the pgcrypto extension so we can use gen_random_uuid()
--      as the default value for primary-key UUID columns.
--   2. Grant necessary permissions on the default database.
--
-- NOTE on row-level security:
--   The POSTGRES_USER defined in .env owns the database and is used by
--   BOTH migrations and the running app. This user is the database owner,
--   which in PostgreSQL causes RLS policies to be bypassed by default
--   unless you use `FORCE ROW LEVEL SECURITY`.
--
--   The Alembic migration uses `ALTER TABLE ... ENABLE ROW LEVEL SECURITY`.
--   For Phase 1, we keep app-layer filtering (WHERE agency_id = :x) as the
--   primary defense; RLS is a defense-in-depth layer that fully activates
--   in Phase 2 when we introduce a separate non-owner app role and switch
--   to `FORCE ROW LEVEL SECURITY`.
-- =============================================================

-- 1. Enable pgcrypto in the current database for gen_random_uuid() support.
--    Postgres 13+ actually has gen_random_uuid() built in, but keeping the
--    extension ensures compatibility and also gives us other crypto helpers.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 2. Confirm the extension is available
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pgcrypto') THEN
        RAISE EXCEPTION 'pgcrypto extension failed to install';
    END IF;
    RAISE NOTICE 'pgcrypto extension is installed';
END $$;
