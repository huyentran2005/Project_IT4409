\set ON_ERROR_STOP on
\getenv app_user TASKFLOW_DB_USER
\getenv app_password TASKFLOW_DB_PASSWORD
\getenv app_database TASKFLOW_DB_NAME

-- Run as a PostgreSQL administrator, connected to the postgres database.
-- Existing roles and databases are preserved, including their passwords.
SELECT format('CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD %L',
              :'app_user', :'app_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'app_user')
\gexec

-- CREATE DATABASE must run outside a transaction.
SELECT format('CREATE DATABASE %I OWNER %I ENCODING %L TEMPLATE template0',
              :'app_database', :'app_user', 'UTF8')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'app_database')
\gexec
