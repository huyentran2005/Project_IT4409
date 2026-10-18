-- Workflow, sprint và công việc.
-- Nguồn: docs/database-design.md. Chạy qua database/migrate.sql.

CREATE TABLE statuses (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    code varchar(40) NOT NULL,
    name varchar(80) NOT NULL,
    category varchar(20) NOT NULL CHECK (category IN ('todo','in_progress','done')),
    color varchar(7) NOT NULL,
    position numeric(20,10) NOT NULL,
    wip_limit integer CHECK (wip_limit IS NULL OR wip_limit > 0),
    UNIQUE (id, project_id),
    UNIQUE (project_id, code),
    UNIQUE (project_id, position),
    CHECK (code ~ '^[a-z][a-z0-9-]*$')
);

CREATE UNIQUE INDEX uq_statuses_name_ci
ON statuses (project_id, lower(name));

CREATE TABLE status_transitions (
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    from_status_id uuid NOT NULL,
    to_status_id uuid NOT NULL,
    PRIMARY KEY (project_id, from_status_id, to_status_id),
    FOREIGN KEY (from_status_id, project_id)
        REFERENCES statuses(id, project_id) ON DELETE CASCADE,
    FOREIGN KEY (to_status_id, project_id)
        REFERENCES statuses(id, project_id) ON DELETE CASCADE,
    CHECK (from_status_id <> to_status_id)
);

CREATE TABLE sprints (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name varchar(120) NOT NULL,
    goal text,
    state sprint_state NOT NULL DEFAULT 'planned',
    starts_at timestamptz,
    ends_at timestamptz,
    completed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, project_id),
    CHECK (ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at)
);

CREATE TABLE tasks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    number bigint NOT NULL,
    sprint_id uuid,
    status_id uuid NOT NULL,
    reporter_id uuid NOT NULL,
    reviewer_id uuid,
    type task_type NOT NULL DEFAULT 'task',
    priority task_priority NOT NULL DEFAULT 'medium',
    title varchar(300) NOT NULL,
    description text NOT NULL,
    overdue_reason text,
    acceptance_result text,
    position numeric(20,10) NOT NULL,
    start_date date NOT NULL,
    end_date date NOT NULL,
    completed_at timestamptz,
    search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(description, ''))
    ) STORED,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz,
    UNIQUE (id, project_id),
    UNIQUE (project_id, number),
    FOREIGN KEY (sprint_id, project_id)
        REFERENCES sprints(id, project_id) ON DELETE SET NULL (sprint_id),
    FOREIGN KEY (status_id, project_id)
        REFERENCES statuses(id, project_id),
    FOREIGN KEY (project_id, reporter_id)
        REFERENCES project_members(project_id, user_id),
    FOREIGN KEY (project_id, reviewer_id)
        REFERENCES project_members(project_id, user_id),
    CHECK (btrim(title) <> ''),
    CHECK (btrim(description) <> ''),
    CHECK (end_date >= start_date)
);

CREATE TABLE task_assignees (
    task_id uuid NOT NULL,
    project_id uuid NOT NULL,
    user_id uuid NOT NULL,
    assigned_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (task_id, user_id),
    FOREIGN KEY (task_id, project_id)
        REFERENCES tasks(id, project_id) ON DELETE CASCADE,
    FOREIGN KEY (project_id, user_id)
        REFERENCES project_members(project_id, user_id) ON DELETE CASCADE
);

CREATE TABLE task_links (
    project_id uuid NOT NULL,
    source_task_id uuid NOT NULL,
    target_task_id uuid NOT NULL,
    link_type varchar(20) NOT NULL CHECK (link_type IN ('blocks','relates','duplicates')),
    created_by uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (source_task_id, target_task_id, link_type),
    FOREIGN KEY (source_task_id, project_id)
        REFERENCES tasks(id, project_id) ON DELETE CASCADE,
    FOREIGN KEY (target_task_id, project_id)
        REFERENCES tasks(id, project_id) ON DELETE CASCADE,
    FOREIGN KEY (project_id, created_by)
        REFERENCES project_members(project_id, user_id),
    CHECK (source_task_id <> target_task_id)
);
