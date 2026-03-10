CREATE TABLE IF NOT EXISTS device_auth_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id TEXT NOT NULL,
    device_code_hash TEXT NOT NULL UNIQUE,
    user_code TEXT NOT NULL UNIQUE,
    state_nonce TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'authorized', 'consumed', 'expired', 'failed')),
    encrypted_refresh_token TEXT,
    workos_user_id TEXT,
    email TEXT,
    profile JSONB NOT NULL DEFAULT '{}'::jsonb,
    error TEXT,
    authorized_at TIMESTAMPTZ,
    consumed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_device_auth_sessions_status_expires
    ON device_auth_sessions (status, expires_at);

