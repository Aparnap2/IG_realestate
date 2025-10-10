#!/usr/bin/env python3
"""
Script to create companies table directly using Supabase client
"""
import os
import sys
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

def create_companies_table():
    """Create companies table using direct Supabase operations"""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        print("Error: SUPABASE_URL and SUPABASE_KEY environment variables must be set")
        sys.exit(1)
    
    supabase = create_client(supabase_url, supabase_key)
    
    try:
        print("Creating companies table...")
        
        # Create table using raw SQL
        create_table_sql = """
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
        """
        
        # Use RPC to execute raw SQL
        supabase.rpc('exec', {'sql': create_table_sql}).execute()
        print("✓ Companies table created")
        
        # Create indexes
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_companies_slug ON public.companies(slug);",
            "CREATE INDEX IF NOT EXISTS idx_companies_is_active ON public.companies(is_active);",
            "CREATE INDEX IF NOT EXISTS idx_companies_industry ON public.companies(industry);"
        ]
        
        for index_sql in indexes:
            supabase.rpc('exec', {'sql': index_sql}).execute()
            print(f"✓ Created index: {index_sql.split()[3]}")
        
        # Enable RLS
        rls_sql = "ALTER TABLE public.companies ENABLE ROW LEVEL SECURITY;"
        supabase.rpc('exec', {'sql': rls_sql}).execute()
        print("✓ RLS enabled")
        
        # Create RLS policy
        policy_sql = """
        CREATE POLICY IF NOT EXISTS "Allow public read for active companies"
            ON public.companies
            FOR SELECT
            USING (is_active = true);
        """
        supabase.rpc('exec', {'sql': policy_sql}).execute()
        print("✓ RLS policy created")
        
        # Insert the company for ngrok subdomain
        company_data = {
            "slug": "5f3d72cd9867",
            "name": "Real Estate Demo",
            "webhook_verify_token": "aaa_real_estate_verify_token_2025",
            "is_active": True,
            "industry": "real_estate",
            "subscription_tier": "starter"
        }
        
        # Check if company already exists
        existing = supabase.table("companies").select("id").eq("slug", company_data["slug"]).execute()
        
        if existing.data:
            # Update existing company
            supabase.table("companies").update(company_data).eq("slug", company_data["slug"]).execute()
            print(f"✓ Updated existing company: {company_data['slug']}")
        else:
            # Insert new company
            supabase.table("companies").insert(company_data).execute()
            print(f"✓ Inserted new company: {company_data['slug']}")
        
        print("\nCompanies table setup completed successfully!")
        print(f"Company slug: {company_data['slug']}")
        print(f"Verify token: {company_data['webhook_verify_token']}")
        
    except Exception as e:
        print(f"Error creating companies table: {e}")
        sys.exit(1)

if __name__ == "__main__":
    create_companies_table()