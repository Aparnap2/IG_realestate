-- Complete Database Schema Fix for Webhook Verification
-- This script addresses all database-related issues for webhook functionality

-- Drop existing policies if they exist
DROP POLICY IF EXISTS "Allow public read for active companies" ON public.companies;
DROP POLICY IF EXISTS "Allow company access to own data" ON public.companies;

-- Drop existing trigger if it exists
DROP TRIGGER IF EXISTS handle_companies_updated_at ON public.companies;
DROP FUNCTION IF EXISTS public.handle_companies_updated_at();

-- Drop existing indexes if they exist
DROP INDEX IF EXISTS idx_companies_slug;
DROP INDEX IF EXISTS idx_companies_is_active;
DROP INDEX IF EXISTS idx_companies_industry;

-- Drop the companies table if it exists
DROP TABLE IF EXISTS public.companies;

-- Create the companies table with proper schema
CREATE TABLE public.companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    industry TEXT DEFAULT 'general',
    is_active BOOLEAN DEFAULT TRUE,
    instagram_user_id TEXT,
    instagram_username TEXT,
    meta_app_id TEXT,
    access_token TEXT,
    webhook_verify_token TEXT,
    settings JSONB DEFAULT '{}'::jsonb,
    subscription_tier TEXT DEFAULT 'starter',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for fast lookups
CREATE INDEX idx_companies_slug ON public.companies(slug);
CREATE INDEX idx_companies_is_active ON public.companies(is_active);
CREATE INDEX idx_companies_industry ON public.companies(industry);

-- Enable Row Level Security (RLS)
ALTER TABLE public.companies ENABLE ROW LEVEL SECURITY;

-- Create policy to allow public read access for active companies
CREATE POLICY "Allow public read for active companies"
    ON public.companies
    FOR SELECT
    USING (is_active = true);

-- Create policy to allow companies to access their own data
CREATE POLICY "Allow company access to own data"
    ON public.companies
    FOR ALL
    USING (true);  -- Simplified for now, can be enhanced with auth context

-- Create a function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION public.handle_companies_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to automatically update updated_at
CREATE TRIGGER handle_companies_updated_at
    BEFORE UPDATE ON public.companies
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_companies_updated_at();

-- Insert the company for ngrok subdomain '5f3d72cd9867'
INSERT INTO public.companies (slug, name, webhook_verify_token, is_active)
VALUES (
    '5f3d72cd9867', 
    'Real Estate Demo',
    'aaa_real_estate_verify_token_2025',
    true
)
ON CONFLICT (slug) DO UPDATE SET
    name = EXCLUDED.name,
    webhook_verify_token = EXCLUDED.webhook_verify_token,
    is_active = EXCLUDED.is_active,
    updated_at = NOW();

-- Verify the insertion
SELECT * FROM public.companies WHERE slug = '5f3d72cd9867';