-- Source: docs/database-design.md (2026-10-18). Apply through database/migrate.sql.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TYPE task_type AS ENUM ('epic', 'story', 'task', 'bug');
CREATE TYPE task_priority AS ENUM ('urgent', 'high', 'medium', 'low');
CREATE TYPE sprint_state AS ENUM ('planned', 'active', 'completed', 'cancelled');
CREATE TYPE custom_field_type AS ENUM (
    'text', 'number', 'date', 'boolean', 'select', 'multi_select'
);

CREATE TABLE users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email varchar(320) NOT NULL,
    password_hash text,
    full_name varchar(120) NOT NULL,
    phone varchar(30),
    avatar_url text,
    avatar_color varchar(7) NOT NULL DEFAULT '#5B5CE2'
        CHECK (avatar_color ~ '^#[0-9A-Fa-f]{6}$'),
    email_verified_at timestamptz,
    locale varchar(10) NOT NULL DEFAULT 'vi',
    timezone varchar(50) NOT NULL DEFAULT 'Asia/Ho_Chi_Minh',
    is_active boolean NOT NULL DEFAULT true,
    last_login_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz
);
CREATE UNIQUE INDEX uq_users_email_active ON users (lower(email)) WHERE deleted_at IS NULL;

CREATE TABLE oauth_accounts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider varchar(20) NOT NULL CHECK (provider IN ('google', 'github')),
    provider_user_id varchar(255) NOT NULL,
    provider_email varchar(320),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (provider, provider_user_id),
    UNIQUE (user_id, provider)
);

CREATE TABLE auth_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    refresh_token_hash text NOT NULL UNIQUE,
    user_agent text,
    ip_address inet,
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE projects (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id uuid NOT NULL REFERENCES users(id),
    name varchar(160) NOT NULL,
    key varchar(8) NOT NULL,
    description text NOT NULL,
    color varchar(7) NOT NULL DEFAULT '#5B5CE2'
        CHECK (color ~ '^#[0-9A-Fa-f]{6}$'),
    icon varchar(50),
    timezone varchar(50) NOT NULL DEFAULT 'Asia/Ho_Chi_Minh',
    task_sequence bigint NOT NULL DEFAULT 0,
    is_archived boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz,
    CHECK (btrim(name) <> ''),
    CHECK (btrim(key) <> ''),
    CHECK (key ~ '^[A-Za-z0-9]{1,8}$'),
    CHECK (btrim(description) <> '')
);
CREATE UNIQUE INDEX uq_projects_key_active ON projects (upper(key)) WHERE deleted_at IS NULL;

CREATE TABLE permissions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code varchar(80) NOT NULL UNIQUE,
    name varchar(120) NOT NULL,
    description text
);

CREATE TABLE project_roles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    code varchar(40) NOT NULL,
    name varchar(80) NOT NULL,
    description text,
    is_system boolean NOT NULL DEFAULT false,
    position integer NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, project_id),
    UNIQUE (project_id, code)
);

CREATE UNIQUE INDEX uq_project_roles_name_ci
ON project_roles (project_id, lower(name));

CREATE TABLE project_role_permissions (
    role_id uuid NOT NULL REFERENCES project_roles(id) ON DELETE CASCADE,
    permission_id uuid NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    granted_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE project_members (
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id uuid NOT NULL,
    joined_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, user_id),
    FOREIGN KEY (role_id, project_id)
        REFERENCES project_roles(id, project_id)
);

CREATE TABLE project_invitations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    email varchar(320) NOT NULL,
    role_id uuid NOT NULL,
    token_hash text NOT NULL UNIQUE,
    invited_by uuid NOT NULL,
    expires_at timestamptz NOT NULL,
    accepted_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (role_id, project_id)
        REFERENCES project_roles(id, project_id),
    FOREIGN KEY (project_id, invited_by)
        REFERENCES project_members(project_id, user_id),
    CHECK (expires_at > created_at),
    CHECK (accepted_at IS NULL OR accepted_at >= created_at)
);

CREATE UNIQUE INDEX uq_project_invitations_pending
ON project_invitations (project_id, lower(email))
WHERE accepted_at IS NULL;

INSERT INTO permissions (code, name, description) VALUES
    ('project.manage',  'Quản lý dự án',     'Sửa thông tin và cấu hình dự án'),
    ('member.manage',   'Quản lý thành viên','Mời, đổi vai trò và xóa thành viên'),
    ('task.manage',     'Quản lý công việc', 'Tạo, sửa và di chuyển công việc'),
    ('document.manage', 'Quản lý tài liệu',  'Tải lên, cập nhật và xóa tài liệu'),
    ('project.view',    'Xem dự án',         'Xem bảng, thành viên và tài liệu')
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description;

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

CREATE TABLE project_documents (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    uploaded_by uuid NOT NULL,
    updated_by uuid NOT NULL,
    name varchar(255) NOT NULL,
    object_key text NOT NULL UNIQUE,
    mime_type varchar(150) NOT NULL,
    size_bytes bigint NOT NULL CHECK (size_bytes >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz,
    FOREIGN KEY (project_id, uploaded_by)
        REFERENCES project_members(project_id, user_id),
    FOREIGN KEY (project_id, updated_by)
        REFERENCES project_members(project_id, user_id)
);

CREATE TABLE meetings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    created_by uuid NOT NULL,
    title varchar(200) NOT NULL,
    description text,
    location varchar(255) NOT NULL,
    starts_at timestamptz NOT NULL,
    ends_at timestamptz NOT NULL,
    meeting_url text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    cancelled_at timestamptz,
    FOREIGN KEY (project_id, created_by)
        REFERENCES project_members(project_id, user_id),
    CHECK (ends_at > starts_at)
);

CREATE TABLE meeting_attendees (
    meeting_id uuid NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    response varchar(20) NOT NULL DEFAULT 'pending'
        CHECK (response IN ('pending', 'accepted', 'declined')), 
    PRIMARY KEY (meeting_id, user_id)
);

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

CREATE TABLE notifications (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id uuid REFERENCES projects(id) ON DELETE CASCADE,
    actor_id uuid REFERENCES users(id) ON DELETE SET NULL,
    type varchar(50) NOT NULL,
    title varchar(200) NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(payload) = 'object'),
    read_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE notification_settings (
    user_id uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    in_app_enabled boolean NOT NULL DEFAULT true,
    email_enabled boolean NOT NULL DEFAULT true,
    preferences jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(preferences) = 'object'),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE activity_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    actor_id uuid REFERENCES users(id) ON DELETE SET NULL,
    entity_type varchar(40) NOT NULL,
    entity_id uuid NOT NULL,
    action varchar(50) NOT NULL,
    description text NOT NULL,
    changes jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(changes) = 'object'),
    ip_address inet,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (entity_type IN ('task', 'timesheet', 'member', 'document', 'meeting')),
    CHECK (action IN ('created', 'updated', 'deleted', 'logged_time', 'meeting_created'))
);

CREATE FUNCTION set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER tr_users_updated_at
BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER tr_oauth_accounts_updated_at
BEFORE UPDATE ON oauth_accounts FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER tr_projects_updated_at
BEFORE UPDATE ON projects FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER tr_project_roles_updated_at
BEFORE UPDATE ON project_roles FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER tr_sprints_updated_at
BEFORE UPDATE ON sprints FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER tr_tasks_updated_at
BEFORE UPDATE ON tasks FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER tr_comments_updated_at
BEFORE UPDATE ON comments FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER tr_time_entries_updated_at
BEFORE UPDATE ON time_entries FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER tr_project_documents_updated_at
BEFORE UPDATE ON project_documents FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER tr_meetings_updated_at
BEFORE UPDATE ON meetings FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER tr_custom_fields_updated_at
BEFORE UPDATE ON custom_fields FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER tr_task_custom_values_updated_at
BEFORE UPDATE ON task_custom_values FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER tr_saved_views_updated_at
BEFORE UPDATE ON saved_views FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER tr_notification_settings_updated_at
BEFORE UPDATE ON notification_settings FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE INDEX ix_project_members_user ON project_members (user_id, project_id);
CREATE INDEX ix_auth_sessions_user_active ON auth_sessions (user_id, expires_at) WHERE revoked_at IS NULL;
CREATE INDEX ix_project_roles_project_position ON project_roles (project_id, position);
CREATE INDEX ix_role_permissions_permission ON project_role_permissions (permission_id, role_id);
CREATE INDEX ix_sprints_project_state ON sprints (project_id, state);
CREATE INDEX ix_tasks_board ON tasks (project_id, status_id, position) WHERE deleted_at IS NULL;
CREATE INDEX ix_tasks_sprint ON tasks (sprint_id, position) WHERE deleted_at IS NULL;
CREATE INDEX ix_tasks_schedule ON tasks (project_id, start_date, end_date) WHERE deleted_at IS NULL;
CREATE INDEX ix_tasks_due ON tasks (project_id, end_date) WHERE deleted_at IS NULL AND completed_at IS NULL;
CREATE INDEX ix_tasks_priority ON tasks (project_id, priority) WHERE deleted_at IS NULL;
CREATE INDEX ix_task_assignees_user ON task_assignees (user_id, task_id);
CREATE INDEX ix_tasks_reviewer ON tasks (project_id, reviewer_id) WHERE reviewer_id IS NOT NULL AND deleted_at IS NULL;
CREATE INDEX ix_task_links_target ON task_links (target_task_id, link_type);
CREATE INDEX ix_task_labels_label ON task_labels (label_id, task_id);
CREATE INDEX ix_comments_task_created ON comments (task_id, created_at) WHERE deleted_at IS NULL;
CREATE INDEX ix_time_entries_task_started ON time_entries (task_id, started_at DESC);
CREATE INDEX ix_time_entries_user_started ON time_entries (user_id, started_at DESC);
CREATE INDEX ix_task_watchers_user ON task_watchers (user_id, task_id);
CREATE INDEX ix_project_documents_project ON project_documents (project_id, updated_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX ix_meetings_project_start ON meetings (project_id, starts_at) WHERE cancelled_at IS NULL;
CREATE INDEX ix_notifications_unread ON notifications (user_id, created_at DESC) WHERE read_at IS NULL;
CREATE INDEX ix_notifications_user_created ON notifications (user_id, created_at DESC);
CREATE INDEX ix_activity_project_created ON activity_logs (project_id, created_at DESC);
CREATE INDEX ix_activity_entity ON activity_logs (entity_type, entity_id, created_at DESC);
CREATE INDEX ix_tasks_search ON tasks USING gin (search_vector) WHERE deleted_at IS NULL;

CREATE UNIQUE INDEX uq_one_active_sprint_per_project
ON sprints (project_id) WHERE state = 'active';
