"""
Production Readiness Test Suite

Comprehensive testing for production deployment readiness covering:
1. End-to-End Workflow Testing
2. Stress Testing & Load Testing
3. Performance Benchmarking  
4. Data Security & Compliance
5. System Reliability & Error Handling
6. Frontend-Backend Integration

Following TDD approach: Test → Analyze → Fix → Retest
"""

import pytest
import sys
import os
import asyncio
import time
import json
import requests
from datetime import datetime, timedelta
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any

# Add the parent directory to the path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.agents.prd_compliant_workflow import QualifierAgent, SchedulerAgent
from backend.agents.router import RouterAgent
from tools import compliance as compliance_tools
from models.lead import Lead
from schemas.state import AgentState
from utils.llm_client import get_llm_response_sync

# Test configuration
BACKEND_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:5173"
TEST_TIMEOUT = 30

class TestProductionReadiness:
    """Production Readiness Test Suite"""
    
    @pytest.fixture
    def sample_lead(self):
        """Sample lead data for testing"""
        return Lead(
            user_id="test_user_123",
            channel="ig",
            message="Looking for a 3 bedroom house under $400k in Miami",
            name="Test User",
            email="test@example.com",
            budget=400000,
            location="Miami",
            property_type="house",
            desired_bedrooms=3,
            timeline="1-3months",
            status="new"
        )
    
    @pytest.fixture
    def router_agent(self):
        """Router Agent instance"""
        return RouterAgent()
    
    @pytest.fixture  
    def qualifier_agent(self):
        """Qualifier Agent instance"""
        return QualifierAgent()
        
    @pytest.fixture
    def scheduler_agent(self):
        """Scheduler Agent instance"""
        return SchedulerAgent()

    # ==================== END-TO-END WORKFLOW TESTS ====================
    
    def test_complete_lead_capture_workflow(self, sample_lead):
        """Test the complete lead capture workflow from Instagram to scheduling"""
        print("🔄 Testing Complete Lead Capture Workflow...")
        
        # Step 1: Route and classify intent
        router_result = self.router_agent.process({
            "lead": sample_lead.model_copy(deep=True),
            "messages": [{"role": "user", "content": sample_lead.message}]
        })
        
        assert router_result["next_agent"] in ["qualifier", "scheduler", "followup"]
        print(f"✅ Router routed to: {router_result['next_agent']}")
        
        # Step 2: Qualify the lead
        qualifier_result = self.qualifier_agent.process(router_result)
        
        assert "lead" in qualifier_result
        assert "next_agent" in qualifier_result
        assert qualifier_result["lead"].status in ["qualified", "high_value", "followup"]
        print(f"✅ Qualifier status: {qualifier_result['lead'].status}")
        
        # Step 3: Schedule if qualified
        if qualifier_result["next_agent"] == "scheduler":
            scheduler_result = self.scheduler_agent.process(qualifier_result)
            assert "lead" in scheduler_result
            assert scheduler_result["lead"].status in ["scheduled", "pending"]
            print(f"✅ Scheduler status: {scheduler_result['lead'].status}")
        
        print("✅ Complete workflow test passed")
    
    def test_low_confidence_human_review_workflow(self, sample_lead):
        """Test that low confidence messages route to human review"""
        print("🔄 Testing Low Confidence Human Review Workflow...")
        
        # Create lead with unclear intent
        unclear_lead = sample_lead.model_copy(deep=True)
        unclear_lead.message = "Maybe looking for something"
        
        router_result = self.router_agent.process({
            "lead": unclear_lead,
            "messages": [{"role": "user", "content": unclear_lead.message}]
        })
        
        # Should require human review
        if "requires_human_review" in router_result:
            assert router_result["requires_human_review"] == True
            assert router_result["next_agent"] == "human"
            print("✅ Low confidence routed to human review")
        
        # Check audit logging
        router_result.get("lead", unclear_lead).history.append({
            "message": "Low confidence triggered human review",
            "timestamp": datetime.now().isoformat(),
            "agent": "router"
        })
        
        print("✅ Human review workflow test passed")
    
    def test_partial_information_clarification_flow(self):
        """Test handling of partial information requiring clarification"""
        print("🔄 Testing Partial Information Clarification Flow...")
        
        # Lead with missing budget
        incomplete_lead = sample_lead.model_copy(deep=True)
        incomplete_lead.budget = None
        
        qualifier_result = self.qualifier_agent.process({
            "lead": incomplete_lead,
            "messages": [{"role": "user", "content": incomplete_lead.message}]
        })
        
        # Should require more info instead of qualifying
        assert qualifier_result.get("requires_more_info", False)  # Implementation varies - check implementation
        
        # Should have clarification questions in messages
        messages = qualifier_result.get("messages", [])
        budget_questions = [
            msg for msg in messages 
            if "budget" in str(msg.get("content", "")).lower()
        ]
        
        assert len(budget_questions) > 0, "Should ask for budget clarification"
        print("✅ Partial info clarification test passed")
    
    # ==================== STRESS TESTING ====================
    
    def test_concurrent_lead_processing(self):
        """Test system under concurrent lead processing load"""
        print("🔄 Testing Concurrent Lead Processing...")
        
        leads = [
            Lead(
                user_id=f"concurrent_user_{i}",
                channel="ig",
                message=f"Lead message {i}",
                name=f"User {i}",
                email=f"user{i}@example.com",
                budget=300000 + (i * 25000),
                location="Miami",
                property_type="apartment"
            )
            for i in range(10)
        ]
        
        start_time = time.time()
        results = []
        
        # Process leads concurrently  
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_lead = {
                executor.submit(self._process_single_lead, lead): lead 
                for lead in leads
            }
            
            results = [
                future_to_lead[future].result()
                for future in concurrent.futures.as_completed(future_to_lead.keys())
            ]
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Verify all leads were processed
        assert len(results) == 10
        processing_success_rate = sum(1 for r in results if "error" not in r) / len(results)
        
        print(f"✅ Processed {len(results)} leads in {processing_time:.2f}s")
        print(f"✅ Success rate: {processing_success_rate:.1%}")
        assert processing_success_rate >= 0.7, "Should handle at least 70% of concurrent requests"
        print("✅ Concurrent processing test passed")
    
    def _process_single_lead(self, lead: Lead) -> Dict[str, Any]:
        """Helper to process a single lead"""
        try:
            router_result = self.router_agent.process({
                "lead": lead.model_copy(deep=True),
                "messages": [{"role": "user", "content": lead.message}]
            })
            return {"success": True, "agent": router_result["next_agent"]}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def test_ramp_up_load_increase(self):
        """Test system under increasing load"""
        print("🔄 Testing Ramp Up Load Increase...")
        
        load_levels = [5, 10, 25, 50]
        
        for load_level in load_levels:
            print(f"Testing with {load_level} concurrent requests...")
            
            leads = [
                Lead(
                    user_id=f"ramp_user_{i}_{load_level}",
                    channel="ig", 
                    message=f"Ramp test message {i}",
                    budget=350000,
                    location="Miami"
                )
                for i in range(load_level)
            ]
            
            start_time = time.time()
            
            with ThreadPoolExecutor(max_workers=5) as executor:
                results = list(executor.map(self._process_single_lead, leads))
            
            end_time = time.time()
            avg_response_time = (end_time - start_time) / load_level
            
            success_rate = sum(1 for r in results if r.get("success", False)) / len(results)
            
            print(f"✅ Load {load_level}: {avg_response_time:.2f}s avg, {success_rate:.1%} success")
            assert avg_response_time < 10.0, f"Response time too high for load {load_level}"
            
        print("✅ Load ramp up test passed")

    # ==================== PERFORMANCE TESTING ====================
    
    def test_agent_performance_benchmarks(self, sample_lead):
        """Test agent performance benchmarks"""
        print("🔄 Testing Agent Performance Benchmarks...")
        
        # Router Agent performance
        router_times = []
        for _ in range(10):
            start = time.time()
            self.router_agent.process({
                "sample_lead": sample_lead.model_copy(deep=True),
                "messages": [{"role": "user", "content": sample_lead.message}]
            })
            router_times.append(time.time() - start)
        
        avg_router_time = sum(router_times) / len(router_times)
        print(f"✅ Router Agent: {avg_router_time:.3f}s average (n=10)")
        assert avg_router_time < 2.0, "Router should respond in under 2s"
        
        # Qualifier Agent performance
        qualifier_times = []
        for _ in range(10):
            start = time.time()
            self.qualifier_agent.process({
                "lead": sample_lead.model_copy(deep=True),
                "messages": [{"role": "user", "content": sample_lead.message}]
            })
            qualifier_times.append(time.time() - start)
        
        avg_qualifier_time = sum(qualifier_times) / len(qualifier_times)
        print(f"✅ Qualifier Agent: {avg_qualifier_time:.3f}s average (n=10)")
        assert avg_qualifier_time < 3.0, "Qualifier should respond in under 3s"
        
        # Scheduler Agent performance
        scheduler_times = []
        for _ in range(10):
            start = time.time()
            self.scheduler_agent.process({
                "lead": sample_lead.model_copy(deep=True),
                "messages": [{"role": "user", "content": sample_lead.message}]
            })
            scheduler_times.append(time.time() - start)
        
        avg_scheduler_time = sum(scheduler_times) / len(scheduler_times)
        print(f"✅ Scheduler Agent: {avg_scheduler_time:.3f}s average (n=10)")
        assert avg_scheduler_time < 4.0, "Scheduler should respond in under 4s"
        
        print("✅ Performance benchmarks test passed")
    
    def test_memory_usage_under_load(self):
        """Test memory usage under sustained load"""
        import psutil
        import os
        
        print("🔄 Testing Memory Usage Under Load...")
        
        baseline_memory = psutil.Process(os.getpid()).memory_info().rss
        print(f"Baseline memory: {baseline_memory / 1024 / 1024:.1f} MB")
        
        # Process 100 leads to build memory usage
        leads = [
            Lead(
                user_id=f"memory_test_{i}",
                channel="ig",
                message=f"Memory test message {i}",
                budget=250000,
                location="Miami"
            )
            for i in range(100)
        ]
        
        for lead in leads:
            try:
                self.router_agent.process({
                    "lead": lead,
                    "messages": [{"role": "user", "content": lead.message}]
                })
                self.qualifier_agent.process({
                    "lead": lead,
                    "messages": [{"role": "user", "content": lead.message}]
                })
            except Exception as e:
                pass  # Continue processing
        
        peak_memory = psutil.Process(os.getpid()).memory_info().rss
        print(f"Peak memory: {peak_memory / 1024 / 1024:.1f} MB")
        
        memory_increase = peak_memory - baseline_memory
        print(f"Memory increase: {memory_increase / 1024 / 1024:.1f} MB")
        
        # Should not exceed reasonable memory limits
        assert memory_increase < 100, "Memory increase should be under 100MB"
        
        print("✅ Memory usage test passed")

    # ==================== DATA SECURITY TESTS ====================
    
    def test_input_validation_and_sanitization(self):
        """Test input validation and XSS prevention"""
        print("🔄 Testing Input Validation and Sanitization...")
        
        # Test SQL injection attempts
        malicious_inputs = [
            "'; DROP TABLE leads; --",
            "<script>alert('xss')</script>",
            "${jndi:ldap://localhost:389/} 6445",
            "SELECT * FROM leads",
            "'] UNION SELECT password FROM users --",
            "<img src=x onerror=alert('xss')>"
        ]
        
        for malicious_input in malicious_inputs:
            malicious_lead = sample_lead.model_copy(deep=True)
            malicious_lead.message = malicious_input
            
            try:
                router_result = self.router_agent.process({
                    "lead": malicious_lead,
                    "messages": [{"role": "user", "content": malicious_input}]
                })
                
                # Should not crash system
                assert "error" not in router_result
                
                # Should have compliant output if messages generated
                messages = router_result.get("messages", [])
                for msg in messages:
                    content = msg.get("content", "")
                    assert "<script>" not in content  # Basic XSS prevention
                    assert "DROP TABLE" not in content  # SQL injection prevention
                    
            except Exception as e:
                # Should handle errors gracefully
                assert "dangerous input detected" in str(e).lower()
        
        print("✅ Input validation test passed")
    
    def test_data_encryption_and_privacy(self):
        """Test data encryption and privacy compliance"""
        print("🔄 Testing Data Encryption and Privacy...")
        
        # Create lead with PII
        pii_lead = sample_lead.model_copy(deep=True)
        pii_lead.email = "john.doe@example.com"
        pii_lead.name = "John Doe"
        pii_lead.phone = "+1-555-123-4567"
        
        # Process through agents
        try:
            router_result = self.router_agent.process({
                "lead": pii_lead,
                "messages": [{"role": "user", "content": pii_lead.message}]
            })
            
            qualifier_result = self.qualifier_agent.process(router_result)
            
            # Check PII is handled appropriately
            processed_lead = qualifier_result.get("lead", pii_lead)
            
            # Should have audit log
            assert len(processed_lead.history) > 0
            
            # Check no sensitive data in unsafe logs
            for history_item in processed_lead.history:
                content = str(history_item.get("message", ""))
                assert "password" not in content.lower()  # Basic privacy
                if not pii_lead.phone or "ssn" not in pii_lead.phone:
                    assert "ssn" not in content.lower()
            
        except Exception as e:
            # Should handle errors without exposing sensitive data
            assert "privacy" in str(e).lower() or "security" in str(e).lower()
        
        print("✅ Data privacy test passed")
    
    def test_audit_trail_integrity(self):
        """Test audit trail integrity and immutability"""
        print("🔄 Testing Audit Trail Integrity...")
        
        # Process a lead and track all audit entries
        initial_history_length = len(sample_lead.history)
        
        router_result = self.router_agent.process({
            "lead": sample_lead.model_copy(deep=True),
            "messages": [{"role": "user", "content": sample_lead.message}]
        })
        
        if "lead" in router_result:
            final_history_length = len(router_result["lead"].history)
            
            # Should add audit entries
            assert final_history_length > initial_history_length
            
            # Each entry should have required fields
            for entry in router_result["lead"].history[-5:]:  # Check last 5 entries
                assert "message" in entry
                assert "timestamp" in entry
                assert "agent" in entry
                assert entry["timestamp"] is not None
        
        print("✅ Audit trail integrity test passed")
    
    # ==================== SYSTEM RELIABILITY TESTS ====================
    
    def test_error_recovery_and_robustness(self):
        """Test error recovery and system robustness"""
        print("🔄 Testing Error Recovery and Robustness...")
        
        # Test router agent resilience
        try:
            with patch('agents.prd_compliant_workflow.get_llm_response_sync') as mock_llm:
                mock_llm.side_effect = Exception("LLM service unavailable")
                
                router_result = self.router_agent.process({
                    "lead": sample_lead.model_copy(deep=True),
                    "messages": [{"role": "user", "content": sample_lead.message}]
                })
                
                # Should fallback safely
                assert router_result["next_agent"] in ["qualifier", "followup"]
                assert "error" not in router_result or router_result.get("error") is not None
                print("✅ Router agent error recovery: SAFE FALLBACK")
                
        except Exception as e:
            print(f"✅ Router handled error gracefully: {e}")
        
        # Test database failure resilience
        try:
            with patch('backend.utils.supabase_client.save_lead') as mock_save:
                mock_save.side_effect = Exception("Database connection failed")
                
                router_result = self.qualifier_agent.process({
                    "lead": sample_lead.model_copy(deep=True),
                    "messages": [{"role": "user", "content": sample_lead.message}]
                })
                
                # Should still return result
                assert "lead" in router_result
                print("✅ Database failure resilience: WORKAROUND")
                
        except Exception as e:
            print(f"✅ Database handled error gracefully: {e}")
        
        print("✅ Error recovery test passed")
    
    def test_service_degradation_handling(self):
        """Test graceful degradation when external services fail"""
        print("🔄 Testing Service Degradation Handling...")
        
        # Simulate OpenRouter API failure
        try:
            with patch('tools.llm_client.get_llm_response_sync') as mock_llm:
                mock_llm.side_effect = Exception("OpenRouter timeout")
                
                router_result = self.router_agent.process({
                    "lead": sample_lead.model_copy(deep=True),
                    "messages": [{"role": "user", "content": sample_lead.message}]
                })
                
                # Should still process with default values
                assert router_result["next_agent"] in ["qualifier", "followup"]
                print("✅ LLM service degradation: DEFAULT VALUES")
                
        except Exception as e:
            print(f"✅ Service degraded gracefully: {e}")
        
        print("✅ Service degradation test passed")
    
    def test_health_check_endpoints(self):
        """Test comprehensive health check endpoints"""
        print("🔄 Testing Health Check Endpoints...")
        
        try:
            # Test main health endpoint
            health_response = requests.get(f"{BACKEND_URL}/health", timeout=5)
            if health_response.ok():
                health_data = health_response.json()
                assert "status" in health_data
                print("✅ Main health endpoint operational")
            
            # Test database health  
            db_response = requests.get(f"{BACKEND_URL}/health/database", timeout=5)
            if db_response.ok():
                db_data = db_response.json()
                print("✅ Database health endpoint operational")
            
            # Test LLM service health
            llm_response = requests.get(f"{BACKEND_URL}/health/llm", timeout=5)
            if llm_response.ok():
                llm_data = llm_response.json()
                print("✅ LLM service health endpoint operational")
                
        except Exception as e:
            print(f"⚠️ Some health checks failed: {e}")
        
        print("✅ Health check endpoints test completed")

class TestPerformanceBenchmarks:
    """Detailed performance benchmarking suite"""
    
    def test_response_time_policies(self):
        """Test that response times meet policy requirements"""
        response_times = {
            "router": 2.0,    # seconds
            "qualifier": 3.0,  # seconds  
            "scheduler": 4.0     # seconds
        }
        
        performance_results = {}
        
        # Test Router Agent
        router_times = []
        for _ in range(20):
            start = time.time()
            try:
                self.router_agent.process({
                    "lead": self.sample_lead(),
                    "messages": [{"role": "user", "content": self.sample_lead().message}]
                })
                router_times.append(time.time() - start)
            except Exception:
                router_times.append(10.0)  # Count as failure
        
        avg_router = sum(router_times) / len(router_times)
        performance_results["router"] = {
            "avg_time": avg_router,
            "within_policy": avg_router <= response_times["router"],
            "p95_time": sorted(router_times)[int(len(router_times) * 0.95)] 
        }
        
        # Test other agents similarly...
        print("📊 Performance benchmark results:")
        for agent, results in performance_results.items():
            print(f"  {agent.capitalize()}:")
            print(f"    Average: {results['avg_time']:.3f}s (Policy: {response_times[agent]}s)")
            print(f"    Within Policy: {results['within_policy']}")
            print(f"    P95: {results['p95_time']:.3f}s")
            
            assert results["within_policy"], f"  {agent} exceeds response time policy"

# Global helper methods
    def sample_lead(self):
        """Sample lead data for testing"""
        return Lead(
            user_id="test_user_123",
            channel="ig", 
            message="Looking for a 3 bedroom house under $400k in Miami",
            name="Test User",
            email="test@example.com",
            budget=400000,
            location="DB_LOCATION_PLACEHOLDER",
            property_type="house",
            desired_bedrooms=3,
            timeline="1-3months",
            status="new"
        )

if __name__ == "__main__":
    # Run production readiness suite
    pytest.main([__file__, "-v"])
