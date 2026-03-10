-- Add key_hash column for O(1) secure proxy validation lookup
ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS key_hash VARCHAR(64);

-- We cannot backfill easily in pure SQL because we need the app-level ENCRYPTION_KEY to decrypt encrypted_key
-- For this Phase 3 migration, all existing API keys will be un-resolvable until users issue new ones 
-- (fail-safe rather than storing insecure fallbacks).

CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);
