-- Migration: Create webhook_events table for Stripe idempotency
-- This table MUST exist before the API handles webhooks.
-- Previously created dynamically at runtime (P1-11 audit finding).

CREATE TABLE IF NOT EXISTS webhook_events (
    event_id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'received',
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE webhook_events ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'received';

-- Auto-cleanup: remove events older than 90 days to prevent bloat
-- (run periodically via cron or pg_cron)
-- DELETE FROM webhook_events WHERE processed_at < NOW() - INTERVAL '90 days';
