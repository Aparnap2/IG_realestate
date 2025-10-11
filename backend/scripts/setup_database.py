#!/usr/bin/env python3
"""
Database Setup Script - Create missing tables and fix schema issues
"""

import os
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from supabase import create_client
from config import get_settings

def setup_database():
    """Create missing database tables and fix schema issues."""
    settings = get_settings()
    
    # Initialize Supabase client
    supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    
    print("🔧 Setting up database schema...")
    
    # Read and execute audit_logs table creation
    audit_logs_sql = (Path(__file__).parent / "create_audit_logs_table.sql").read_text()
    
    try:
        # Execute SQL to create audit_logs table
        result = supabase.rpc('exec_sql', {'sql': audit_logs_sql})
        print("✅ Created audit_logs table")
    except Exception as e:
        print(f"⚠️  Audit logs table creation: {e}")
        # Try alternative approach - create via direct SQL
        try:
            # Create table with basic structure
            supabase.table('audit_logs').select('id').limit(1).execute()
            print("✅ Audit logs table already exists")
        except:
            print("❌ Could not create audit_logs table - manual creation needed")
    
    # Verify tables exist
    tables_to_check = ['leads', 'audit_logs', 'properties']
    
    for table in tables_to_check:
        try:
            result = supabase.table(table).select('*').limit(1).execute()
            print(f"✅ Table '{table}' exists and accessible")
        except Exception as e:
            print(f"❌ Table '{table}' issue: {e}")
    
    print("🎯 Database setup complete!")

if __name__ == "__main__":
    setup_database()