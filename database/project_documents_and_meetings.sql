-- Tài liệu dự án và meeting.
-- Nguồn: docs/database-design.md. Chạy qua database/migrate.sql.

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
