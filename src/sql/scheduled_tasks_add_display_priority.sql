ALTER TABLE scheduled_tasks
ADD COLUMN display_priority INT NOT NULL DEFAULT 100 AFTER is_enabled;

UPDATE scheduled_tasks
SET display_priority = 100
WHERE display_priority IS NULL;

CREATE INDEX idx_display_priority ON scheduled_tasks (display_priority);

