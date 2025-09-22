#!/usr/bin/env python3
"""
Setup test database with sample data for E2E testing
"""
import os
import sys
from dotenv import load_dotenv

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

load_dotenv('backend/.env')

from supabase import create_client

def setup_test_database():
    """Setup database with test data"""
    supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))
    
    print("Setting up test database...")
    
    # Insert test properties
    test_properties = [
        {
            'id': 'prop-1',
            'price': 250000,
            'location': 'Miami',
            'property_type': '1BHK',
            'amenities': {'pool': True, 'parking': True},
            'details': {'sqft': 800, 'year_built': 2020}
        },
        {
            'id': 'prop-2', 
            'price': 350000,
            'location': 'Miami',
            'property_type': '2BHK',
            'amenities': {'pool': True, 'parking': True, 'gym': True},
            'details': {'sqft': 1200, 'year_built': 2021}
        },
        {
            'id': 'prop-3',
            'price': 600000,
            'location': 'Miami',
            'property_type': '3BHK',
            'amenities': {'pool': True, 'parking': True, 'gym': True, 'balcony': True},
            'details': {'sqft': 1600, 'year_built': 2022}
        }
    ]
    
    for prop in test_properties:
        try:
            supabase.table('properties').upsert(prop).execute()
            print(f"✓ Property: {prop['property_type']} - ${prop['price']:,}")
        except Exception as e:
            print(f"Property insert error: {e}")
    
    # Insert test configs
    test_configs = [
        {
            'key': 'qualifier_prompt',
            'value': 'Score this lead (0-1) based on budget, location, property type. Return JSON: {"score": 0.8, "reasoning": "explanation"}'
        },
        {
            'key': 'hitl_threshold',
            'value': '0.9'
        },
        {
            'key': 'scheduler_prompt',
            'value': 'You are a real estate scheduler. Book property tours.'
        },
        {
            'key': 'followup_prompt',
            'value': 'You are a follow-up agent. Nurture leads with suggestions.'
        }
    ]
    
    for config in test_configs:
        try:
            supabase.table('configs').upsert(config).execute()
            print(f"✓ Config: {config['key']}")
        except Exception as e:
            print(f"Config insert error: {e}")
    
    # Insert test leads for different scenarios
    test_leads = [
        {
            'id': 'lead-1',
            'user_id': 'test_user_low_score',
            'channel': 'ig',
            'message': 'Looking for cheap apartment',
            'qualified_score': 0.3,
            'budget': 150000,
            'location': 'Miami',
            'property_type': '1BHK',
            'status': 'new',
            'history': []
        },
        {
            'id': 'lead-2',
            'user_id': 'test_user_high_score',
            'channel': 'whatsapp',
            'message': 'Need luxury 3BHK in Miami, budget 600k',
            'qualified_score': 0.95,
            'budget': 600000,
            'location': 'Miami',
            'property_type': '3BHK',
            'status': 'interrupted',
            'history': [{'message': 'High-value lead flagged for HITL', 'timestamp': '2024-01-01T10:00:00Z', 'agent': 'qualifier'}]
        },
        {
            'id': 'lead-3',
            'user_id': 'test_user_scheduled',
            'channel': 'ig',
            'message': 'Want to see 2BHK properties',
            'qualified_score': 0.8,
            'budget': 350000,
            'location': 'Miami',
            'property_type': '2BHK',
            'status': 'scheduled',
            'email': 'test@example.com',
            'name': 'Test User',
            'history': [
                {'message': 'Lead qualified', 'timestamp': '2024-01-01T10:00:00Z', 'agent': 'qualifier'},
                {'message': 'Meeting scheduled', 'timestamp': '2024-01-01T11:00:00Z', 'agent': 'scheduler'}
            ]
        }
    ]
    
    for lead in test_leads:
        try:
            supabase.table('leads').upsert(lead).execute()
            print(f"✓ Lead: {lead['user_id']} - Score: {lead.get('qualified_score', 'N/A')}")
        except Exception as e:
            print(f"Lead insert error: {e}")
    
    print("✓ Test database setup complete!")
    return True

if __name__ == "__main__":
    setup_test_database()
