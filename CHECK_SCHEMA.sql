-- Check the actual schema of your properties table
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns 
WHERE table_name = 'properties' 
ORDER BY ordinal_position;
