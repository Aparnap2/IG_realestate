#!/usr/bin/env python3
"""
Script to initialize database with RLS policies
"""
import os
import sys
from supabase import create_client

def initialize_rls():
    """Initialize database with RLS policies"""
    # Get Supabase credentials from environment
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        print("Error: SUPABASE_URL and SUPABASE_KEY environment variables must be set")
        sys.exit(1)
    
    # Create Supabase client
    supabase = create_client(supabase_url, supabase_key)
    
    try:
        # Enable RLS on leads table
        supabase.rpc("enable_rls", {"table_name": "leads"}).execute()
        
        # Enable RLS on properties table
        supabase.rpc("enable_rls", {"table_name": "properties"}).execute()
        
        # Enable RLS on configs table
        supabase.rpc("enable_rls", {"table_name": "configs"}).execute()
        
        # Create policies for leads table
        # Allow authenticated users to read their own leads
        supabase.rpc("create_policy", {
            "table_name": "leads",
            "policy_name": "Allow users to read their own leads",
            "policy_definition": "USING (auth.uid() = user_id)"
        }).execute()
        
        # Allow authenticated users to insert leads
        supabase.rpc("create_policy", {
            "table_name": "leads",
            "policy_name": "Allow users to insert leads",
            "policy_definition": "WITH CHECK (auth.role() = 'authenticated')"
        }).execute()
        
        # Allow authenticated users to update their own leads
        supabase.rpc("create_policy", {
            "table_name": "leads",
            "policy_name": "Allow users to update their own leads",
            "policy_definition": "USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id)"
        }).execute()
        
        # Create policies for properties table
        # Allow authenticated users to read properties
        supabase.rpc("create_policy", {
            "table_name": "properties",
            "policy_name": "Allow authenticated users to read properties",
            "policy_definition": "USING (auth.role() = 'authenticated')"
        }).execute()
        
        # Allow service role to insert/update properties
        supabase.rpc("create_policy", {
            "table_name": "properties",
            "policy_name": "Allow service role to manage properties",
            "policy_definition": "WITH CHECK (auth.role() = 'service_role')"
        }).execute()
        
        # Create policies for configs table
        # Allow authenticated users to read configs
        supabase.rpc("create_policy", {
            "table_name": "configs",
            "policy_name": "Allow authenticated users to read configs",
            "policy_definition": "USING (auth.role() = 'authenticated')"
        }).execute()
        
        # Allow service role to insert/update configs
        supabase.rpc("create_policy", {
            "table_name": "configs",
            "policy_name": "Allow service role to manage configs",
            "policy_definition": "WITH CHECK (auth.role() = 'service_role')"
        }).execute()
        
        print("RLS policies initialized successfully!")
    except Exception as e:
        print(f"Error initializing RLS policies: {e}")
        sys.exit(1)

if __name__ == "__main__":
    initialize_rls()