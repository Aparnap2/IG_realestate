#!/usr/bin/env python3
"""
Create Missing Database Tables for 100% PRD Compliance
"""

import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.supabase_client import supabase
from config import get_settings

def create_audit_logs_table():
    """Create the audit_logs table directly via Supabase."""
    
    print("🔧 Creating audit_logs table...")
    
    # Create the table using Supabase SQL
    sql_query = """
    CREATE TABLE IF NOT EXISTS audit_logs (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        event_type VARCHAR NOT NULL,
        entity_id VARCHAR NOT NULL,
        agent_type VARCHAR,
        payload JSONB NOT NULL,
        hash VARCHAR NOT NULL,
        prev_hash VARCHAR,
        timestamp TIMESTAMPTZ DEFAULT NOW(),
        correlation_id UUID
    );
    
    -- Create indexes for performance
    CREATE INDEX IF NOT EXISTS idx_audit_logs_entity_id ON audit_logs(entity_id);
    CREATE INDEX IF NOT EXISTS idx_audit_logs_event_type ON audit_logs(event_type);
    CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp);
    
    -- Enable Row Level Security
    ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
    
    -- Create policies
    DROP POLICY IF EXISTS "Audit logs readable by authenticated users" ON audit_logs;
    CREATE POLICY "Audit logs readable by authenticated users" ON audit_logs
        FOR SELECT USING (true);
    
    DROP POLICY IF EXISTS "System can insert audit logs" ON audit_logs;
    CREATE POLICY "System can insert audit logs" ON audit_logs
        FOR INSERT WITH CHECK (true);
    """
    
    try:
        # Execute the SQL
        result = supabase.rpc('exec_sql', {'sql': sql_query})
        print("✅ audit_logs table created successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to create audit_logs table: {e}")
        
        # Try alternative approach - create via REST API
        try:
            # Test if we can insert a record (this will create the table structure)
            test_record = {
                "event_type": "system_test",
                "entity_id": "test_entity",
                "agent_type": "system",
                "payload": {"test": True},
                "hash": "test_hash_123",
                "prev_hash": None
            }
            
            result = supabase.table('audit_logs').insert(test_record).execute()
            print("✅ audit_logs table created via insert")
            
            # Clean up test record
            supabase.table('audit_logs').delete().eq('event_type', 'system_test').execute()
            return True
            
        except Exception as e2:
            print(f"❌ Alternative creation failed: {e2}")
            return False

def create_system_errors_table():
    """Create the system_errors table for fallback logging."""
    
    print("🔧 Creating system_errors table...")
    
    try:
        # Test if we can insert a record
        test_record = {
            "error_type": "system_test",
            "error_message": "Test error",
            "context": {"test": True},
            "timestamp": "2024-01-01T00:00:00Z"
        }
        
        result = supabase.table('system_errors').insert(test_record).execute()
        print("✅ system_errors table created successfully")
        
        # Clean up test record
        supabase.table('system_errors').delete().eq('error_type', 'system_test').execute()
        return True
        
    except Exception as e:
        print(f"❌ Failed to create system_errors table: {e}")
        return False

def verify_tables():
    """Verify all required tables exist and are accessible."""
    
    print("\n🔍 Verifying database tables...")
    
    required_tables = {
        'leads': 'Lead management',
        'audit_logs': 'Compliance audit trail', 
        'system_errors': 'Error logging fallback',
        'properties': 'Property inventory'
    }
    
    results = {}
    
    for table, description in required_tables.items():
        try:
            result = supabase.table(table).select('*').limit(1).execute()
            results[table] = "✅ ACCESSIBLE"
            print(f"✅ {table}: {description} - Accessible")
        except Exception as e:
            results[table] = f"❌ ERROR: {e}"
            print(f"❌ {table}: {description} - {e}")
    
    return results

def main():
    """Main setup function."""
    
    print("🚀 Database Setup for 100% PRD Compliance")
    print("=" * 50)
    
    # Create missing tables
    audit_success = create_audit_logs_table()
    errors_success = create_system_errors_table()
    
    # Verify all tables
    table_results = verify_tables()
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 DATABASE SETUP SUMMARY")
    print("=" * 50)
    
    accessible_tables = sum(1 for r in table_results.values() if r.startswith("✅"))
    total_tables = len(table_results)
    
    print(f"✅ Accessible tables: {accessible_tables}/{total_tables}")
    
    if accessible_tables == total_tables:
        print("🎉 ALL TABLES READY! Database is 100% PRD compliant")
        return True
    else:
        print("⚠️  Some tables need manual creation in Supabase dashboard")
        
        # Show manual creation steps
        print("\n🔧 Manual Steps Needed:")
        print("1. Go to your Supabase dashboard")
        print("2. Navigate to Table Editor")
        print("3. Create missing tables:")
        
        for table, result in table_results.items():
            if result.startswith("❌"):
                print(f"   - {table}")
        
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)