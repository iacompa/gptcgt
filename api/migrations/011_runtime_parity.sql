-- Align canonical schema with runtime expectations for Hub and billing.

ALTER TABLE teams
    ADD COLUMN IF NOT EXISTS overage_enabled BOOLEAN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'hub_runs' AND column_name = 'prompt'
    ) AND NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'hub_runs' AND column_name = 'task_prompt'
    ) THEN
        ALTER TABLE hub_runs RENAME COLUMN prompt TO task_prompt;
    END IF;
END $$;

ALTER TABLE hub_runs
    ADD COLUMN IF NOT EXISTS task_prompt TEXT;

UPDATE hub_runs
SET task_prompt = ''
WHERE task_prompt IS NULL;

ALTER TABLE hub_runs
    ALTER COLUMN task_prompt SET NOT NULL;

ALTER TABLE hub_runs
    ADD COLUMN IF NOT EXISTS logs TEXT NOT NULL DEFAULT '';

UPDATE users
SET subscription_status = 'cancelled'
WHERE subscription_status = 'canceled';

ALTER TABLE users
    DROP CONSTRAINT IF EXISTS users_subscription_status_check;

ALTER TABLE users
    ADD CONSTRAINT users_subscription_status_check
    CHECK (subscription_status IN ('none', 'active', 'past_due', 'cancelled'));
