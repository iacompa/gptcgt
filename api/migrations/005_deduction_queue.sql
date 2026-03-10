-- Deduction queue for retry logic
CREATE TABLE IF NOT EXISTS pending_deductions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workos_user_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    cost_credits INTEGER NOT NULL,
    attempts INTEGER DEFAULT 0,
    last_error TEXT,
    next_retry_at TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pending_deductions_retry ON pending_deductions(next_retry_at) 
    WHERE attempts < 5;
