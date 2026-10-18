\set ON_ERROR_STOP on

-- Exercise constraints using temporary fixture rows. Nothing is committed.
BEGIN;
SET LOCAL search_path = public;

DO $$
DECLARE
    user_a uuid;
    user_b uuid;
    project_a uuid;
    project_b uuid;
    role_a uuid;
    role_b uuid;
    status_a uuid;
    status_b uuid;
    task_a uuid;
    sprint_a uuid;
    sample_email text := gen_random_uuid()::text || '@database-check.invalid';
    calculated_minutes integer;
    changed_at timestamptz;
BEGIN
    IF (SELECT count(*) FROM pg_tables
        WHERE schemaname = 'public' AND tablename <> 'schema_migrations') <> 31 THEN
        RAISE EXCEPTION 'Expected 31 application tables';
    END IF;
    IF (SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND NOT t.tgisinternal) <> 14 THEN
        RAISE EXCEPTION 'Expected 14 updated_at triggers';
    END IF;
    IF (SELECT count(*) FROM permissions WHERE code IN
        ('project.manage', 'member.manage', 'task.manage', 'document.manage', 'project.view')) <> 5 THEN
        RAISE EXCEPTION 'Missing default permissions';
    END IF;

    INSERT INTO users (email, full_name, updated_at)
    VALUES (sample_email, 'Database verification A', '2000-01-01') RETURNING id INTO user_a;
    INSERT INTO users (email, full_name)
    VALUES (gen_random_uuid()::text || '@database-check.invalid', 'Database verification B')
    RETURNING id INTO user_b;
    BEGIN
        INSERT INTO users (email, full_name) VALUES (upper(sample_email), 'Duplicate email');
        RAISE EXCEPTION 'Case-insensitive email uniqueness did not reject a duplicate';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;
    UPDATE users SET full_name = 'Updated verification user' WHERE id = user_a
    RETURNING updated_at INTO changed_at;
    IF changed_at <> transaction_timestamp() THEN
        RAISE EXCEPTION 'updated_at trigger did not run';
    END IF;

    INSERT INTO projects (owner_id, name, key, description)
    VALUES (user_a, 'Verification A', left(replace(gen_random_uuid()::text, '-', ''), 8), 'Temporary fixture')
    RETURNING id INTO project_a;
    INSERT INTO projects (owner_id, name, key, description)
    VALUES (user_b, 'Verification B', left(replace(gen_random_uuid()::text, '-', ''), 8), 'Temporary fixture')
    RETURNING id INTO project_b;
    INSERT INTO project_roles (project_id, code, name, is_system)
    VALUES (project_a, 'owner', 'Owner', true) RETURNING id INTO role_a;
    INSERT INTO project_roles (project_id, code, name, is_system)
    VALUES (project_b, 'owner', 'Owner', true) RETURNING id INTO role_b;
    INSERT INTO project_members (project_id, user_id, role_id)
    VALUES (project_a, user_a, role_a), (project_b, user_b, role_b);
    INSERT INTO statuses (project_id, code, name, category, color, position)
    VALUES (project_a, 'backlog', 'Backlog', 'todo', '#5B5CE2', 1000) RETURNING id INTO status_a;
    INSERT INTO statuses (project_id, code, name, category, color, position)
    VALUES (project_b, 'backlog', 'Backlog', 'todo', '#5B5CE2', 1000) RETURNING id INTO status_b;
    INSERT INTO tasks (project_id, number, status_id, reporter_id, title, description,
                       position, start_date, end_date)
    VALUES (project_a, 1, status_a, user_a, 'Verification task', 'Searchable content',
            1000, '2026-10-01', '2026-10-02') RETURNING id INTO task_a;
    IF NOT (SELECT search_vector @@ to_tsquery('simple', 'searchable') FROM tasks WHERE id = task_a) THEN
        RAISE EXCEPTION 'Generated search_vector is incorrect';
    END IF;

    BEGIN
        UPDATE tasks SET status_id = status_b WHERE id = task_a;
        RAISE EXCEPTION 'Cross-project status was accepted';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;
    BEGIN
        UPDATE tasks SET reviewer_id = user_b WHERE id = task_a;
        RAISE EXCEPTION 'Cross-project reviewer was accepted';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;
    BEGIN
        INSERT INTO task_assignees (task_id, project_id, user_id) VALUES (task_a, project_a, user_b);
        RAISE EXCEPTION 'Cross-project assignee was accepted';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;
    BEGIN
        UPDATE tasks SET end_date = '2026-09-30' WHERE id = task_a;
        RAISE EXCEPTION 'Invalid task date range was accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;

    INSERT INTO time_entries (task_id, project_id, user_id, started_at, ended_at)
    VALUES (task_a, project_a, user_a, '2026-10-01 08:00:00+00', '2026-10-01 09:30:59+00')
    RETURNING minutes INTO calculated_minutes;
    IF calculated_minutes <> 90 THEN
        RAISE EXCEPTION 'Generated minutes should round down to 90, got %', calculated_minutes;
    END IF;
    BEGIN
        INSERT INTO time_entries (task_id, project_id, user_id, started_at, ended_at)
        VALUES (task_a, project_a, user_a, '2026-10-01 09:00:00+00', '2026-10-01 08:00:00+00');
        RAISE EXCEPTION 'Negative timesheet duration was accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;

    INSERT INTO sprints (project_id, name, state)
    VALUES (project_a, 'Active verification sprint', 'active') RETURNING id INTO sprint_a;
    BEGIN
        INSERT INTO sprints (project_id, name, state) VALUES (project_a, 'Another active sprint', 'active');
        RAISE EXCEPTION 'Multiple active sprints were accepted';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;
    UPDATE tasks SET sprint_id = sprint_a WHERE id = task_a;
    DELETE FROM sprints WHERE id = sprint_a;
    IF NOT EXISTS (SELECT 1 FROM tasks WHERE id = task_a AND project_id = project_a AND sprint_id IS NULL) THEN
        RAISE EXCEPTION 'Deleting a sprint did not preserve the task project';
    END IF;

    RAISE NOTICE 'PASS: schema, permissions, email uniqueness, updated_at, search, project isolation, dates, timesheets and sprints';
END;
$$;

ROLLBACK;
