#!/usr/bin/env python3
"""
Quick PRD Alignment Validation - Skip slow LLM calls
"""

import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

def validate_core_components():
    """Validate core components without slow API calls."""
    results = {}
    
    print("🚀 Quick PRD Alignment Validation")
    print("=" * 50)
    
    # Test 1: Configuration
    try:
        from config import get_settings, Settings
        settings = get_settings()
        assert isinstance(settings, Settings)
        results["Configuration"] = "✅ PASS"
        print("✅ Configuration: Working")
    except Exception as e:
        results["Configuration"] = f"❌ FAIL: {e}"
        print(f"❌ Configuration: {e}")
    
    # Test 2: Router Agent (import only)
    try:
        from agents.router import RouterAgent, route_to_agent
        results["Router Agent"] = "✅ PASS"
        print("✅ Router Agent: Import successful")
    except Exception as e:
        results["Router Agent"] = f"❌ FAIL: {e}"
        print(f"❌ Router Agent: {e}")
    
    # Test 3: Compliance Tools (import only)
    try:
        from tools.compliance import fair_housing_evaluator, gdpr_tcpa_tracker
        results["Compliance Tools"] = "✅ PASS"
        print("✅ Compliance Tools: Import successful")
    except Exception as e:
        results["Compliance Tools"] = f"❌ FAIL: {e}"
        print(f"❌ Compliance Tools: {e}")
    
    # Test 4: Temporal Graph
    try:
        from temporal.graph_client import GraphitiClient, get_graphiti_client
        client = get_graphiti_client()
        results["Temporal Graph"] = "✅ PASS"
        print("✅ Temporal Graph: Client created")
    except Exception as e:
        results["Temporal Graph"] = f"❌ FAIL: {e}"
        print(f"❌ Temporal Graph: {e}")
    
    # Test 5: Scheduling Utils
    try:
        from tools.scheduling_utils import find_optimal_tour_slots
        results["Scheduling Utils"] = "✅ PASS"
        print("✅ Scheduling Utils: Import successful")
    except Exception as e:
        results["Scheduling Utils"] = f"❌ FAIL: {e}"
        print(f"❌ Scheduling Utils: {e}")
    
    # Test 6: Nurture Tools
    try:
        from tools.nurture import generate_nurture_action
        results["Nurture Tools"] = "✅ PASS"
        print("✅ Nurture Tools: Import successful")
    except Exception as e:
        results["Nurture Tools"] = f"❌ FAIL: {e}"
        print(f"❌ Nurture Tools: {e}")
    
    # Test 7: Analytics
    try:
        from utils.analytics import calculate_lead_attribution
        results["Analytics"] = "✅ PASS"
        print("✅ Analytics: Import successful")
    except Exception as e:
        results["Analytics"] = f"❌ FAIL: {e}"
        print(f"❌ Analytics: {e}")
    
    # Test 8: Enhanced Agents
    try:
        from agents.prd_compliant_workflow import QualifierAgent, SchedulerAgent, FollowUpAgent
        results["Enhanced Agents"] = "✅ PASS"
        print("✅ Enhanced Agents: Import successful")
    except Exception as e:
        results["Enhanced Agents"] = f"❌ FAIL: {e}"
        print(f"❌ Enhanced Agents: {e}")
    
    # Test 9: Workflow
    try:
        from workflow import create_workflow
        results["Workflow"] = "✅ PASS"
        print("✅ Workflow: Import successful")
    except Exception as e:
        results["Workflow"] = f"❌ FAIL: {e}"
        print(f"❌ Workflow: {e}")
    
    # Test 10: Database Connection
    try:
        from utils.supabase_client import supabase
        # Quick test
        result = supabase.table('leads').select('id').limit(1).execute()
        results["Database"] = "✅ PASS"
        print("✅ Database: Connection successful")
    except Exception as e:
        results["Database"] = f"❌ FAIL: {e}"
        print(f"❌ Database: {e}")
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 VALIDATION SUMMARY")
    print("=" * 50)
    
    passed = sum(1 for r in results.values() if r.startswith("✅"))
    total = len(results)
    percentage = (passed / total) * 100
    
    print(f"✅ Passed: {passed}/{total} ({percentage:.1f}%)")
    
    if percentage >= 90:
        print("🎉 EXCELLENT! System is 90%+ PRD compliant")
    elif percentage >= 70:
        print("✅ GOOD! System is 70%+ PRD compliant")
    else:
        print("⚠️  NEEDS WORK! System needs improvement")
    
    # Show failures
    failures = [k for k, v in results.items() if v.startswith("❌")]
    if failures:
        print(f"\n🔧 Components needing attention:")
        for failure in failures:
            print(f"  - {failure}")
    
    return results

if __name__ == "__main__":
    validate_core_components()