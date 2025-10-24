-- Refresh PostgREST schema cache
-- Run this in Supabase SQL Editor to fix the "Could not find 'updated_at' column" error

-- Notify PostgREST to reload schema cache
NOTIFY pgrst, 'reload schema';

-- Verify the updated_at column exists and trigger is working
SELECT column_name, data_type, column_default 
FROM information_schema.columns 
WHERE table_name = 'leads' AND column_name = 'updated_at';

-- Verify the trigger exists
SELECT trigger_name, event_manipulation, action_statement
FROM information_schema.triggers
WHERE event_object_table = 'leads' AND trigger_name LIKE '%updated_at%';
