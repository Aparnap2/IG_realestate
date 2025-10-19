#!/usr/bin/env python3
"""
Script to add missing instagram_id column to existing leads table.
Run this if you're getting 'column leads.instagram_id does not exist' errors.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def add_instagram_id_column():
    """Add instagram_id column to leads table if it doesn't exist."""
    
    try:
        from utils.supabase_client import supabase
        
        print("🔧 Checking if instagram_id column exists...")
        
        # Try to query the instagram_id column
        try:
            result = supabase.table("leads").select("instagram_id").limit(1).execute()
            print("✅ instagram_id column already exists")
            return True
        except Exception as e:
            if "does not exist" in str(e):
                print("⚠️ instagram_id column missing, adding it...")
                
                # Add the column using raw SQL
                sql = """
                ALTER TABLE leads 
                ADD COLUMN IF NOT EXISTS instagram_id TEXT;
                
                CREATE INDEX IF NOT EXISTS idx_leads_instagram_id ON leads(instagram_id);
                """
                
                # Execute the SQL
                result = supabase.rpc('exec_sql', {'sql': sql}).execute()
                print("✅ instagram_id column added successfully")
                return True
            else:
                print(f"❌ Error checking column: {e}")
                return False
                
    except ImportError:
        print("❌ Could not import supabase client. Make sure you're in the backend directory.")
        return False
    except Exception as e:
        print(f"❌ Error adding instagram_id column: {e}")
        return False

def main():
    print("🚀 Adding missing instagram_id column to leads table")
    print("=" * 60)
    
    # Check environment
    if not os.getenv("SUPABASE_URL"):
        print("❌ SUPABASE_URL not set in environment")
        return False
    
    if not os.getenv("SUPABASE_KEY"):
        print("❌ SUPABASE_KEY not set in environment")
        return False
    
    print(f"📊 Supabase URL: {os.getenv('SUPABASE_URL')}")
    print()
    
    # Add the column
    success = add_instagram_id_column()
    
    if success:
        print("\n✅ Success! The instagram_id column has been added to your leads table.")
        print("🔄 Please restart your backend server to pick up the changes.")
    else:
        print("\n❌ Failed to add instagram_id column.")
        print("💡 You may need to run the SQL manually in Supabase SQL Editor:")
        print("   ALTER TABLE leads ADD COLUMN IF NOT EXISTS instagram_id TEXT;")
        print("   CREATE INDEX IF NOT EXISTS idx_leads_instagram_id ON leads(instagram_id);")
    
    return success

if __name__ == "__main__":
    main()