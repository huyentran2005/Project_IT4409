-- Tài khoản và dự án.
-- Nguồn: docs/database-design.md. Chạy qua database/migrate.sql.

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
