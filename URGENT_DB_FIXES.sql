-- URGENT: Run these 3 commands in Supabase SQL Editor NOW

-- Fix 1: Allow message and assistant_response in lead_events
ALTER TABLE lead_events DROP CONSTRAINT IF EXISTS lead_events_event_type_check;
ALTER TABLE lead_events ADD CONSTRAINT lead_events_event_type_check 
CHECK (event_type IN ('created', 'qualified', 'scheduled', 'booked', 'interrupted', 'approved', 'rejected', 'error', 'message', 'assistant_response', 'qualification', 'property_search'));

-- Fix 2: Add missing source column to leads table
ALTER TABLE leads ADD COLUMN IF NOT EXISTS source VARCHAR DEFAULT 'instagram' CHECK (source IN ('instagram', ' ', 'web'));
