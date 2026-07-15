ALTER TABLE scheduled_tasks
  ADD COLUMN fc_account_id VARCHAR(32) NULL,
  ADD COLUMN fc_region VARCHAR(32) NULL,
  ADD COLUMN fc_function_name VARCHAR(255) NULL,
  ADD COLUMN fc_trigger_name VARCHAR(255) NULL,
  ADD COLUMN fc_trigger_type VARCHAR(32) NULL DEFAULT 'timer',
  ADD COLUMN fc_qualifier VARCHAR(32) NULL DEFAULT 'LATEST',
  ADD COLUMN sync_status VARCHAR(32) NULL,
  ADD COLUMN sync_error_message TEXT NULL,
  ADD COLUMN last_synced_at DATETIME NULL;

