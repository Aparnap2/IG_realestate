-- Migration script to add leads_channel_check constraint
-- This script ensures the channel field has proper validation

-- First, check if the constraint already exists
DO $$
BEGIN
    -- Drop the existing constraint if it exists (to avoid conflicts)
    IF EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'leads_channel_check' 
        AND table_name = 'leads'
    ) THEN
        RAISE NOTICE 'Dropping existing leads_channel_check constraint';
        ALTER TABLE leads DROP CONSTRAINT leads_channel_check;
    END IF;
END $$;

-- Update any existing records that might have invalid channel values
-- Set them to 'instagram' as a safe default
UPDATE leads
SET channel = 'instagram'
WHERE channel IS NULL OR channel NOT IN ('instagram', ' ', 'web', 'email', ' ');

-- Add the constraint with proper channel values
ALTER TABLE leads
ADD CONSTRAINT leads_channel_check
CHECK (channel IN ('instagram', ' ', 'web', 'email', ' '));

-- Verify the constraint was added successfully
SELECT
    conname as constraint_name,
    contype as constraint_type,
    pg_get_constraintdef(oid) as constraint_definition
FROM pg_constraint
WHERE conrelid = 'leads'::regclass
    AND conname = 'leads_channel_check';

-- Show current channel distribution
SELECT 
    channel, 
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as percentage
FROM leads 
GROUP BY channel 
ORDER BY count DESC;

SELECT 'Channel constraint migration completed successfully' as migration_status;