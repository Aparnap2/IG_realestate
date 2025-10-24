#!/usr/bin/env python3
"""
Validation script to check if the fixes are properly implemented.
"""

import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def check_graphiti_fix():
    """Check if the Graphiti fallback fix is in place."""
    with open('temporal/graph_client.py', 'r') as f:
        content = f.read()
    
    # Check for the fix: null check for supabase client
    if 'if not supabase:' in content and 'Supabase client not initialized' in content:
        print("✅ Graphiti fallback fix found: null check for supabase client")
        return True
    else:
        print("❌ Graphiti fallback fix not found")
        return False

def check_multitenant_fix():
    """Check if the multi-tenant company_id fix is in place."""
    with open('utils/supabase_client.py', 'r') as f:
        content = f.read()
    
    # Check for improved company_id handling
    if 'get_instagram_user_mapping' in content and 'create_instagram_user_mapping' in content:
        print("✅ Multi-tenant fix found: improved company_id handling with instagram_user_mapping")
        return True
    else:
        print("❌ Multi-tenant fix not found")
        return False

def check_lead_processing_fix():
    """Check if lead processing includes company_id assignment."""
    with open('tasks/production_lead_processing.py', 'r') as f:
        content = f.read()
    
    # Check for company_id assignment in the lead processing
    if 'company_id' in content and 'default_company_id' in content:
        print("✅ Lead processing fix found: company_id assignment")
        return True
    else:
        print("❌ Lead processing fix not found")
        return False

if __name__ == "__main__":
    print("Validating implemented fixes...")
    
    graphiti_fixed = check_graphiti_fix()
    multitenant_fixed = check_multitenant_fix()
    lead_processing_fixed = check_lead_processing_fix()
    
    print(f"\nSummary:")
    print(f"Graphiti fallback fix: {'✓' if graphiti_fixed else '✗'}")
    print(f"Multi-tenant isolation fix: {'✓' if multitenant_fixed else '✗'}")
    print(f"Lead processing company_id fix: {'✓' if lead_processing_fixed else '✗'}")
    
    if graphiti_fixed and multitenant_fixed and lead_processing_fixed:
        print("\n🎉 All fixes have been successfully implemented!")
    else:
        print("\n❌ Some fixes are missing. Please review implementation.")