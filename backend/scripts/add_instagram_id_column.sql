-- Add instagram_id column to leads table
-- This column is needed for the temporal graph client to properly identify leads

ALTER TABLE leads 
ADD COLUMN IF NOT EXISTS instagram_id TEXT;

-- Create index for better performance
CREATE INDEX IF NOT EXISTS idx_leads_instagram_id ON leads(instagram_id);

-- Add comment for documentation
COMMENT ON COLUMN leads.instagram_id IS 'Instagram user ID for temporal graph integration';