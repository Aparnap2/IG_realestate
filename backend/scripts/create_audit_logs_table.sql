-- Create audit_logs table for immutable compliance tracking
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR NOT NULL,
    entity_type VARCHAR NOT NULL,
    entity_id VARCHAR NOT NULL,
    agent_type VARCHAR,
    payload JSONB NOT NULL,
    hash VARCHAR NOT NULL,
    prev_hash VARCHAR,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    correlation_id UUID
);

-- Create indexes for performance (PostgreSQL syntax)
CREATE INDEX IF NOT EXISTS idx_audit_logs_entity_id ON audit_logs(entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_event_type ON audit_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_logs_entity_type ON audit_logs(entity_type);
CREATE INDEX IF NOT EXISTS idx_audit_logs_correlation_id ON audit_logs(correlation_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_hash ON audit_logs(hash);

-- Enable Row Level Security
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

-- Create policy for audit logs (read-only for most users)
CREATE POLICY "Audit logs are readable by authenticated users" ON audit_logs
    FOR SELECT USING (auth.role() = 'authenticated');

-- Create policy for system to insert audit logs
CREATE POLICY "System can insert audit logs" ON audit_logs
    FOR INSERT WITH CHECK (true);

-- Add comment
COMMENT ON TABLE audit_logs IS 'Immutable audit trail for compliance and debugging';