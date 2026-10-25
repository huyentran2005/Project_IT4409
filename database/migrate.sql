\set ON_ERROR_STOP on

BEGIN;
SET LOCAL search_path = public;
SET LOCAL timezone = 'UTC';
SELECT pg_advisory_xact_lock(4409, 1);

CREATE TABLE IF NOT EXISTS schema_migrations (
    version integer PRIMARY KEY,
    name text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now()
);

SELECT EXISTS (SELECT 1 FROM schema_migrations WHERE version = 1) AS already_applied
\gset

\if :already_applied
    \echo 'Migration 001 already applied; existing data preserved.'
\else
    \ir migrations/001_initial_schema.sql
    INSERT INTO schema_migrations (version, name)
    VALUES (1, 'initial_schema_from_database_design');
\endif

SELECT EXISTS (SELECT 1 FROM schema_migrations WHERE version = 2) AS migration_002_applied
\gset

\if :migration_002_applied
    \echo 'Migration 002 already applied; existing data preserved.'
\else
    \ir migrations/002_backfill_default_statuses.sql
    INSERT INTO schema_migrations (version, name)
    VALUES (2, 'backfill_default_project_statuses');
\endif

SELECT EXISTS (SELECT 1 FROM schema_migrations WHERE version = 3) AS migration_003_applied
\gset

\if :migration_003_applied
    \echo 'Migration 003 already applied; existing data preserved.'
\else
    \ir migrations/003_remove_status_wip_limits.sql
    INSERT INTO schema_migrations (version, name)
    VALUES (3, 'remove_status_wip_limits');
\endif

SELECT format('ALTER DATABASE %I SET timezone TO %L', current_database(), 'UTC')
\gexec
COMMIT;
