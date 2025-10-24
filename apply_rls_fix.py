#!/usr/bin/env python3
"""
Apply RLS policy fixes to Supabase database
"""
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

def apply_rls_fix():
    """Apply RLS policy fixes"""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    
    if not url or not key:
        print("❌ Missing SUPABASE_URL or SUPABASE_KEY")
        return
    
    client = create_client(url, key)
    
    # Read the SQL file
    with open("fix_rls_policies.sql", "r") as f:
        sql = f.read()
    
    print("🔧 Applying RLS policy fixes...")
    
    try:
        # Execute the SQL (note: this requires admin privileges)
        # For Supabase, you'll need to run this in the SQL Editor
        print("⚠️  Please run the SQL in fix_rls_policies.sql in your Supabase SQL Editor")
        print("📋 SQL file location: fix_rls_policies.sql")
        print("\n✅ Instructions:")
        print("1. Go to your Supabase dashboard")
        print("2. Navigate to SQL Editor")
        print("3. Copy and paste the contents of fix_rls_policies.sql")
        print("4. Click 'Run'")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    apply_rls_fix()
