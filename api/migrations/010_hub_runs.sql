-- P1-09: Hub Execution Runs Tracking
CREATE TABLE IF NOT EXISTS hub_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    repo_url TEXT NOT NULL,
    task_prompt TEXT NOT NULL,
    status TEXT DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
    pr_url TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_hub_runs_user ON hub_runs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_hub_runs_status ON hub_runs(status);

-- Trigger to automatically update updated_at
CREATE OR REPLACE FUNCTION update_hub_runs_modtime()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS trg_hub_runs_update ON hub_runs;
CREATE TRIGGER trg_hub_runs_update
    BEFORE UPDATE ON hub_runs
    FOR EACH ROW
    EXECUTE PROCEDURE update_hub_runs_modtime();
