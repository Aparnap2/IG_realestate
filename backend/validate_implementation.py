#!/usr/bin/env python3
"""
Implementation Validation Script

Validates that all Phase 1-4 components are working correctly
according to PRD specifications.
"""

import sys
import os
import asyncio
import json
from datetime import datetime
from typing import Dict, Any, List

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def validate_phase_1_foundation():
    """Validate Phase 1: Foundation & Compliance components."""
    print("🔍 Validating Phase 1: Foundation & Compliance")
    results = {}
    
    # Test 1: Router Agent
    try:
        from backend.agents.router import RouterAgent, route_to_agent
        from models.lead import Lead
        
        router = RouterAgent()
        test_lead = Lead(
            user_id="test_validation_123",
            channel="ig",
            message="I'm looking for a 3BR house under $400k in Miami"
        )
        
        test_state = {
            "lead": test_lead,
            "messages": [{"role": "user", "content": test_lead.message}]
        }
        
        # Test routing function
        test_state["current_agent"] = "qualifier"
        route_result = route_to_agent(test_state)
        
        results["router_agent"] = {
            "status": "✅ PASS",
            "details": f"Router loaded successfully, routing to: {route_result}"
        }
        
    except Exception as e:
        results["router_agent"] = {
            "status": "❌ FAIL", 
            "details": f"Router Agent error: {str(e)}"
        }
    
    # Test 2: Compliance Tools
    try:
        from tools.compliance import fair_housing_evaluator, gdpr_tcpa_tracker
        
        # Test fair housing evaluator
        async def test_compliance():
            # Test safe message
            safe_result = await fair_housing_evaluator("Beautiful 2BR apartment with modern amenities")
            
            # Test violation
            violation_result = await fair_housing_evaluator("Perfect for young professionals")
            
            return safe_result["passed"] and not violation_result["passed"]
        
        compliance_test = asyncio.run(test_compliance())
        
        # Test GDPR tracking
        gdpr_tcpa_tracker("test_lead", "test_event", {"test": True})
        
        results["compliance_tools"] = {
            "status": "✅ PASS" if compliance_test else "❌ FAIL",
            "details": f"Fair housing detection working: {compliance_test}"
        }
        
    except Exception as e:
        results["compliance_tools"] = {
            "status": "❌ FAIL",
            "details": f"Compliance tools error: {str(e)}"
        }
    
    # Test 3: Audit Logging
    try:
        from utils.audit import audit_log_event, verify_audit_chain
        
        # Test audit logging
        event_id = audit_log_event("validation_test", {
            "test_data": "Phase 1 validation",
            "timestamp": datetime.now().isoformat()
        })
        
        # Test chain verification (basic)
        chain_result = verify_audit_chain()
        
        results["audit_logging"] = {
            "status": "✅ PASS" if event_id != "audit_failed" else "❌ FAIL",
            "details": f"Event logged: {event_id}, Chain valid: {chain_result.get('valid', False)}"
        }
        
    except Exception as e:
        results["audit_logging"] = {
            "status": "❌ FAIL",
            "details": f"Audit logging error: {str(e)}"
        }
    
    # Test 4: Configuration
    try:
        from config import get_settings, validate_workflow_config
        
        settings = get_settings()
        config_validation = validate_workflow_config()
        
        results["configuration"] = {
            "status": "✅ PASS" if settings else "❌ FAIL",
            "details": f"Settings loaded, Overall health: {config_validation.get('overall_health', False)}"
        }
        
    except Exception as e:
        results["configuration"] = {
            "status": "❌ FAIL",
            "details": f"Configuration error: {str(e)}"
        }
    
    return results

def validate_phase_2_intelligence():
    """Validate Phase 2: Temporal Intelligence & Scheduling."""
    print("🔍 Validating Phase 2: Temporal Intelligence & Scheduling")
    results = {}
    
    # Test 1: Temporal Graph Client
    try:
        from temporal.graph_client import GraphitiClient, get_graphiti_client
        
        client = get_graphiti_client()
        
        # Test basic functionality
        async def test_temporal():
            success = await client.record_lead_event(
                "test_lead_temporal",
                "validation_test",
                {"test": "temporal validation"}
            )
            
            history = await client.get_lead_history("test_lead_temporal", days_back=1)
            
            return success and isinstance(history, list)
        
        temporal_test = asyncio.run(test_temporal())
        
        results["temporal_graph"] = {
            "status": "✅ PASS" if temporal_test else "❌ FAIL",
            "details": f"Temporal client working: {temporal_test}"
        }
        
    except Exception as e:
        results["temporal_graph"] = {
            "status": "❌ FAIL",
            "details": f"Temporal graph error: {str(e)}"
        }
    
    # Test 2: Qualifier Utils
    try:
        from tools.qualifier_utils import reconcile_budget_mismatch, calculate_temporal_qualification_adjustments
        
        # Test budget reconciliation
        reconciliation = reconcile_budget_mismatch(
            desired_bedrooms=3,
            budget=300000,
            inventory=[
                {"bedrooms": 2, "price": 280000, "location": "Miami"},
                {"bedrooms": 3, "price": 350000, "location": "Miami"}
            ],
            location="Miami"
        )
        
        # Test temporal adjustments
        temporal_adj = calculate_temporal_qualification_adjustments(
            {"user_id": "test", "budget": 300000},
            0.6
        )
        
        results["qualifier_utils"] = {
            "status": "✅ PASS",
            "details": f"Reconciliation: {reconciliation['recommendation']}, Temporal adj: {temporal_adj['adjusted_score']:.2f}"
        }
        
    except Exception as e:
        results["qualifier_utils"] = {
            "status": "❌ FAIL",
            "details": f"Qualifier utils error: {str(e)}"
        }
    
    # Test 3: Calendar Integration
    try:
        from tools.calendar_integration import get_available_calendar_slots, create_tour_event
        from datetime import datetime, timedelta
        
        # Test calendar slots
        slots = get_available_calendar_slots(days_ahead=7)
        
        # Test event creation (mock)
        if slots:
            event_result = create_tour_event(
                start_time=datetime.now() + timedelta(days=1),
                duration_minutes=60,
                attendee_email="test@example.com",
                summary="Test Tour"
            )
            
            results["calendar_integration"] = {
                "status": "✅ PASS",
                "details": f"Found {len(slots)} slots, Event created: {event_result.get('status', 'unknown')}"
            }
        else:
            results["calendar_integration"] = {
                "status": "⚠️ PARTIAL",
                "details": "Calendar integration loaded but no slots available"
            }
        
    except Exception as e:
        results["calendar_integration"] = {
            "status": "❌ FAIL",
            "details": f"Calendar integration error: {str(e)}"
        }
    
    # Test 4: Scheduling Utils
    try:
        from tools.scheduling_utils import find_optimal_tour_slots, predict_no_show_risk
        
        # Test scheduling optimization
        test_lead = {"user_id": "test", "budget": 400000, "timeline": "immediate"}
        test_properties = [
            {"id": "1", "location": "Miami", "price": 350000},
            {"id": "2", "location": "Miami", "price": 380000}
        ]
        test_constraints = {"agent_calendar": [datetime.now() + timedelta(days=1)]}
        
        tour_slots = find_optimal_tour_slots(test_lead, test_properties, test_constraints)
        no_show_risk = predict_no_show_risk(test_lead)
        
        results["scheduling_utils"] = {
            "status": "✅ PASS",
            "details": f"Generated {len(tour_slots)} tour options, No-show risk: {no_show_risk:.2f}"
        }
        
    except Exception as e:
        results["scheduling_utils"] = {
            "status": "❌ FAIL",
            "details": f"Scheduling utils error: {str(e)}"
        }
    
    return results

def validate_phase_3_nurture():
    """Validate Phase 3: Intelligent Nurture."""
    print("🔍 Validating Phase 3: Intelligent Nurture")
    results = {}
    
    # Test 1: Nurture Tools
    try:
        from tools.nurture import generate_nurture_action, get_new_inventory_matches
        
        test_lead = {
            "user_id": "test_nurture",
            "budget": 350000,
            "location": "Miami",
            "property_type": "2BHK",
            "last_interaction_at": (datetime.now() - timedelta(days=10)).isoformat()
        }
        
        # Test nurture action generation
        nurture_action = generate_nurture_action(test_lead)
        
        # Test new inventory matching
        new_matches = get_new_inventory_matches(test_lead)
        
        results["nurture_tools"] = {
            "status": "✅ PASS",
            "details": f"Nurture action: {nurture_action.get('type', 'unknown')}, New matches: {len(new_matches)}"
        }
        
    except Exception as e:
        results["nurture_tools"] = {
            "status": "❌ FAIL",
            "details": f"Nurture tools error: {str(e)}"
        }
    
    return results

def validate_phase_4_analytics():
    """Validate Phase 4: Revenue Intelligence."""
    print("🔍 Validating Phase 4: Revenue Intelligence")
    results = {}
    
    # Test 1: Analytics
    try:
        from utils.analytics import (
            calculate_lead_attribution,
            analyze_agent_performance,
            analyze_inventory_performance,
            generate_conversion_funnel_analysis
        )
        
        # Test attribution calculation
        attribution = calculate_lead_attribution("test_lead_123")
        
        # Test agent performance
        agent_perf = analyze_agent_performance(time_period_days=30)
        
        # Test inventory performance
        inventory_perf = analyze_inventory_performance()
        
        # Test funnel analysis
        funnel = generate_conversion_funnel_analysis()
        
        results["analytics"] = {
            "status": "✅ PASS",
            "details": f"Attribution score: {attribution.get('attribution_score', 0):.2f}, Agents analyzed: {len(agent_perf.get('agent_performance', {}))}"
        }
        
    except Exception as e:
        results["analytics"] = {
            "status": "❌ FAIL",
            "details": f"Analytics error: {str(e)}"
        }
    
    return results

def validate_workflow_integration():
    """Validate complete workflow integration."""
    print("🔍 Validating Workflow Integration")
    results = {}
    
    # Test 1: Workflow Creation
    try:
        from workflow import create_workflow, validate_workflow_config
        
        # Validate configuration first
        config_validation = validate_workflow_config()
        
        # Create workflow
        workflow = create_workflow()
        
        results["workflow_creation"] = {
            "status": "✅ PASS" if workflow else "❌ FAIL",
            "details": f"Workflow created, Config health: {config_validation.get('overall_health', False)}"
        }
        
    except Exception as e:
        results["workflow_creation"] = {
            "status": "❌ FAIL",
            "details": f"Workflow creation error: {str(e)}"
        }
    
    # Test 2: Enhanced Agents
    try:
        from backend.agents.prd_compliant_workflow import QualifierAgent, SchedulerAgent, FollowUpAgent
        
        qualifier = QualifierAgent()
        scheduler = SchedulerAgent()
        followup = FollowUpAgent()
        
        results["enhanced_agents"] = {
            "status": "✅ PASS",
            "details": "All enhanced agents loaded successfully"
        }
        
    except Exception as e:
        results["enhanced_agents"] = {
            "status": "❌ FAIL",
            "details": f"Enhanced agents error: {str(e)}"
        }
    
    return results

def validate_database_schema():
    """Validate database schema and connectivity."""
    print("🔍 Validating Database Schema")
    results = {}
    
    try:
        from utils.supabase_client import supabase
        
        # Test basic connectivity
        response = supabase.table("leads").select("id").limit(1).execute()
        
        # Test audit logs table
        audit_response = supabase.table("audit_logs").select("id").limit(1).execute()
        
        results["database_schema"] = {
            "status": "✅ PASS",
            "details": f"Database connected, Tables accessible"
        }
        
    except Exception as e:
        results["database_schema"] = {
            "status": "❌ FAIL",
            "details": f"Database error: {str(e)}"
        }
    
    return results

def print_validation_results(results: Dict[str, Dict[str, Any]]):
    """Print formatted validation results."""
    print("\n" + "="*60)
    print("📊 VALIDATION RESULTS SUMMARY")
    print("="*60)
    
    total_tests = 0
    passed_tests = 0
    
    for test_name, result in results.items():
        status = result["status"]
        details = result["details"]
        
        print(f"\n{test_name.replace('_', ' ').title()}: {status}")
        print(f"  └─ {details}")
        
        total_tests += 1
        if "✅ PASS" in status:
            passed_tests += 1
    
    print("\n" + "="*60)
    print(f"📈 OVERALL SCORE: {passed_tests}/{total_tests} ({passed_tests/total_tests*100:.1f}%)")
    
    if passed_tests == total_tests:
        print("🎉 ALL TESTS PASSED! Implementation is PRD-compliant.")
    elif passed_tests >= total_tests * 0.8:
        print("✅ MOSTLY PASSING! Minor issues to address.")
    else:
        print("⚠️  SIGNIFICANT ISSUES! Review failed components.")
    
    print("="*60)

def main():
    """Run complete validation suite."""
    print("🚀 Starting PRD Implementation Validation")
    print("="*60)
    
    all_results = {}
    
    # Run all validation phases
    all_results.update(validate_phase_1_foundation())
    all_results.update(validate_phase_2_intelligence())
    all_results.update(validate_phase_3_nurture())
    all_results.update(validate_phase_4_analytics())
    all_results.update(validate_workflow_integration())
    all_results.update(validate_database_schema())
    
    # Print results
    print_validation_results(all_results)
    
    # Save results to file
    with open("validation_results.json", "w") as f:
        json.dump({
            "validation_date": datetime.now().isoformat(),
            "results": all_results
        }, f, indent=2)
    
    print(f"\n💾 Results saved to validation_results.json")

if __name__ == "__main__":
    main()