-- Phase 6: ToS acceptance tracking
-- Created: Phase 6 Polish & Launch Prep

ALTER TABLE users ADD COLUMN IF NOT EXISTS tos_version VARCHAR(10) DEFAULT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS tos_accepted_at TIMESTAMPTZ DEFAULT NULL;
