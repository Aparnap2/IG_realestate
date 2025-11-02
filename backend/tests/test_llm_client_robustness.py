"""
Comprehensive tests for LLM client robustness and failure handling.

Tests circuit breaker patterns, fallback mechanisms, performance monitoring,
and SLA compliance for the enhanced LLM client implementation.
"""

import pytest
import asyncio
import os
import time
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

# Import the LLM client components
import sys
sys.path.append('/home/aparna/Desktop/IG_realestate/backend')
from utils.llm_client import (
    CircuitBreaker, CircuitState, PerformanceMonitor,
    get_llm_response, get_llm_response_sync, extract_lead_info,
    generate_response_message, get_llm_health_status,
    reset_circuit_breakers, clear_performance_metrics,
    validate_api_key_environment, local_extract_lead_info,
    generate_contextual_fallback
)

class TestCircuitBreaker:
    """Test circuit breaker functionality."""
    
    def test_circuit_breaker_closed_state(self):
        """Test circuit breaker starts in CLOSED state."""
        cb = CircuitBreaker(failure_threshold=3, timeout=60)
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
    
    def test_circuit_breaker_opens_after_threshold(self):
        """Test circuit breaker opens after reaching failure threshold."""
        cb = CircuitBreaker(failure_threshold=2, timeout=60)
        
        # Mock function that always fails
        def failing_function():
            raise Exception("API failure")
        
        # First failure
        with pytest.raises(Exception):
            cb.call(failing_function)
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 1
        
        # Second failure - should open circuit
        with pytest.raises(Exception):
            cb.call(failing_function)
        assert cb.state == CircuitState.OPEN
        assert cb.failure_count == 2
        
        # Third call should be rejected immediately
        with pytest.raises(Exception, match="Circuit breaker is OPEN"):
            cb.call(failing_function)
    
    def test_circuit_breaker_half_open_recovery(self):
        """Test circuit breaker recovery from HALF_OPEN state."""
        cb = CircuitBreaker(failure_threshold=2, timeout=0.1)  # Short timeout for testing
        
        # Trigger failure to open circuit
        def failing_function():
            raise Exception("API failure")
        
        with pytest.raises(Exception):
            cb.call(failing_function)
        with pytest.raises(Exception):
            cb.call(failing_function)
        
        assert cb.state == CircuitState.OPEN
        
        # Wait for timeout period
        time.sleep(0.2)
        
        # Next call should move to HALF_OPEN
        with pytest.raises(Exception):
            cb.call(failing_function)
        assert cb.state == CircuitState.HALF_OPEN
        
        # Successful call should reset to CLOSED
        def success_function():
            return "success"
        
        result = cb.call(success_function)
        assert result == "success"
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
    
    def test_circuit_breaker_success_resets_failures(self):
        """Test that successful calls reset failure count."""
        cb = CircuitBreaker(failure_threshold=3, timeout=60)
        
        def failing_function():
            raise Exception("API failure")
        
        # Trigger some failures
        for _ in range(2):
            with pytest.raises(Exception):
                cb.call(failing_function)
        
        assert cb.failure_count == 2
        
        # Successful call should reset count
        def success_function():
            return "success"
        
        result = cb.call(success_function)
        assert result == "success"
        assert cb.failure_count == 0

class TestPerformanceMonitor:
    """Test performance monitoring and SLA compliance."""
    
    def test_performance_monitor_empty_state(self):
        """Test performance monitor with no data."""
        pm = PerformanceMonitor()
        metrics = pm.get_metrics()
        
        assert metrics["status"] == "no_data"
        assert metrics["avg_response_time"] == 0
        assert metrics["error_rate"] == 0
        assert metrics["sla_compliance"] == 100.0
        assert metrics["total_requests"] == 0
    
    def test_performance_monitor_tracks_response_times(self):
        """Test performance monitor tracks response times."""
        pm = PerformanceMonitor()
        
        # Simulate requests with different response times
        pm.start_request()
        time.sleep(0.01)  # 10ms
        pm.end_request(success=True)
        
        pm.start_request()
        time.sleep(0.02)  # 20ms
        pm.end_request(success=False, error="API timeout")
        
        pm.start_request()
        time.sleep(0.005)  # 5ms
        pm.end_request(success=True)
        
        metrics = pm.get_metrics()
        
        assert metrics["total_requests"] == 3
        assert metrics["error_rate"] == pytest.approx(33.33, rel=1e-2)
        assert metrics["sla_compliance"] == 100.0  # All under 60s SLA
        assert metrics["min_response_time"] == pytest.approx(0.005, rel=1e-2)
        assert metrics["max_response_time"] == pytest.approx(0.02, rel=1e-2)
    
    def test_performance_monitor_sla_violations(self):
        """Test performance monitor detects SLA violations."""
        pm = PerformanceMonitor(sla_threshold=0.01)  # 10ms SLA
        
        # Request within SLA
        pm.start_request()
        time.sleep(0.005)  # 5ms
        pm.end_request(success=True)
        
        # Request violating SLA
        pm.start_request()
        time.sleep(0.02)  # 20ms (violates 10ms SLA)
        pm.end_request(success=True)
        
        metrics = pm.get_metrics()
        assert metrics["sla_compliance"] == pytest.approx(50.0, rel=1e-2)
    
    def test_performance_monitor_window_size_limit(self):
        """Test performance monitor respects window size limit."""
        pm = PerformanceMonitor(window_size=3)
        
        # Add more requests than window size
        for i in range(5):
            pm.start_request()
            time.sleep(0.001)
            pm.end_request(success=True)
        
        metrics = pm.get_metrics()
        assert metrics["total_requests"] == 3  # Window size limit

class TestAPIFallbackMechanisms:
    """Test API fallback mechanisms and local processing."""
    
    @patch.dict(os.environ, {}, clear=True)
    def test_no_api_keys_uses_local_fallback(self):
        """Test that missing API keys trigger local fallback."""
        # Clear all API keys
        env_keys = ["OPENAI_API_KEY", "OPENROUTER_API_KEY", "GOOGLE_API_KEY"]
        original_values = {key: os.environ.get(key) for key in env_keys}
        
        try:
            for key in env_keys:
                os.environ.pop(key, None)
            
            api_status = validate_api_key_environment()
            assert not api_status["openai"]
            assert not api_status["openrouter"]
            assert not api_status["google"]
            assert not api_status["has_any_llm"]
            
        finally:
            # Restore original values
            for key, value in original_values.items():
                if value:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)
    
    def test_local_lead_extraction(self):
        """Test local lead extraction functionality."""
        # Test budget extraction
        message = "I'm looking for a house under $500,000"
        result = local_extract_lead_info(message)
        
        assert result["budget"] == 500000.0
        assert "house" in result["property_type"].lower()
        
        # Test location extraction
        message = "I'm interested in properties in Downtown Austin"
        result = local_extract_lead_info(message)
        
        assert "downtown" in result["location"].lower()
        
        # Test property type extraction
        message = "Looking for a 3BHK apartment"
        result = local_extract_lead_info(message)
        
        assert result["property_type"] == "3BHK"
    
    def test_contextual_fallback_messages(self):
        """Test contextual fallback message generation."""
        # Test lead extraction fallback
        prompt = "extract lead information from message"
        fallback = generate_contextual_fallback(prompt)
        
        assert "Extraction service temporarily unavailable" in fallback
        
        # Test qualifier fallback
        prompt = "qualification agent response"
        fallback = generate_contextual_fallback(prompt)
        
        assert "budget range" in fallback.lower()
        assert "location" in fallback.lower()
        
        # Test scheduler fallback
        prompt = "schedule property tour"
        fallback = generate_contextual_fallback(prompt)
        
        assert "schedule" in fallback.lower() or "consultation" in fallback.lower()

class TestHealthMonitoring:
    """Test health monitoring and status reporting."""
    
    def test_health_status_with_no_data(self):
        """Test health status when no requests have been made."""
        clear_performance_metrics()
        reset_circuit_breakers()
        
        status = get_llm_health_status()
        
        assert "status" in status
        assert "timestamp" in status
        assert "api_availability" in status
        assert "circuit_breakers" in status
        assert "performance_metrics" in status
        assert "sla_compliance" in status
        assert "recommendations" in status
    
    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test_key"})
    def test_health_status_with_configured_apis(self):
        """Test health status when APIs are configured."""
        status = get_llm_health_status()
        
        assert status["api_availability"]["openrouter"] == True
        assert status["api_availability"]["has_any_llm"] == True
    
    def test_health_recommendations(self):
        """Test health recommendations generation."""
        status = get_llm_health_status()
        recommendations = status["recommendations"]
        
        assert isinstance(recommendations, list)
        assert len(recommendations) > 0
        assert "Configure" in recommendations[0] or "All systems operational" in recommendations[0]

class TestRobustErrorHandling:
    """Test comprehensive error handling scenarios."""
    
    @patch('utils.llm_client.aiohttp.ClientSession.post')
    async def test_openrouter_api_failure_handling(self, mock_post):
        """Test OpenRouter API failure handling."""
        # Mock aiohttp response for API failure
        mock_response = MagicMock()
        mock_response.status = 500
        mock_response.text = asyncio.coroutine(lambda: "Internal Server Error")
        mock_post.return_value.__aenter__.return_value = mock_response
        
        # Should fall back to local processing
        result = await get_llm_response("Test prompt")
        
        # Should return fallback message, not crash
        assert result is not None
        assert "service temporarily unavailable" in result.lower()
    
    @patch('utils.llm_client.os.getenv')
    def test_sync_error_handling(self, mock_getenv):
        """Test synchronous error handling."""
        # Mock no API keys
        mock_getenv.return_value = None
        
        result = get_llm_response_sync("Test prompt")
        
        # Should return fallback without crashing
        assert result is not None
    
    def test_extract_lead_info_with_no_apis(self):
        """Test lead extraction with no API availability."""
        with patch('utils.llm_client.validate_api_key_environment') as mock_validate:
            mock_validate.return_value = {
                "openai": False,
                "openrouter": False, 
                "google": False,
                "has_any_llm": False
            }
            
            result = extract_lead_info("I'm looking for a $300k house in Austin")
            
            # Should use local extraction
            assert isinstance(result, dict)
            assert "budget" in result
            assert result["budget"] == 300000.0

class TestSLACompliance:
    """Test SLA compliance and timeout handling."""
    
    @pytest.mark.asyncio
    async def test_request_timeout_handling(self):
        """Test timeout handling for slow requests."""
        with patch('utils.llm_client.aiohttp.ClientSession.post') as mock_post:
            # Mock timeout
            mock_post.side_effect = asyncio.TimeoutError()
            
            result = await get_llm_response("Test prompt", timeout=1)
            
            # Should handle timeout gracefully and return fallback
            assert result is not None
    
    def test_sla_threshold_compliance(self):
        """Test SLA threshold compliance."""
        pm = PerformanceMonitor(sla_threshold=1.0)  # 1 second SLA
        
        # Simulate requests
        for _ in range(5):
            pm.start_request()
            time.sleep(0.5)  # Within SLA
            pm.end_request(success=True)
        
        metrics = pm.get_metrics()
        assert metrics["sla_compliance"] == 100.0

class TestIntegrationScenarios:
    """Test integration scenarios and real-world failure cases."""
    
    @pytest.mark.asyncio
    async def test_cascading_failure_recovery(self):
        """Test system recovery from cascading failures."""
        clear_performance_metrics()
        reset_circuit_breakers()
        
        # Simulate multiple API failures
        with patch('utils.llm_client.aiohttp.ClientSession.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status = 503
            mock_response.text = asyncio.coroutine(lambda: "Service Unavailable")
            mock_post.return_value.__aenter__.return_value = mock_response
            
            # Multiple failures should trigger circuit breaker
            for _ in range(5):
                result = await get_llm_response("Test prompt")
                assert result is not None  # Should always return fallback
            
            # Check that circuit breaker opened
            status = get_llm_health_status()
            assert status["circuit_breakers"]["openrouter"] == CircuitState.OPEN
    
    def test_performance_degradation_handling(self):
        """Test handling of performance degradation."""
        clear_performance_metrics()
        
        pm = PerformanceMonitor(sla_threshold=0.1)
        
        # Simulate slow responses
        for _ in range(10):
            pm.start_request()
            time.sleep(0.15)  # Over SLA threshold
            pm.end_request(success=True)
        
        metrics = pm.get_metrics()
        assert metrics["sla_compliance"] < 100.0
        assert metrics["avg_response_time"] > 0.1
    
    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test_key"})
    @pytest.mark.asyncio
    async def test_partial_api_availability(self):
        """Test behavior with partial API availability."""
        clear_performance_metrics()
        
        with patch('utils.llm_client.aiohttp.ClientSession.post') as mock_post:
            # Mock successful response
            mock_response = MagicMock()
            mock_response.status = 200
            
            async def mock_json():
                return {
                    "choices": [{
                        "message": {
                            "content": "Test response from OpenRouter"
                        }
                    }]
                }
            
            mock_response.json = mock_json
            mock_post.return_value.__aenter__.return_value = mock_response
            
            result = await get_llm_response("Test prompt")
            
            assert "Test response from OpenRouter" in result
            
            # Check performance metrics
            metrics = pm.get_metrics()
            assert metrics["total_requests"] == 1
            assert metrics["error_rate"] == 0.0

if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])