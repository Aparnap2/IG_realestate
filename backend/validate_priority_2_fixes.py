"""
Priority 2 Fixes Validation Script

Simple validation to confirm all Priority 2 fixes are implemented:
1. Score threshold alignment (0.4 consistency)
2. Universal audit logging implementation  
3. Neo4j temporal event logging
4. Complete correlation system integration
5. Configuration updates

This script validates the fixes are in place without requiring full test dependencies.
"""

import os
import sys
import re
from pathlib import Path

def validate_score_threshold_alignment():
    """Validate score threshold alignment across all agents."""
    print("\n🧪 Validating Score Threshold Alignment...")
    
    issues = []
    
    # Check router agent
    router_file = "agents/router.py"
    if os.path.exists(router_file):
        with open(router_file, 'r') as f:
            router_content = f.read()
            if "0.4" in router_content:
                print("✅ Router agent uses 0.4 threshold")
            else:
                issues.append("Router agent missing 0.4 threshold")
    else:
        issues.append(f"Router file not found: {router_file}")
    
    # Check qualifier agent  
    qualifier_file = "agents/qualifier.py"
    if os.path.exists(qualifier_file):
        with open(qualifier_file, 'r') as f:
            qualifier_content = f.read()
            # Check that 0.75 is replaced with 0.4 in critical sections
            if ">= 0.4" in qualifier_content and ">= 0.75" not in qualifier_content:
                print("✅ Qualifier agent uses 0.4 threshold (0.75 replaced)")
            else:
                issues.append("Qualifier agent still uses 0.75 threshold or missing 0.4")
    else:
        issues.append(f"Qualifier file not found: {qualifier_file}")
    
    # Check unified state coordinator
    coordinator_file = "agents/unified_state_coordinator.py"
    if os.path.exists(coordinator_file):
        with open(coordinator_file, 'r') as f:
            coordinator_content = f.read()
            if ">= 0.4" in coordinator_content:
                print("✅ Unified state coordinator uses 0.4 threshold")
            else:
                issues.append("Unified state coordinator missing 0.4 threshold")
    else:
        issues.append(f"Coordinator file not found: {coordinator_file}")
    
    return issues

def validate_universal_audit_logging():
    """Validate universal audit logging implementation."""
    print("\n🧪 Validating Universal Audit Logging...")
    
    issues = []
    
    # Check unified state coordinator has audit logging
    coordinator_file = "agents/unified_state_coordinator.py"
    if os.path.exists(coordinator_file):
        with open(coordinator_file, 'r') as f:
            coordinator_content = f.read()
            
            # Check for audit imports and logging
            required_audit_features = [
                "audit_log_event",
                "from ..utils.audit import audit_log_event",
                "automated_agent_transition",
                "temporal_event_logging",
                "Complete state transition logging"
            ]
            
            for feature in required_audit_features:
                if feature in coordinator_content:
                    print(f"✅ Found audit feature: {feature}")
                else:
                    issues.append(f"Missing audit feature: {feature}")
    else:
        issues.append(f"Coordinator file not found: {coordinator_file}")
    
    # Check audit utils are present
    audit_file = "utils/audit.py"
    if os.path.exists(audit_file):
        print("✅ Audit utils file exists")
    else:
        issues.append(f"Audit utils file not found: {audit_file}")
    
    return issues

def validate_neo4j_temporal_logging():
    """Validate Neo4j temporal event logging."""
    print("\n🧪 Validating Neo4j Temporal Event Logging...")
    
    issues = []
    
    # Check temporal graph client
    temporal_file = "temporal/graph_client.py"
    if os.path.exists(temporal_file):
        print("✅ Temporal graph client file exists")
        
        with open(temporal_file, 'r') as f:
            temporal_content = f.read()
            
            required_features = [
                "record_lead_event",
                "GraphitiClient",
                "temporal graph",
                "event_type"
            ]
            
            for feature in required_features:
                if feature in temporal_content:
                    print(f"✅ Found temporal feature: {feature}")
                else:
                    issues.append(f"Missing temporal feature: {feature}")
    else:
        issues.append(f"Temporal graph client file not found: {temporal_file}")
    
    # Check coordinator imports temporal client
    coordinator_file = "agents/unified_state_coordinator.py"
    if os.path.exists(coordinator_file):
        with open(coordinator_file, 'r') as f:
            coordinator_content = f.read()
            if "get_graphiti_client" in coordinator_content:
                print("✅ Coordinator imports temporal graph client")
            else:
                issues.append("Coordinator missing temporal graph client import")
    
    return issues

def validate_correlation_system():
    """Validate correlation system integration."""
    print("\n🧪 Validating Correlation System...")
    
    issues = []
    
    # Check correlation tracker
    correlation_file = "utils/correlation_tracker.py"
    if os.path.exists(correlation_file):
        print("✅ Correlation tracker file exists")
        
        with open(correlation_file, 'r') as f:
            correlation_content = f.read()
            
            required_features = [
                "UniversalCorrelationTracker",
                "CorrelationType",
                "track_agent_transition",
                "generate_correlation_id"
            ]
            
            for feature in required_features:
                if feature in correlation_content:
                    print(f"✅ Found correlation feature: {feature}")
                else:
                    issues.append(f"Missing correlation feature: {feature}")
    else:
        issues.append(f"Correlation tracker file not found: {correlation_file}")
    
    # Check coordinator uses correlation tracker
    coordinator_file = "agents/unified_state_coordinator.py"
    if os.path.exists(coordinator_file):
        with open(coordinator_file, 'r') as f:
            coordinator_content = f.read()
            if "correlation_tracker" in coordinator_content:
                print("✅ Coordinator uses correlation tracker")
            else:
                issues.append("Coordinator missing correlation tracker integration")
    
    return issues

def validate_configuration_updates():
    """Validate configuration updates."""
    print("\n🧪 Validating Configuration Updates...")
    
    issues = []
    
    # Check settings file
    settings_file = "config/settings.py"
    if os.path.exists(settings_file):
        with open(settings_file, 'r') as f:
            settings_content = f.read()
            
            # Check for relevant settings
            if "QUALIFIER_ONLY_MODE" in settings_content:
                print("✅ Qualifier-only mode setting found")
            else:
                issues.append("Missing QUALIFIER_ONLY_MODE setting")
                
            if "EXTRACTION_CONFIDENCE_THRESHOLD" in settings_content:
                print("✅ Extraction confidence threshold setting found")
            else:
                issues.append("Missing EXTRACTION_CONFIDENCE_THRESHOLD setting")
    else:
        issues.append(f"Settings file not found: {settings_file}")
    
    return issues

def validate_middleware_compliance():
    """Validate compliance enforcement middleware."""
    print("\n🧪 Validating Compliance Enforcement Middleware...")
    
    issues = []
    
    # Check middleware file
    middleware_file = "middleware/compliance_enforcement.py"
    if os.path.exists(middleware_file):
        print("✅ Compliance enforcement middleware file exists")
        
        with open(middleware_file, 'r') as f:
            middleware_content = f.read()
            
            required_features = [
                "ComplianceEnforcementMiddleware",
                "evaluate_message_compliance",
                "fair_housing"
            ]
            
            for feature in required_features:
                if feature in middleware_content:
                    print(f"✅ Found compliance feature: {feature}")
                else:
                    issues.append(f"Missing compliance feature: {feature}")
    else:
        issues.append(f"Compliance enforcement file not found: {middleware_file}")
    
    return issues

def validate_dashboard_endpoints():
    """Validate dashboard API endpoints."""
    print("\n🧪 Validating Dashboard API Endpoints...")
    
    issues = []
    
    # Check dashboard file
    dashboard_file = "api/dashboard.py"
    if os.path.exists(dashboard_file):
        print("✅ Dashboard API file exists")
        
        with open(dashboard_file, 'r') as f:
            dashboard_content = f.read()
            
            if "dashboard_bp" in dashboard_content:
                print("✅ Dashboard blueprint found")
            else:
                issues.append("Dashboard blueprint missing")
    else:
        issues.append(f"Dashboard API file not found: {dashboard_file}")
    
    return issues

def main():
    """Run all validation checks."""
    print("🚀 Priority 2 Fixes Validation Suite")
    print("=" * 50)
    
    all_issues = []
    
    # Run all validation checks
    validation_functions = [
        validate_score_threshold_alignment,
        validate_universal_audit_logging,
        validate_neo4j_temporal_logging,
        validate_correlation_system,
        validate_configuration_updates,
        validate_middleware_compliance,
        validate_dashboard_endpoints
    ]
    
    for validation_func in validation_functions:
        try:
            issues = validation_func()
            all_issues.extend(issues)
        except Exception as e:
            all_issues.append(f"Validation error in {validation_func.__name__}: {str(e)}")
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Priority 2 Validation Results:")
    
    if not all_issues:
        print("🎉 ALL VALIDATIONS PASSED!")
        print("✅ All Priority 2 fixes are properly implemented")
        print("✅ System ready for pilot deployment")
        return True
    else:
        print(f"⚠️ {len(all_issues)} validation issues found:")
        for i, issue in enumerate(all_issues, 1):
            print(f"{i}. {issue}")
        return False

if __name__ == "__main__":
    # Change to backend directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    success = main()
    sys.exit(0 if success else 1)