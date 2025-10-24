-- Enhanced Deduplication Constraints for Instagram Lead Management
-- This script adds robust deduplication constraints to prevent duplicate prospect creation

-- Add enhanced unique constraints with NULLS NOT DISTINCT for strict deduplication
ALTER TABLE leads DROP CONSTRAINT IF EXISTS leads_instagram_id_key;
ALTER TABLE leads ADD CONSTRAINT leads_instagram_id_key 
UNIQUE NULLS NOT DISTINCT (instagram_id);

-- Add composite unique constraint for legacy compatibility during migration
ALTER TABLE leads DROP CONSTRAINT IF EXISTS leads_user_id_company_id_key;
ALTER TABLE leads ADD CONSTRAINT leads_user_id_company_id_key 
UNIQUE NULLS NOT DISTINCT (user_id, company_id) WHERE instagram_id IS NULL;

-- Create performance indexes for deduplication queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_leads_instagram_id_lookup 
ON leads(instagram_id) WHERE instagram_id IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_leads_user_id_company_id_lookup 
ON leads(user_id, company_id) WHERE instagram_id IS NULL;

-- Add partial index for active/deactive status to improve query performance
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_leads_active_by_instagram_id 
ON leads(instagram_id, is_active) WHERE instagram_id IS NOT NULL;

-- Add constraint to prevent duplicate langgraph_thread_id per instagram_id
ALTER TABLE leads DROP CONSTRAINT IF EXISTS leads_langgraph_thread_id_instagram_id_unique;
ALTER TABLE leads ADD CONSTRAINT leads_langgraph_thread_id_instagram_id_unique 
EXCLUDE (langgraph_thread_id WITH =, instagram_id WITH =) WHERE (langgraph_thread_id IS NOT NULL AND instagram_id IS NOT NULL);

-- Add function to automatically migrate legacy leads to use instagram_id
CREATE OR REPLACE FUNCTION migrate_legacy_leads_to_instagram_id()
RETURNS INTEGER AS $$
DECLARE
    migrated_count INTEGER := 0;
    legacy_lead RECORD;
BEGIN
    -- Find leads that have user_id but no instagram_id
    FOR legacy_lead IN 
        SELECT id, user_id, company_id 
        FROM leads 
        WHERE user_id IS NOT NULL 
        AND instagram_id IS NULL
        AND user_id LIKE 'PSID_%'  -- Only migrate Meta PSID format
    LOOP
        -- Update the lead to set instagram_id from user_id
        UPDATE leads 
        SET instagram_id = user_id,
            updated_at = NOW()
        WHERE id = legacy_lead.id;
        
        migrated_count := migrated_count + 1;
    END LOOP;
    
    RETURN migrated_count;
END;
$$ LANGUAGE plpgsql;

-- Add trigger to automatically set instagram_id from user_id when inserting
CREATE OR REPLACE FUNCTION set_instagram_id_from_user_id()
RETURNS TRIGGER AS $$
BEGIN
    -- If instagram_id is not set but user_id is, and user_id looks like a PSID
    IF NEW.instagram_id IS NULL AND NEW.user_id IS NOT NULL AND NEW.user_id LIKE 'PSID_%' THEN
        NEW.instagram_id := NEW.user_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger if it doesn't exist
DROP TRIGGER IF EXISTS trigger_set_instagram_id_from_user_id ON leads;
CREATE TRIGGER trigger_set_instagram_id_from_user_id
    BEFORE INSERT OR UPDATE ON leads
    FOR EACH ROW
    EXECUTE FUNCTION set_instagram_id_from_user_id();

-- Add monitoring view for deduplication health
CREATE OR REPLACE VIEW deduplication_health AS
SELECT 
    'instagram_id_duplicates' as metric,
    COUNT(*) as total_records,
    COUNT(DISTINCT instagram_id) as unique_instagram_ids,
    COUNT(*) - COUNT(DISTINCT instagram_id) as potential_duplicates
FROM leads 
WHERE instagram_id IS NOT NULL

UNION ALL

SELECT 
    'legacy_user_id_only' as metric,
    COUNT(*) as total_records,
    COUNT(DISTINCT user_id) as unique_user_ids,
    COUNT(*) - COUNT(DISTINCT user_id) as potential_duplicates
FROM leads 
WHERE instagram_id IS NULL AND user_id IS NOT NULL

UNION ALL

SELECT 
    'missing_identifiers' as metric,
    COUNT(*) as total_records,
    0 as unique_instagram_ids,
    COUNT(*) as potential_duplicates
FROM leads 
WHERE instagram_id IS NULL AND user_id IS NULL;

-- Add comment documenting the deduplication strategy
COMMENT ON TABLE leads IS 'Enhanced with instagram_id as primary deduplication field. instagram_id has UNIQUE NULLS NOT DISTINCT constraint to prevent duplicate prospects. Legacy user_id is maintained for backward compatibility.';

-- Run migration function manually if needed
-- SELECT migrate_legacy_leads_to_instagram_id();
