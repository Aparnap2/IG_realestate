-- Apply these fixes in Supabase SQL Editor to get the bot working

-- Fix 1: Update lead_events constraint to allow message and assistant_response
ALTER TABLE lead_events DROP CONSTRAINT IF EXISTS lead_events_event_type_check;
ALTER TABLE lead_events ADD CONSTRAINT lead_events_event_type_check 
CHECK (event_type IN ('created', 'qualified', 'scheduled', 'booked', 'interrupted', 'approved', 'rejected', 'error', 'message', 'assistant_response', 'qualification', 'property_search'));

-- Fix 2: Add source column to leads table if it doesn't exist
ALTER TABLE leads ADD COLUMN IF NOT EXISTS source VARCHAR DEFAULT 'instagram' CHECK (source IN ('instagram', ' ', 'web'));

-- Fix 3: Check if we have Miami properties in the database
SELECT mls_id, price, address, location, property_type 
FROM properties 
WHERE location = 'Miami' AND property_type = 'Condo' AND price <= 300000 
ORDER BY price;
