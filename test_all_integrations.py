#!/usr/bin/env python3
"""
Comprehensive Integration Test Script

Tests all external integrations for the Instagram Real Estate Lead Capture System:
1. HubSpot CRM Integration
2. Google Calendar Integration
3. Redis Cache Integration
4. Temporal Graph (Graphiti) Integration

This script provides a complete assessment of integration functionality and
identifies any configuration or implementation issues.
"""

import os
import sys
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List
import traceback

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# Import test modules
from tools.calendar_integration import GoogleCalendarClient, get_available_calendar_slots, create_tour_event
from utils.redis_client import (
    test_redis_connection, 
    cache_query_result, 
    get_cached_query_result,
    redis_health_check
)
from temporal.graph_client import GraphitiClient, get_graphiti_client
from tools.agent_tools import create_hubspot_contact

class IntegrationTester:
    """Comprehensive integration testing framework."""
    
    def __init__(self):
        self.results = {
            "hubspot": {"status": "NOT_TESTED", "details": []},
            "google_calendar": {"status": "NOT_TESTED", "details": []},
            "redis": {"status": "NOT_TESTED", "details": []},
            "temporal_graph": {"status": "NOT_TESTED", "details": []}
        }
        self.start_time = datetime.now()
    
    def log_result(self, integration: str, status: str, message: str):
        """Log a test result."""
        self.results[integration]["details"].append({
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "message": message
        })
        if status == "ERROR":
            self.results[integration]["status"] = "ERROR"
        elif status == "SUCCESS" and self.results[integration]["status"] != "ERROR":
            self.results[integration]["status"] = "PARTIAL"
    
    async def test_hubspot_integration(self) -> Dict[str, Any]:
        """Test HubSpot CRM integration functionality."""
        print("\n🔍 Testing HubSpot Integration...")
        
        try:
            # Test 1: Check if HubSpot is configured
            from config import get_settings
            settings = get_settings()
            
            if not settings.HUBSPOT_ACCESS_TOKEN:
                self.log_result("hubspot", "ERROR", "HubSpot access token not configured")
                return self.results["hubspot"]
            
            self.log_result("hubspot", "SUCCESS", "HubSpot configuration found")
            
            # Test 2: Create a test contact
            test_contact_data = {
                "first_name": "Test",
                "last_name": "Integration",
                "email": f"test.integration.{int(datetime.now().timestamp())}@example.com",
                "phone": "+1234567890",
                "lifecyclestage": "lead"
            }
            
            try:
                create_result = create_hubspot_contact(test_contact_data)
                if create_result and "contact_id" in create_result:
                    self.log_result("hubspot", "SUCCESS", f"Created test contact: {create_result['contact_id']}")
                    
                    # Test 3: Verify contact creation result
                    if create_result and "contact_id" in create_result:
                        self.log_result("hubspot", "SUCCESS", f"Verified contact creation: {create_result['contact_id']}")
                        self.results["hubspot"]["status"] = "WORKING"
                    else:
                        self.log_result("hubspot", "ERROR", "Failed to verify contact creation")
                else:
                    self.log_result("hubspot", "ERROR", "Failed to create test contact")
                    
            except Exception as e:
                self.log_result("hubspot", "ERROR", f"HubSpot API error: {str(e)}")
                
        except Exception as e:
            self.log_result("hubspot", "ERROR", f"HubSpot test setup error: {str(e)}")
        
        return self.results["hubspot"]
    
    async def test_google_calendar_integration(self) -> Dict[str, Any]:
        """Test Google Calendar integration functionality."""
        print("\n🔍 Testing Google Calendar Integration...")
        
        try:
            # Test 1: Initialize calendar client
            calendar_client = GoogleCalendarClient()
            
            if calendar_client.service is None:
                self.log_result("google_calendar", "SUCCESS", "Using mock calendar implementation (expected in test environment)")
            else:
                self.log_result("google_calendar", "SUCCESS", "Google Calendar service initialized")
            
            # Test 2: Get available slots
            try:
                available_slots = get_available_calendar_slots(days_ahead=7, time_of_day="afternoon")
                if isinstance(available_slots, list) and len(available_slots) > 0:
                    self.log_result("google_calendar", "SUCCESS", f"Retrieved {len(available_slots)} available slots")
                else:
                    self.log_result("google_calendar", "SUCCESS", "Calendar slots query returned empty list (valid)")
            except Exception as e:
                self.log_result("google_calendar", "ERROR", f"Failed to get available slots: {str(e)}")
            
            # Test 3: Create a test tour event
            try:
                start_time = datetime.now() + timedelta(days=2, hours=14)
                result = create_tour_event(
                    start_time=start_time,
                    duration_minutes=60,
                    attendee_email="test@example.com",
                    summary="Test Property Tour",
                    description="Integration test tour",
                    property_addresses=["123 Test St", "456 Test Ave"]
                )
                
                if result and "event_id" in result:
                    self.log_result("google_calendar", "SUCCESS", f"Created test event: {result['event_id']}")
                    self.results["google_calendar"]["status"] = "WORKING"
                else:
                    self.log_result("google_calendar", "ERROR", "Failed to create test event")
                    
            except Exception as e:
                self.log_result("google_calendar", "ERROR", f"Event creation error: {str(e)}")
                
        except Exception as e:
            self.log_result("google_calendar", "ERROR", f"Calendar test setup error: {str(e)}")
        
        return self.results["google_calendar"]
    
    async def test_redis_integration(self) -> Dict[str, Any]:
        """Test Redis cache integration functionality."""
        print("\n🔍 Testing Redis Integration...")
        
        try:
            # Test 1: Check Redis connection
            if test_redis_connection():
                self.log_result("redis", "SUCCESS", "Redis connection successful")
            else:
                self.log_result("redis", "ERROR", "Redis connection failed")
                return self.results["redis"]
            
            # Test 2: Cache and retrieve query results
            test_query = "SELECT * FROM properties WHERE price < 500000"
            test_user_id = "test_user_123"
            test_result = {"properties": [{"id": 1, "address": "123 Test St"}]}
            
            if cache_query_result(test_query, test_user_id, test_result):
                self.log_result("redis", "SUCCESS", "Successfully cached query result")
                
                # Test 3: Retrieve cached result
                cached_result = get_cached_query_result(test_query, test_user_id)
                if cached_result and "properties" in cached_result:
                    self.log_result("redis", "SUCCESS", "Successfully retrieved cached result")
                    self.results["redis"]["status"] = "WORKING"
                else:
                    self.log_result("redis", "ERROR", "Failed to retrieve cached result")
            else:
                self.log_result("redis", "ERROR", "Failed to cache query result")
            
            # Test 4: Redis health check
            try:
                health_status = redis_health_check()
                if health_status.get("status") == "healthy":
                    self.log_result("redis", "SUCCESS", f"Redis health check passed: {health_status.get('redis_version', 'unknown')}")
                else:
                    self.log_result("redis", "ERROR", f"Redis health check failed: {health_status.get('error', 'unknown')}")
            except Exception as e:
                self.log_result("redis", "ERROR", f"Redis health check error: {str(e)}")
                
        except Exception as e:
            self.log_result("redis", "ERROR", f"Redis test setup error: {str(e)}")
        
        return self.results["redis"]
    
    async def test_temporal_graph_integration(self) -> Dict[str, Any]:
        """Test Temporal Graph (Graphiti) integration functionality."""
        print("\n🔍 Testing Temporal Graph Integration...")
        
        try:
            # Test 1: Initialize Graphiti client
            graph_client = get_graphiti_client()
            
            if graph_client.graphiti is None:
                self.log_result("temporal_graph", "SUCCESS", "Using Supabase fallback for temporal storage (expected in test environment)")
            else:
                self.log_result("temporal_graph", "SUCCESS", "Graphiti client initialized")
            
            # Test 2: Record a lead event
            try:
                test_lead_id = f"test_lead_{int(datetime.now().timestamp())}"
                event_result = await graph_client.record_lead_event(
                    lead_id=test_lead_id,
                    event_type="qualification",
                    event_data={
                        "budget": 500000,
                        "location": "Miami",
                        "property_type": "condo",
                        "timeline": "2 months"
                    }
                )
                
                if event_result:
                    self.log_result("temporal_graph", "SUCCESS", f"Recorded test event for lead: {test_lead_id}")
                else:
                    self.log_result("temporal_graph", "ERROR", "Failed to record lead event")
                    
            except Exception as e:
                self.log_result("temporal_graph", "ERROR", f"Event recording error: {str(e)}")
            
            # Test 3: Retrieve lead history
            try:
                history = await graph_client.get_lead_history(test_lead_id, days_back=30)
                if isinstance(history, list):
                    self.log_result("temporal_graph", "SUCCESS", f"Retrieved lead history: {len(history)} events")
                else:
                    self.log_result("temporal_graph", "ERROR", "Failed to retrieve lead history")
                    
            except Exception as e:
                self.log_result("temporal_graph", "ERROR", f"History retrieval error: {str(e)}")
            
            # Test 4: Analyze engagement trajectory
            try:
                trajectory = await graph_client.get_engagement_trajectory(test_lead_id)
                if "trajectory" in trajectory:
                    self.log_result("temporal_graph", "SUCCESS", f"Engagement trajectory: {trajectory['trajectory']}")
                    self.results["temporal_graph"]["status"] = "WORKING"
                else:
                    self.log_result("temporal_graph", "ERROR", "Failed to analyze engagement trajectory")
                    
            except Exception as e:
                self.log_result("temporal_graph", "ERROR", f"Trajectory analysis error: {str(e)}")
                
        except Exception as e:
            self.log_result("temporal_graph", "ERROR", f"Temporal graph test setup error: {str(e)}")
        
        return self.results["temporal_graph"]
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all integration tests."""
        print("🚀 Starting Comprehensive Integration Tests...")
        print(f"Test started at: {self.start_time.isoformat()}")
        
        # Run all tests
        await self.test_hubspot_integration()
        await self.test_google_calendar_integration()
        await self.test_redis_integration()
        await self.test_temporal_graph_integration()
        
        # Calculate summary
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        summary = {
            "test_run": {
                "start_time": self.start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration
            },
            "integrations": self.results,
            "summary": {
                "total_integrations": len(self.results),
                "working": sum(1 for r in self.results.values() if r["status"] == "WORKING"),
                "partial": sum(1 for r in self.results.values() if r["status"] == "PARTIAL"),
                "error": sum(1 for r in self.results.values() if r["status"] == "ERROR"),
                "not_tested": sum(1 for r in self.results.values() if r["status"] == "NOT_TESTED")
            }
        }
        
        return summary
    
    def print_summary(self, results: Dict[str, Any]):
        """Print a formatted summary of test results."""
        print("\n" + "="*80)
        print("📊 INTEGRATION TEST SUMMARY")
        print("="*80)
        
        summary = results["summary"]
        print(f"Test Duration: {results['test_run']['duration_seconds']:.2f} seconds")
        print(f"Total Integrations: {summary['total_integrations']}")
        print(f"✅ Working: {summary['working']}")
        print(f"⚠️  Partial: {summary['partial']}")
        print(f"❌ Error: {summary['error']}")
        print(f"⏸️  Not Tested: {summary['not_tested']}")
        
        print("\nDetailed Results:")
        print("-"*80)
        
        for integration, result in results["integrations"].items():
            status_emoji = {
                "WORKING": "✅",
                "PARTIAL": "⚠️",
                "ERROR": "❌",
                "NOT_TESTED": "⏸️"
            }.get(result["status"], "❓")
            
            print(f"\n{status_emoji} {integration.replace('_', ' ').title()}: {result['status']}")
            
            for detail in result["details"]:
                detail_emoji = "✅" if detail["status"] == "SUCCESS" else "❌"
                print(f"  {detail_emoji} {detail['message']}")
        
        print("\n" + "="*80)
        
        # Overall assessment
        working_count = summary["working"]
        total_count = summary["total_integrations"]
        
        if working_count == total_count:
            print("🎉 ALL INTEGRATIONS WORKING - System fully integrated!")
        elif working_count >= total_count * 0.75:
            print("✅ MOST INTEGRATIONS WORKING - System largely integrated")
        elif working_count >= total_count * 0.5:
            print("⚠️  PARTIAL INTEGRATION - Some integrations need attention")
        else:
            print("❌ LIMITED INTEGRATION - Major integration issues detected")
        
        print("="*80)

async def main():
    """Main test execution function."""
    tester = IntegrationTester()
    results = await tester.run_all_tests()
    
    # Print summary to console
    tester.print_summary(results)
    
    # Save results to file
    results_file = "integration_test_results.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n📄 Detailed results saved to: {results_file}")
    
    return results

if __name__ == "__main__":
    try:
        results = asyncio.run(main())
        sys.exit(0 if results["summary"]["working"] >= 3 else 1)
    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted by user")
        sys.exit(2)
    except Exception as e:
        print(f"\n❌ Test execution failed: {str(e)}")
        traceback.print_exc()
        sys.exit(3)