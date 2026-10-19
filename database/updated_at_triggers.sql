-- Tự động cập nhật updated_at.
-- Nguồn: docs/database-design.md. Chạy qua database/migrate.sql.

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
