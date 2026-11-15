-- Quy tắc toàn vẹn.
-- Nguồn: docs/database-design.md. Được include bởi database/schema.sql.

CREATE UNIQUE INDEX uq_one_active_sprint_per_project
ON sprints (project_id) WHERE state = 'active';
