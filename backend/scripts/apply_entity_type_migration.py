#!/usr/bin/env python3
"""
Script to apply the entity_type column migration to audit_logs table using Supabase
"""
import sys
import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_supabase_client() -> Client:
    """Get Supabase client from environment variables"""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        raise ValueError(f"Missing Supabase environment variables: URL={bool(supabase_url)}, KEY={bool(supabase_key)}")
    
    return create_client(supabase_url, supabase_key)

def check_column_exists(client: Client, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table using information_schema"""
    try:
        response = client.rpc('check_column_exists', {
            'table_name': table_name,
            'column_name': column_name
        }).execute()
        
        if response.data:
            return response.data[0]['exists']
        return False
    except Exception:
        # If the RPC function doesn't exist, assume column doesn't exist
        return False

def apply_migration():
    """Apply the migration to add entity_type column using Supabase SQL"""
    client = get_supabase_client()
    
    try:
        # First, let's try to execute SQL directly using Supabase SQL editor
        # Since Supabase doesn't have a direct SQL execution in the client,
        # we'll need to use a different approach
        
        # For now, let's create a simple SQL file that can be executed manually
        sql_statements = [
            "-- Add entity_type column to audit_logs table if it doesn't exist",
            "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS entity_type VARCHAR(255) NOT NULL DEFAULT 'system';",
            "",
            "-- Create index for entity_type if it doesn't exist",
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_entity_type ON audit_logs (entity_type);"
        ]
        
        # Write SQL to a file for manual execution
        with open('add_entity_type_to_audit_logs.sql', 'w') as f:
            f.write('\n'.join(sql_statements))
        
        print("SQL file 'add_entity_type_to_audit_logs.sql' created successfully.")
        print("Please execute this SQL in your Supabase SQL editor to apply the migration.")
        print("\nSQL content:")
        print("-" * 50)
        for statement in sql_statements:
            print(statement)
        print("-" * 50)
        
        return True
        
    except Exception as e:
        print(f"Error creating migration file: {e}")
        return False

if __name__ == "__main__":
    success = apply_migration()
    sys.exit(0 if success else 1)