## 目标

以 `scheduled_tasks` 为配置真源，页面对任务的增删改查会同步映射到阿里云 FC 的 timer trigger，从而由 FC 原生定时触发执行；系统仅保留“立即执行”用于手工触发与调试。

## 映射规则

- FC Function Name ⇢ `scheduled_tasks.policy`
- FC Trigger Name ⇢ `scheduled_tasks.task_name`
- FC Trigger Config
  - `cronExpression` ⇢ `scheduled_tasks.cron_expression`
  - `payload` ⇢ `scheduled_tasks.payload`
  - `enable` ⇢ `scheduled_tasks.is_enabled`

## Payload 约定

- 当前实现会尽量保持业务 payload 原样，不再依赖注入内部元数据字段。
- 任务执行状态回写优先通过以下信息识别任务：
  - `scheduled_tasks.task_name`
  - `scheduled_tasks.fc_trigger_name`
  - `scheduled_tasks.policy`
  - `scheduled_tasks.fc_function_name`
- 仅在历史兼容场景下，若 payload 中仍带有下列字段，系统也会继续识别：

- `__scheduled_task_id`: 对应 `scheduled_tasks.task_id`
- `__scheduled_task_name`: 对应 `scheduled_tasks.task_name`

业务入口统一解析事件时，会尝试根据上述标识回写 `scheduled_tasks.last_executed_at / last_executed_status`。

## 后端接口

- 获取任务列表：`GET /api/scheduled-tasks`
- 立即执行：`POST /api/scheduled-tasks/{id}/run`
- 新增任务（同步创建 trigger）：`POST /api/scheduled-tasks`
- 更新任务（同步更新 trigger）：`PUT /api/scheduled-tasks/{id}`
- 删除任务（同步删除 trigger）：`DELETE /api/scheduled-tasks/{id}`
- 从 FC 同步任务配置：`POST /api/scheduled-tasks/fc/sync-from-fc`

## 执行链路

- 定时触发：FC timer trigger -> `src.task.*` -> `bussiness/service`
- 立即执行：管理接口 -> FC OpenAPI `InvokeFunction` -> 云端函数执行
- 本地兼容执行：`src/scheduled_tasks/executor.py` 仍保留对历史 `index.py` 入口的回退，供迁移期兼容使用

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
