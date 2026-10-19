-- Index quan trọng.
-- Nguồn: docs/database-design.md. Chạy qua database/migrate.sql.

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
