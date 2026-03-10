CREATE TABLE IF NOT EXISTS team_invites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'member',
    invited_by TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT valid_role CHECK (role IN ('member', 'admin')),
    CONSTRAINT valid_status CHECK (status IN ('pending', 'accepted', 'cancelled', 'expired'))
);

CREATE INDEX IF NOT EXISTS idx_team_invites_team_status ON team_invites(team_id, status);
CREATE INDEX IF NOT EXISTS idx_team_invites_email ON team_invites(email);
