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
    correlation_id UUID,
    
    -- Indexes for performance
    INDEX idx_audit_logs_entity_id (entity_id),
    INDEX idx_audit_logs_event_type (event_type),
    INDEX idx_audit_logs_timestamp (timestamp),
    INDEX idx_audit_logs_correlation_id (correlation_id)
);

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