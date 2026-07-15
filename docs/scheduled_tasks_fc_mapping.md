## 目标

以 `scheduled_tasks` 为配置真源，页面对任务的增删改查会同步映射到阿里云 FC 的 timer trigger，从而由 FC 原生定时触发执行；系统仅保留“立即执行”用于手工触发与调试。

## 映射规则

- FC Function Name ⇢ `scheduled_tasks.policy`
- FC Trigger Name ⇢ `scheduled_tasks.task_name`
- FC Trigger Config
  - `cronExpression` ⇢ `scheduled_tasks.cron_expression`
  - `payload` ⇢ `scheduled_tasks.payload`
  - `enable` ⇢ `scheduled_tasks.is_enabled`

## Payload 注入约定

系统在创建/更新 trigger 时会往 payload 注入以下字段（不影响原业务参数）：

- `__scheduled_task_id`: 对应 `scheduled_tasks.task_id`
- `__scheduled_task_name`: 对应 `scheduled_tasks.task_name`

业务入口统一解析事件时，会尝试根据上述字段回写 `scheduled_tasks.last_executed_at / last_executed_status`。

## 后端接口

- 获取任务列表：`GET /api/scheduled-tasks`
- 立即执行：`POST /api/scheduled-tasks/{id}/run`
- 新增任务（同步创建 trigger）：`POST /api/scheduled-tasks`
- 更新任务（同步更新 trigger）：`PUT /api/scheduled-tasks/{id}`
- 删除任务（同步删除 trigger）：`DELETE /api/scheduled-tasks/{id}`
- 清空并从 FC 初始化（FC → DB，然后再执行一次 DB → FC 注入）：`POST /api/scheduled-tasks/fc/init-from-fc`，body 必须包含 `{"confirm": true}`

## 数据库字段（FC 扩展）

`scheduled_tasks` 增加以下字段用于记录映射与同步状态：

- `fc_account_id`
- `fc_region`
- `fc_function_name`
- `fc_trigger_name`
- `fc_trigger_type`
- `fc_qualifier`
- `sync_status`：OK/FAILED/IMPORTED
- `sync_error_message`
- `last_synced_at`
