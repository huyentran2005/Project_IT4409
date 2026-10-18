-- Nhãn, cộng tác và file.
-- Nguồn: docs/database-design.md. Chạy qua database/migrate.sql.

CREATE TABLE labels (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name varchar(60) NOT NULL,
    color varchar(7) NOT NULL,
    UNIQUE (id, project_id)
);

CREATE UNIQUE INDEX uq_labels_name_ci
ON labels (project_id, lower(name));

CREATE TABLE task_labels (
    task_id uuid NOT NULL,
    label_id uuid NOT NULL,
    project_id uuid NOT NULL,
    PRIMARY KEY (task_id, label_id),
    FOREIGN KEY (task_id, project_id)
        REFERENCES tasks(id, project_id) ON DELETE CASCADE,
    FOREIGN KEY (label_id, project_id)
        REFERENCES labels(id, project_id) ON DELETE CASCADE
);

CREATE TABLE checklist_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id uuid NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    title varchar(300) NOT NULL,
    is_completed boolean NOT NULL DEFAULT false,
    position numeric(20,10) NOT NULL,
    completed_by uuid REFERENCES users(id) ON DELETE SET NULL,
    completed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE comments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id uuid NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    author_id uuid NOT NULL REFERENCES users(id),
    parent_id uuid REFERENCES comments(id) ON DELETE CASCADE,
    body text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz
);

CREATE TABLE attachments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id uuid NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    uploaded_by uuid NOT NULL REFERENCES users(id),
    object_key text NOT NULL UNIQUE,
    original_name varchar(255) NOT NULL,
    mime_type varchar(150) NOT NULL,
    size_bytes bigint NOT NULL CHECK (size_bytes >= 0),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE task_watchers (
    task_id uuid NOT NULL,
    project_id uuid NOT NULL,
    user_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (task_id, user_id),
    FOREIGN KEY (task_id, project_id)
        REFERENCES tasks(id, project_id) ON DELETE CASCADE,
    FOREIGN KEY (project_id, user_id)
        REFERENCES project_members(project_id, user_id) ON DELETE CASCADE
);

CREATE TABLE time_entries (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id uuid NOT NULL,
    project_id uuid NOT NULL,
    user_id uuid NOT NULL,
    started_at timestamptz NOT NULL,
    ended_at timestamptz NOT NULL,
    minutes integer GENERATED ALWAYS AS
        (floor(extract(epoch FROM (ended_at - started_at)) / 60)::integer) STORED,
    note text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (task_id, project_id)
        REFERENCES tasks(id, project_id) ON DELETE CASCADE,
    FOREIGN KEY (project_id, user_id)
        REFERENCES project_members(project_id, user_id),
    CHECK (ended_at > started_at)
);
