ALTER TABLE users ADD COLUMN IF NOT EXISTS overage_enabled BOOLEAN DEFAULT false;
ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_subscription_id TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_status TEXT DEFAULT 'none' CHECK (subscription_status IN ('none', 'active', 'past_due', 'cancelled'));
ALTER TABLE users ADD COLUMN IF NOT EXISTS current_period_end TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS suspended_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS suspended_until TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS suspended_reason TEXT;

CREATE INDEX IF NOT EXISTS idx_users_subscription ON users(stripe_subscription_id);
CREATE INDEX IF NOT EXISTS idx_users_suspended ON users(suspended_at) WHERE suspended_at IS NOT NULL;

CREATE OR REPLACE FUNCTION deduct_credits(p_user_id UUID, p_amount INTEGER)
RETURNS INTEGER AS $$
DECLARE
    v_remaining INTEGER;
    v_overage BOOLEAN;
BEGIN
    SELECT credits_remaining, overage_enabled INTO v_remaining, v_overage
    FROM users WHERE id = p_user_id FOR UPDATE;

    IF v_remaining >= p_amount OR v_overage THEN
        UPDATE users SET credits_remaining = credits_remaining - p_amount
        WHERE id = p_user_id
        RETURNING credits_remaining INTO v_remaining;
        RETURN v_remaining;
    ELSE
        RETURN -1;  -- insufficient credits
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE IF NOT EXISTS usage_events_2026_05 PARTITION OF usage_events
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE IF NOT EXISTS audit_log_2026_04 PARTITION OF audit_log
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
