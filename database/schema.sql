\set ON_ERROR_STOP on

-- Direct schema initialization. Run only against a new, empty database.
BEGIN;
SET LOCAL search_path = public;
SET LOCAL timezone = 'UTC';
SELECT pg_advisory_xact_lock(4409, 1);

\ir accounts_and_projects.sql
\ir workflow_sprints_and_tasks.sql
\ir labels_collaboration_and_files.sql
\ir project_documents_and_meetings.sql
\ir project_chatbot.sql
\ir custom_fields_and_saved_views.sql
\ir notifications_and_audit_logs.sql
\ir updated_at_triggers.sql
CREATE TRIGGER tr_project_chat_sessions_updated_at
BEFORE UPDATE ON project_chat_sessions FOR EACH ROW EXECUTE FUNCTION set_updated_at();
\ir indexes.sql
\ir integrity_constraints.sql

-- Keep the baseline Kanban workflow consistent with projects created after init.
INSERT INTO statuses (project_id, code, name, category, color, position, wip_limit)
SELECT p.id, defaults.code, defaults.name, defaults.category, defaults.color,
       defaults.position, defaults.wip_limit
FROM projects AS p
CROSS JOIN (VALUES
    ('backlog', 'Cần làm', 'todo', '#64748b', 1000::numeric, NULL),
    ('in-progress', 'Đang làm', 'in_progress', '#2563eb', 2000::numeric, NULL),
    ('review', 'Đang duyệt', 'in_progress', '#d97706', 3000::numeric, NULL),
    ('done', 'Hoàn thành', 'done', '#0f9f8f', 4000::numeric, NULL)
) AS defaults(code, name, category, color, position, wip_limit)
WHERE p.deleted_at IS NULL
ON CONFLICT DO NOTHING;
UPDATE statuses SET wip_limit = NULL WHERE wip_limit IS NOT NULL;

SELECT format('ALTER DATABASE %I SET timezone TO %L', current_database(), 'UTC')
\gexec
COMMIT;
