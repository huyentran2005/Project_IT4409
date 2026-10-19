-- Trường tùy chỉnh và giao diện đã lưu.
-- Nguồn: docs/database-design.md. Chạy qua database/migrate.sql.

CREATE TABLE custom_fields (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name varchar(80) NOT NULL,
    field_type custom_field_type NOT NULL,
    options jsonb NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(options) = 'array'),
    is_required boolean NOT NULL DEFAULT false,
    position numeric(20,10) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, project_id),
    UNIQUE (project_id, position)
);

CREATE UNIQUE INDEX uq_custom_fields_name_ci
ON custom_fields (project_id, lower(name));

CREATE TABLE task_custom_values (
    task_id uuid NOT NULL,
    field_id uuid NOT NULL,
    project_id uuid NOT NULL,
    value jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (task_id, field_id),
    FOREIGN KEY (task_id, project_id)
        REFERENCES tasks(id, project_id) ON DELETE CASCADE,
    FOREIGN KEY (field_id, project_id)
        REFERENCES custom_fields(id, project_id) ON DELETE CASCADE
);

CREATE TABLE saved_views (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL,
    user_id uuid NOT NULL,
    name varchar(100) NOT NULL,
    view_type varchar(20) NOT NULL
        CHECK (view_type IN ('board', 'list', 'calendar', 'timeline')),
    configuration jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(configuration) = 'object'),
    is_default boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (project_id, user_id)
        REFERENCES project_members(project_id, user_id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX uq_saved_views_name_ci
ON saved_views (project_id, user_id, lower(name));

CREATE UNIQUE INDEX uq_saved_views_one_default
ON saved_views (project_id, user_id, view_type)
WHERE is_default;
