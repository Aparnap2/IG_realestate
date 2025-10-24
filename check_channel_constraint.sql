-- SQL script to check the leads_channel_check constraint definition
-- Run this in Supabase SQL Editor to inspect the actual constraint

-- Check all constraints on the leads table
SELECT 
    tc.constraint_name,
    tc.constraint_type,
    tc.check_clause,
    tc.is_deferrable,
    tc.initially_deferred
FROM information_schema.table_constraints tc
WHERE tc.table_name = 'leads' 
    AND tc.constraint_name = 'leads_channel_check';

-- Alternatively, get all check constraints on the leads table
SELECT 
    conname as constraint_name,
    pg_get_constraintdef(oid) as constraint_definition
FROM pg_constraint 
WHERE conrelid = 'leads'::regclass 
    AND contype = 'c'
    AND conname LIKE '%channel%';

-- Check what values are currently in the channel column
SELECT DISTINCT channel, COUNT(*) as count
FROM leads 
GROUP BY channel
ORDER BY count DESC;

-- Check if there are any records with invalid channel values
SELECT instagram_id, name, channel, created_at
FROM leads 
WHERE channel NOT IN ('instagram', ' ', 'web', 'email', ' ')
LIMIT 10;