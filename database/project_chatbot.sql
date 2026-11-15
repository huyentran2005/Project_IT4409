-- Chatbot history is private to the user and project that own each session.
CREATE TABLE project_chat_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title varchar(180) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ix_project_chat_sessions_owner
    ON project_chat_sessions (project_id, user_id, updated_at DESC);

CREATE TABLE project_chat_messages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id uuid NOT NULL REFERENCES project_chat_sessions(id) ON DELETE CASCADE,
    role varchar(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    content text NOT NULL,
    sources jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ix_project_chat_messages_session
    ON project_chat_messages (session_id, created_at);
