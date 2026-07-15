-- 清理 scheduled_tasks.payload 中残留的 __scheduled_task_id / __scheduled_task_name 元数据字段
-- 这些字段之前被意外注入并存储，现在代码层已完全剔除

UPDATE scheduled_tasks
SET payload = JSON_REMOVE(
    JSON_REMOVE(payload, '$.__scheduled_task_id'),
    '$.__scheduled_task_name'
)
WHERE JSON_EXTRACT(payload, '$.__scheduled_task_id') IS NOT NULL
   OR JSON_EXTRACT(payload, '$.__scheduled_task_name') IS NOT NULL;
