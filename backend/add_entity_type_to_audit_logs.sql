-- Add entity_type column to audit_logs table if it doesn't exist
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS entity_type VARCHAR(255) NOT NULL DEFAULT 'system';

-- Create index for entity_type if it doesn't exist
CREATE INDEX IF NOT EXISTS idx_audit_logs_entity_type ON audit_logs (entity_type);