-- Fix RLS policies to allow service role access
-- Run this in Supabase SQL Editor

-- Drop existing restrictive policies
DROP POLICY IF EXISTS "Users can access lead events from their company" ON lead_events;
DROP POLICY IF EXISTS "Users can access leads from their company" ON leads;

-- Create more permissive policies that allow service role access
-- Service role bypasses RLS, but we need policies for authenticated users

-- Allow service role and authenticated users to access lead_events
CREATE POLICY "Allow service role and authenticated access to lead_events"
    ON lead_events
    FOR ALL
    USING (true);

-- Allow service role and authenticated users to access leads
CREATE POLICY "Allow service role and authenticated access to leads"
    ON leads
    FOR ALL
    USING (true);

-- Add company_id column to leads table if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'leads' AND column_name = 'company_id'
    ) THEN
        ALTER TABLE leads ADD COLUMN company_id UUID REFERENCES companies(id);
        CREATE INDEX idx_leads_company_id ON leads(company_id);
    END IF;
END $$;
