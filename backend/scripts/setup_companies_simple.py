#!/usr/bin/env python3
"""
Simple script to create companies table and insert data
"""
import os
import sys
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

def setup_companies():
    """Setup companies table using simple operations"""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        print("Error: SUPABASE_URL and SUPABASE_KEY environment variables must be set")
        sys.exit(1)
    
    supabase = create_client(supabase_url, supabase_key)
    
    try:
        print("Setting up companies table...")
        
        # First, let's check if we can create a simple table structure
        # We'll use the existing configs table as a reference
        
        # Create companies table using raw SQL through RPC
        # Note: This might need to be done manually in Supabase SQL Editor
        
        # For now, let's just insert the company data and see what happens
        company_data = {
            "slug": "5f3d72cd9867",
            "name": "Real Estate Demo",
            "webhook_verify_token": "aaa_real_estate_verify_token_2025",
            "is_active": True,
            "industry": "real_estate",
            "subscription_tier": "starter"
        }
        
        print("Attempting to insert company data...")
        
        # Try to insert - this will fail if table doesn't exist, but we'll get useful error
        result = supabase.table("companies").insert(company_data).execute()
        
        if result.data:
            print("✓ Company inserted successfully!")
            print(f"Company slug: {company_data['slug']}")
            print(f"Verify token: {company_data['webhook_verify_token']}")
        else:
            print("Company may already exist or table needs to be created")
            
            # Try to update instead
            update_result = supabase.table("companies").update(company_data).eq("slug", company_data["slug"]).execute()
            
            if update_result.data:
                print("✓ Company updated successfully!")
            else:
                print("❌ Table 'companies' doesn't exist. Please create it manually in Supabase SQL Editor:")
                print("\nSQL to execute:")
                print("""
-- Create companies table
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

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_companies_slug ON public.companies(slug);
CREATE INDEX IF NOT EXISTS idx_companies_is_active ON public.companies(is_active);

-- Enable RLS
ALTER TABLE public.companies ENABLE ROW LEVEL SECURITY;

-- Create RLS policy
CREATE POLICY IF NOT EXISTS "Allow public read for active companies"
    ON public.companies
    FOR SELECT
    USING (is_active = true);

-- Insert company
INSERT INTO public.companies (slug, name, webhook_verify_token, is_active, industry, subscription_tier)
VALUES (
    '5f3d72cd9867',
    'Real Estate Demo',
    'aaa_real_estate_verify_token_2025',
    true,
    'real_estate',
    'starter'
)
ON CONFLICT (slug) DO UPDATE SET
    name = EXCLUDED.name,
    webhook_verify_token = EXCLUDED.webhook_verify_token,
    is_active = EXCLUDED.is_active,
    industry = EXCLUDED.industry,
    subscription_tier = EXCLUDED.subscription_tier,
    updated_at = NOW();
                """)
        
    except Exception as e:
        print(f"Error: {e}")
        if "doesn't exist" in str(e).lower():
            print("\n❌ Table 'companies' doesn't exist. Please create it using the SQL above.")
        else:
            print("❌ Unexpected error occurred")

if __name__ == "__main__":
    setup_companies()