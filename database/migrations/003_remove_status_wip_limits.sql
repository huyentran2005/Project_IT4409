-- Không giới hạn số lượng task trong bất kỳ cột Kanban nào.
UPDATE statuses
SET wip_limit = NULL
WHERE wip_limit IS NOT NULL;
