#!/usr/bin/env python3
"""
Production database setup for AAA Real Estate System.
Creates all required tables and inserts production data.
"""

import os
import sys
from dotenv import load_dotenv
from supabase import create_client
import json

# Load environment variables
load_dotenv(dotenv_path='backend/.env')

def create_production_database():
    """Create production database with all tables and data"""
    
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        print("❌ Missing Supabase environment variables")
        return False
    
    print(f"🔗 Connecting to Supabase: {supabase_url}")
    supabase = create_client(supabase_url, supabase_key)
    
    # Create tables using direct SQL execution via RPC
    print("📝 Creating database tables...")
    
    # Since we can't execute DDL directly, we'll create the data and let you know to run the SQL
    print("\n⚠️  IMPORTANT: You need to run this SQL in Supabase SQL Editor first:")
    print("=" * 60)
    
    sql_commands = """
-- Create leads table
CREATE TABLE IF NOT EXISTS leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR NOT NULL,
    channel VARCHAR NOT NULL CHECK (channel IN ('ig', 'whatsapp')),
    message TEXT NOT NULL,
    qualified_score FLOAT CHECK (qualified_score >= 0 AND qualified_score <= 1),
    budget INTEGER,
    location VARCHAR,
    property_type VARCHAR,
    timeline VARCHAR,
    name VARCHAR,
    email VARCHAR,
    meeting_slot TIMESTAMP WITH TIME ZONE,
    status VARCHAR DEFAULT 'new' CHECK (status IN ('new', 'qualified', 'scheduled', 'booked', 'interrupted', 'approved', 'rejected')),
    history JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create properties table
CREATE TABLE IF NOT EXISTS properties (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    price INTEGER NOT NULL,
    location VARCHAR NOT NULL,
    property_type VARCHAR NOT NULL,
    amenities JSONB DEFAULT '{}'::jsonb,
    details JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create configs table
CREATE TABLE IF NOT EXISTS configs (
    key VARCHAR PRIMARY KEY,
    value TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable Row Level Security
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE properties ENABLE ROW LEVEL SECURITY;
ALTER TABLE configs ENABLE ROW LEVEL SECURITY;

-- Create policies for public access (for demo - restrict in production)
CREATE POLICY "Allow all operations on leads" ON leads FOR ALL USING (true);
CREATE POLICY "Allow all operations on properties" ON properties FOR ALL USING (true);
CREATE POLICY "Allow all operations on configs" ON configs FOR ALL USING (true);
"""
    
    print(sql_commands)
    print("=" * 60)
    print("\nAfter running the SQL above, press Enter to continue with data insertion...")
    input()
    
    # Insert production data
    try:
        print("🏠 Inserting production properties...")
        properties = [
            {
                'price': 250000,
                'location': 'Miami',
                'property_type': '1BHK',
                'amenities': {"pool": True, "parking": True, "gym": False, "balcony": True},
                'details': {"sqft": 800, "year_built": 2020, "floor": 5, "bedrooms": 1, "bathrooms": 1}
            },
            {
                'price': 350000,
                'location': 'Miami',
                'property_type': '2BHK',
                'amenities': {"pool": True, "parking": True, "gym": True, "balcony": True},
                'details': {"sqft": 1200, "year_built": 2021, "floor": 8, "bedrooms": 2, "bathrooms": 2}
            },
            {
                'price': 500000,
                'location': 'Miami',
                'property_type': '3BHK',
                'amenities': {"pool": True, "parking": True, "gym": True, "balcony": True, "concierge": True},
                'details': {"sqft": 1600, "year_built": 2022, "floor": 12, "bedrooms": 3, "bathrooms": 2}
            },
            {
                'price': 300000,
                'location': 'Orlando',
                'property_type': '2BHK',
                'amenities': {"pool": False, "parking": True, "gym": False, "balcony": False},
                'details': {"sqft": 1100, "year_built": 2019, "floor": 3, "bedrooms": 2, "bathrooms": 1}
            },
            {
                'price': 450000,
                'location': 'Tampa',
                'property_type': 'Condo',
                'amenities': {"pool": True, "parking": True, "gym": True, "concierge": True, "rooftop": True},
                'details': {"sqft": 1400, "year_built": 2023, "floor": 15, "bedrooms": 2, "bathrooms": 2}
            },
            {
                'price': 750000,
                'location': 'Miami Beach',
                'property_type': '3BHK',
                'amenities': {"pool": True, "parking": True, "gym": True, "balcony": True, "ocean_view": True, "concierge": True},
                'details': {"sqft": 2000, "year_built": 2023, "floor": 20, "bedrooms": 3, "bathrooms": 3}
            },
            {
                'price': 180000,
                'location': 'Jacksonville',
                'property_type': '1BHK',
                'amenities': {"pool": False, "parking": True, "gym": False, "balcony": False},
                'details': {"sqft": 650, "year_built": 2018, "floor": 2, "bedrooms": 1, "bathrooms": 1}
            }
        ]
        
        for prop in properties:
            result = supabase.table('properties').insert(prop).execute()
            print(f"✅ Property: {prop['property_type']} in {prop['location']} - ${prop['price']:,}")
        
        print(f"\n✅ Inserted {len(properties)} properties")
        
        # Insert production configs
        print("\n⚙️  Inserting production configs...")
        configs = [
            {
                'key': 'qualifier_prompt',
                'value': '''You are a real estate lead qualifier. Analyze the lead and provide a JSON response with score and reasoning.

Scoring criteria:
- Budget: >$500k (+0.4), $100k-$500k (+0.2), <$100k (0)
- Location match with available properties: Exact (+0.3), Partial (+0.1)
- Property type match: Exact (+0.2)
- Timeline: <3 months (+0.2), 3-6 months (+0.1)

Lead: Budget: {budget}, Location: {location}, Type: {property_type}, Timeline: {timeline}
Available properties: {db_results}

Respond with JSON: {"score": 0.8, "reasoning": "High budget, exact location match, urgent timeline"}'''
            },
            {
                'key': 'hitl_threshold',
                'value': '0.9'
            },
            {
                'key': 'high_value_budget',
                'value': '500000'
            },
            {
                'key': 'scheduler_prompt',
                'value': '''You are a real estate scheduler. Help qualified leads book property tours and consultations.

Available actions:
1. Query available calendar slots
2. Propose meeting times
3. Book confirmed appointments
4. Send confirmation details

Be professional and helpful. Always confirm details before booking.'''
            },
            {
                'key': 'followup_prompt',
                'value': '''You are a real estate follow-up agent. Nurture leads who didn't qualify immediately.

Your goals:
1. Provide relevant property suggestions
2. Educate about the market
3. Build relationship for future opportunities
4. Gather more information to improve qualification

Be helpful and not pushy. Focus on providing value.'''
            },
            {
                'key': 'openrouter_model',
                'value': 'anthropic/claude-3.5-sonnet'
            },
            {
                'key': 'system_timezone',
                'value': 'America/New_York'
            }
        ]
        
        for config in configs:
            result = supabase.table('configs').upsert(config).execute()
            print(f"✅ Config: {config['key']}")
        
        print(f"\n✅ Inserted {len(configs)} configurations")
        
        # Test data access
        print("\n🧪 Testing data access...")
        
        # Test property queries
        miami_properties = supabase.table('properties').select('*').eq('location', 'Miami').execute()
        print(f"✅ Miami properties: {len(miami_properties.data)}")
        
        budget_properties = supabase.table('properties').select('*').lte('price', 400000).execute()
        print(f"✅ Properties under $400k: {len(budget_properties.data)}")
        
        # Test config access
        qualifier_config = supabase.table('configs').select('value').eq('key', 'qualifier_prompt').execute()
        print(f"✅ Qualifier prompt configured: {len(qualifier_config.data) > 0}")
        
        print("\n🎉 Production database setup completed successfully!")
        print("\n📋 Database Summary:")
        print(f"   - Properties: {len(properties)} listings across multiple locations")
        print(f"   - Configs: {len(configs)} system configurations")
        print("   - Tables: leads, properties, configs with RLS enabled")
        print("   - Ready for production lead processing")
        
        return True
        
    except Exception as e:
        print(f"❌ Error inserting data: {e}")
        print("Make sure you've run the SQL commands in Supabase first!")
        return False

if __name__ == "__main__":
    print("🚀 Setting up AAA Real Estate Production Database")
    success = create_production_database()
    sys.exit(0 if success else 1)