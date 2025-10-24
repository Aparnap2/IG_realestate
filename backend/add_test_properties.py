#!/usr/bin/env python3
"""
Add test properties to database for personalization testing
"""

import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.supabase_client import _ensure_supabase
import json

def add_test_properties():
    """Add test properties to the database."""
    
    print("🏠 Adding Test Properties")
    print("=" * 30)
    
    try:
        client = _ensure_supabase()
        
        test_properties = [
            {
                "id": "prop_001",
                "price": 250000,
                "location": "downtown Austin",
                "property_type": "2-bedroom apartment",
                "bedrooms": 2,
                "bathrooms": 2.0,
                "square_feet": 1200,
                "address": "123 Main St, Austin, TX 78701",
                "description": "Modern downtown apartment with great city views",
                "amenities": {"parking": True, "gym": True, "pool": True},
                "is_available": True,
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-01T00:00:00Z"
            },
            {
                "id": "prop_002", 
                "price": 280000,
                "location": "downtown Austin",
                "property_type": "2-bedroom apartment",
                "bedrooms": 2,
                "bathrooms": 1.5,
                "square_feet": 1100,
                "address": "456 Congress Ave, Austin, TX 78701",
                "description": "Cozy apartment in heart of downtown",
                "amenities": {"parking": True, "gym": False, "pool": True},
                "is_available": True,
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-01T00:00:00Z"
            },
            {
                "id": "prop_003",
                "price": 180000,
                "location": "downtown Austin", 
                "property_type": "1-bedroom apartment",
                "bedrooms": 1,
                "bathrooms": 1.0,
                "square_feet": 800,
                "address": "789 6th St, Austin, TX 78701",
                "description": "Affordable downtown living",
                "amenities": {"parking": False, "gym": True, "pool": False},
                "is_available": True,
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-01T00:00:00Z"
            },
            {
                "id": "prop_004",
                "price": 350000,
                "location": "South Austin",
                "property_type": "3-bedroom house",
                "bedrooms": 3,
                "bathrooms": 2.5,
                "square_feet": 2000,
                "address": "321 South Lamar, Austin, TX 78704",
                "description": "Spacious family home in South Austin",
                "amenities": {"parking": True, "gym": False, "pool": True, "yard": True},
                "is_available": True,
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-01T00:00:00Z"
            }
        ]
        
        # Add properties one by one to handle potential duplicates
        added_count = 0
        for prop in test_properties:
            try:
                # Use upsert to handle potential duplicates
                response = client.table("properties").upsert(prop).execute()
                if response.data:
                    print(f"✅ Added property: {prop['address']} - ${prop['price']:,}")
                    added_count += 1
                else:
                    print(f"⚠️ Failed to add property: {prop['id']}")
            except Exception as e:
                print(f"❌ Error adding property {prop['id']}: {e}")
        
        print(f"\n📊 Summary: {added_count}/{len(test_properties)} properties added")
        
        # Verify properties exist
        total_props = client.table("properties").select("id").execute()
        print(f"🏠 Total properties in database: {len(total_props.data)}")
        
        return added_count > 0
        
    except Exception as e:
        print(f"❌ Error adding test properties: {e}")
        return False

if __name__ == "__main__":
    success = add_test_properties()
    sys.exit(0 if success else 1)
