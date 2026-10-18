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

SELECT format('ALTER DATABASE %I SET timezone TO %L', current_database(), 'UTC')
\gexec
COMMIT;
