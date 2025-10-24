#!/usr/bin/env python3
"""
Add Austin properties to database for personalization testing
"""

import sys
import os
from pathlib import Path
import uuid

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.supabase_client import _ensure_supabase

def add_austin_properties():
    """Add Austin properties with correct schema."""
    
    print("🏠 Adding Austin Properties")
    print("=" * 30)
    
    try:
        client = _ensure_supabase()
        
        # Company UUID for testing
        company_id = "d984203d-91a2-42d3-b9a4-cd138ed08541"
        
        austin_properties = [
            {
                "id": str(uuid.uuid4()),
                "price": 280000,
                "location": "downtown Austin",
                "property_type": "2BHK", 
                "amenities": {
                    "gym": True,
                    "pool": True,
                    "parking": True,
                    "balcony": True
                },
                "details": {
                    "sqft": 1200,
                    "bedrooms": 2,
                    "bathrooms": 2,
                    "year_built": 2021,
                    "floor": 8
                },
                "company_id": company_id
            },
            {
                "id": str(uuid.uuid4()),
                "price": 250000,
                "location": "downtown Austin",
                "property_type": "1BHK",
                "amenities": {
                    "gym": True,
                    "pool": False,
                    "parking": True,
                    "balcony": False
                },
                "details": {
                    "sqft": 800,
                    "bedrooms": 1,
                    "bathrooms": 1,
                    "year_built": 2020,
                    "floor": 5
                },
                "company_id": company_id
            },
            {
                "id": str(uuid.uuid4()),
                "price": 200000,
                "location": "North Austin",
                "property_type": "1BHK",
                "amenities": {
                    "gym": False,
                    "pool": True,
                    "parking": True,
                    "balcony": True
                },
                "details": {
                    "sqft": 750,
                    "bedrooms": 1,
                    "bathrooms": 1,
                    "year_built": 2019,
                    "floor": 3
                },
                "company_id": company_id
            },
            {
                "id": str(uuid.uuid4()),
                "price": 320000,
                "location": "South Austin",
                "property_type": "2BHK",
                "amenities": {
                    "gym": True,
                    "pool": True,
                    "parking": True,
                    "balcony": True,
                    "concierge": False
                },
                "details": {
                    "sqft": 1400,
                    "bedrooms": 2,
                    "bathrooms": 2.5,
                    "year_built": 2022,
                    "floor": 1
                },
                "company_id": company_id
            }
        ]
        
        # Add properties one by one
        added_count = 0
        for prop in austin_properties:
            try:
                response = client.table("properties").insert(prop).execute()
                if response.data:
                    print(f"✅ Added: {prop['location']} {prop['property_type']} - ${prop['price']:,}")
                    added_count += 1
                else:
                    print(f"⚠️ Failed to add property: {prop['id']}")
            except Exception as e:
                try:
                    # Try upsert if insert fails (duplicate)
                    response = client.table("properties").upsert(prop).execute()
                    if response.data:
                        print(f"✅ Updated: {prop['location']} {prop['property_type']} - ${prop['price']:,}")
                        added_count += 1
                except Exception as e2:
                    print(f"❌ Error with property {prop['location']}: {e2}")
        
        print(f"\n📊 Summary: {added_count}/{len(austin_properties)} Austin properties added")
        
        # Check all Austin properties
        austin_props = client.table("properties").select("*").eq("location", "downtown Austin").execute()
        print(f"🏠 Downtown Austin properties: {len(austin_props.data)}")
        
        return added_count > 0
        
    except Exception as e:
        print(f"❌ Error adding Austin properties: {e}")
        return False

if __name__ == "__main__":
    success = add_austin_properties()
    sys.exit(0 if success else 1)
