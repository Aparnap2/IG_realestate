import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))

try:
    # Test connection
    response = supabase.table('leads').select('id').limit(1).execute()
    print('✓ Database connection successful')
    
    # Insert sample properties
    properties = [
        {'price': 250000, 'location': 'Miami', 'property_type': '1BHK'},
        {'price': 350000, 'location': 'Miami', 'property_type': '2BHK'},
        {'price': 500000, 'location': 'Miami', 'property_type': '3BHK'}
    ]
    
    for prop in properties:
        try:
            supabase.table('properties').insert(prop).execute()
            print(f'✓ Property: {prop["property_type"]} - ${prop["price"]:,}')
        except:
            pass
    
    # Insert configs
    configs = [
        {'key': 'qualifier_prompt', 'value': 'Score lead 0-1 based on budget, location, property type'},
        {'key': 'hitl_threshold', 'value': '0.9'}
    ]
    
    for config in configs:
        try:
            supabase.table('configs').upsert(config).execute()
            print(f'✓ Config: {config["key"]}')
        except:
            pass
            
    print('✓ Database setup completed')
    
except Exception as e:
    print(f'Database needs tables created manually in Supabase dashboard: {e}')
