ALTER TABLE hub_runs
    ADD COLUMN IF NOT EXISTS workspace_path TEXT;

ALTER TABLE hub_runs
    ADD COLUMN IF NOT EXISTS head_branch TEXT;

ALTER TABLE hub_runs
    ADD COLUMN IF NOT EXISTS base_branch TEXT;
