-- Initial schema from docs/database-design.md (2026-10-18).
-- Apply through database/migrate.sql; include paths are relative to this file.
-- Keep dependency order: accounts/projects, tasks, related tables, triggers, indexes.

\ir ../accounts_and_projects.sql
\ir ../workflow_sprints_and_tasks.sql
\ir ../labels_collaboration_and_files.sql
\ir ../project_documents_and_meetings.sql
\ir ../custom_fields_and_saved_views.sql
\ir ../notifications_and_audit_logs.sql
\ir ../updated_at_triggers.sql
\ir ../indexes.sql
\ir ../integrity_constraints.sql
