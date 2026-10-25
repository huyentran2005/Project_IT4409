-- Bổ sung các cột Kanban chuẩn cho những project được tạo trước API task.
INSERT INTO statuses (
    project_id,
    code,
    name,
    category,
    color,
    position,
    wip_limit
)
SELECT
    p.id,
    defaults.code,
    defaults.name,
    defaults.category,
    defaults.color,
    defaults.position,
    defaults.wip_limit
FROM projects AS p
CROSS JOIN (
    VALUES
        ('backlog',     'Cần làm',     'todo',        '#64748b', 1000::numeric, NULL),
        ('in-progress', 'Đang làm',    'in_progress', '#2563eb', 2000::numeric, NULL),
        ('review',      'Đang duyệt',  'in_progress', '#d97706', 3000::numeric, NULL),
        ('done',        'Hoàn thành',   'done',        '#0f9f8f', 4000::numeric, NULL)
) AS defaults(code, name, category, color, position, wip_limit)
WHERE p.deleted_at IS NULL
ON CONFLICT DO NOTHING;
