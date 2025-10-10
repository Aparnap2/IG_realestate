-- Create companies table for multi-tenant support
-- Run this in your Supabase SQL Editor

-- Create the table
CREATE TABLE IF NOT EXISTS public.companies (
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
CREATE INDEX IF NOT EXISTS idx_companies_slug ON public.companies(slug);
CREATE INDEX IF NOT EXISTS idx_companies_is_active ON public.companies(is_active);
CREATE INDEX IF NOT EXISTS idx_companies_industry ON public.companies(industry);

-- Enable Row Level Security (RLS)
ALTER TABLE public.companies ENABLE ROW LEVEL SECURITY;

-- Create policy to allow public read access for active companies
CREATE POLICY IF NOT EXISTS "Allow public read for active companies"
    ON public.companies
    FOR SELECT
    USING (is_active = true);

-- Insert the company for your ngrok subdomain
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