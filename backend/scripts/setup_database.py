#!/usr/bin/env python3
"""
Simplified script to set up database schema and sample data in Supabase.
"""
import os
import sys
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv()

def setup_database():
    """Set up database with sample data and configurations"""
    # Get Supabase credentials from environment
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        print("Error: SUPABASE_URL and SUPABASE_KEY environment variables must be set")
        print(f"SUPABASE_URL: {supabase_url}")
        print(f"SUPABASE_KEY: {'***' if supabase_key else 'None'}")
        sys.exit(1)
    
    # Create Supabase client
    supabase = create_client(supabase_url, supabase_key)
    
    try:
        print("Setting up database...")
        
        # Insert default configurations
        default_configs = [
            {
                "key": "qualifier_prompt",
                "value": """Score this lead (0-1) for real estate interest based on:
Budget: {budget}
Location: {location}
Type: {property_type}
Timeline: {timeline}

DB properties: {db_results}

Scoring Rubric:
- Budget > $500k: +0.3
- Budget > $300k: +0.2  
- Budget > $100k: +0.1
- Location and property type match DB: +0.3
- Timeline < 6 months: +0.1

Provide your response as a JSON object with the following structure:
{
    "score": 0.8,
    "reasoning": "Explanation of the score"
}"""
            },
            {
                "key": "hitl_threshold",
                "value": "0.9"
            },
            {
                "key": "scheduler_prompt",
                "value": "You are a real estate scheduler. Help book property tours and consultations."
            },
            {
                "key": "followup_prompt", 
                "value": "You are a real estate follow-up agent. Nurture leads with relevant property suggestions."
            }
        ]
        
        print("Inserting default configurations...")
        for config in default_configs:
            try:
                supabase.table("configs").upsert(config).execute()
                print(f"  ✓ Config: {config['key']}")
            except Exception as e:
                print(f"  ✗ Config {config['key']}: {e}")
        
        # Insert sample properties
        sample_properties = [
            {
                "price": 250000,
                "location": "Miami",
                "property_type": "1BHK",
                "amenities": {"pool": True, "parking": True, "gym": False},
                "details": {"sqft": 800, "year_built": 2020, "floor": 5}
            },
            {
                "price": 350000,
                "location": "Miami", 
                "property_type": "2BHK",
                "amenities": {"pool": True, "parking": True, "gym": True},
                "details": {"sqft": 1200, "year_built": 2021, "floor": 8}
            },
            {
                "price": 500000,
                "location": "Miami",
                "property_type": "3BHK", 
                "amenities": {"pool": True, "parking": True, "gym": True, "balcony": True},
                "details": {"sqft": 1600, "year_built": 2022, "floor": 12}
            },
            {
                "price": 300000,
                "location": "Orlando",
                "property_type": "2BHK",
                "amenities": {"pool": False, "parking": True, "gym": False},
                "details": {"sqft": 1100, "year_built": 2019, "floor": 3}
            },
            {
                "price": 450000,
                "location": "Tampa",
                "property_type": "Condo",
                "amenities": {"pool": True, "parking": True, "gym": True, "concierge": True},
                "details": {"sqft": 1400, "year_built": 2023, "floor": 15}
            }
        ]
        
        print("Inserting sample properties...")
        for property_data in sample_properties:
            try:
                supabase.table("properties").insert(property_data).execute()
                print(f"  ✓ Property: {property_data['property_type']} in {property_data['location']} - ${property_data['price']:,}")
            except Exception as e:
                print(f"  ✗ Property {property_data['property_type']}: {e}")
        
        print("\nDatabase setup completed successfully!")
        print("✓ Default configurations inserted")
        print("✓ Sample properties inserted")
        
        # Test database queries
        print("\nTesting database queries...")
        
        # Test configs
        config_response = supabase.table("configs").select("*").execute()
        print(f"✓ Configs table: {len(config_response.data)} records")
        
        # Test properties
        properties_response = supabase.table("properties").select("*").execute()
        print(f"✓ Properties table: {len(properties_response.data)} records")
        
        # Test property query
        miami_properties = supabase.table("properties").select("*").eq("location", "Miami").execute()
        print(f"✓ Miami properties: {len(miami_properties.data)} found")
        
    except Exception as e:
        print(f"Error setting up database: {e}")
        sys.exit(1)

if __name__ == "__main__":
    setup_database()
