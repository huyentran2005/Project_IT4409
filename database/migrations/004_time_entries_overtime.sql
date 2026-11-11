-- Timesheet: đánh dấu giờ OT (làm ngoài giờ hành chính / cuối tuần).
-- Giờ OT không tính vào cảnh báo quá 8h/ngày.
ALTER TABLE time_entries
    ADD COLUMN IF NOT EXISTS is_overtime boolean NOT NULL DEFAULT false;

CREATE INDEX IF NOT EXISTS ix_time_entries_project_user_started
    ON time_entries (project_id, user_id, started_at DESC);
