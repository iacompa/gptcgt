-- Users (source of truth is WorkOS, this is our working copy)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workos_user_id TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    display_name TEXT,
    plan TEXT DEFAULT 'free' CHECK (plan IN ('free', 'pro', 'team', 'enterprise')),
    credits_remaining INTEGER DEFAULT 0,
    credits_monthly INTEGER DEFAULT 0,
    spending_cap INTEGER,                  -- User-set monthly max in dollars
    stripe_customer_id TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    last_active_at TIMESTAMPTZ
);

-- Organizations (Team and Enterprise plans)
CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workos_org_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    plan TEXT NOT NULL CHECK (plan IN ('team', 'enterprise')),
    seats_purchased INTEGER NOT NULL,
    shared_credits INTEGER DEFAULT 0,
    stripe_customer_id TEXT,
    sso_enabled BOOLEAN DEFAULT false,
    data_residency TEXT DEFAULT 'us' CHECK (data_residency IN ('us', 'eu')),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Org memberships
CREATE TABLE IF NOT EXISTS org_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    org_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    role TEXT DEFAULT 'member' CHECK (role IN ('owner', 'admin', 'member')),
    joined_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, org_id)
);

-- API key vault (encrypted, for managed BYOK at org level)
CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_type TEXT NOT NULL CHECK (owner_type IN ('user', 'org')),
    owner_id UUID NOT NULL,
    provider TEXT NOT NULL,               -- anthropic/openai/google/xai/deepseek
    encrypted_key BYTEA NOT NULL,          -- AES-256-GCM encrypted
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Usage tracking (append-only, high-volume, partitioned by month)
CREATE TABLE IF NOT EXISTS usage_events (
    id UUID DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    org_id UUID,
    task_mode TEXT NOT NULL,               -- scout/standard/ensemble/architect
    credits_consumed INTEGER NOT NULL,
    models_used TEXT[] NOT NULL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cached_tokens INTEGER,
    api_cost_cents INTEGER,                -- Actual API cost in cents
    task_type TEXT,                         -- bug_fix/feature/refactor/review
    language TEXT,
    success BOOLEAN,
    duration_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- Create monthly partitions
CREATE TABLE IF NOT EXISTS usage_events_2026_02 PARTITION OF usage_events
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
CREATE TABLE IF NOT EXISTS usage_events_2026_03 PARTITION OF usage_events
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');
CREATE TABLE IF NOT EXISTS usage_events_2026_04 PARTITION OF usage_events
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');

-- Conversations (optional cloud sync, encrypted)
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    project_hash TEXT,                     -- Hash of project root path (not the path itself)
    summary TEXT,
    messages_encrypted BYTEA,              -- AES-256-GCM encrypted
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Audit log (Enterprise only, partitioned by month)
CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL,
    org_id UUID,
    user_id UUID,
    action TEXT NOT NULL,
    details JSONB,
    ip_address INET,
    created_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

CREATE TABLE IF NOT EXISTS audit_log_2026_02 PARTITION OF audit_log
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
CREATE TABLE IF NOT EXISTS audit_log_2026_03 PARTITION OF audit_log
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');

-- Indexes
CREATE INDEX IF NOT EXISTS idx_users_workos ON users(workos_user_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_stripe ON users(stripe_customer_id);
CREATE INDEX IF NOT EXISTS idx_org_members_user ON org_members(user_id);
CREATE INDEX IF NOT EXISTS idx_org_members_org ON org_members(org_id);
CREATE INDEX IF NOT EXISTS idx_usage_user_date ON usage_events(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_usage_org_date ON usage_events(org_id, created_at);
CREATE INDEX IF NOT EXISTS idx_api_keys_owner ON api_keys(owner_type, owner_id);
