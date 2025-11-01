"""
Comprehensive test suite for Universal Lead Processing Pipeline

Tests all components integration, LangGraph workflow orchestration,
and industry-adaptive lead processing capabilities.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any

# Import the universal lead processor
from backend.pipeline.universal_lead_processor import (
    UniversalLeadProcessor,
    WorkflowType,
    IndustryType,
    LeadReadinessAssessment,
    ProcessingContext,
    universal_lead_processor,
    process_message
)

class TestUniversalLeadProcessor:
    """Test cases for Universal Lead Processor"""
    
    @pytest.fixture
    def processor(self):
        """Create processor instance for testing"""
        return UniversalLeadProcessor()
    
    @pytest.fixture
    def sample_context(self):
        """Create sample processing context"""
        return ProcessingContext(
            user_id="test_user_123",
            message="I'm looking for a 3-bedroom house in downtown area",
            channel="instagram",
            user_name="John Doe",
            industry_type="real_estate",
            lead_data={"budget": 500000, "location": "downtown"},
            conversation_history=[],
            previous_scores=[0.7, 0.8],
            touch_points=[],
            processing_start_time=datetime.now(),
            metadata={}
        )
    
    @pytest.fixture
    def sample_assessment(self):
        """Create sample lead readiness assessment"""
        return LeadReadinessAssessment(
            user_id="test_user_123",
            industry_type="real_estate",
            booking_readiness=True,
            nurture_required=False,
            immediate_response=False,
            qualification_gathering=False,
            readiness_score=0.85,
            confidence_level=0.9,
            assessment_factors={"enhanced_score": 0.85, "response_urgency": 0.7},
            recommended_workflow=WorkflowType.BOOKING_FLOW,
            next_steps=["Schedule consultation", "Confirm requirements"],
            assessment_timestamp=datetime.now()
        )

class TestIndustryDetection:
    """Test industry detection and configuration management"""
    
    @pytest.mark.asyncio
    async def test_detect_real_estate_industry(self, processor):
        """Test detection of real estate industry"""
        message = "I'm looking for a 3-bedroom house with garden"
        conversation_history = []
        
        result = await processor.detect_and_configure_industry(
            "test_user", message, conversation_history
        )
        
        assert result["industry_type"] == "real_estate"
        assert "industry_config" in result
        assert result["confidence"] > 0.5
        assert "extracted_info" in result
    
    @pytest.mark.asyncio
    async def test_detect_fitness_industry(self, processor):
        """Test detection of fitness industry"""
        message = "I want to join a gym with personal training"
        conversation_history = []
        
        result = await processor.detect_and_configure_industry(
            "test_user", message, conversation_history
        )
        
        assert result["industry_type"] == "fitness"
        assert "industry_config" in result
    
    @pytest.mark.asyncio
    async def test_industry_detection_fallback(self, processor):
        """Test fallback to default industry on error"""
        with patch.object(processor.industry_config_manager, 'detect_industry_type', side_effect=Exception("Test error")):
            result = await processor.detect_and_configure_industry(
                "test_user", "test message", []
            )
            
            assert result["industry_type"] == "real_estate"  # Default fallback
            assert "error" in result

class TestLeadReadinessAssessment:
    """Test lead readiness assessment functionality"""
    
    @pytest.mark.asyncio
    async def test_high_readiness_assessment(self, processor):
        """Test assessment for high-readiness lead"""
        lead_data = {
            "budget": 500000,
            "location": "downtown",
            "timeline": "immediate",
            "contact_info": "john@example.com"
        }
        
        assessment = await processor.assess_lead_readiness(
            "test_user", lead_data, "real_estate"
        )
        
        assert assessment.readiness_score > 0.7
        assert assessment.booking_readiness == True
        assert assessment.confidence_level > 0.8
    
    @pytest.mark.asyncio
    async def test_low_readiness_assessment(self, processor):
        """Test assessment for low-readiness lead"""
        lead_data = {
            "message": "just browsing",
            "timeline": "maybe someday"
        }
        
        assessment = await processor.assess_lead_readiness(
            "test_user", lead_data, "real_estate"
        )
        
        assert assessment.readiness_score < 0.5
        assert assessment.qualification_gathering == True
        assert assessment.nurture_required == True

class TestWorkflowRouting:
    """Test intelligent workflow routing with LangGraph"""
    
    @pytest.mark.asyncio
    async def test_langgraph_routing(self, processor, sample_assessment, sample_context):
        """Test LangGraph-based workflow routing"""
        with patch('backend.pipeline.universal_lead_processor.LANGGRAPH_AVAILABLE', True):
            result = await processor.route_to_appropriate_workflow(
                "test_user", sample_assessment, "real_estate", sample_context
            )
            
            assert "workflow_type" in result
            assert "reasoning" in result
            assert "confidence" in result
            assert result.get("routing_method") == "langgraph_dynamic"
    
    @pytest.mark.asyncio
    async def test_traditional_routing_fallback(self, processor, sample_assessment):
        """Test traditional routing fallback when LangGraph unavailable"""
        with patch('backend.pipeline.universal_lead_processor.LANGGRAPH_AVAILABLE', False):
            result = await processor.route_to_appropriate_workflow(
                "test_user", sample_assessment, "real_estate", None
            )
            
            assert "workflow_type" in result
            assert "reasoning" in result
            assert result.get("routing_method") == "traditional_logic"
    
    @pytest.mark.asyncio
    async def test_booking_workflow_routing(self, processor, sample_assessment, sample_context):
        """Test routing to booking workflow"""
        sample_assessment.booking_readiness = True
        sample_assessment.readiness_score = 0.9
        
        result = await processor.route_to_appropriate_workflow(
            "test_user", sample_assessment, "real_estate", sample_context
        )
        
        assert result["workflow_type"] == WorkflowType.BOOKING_FLOW
    
    @pytest.mark.asyncio
    async def test_nurture_workflow_routing(self, processor, sample_assessment, sample_context):
        """Test routing to nurture workflow"""
        sample_assessment.nurture_required = True
        sample_assessment.readiness_score = 0.4
        
        result = await processor.route_to_appropriate_workflow(
            "test_user", sample_assessment, "real_estate", sample_context
        )
        
        assert result["workflow_type"] == WorkflowType.NURTURE_SEQUENCE

class TestLangGraphIntegration:
    """Test LangGraph workflow integration"""
    
    @pytest.mark.asyncio
    async def test_langgraph_workflow_creation(self, processor):
        """Test LangGraph workflow creation"""
        with patch('backend.pipeline.universal_lead_processor.LANGGRAPH_AVAILABLE', True):
            workflow = processor._create_langgraph_workflow()
            assert workflow is not None
    
    @pytest.mark.asyncio
    async def test_langgraph_workflow_execution(self, processor, sample_context, sample_assessment):
        """Test LangGraph workflow execution"""
        with patch('backend.pipeline.universal_lead_processor.LANGGRAPH_AVAILABLE', True):
            # Mock the workflow creation
            mock_workflow = Mock()
            mock_workflow.invoke = AsyncMock(return_value={
                "user_id": "test_user",
                "analysis": {"recommended_workflow": "booking_flow"},
                "strategy": {"primary_channel": "instagram_dm"},
                "response": "Test response",
                "workflow_result": {"status": "success"}
            })
            
            with patch.object(processor, '_create_langgraph_workflow', return_value=mock_workflow):
                result = await processor._execute_workflow_with_langgraph(
                    WorkflowType.BOOKING_FLOW, sample_context, sample_assessment
                )
                
                assert result["status"] == "langgraph_executed"
                assert result["langgraph_used"] == True
    
    @pytest.mark.asyncio
    async def test_langgraph_fallback_execution(self, processor, sample_context, sample_assessment):
        """Test fallback execution when LangGraph fails"""
        with patch('backend.pipeline.universal_lead_processor.LANGGRAPH_AVAILABLE', False):
            result = await processor._execute_workflow_with_langgraph(
                WorkflowType.BOOKING_FLOW, sample_context, sample_assessment
            )
            
            assert result["status"] == "booking_initiated"
            assert result.get("langgraph_used") != True

class TestWorkflowExecution:
    """Test individual workflow execution"""
    
    @pytest.mark.asyncio
    async def test_booking_workflow_execution(self, processor, sample_context, sample_assessment):
        """Test booking workflow execution - now handled by Self-Driving Booking Ops 2.0"""
        # Booking is now handled by the state machine, not this processor
        result = await processor._execute_booking_workflow(sample_context, sample_assessment)

        # Updated expectations for new booking system
        assert result["status"] == "not_implemented"  # Placeholder until fully integrated
        assert "message" in result
    
    @pytest.mark.asyncio
    async def test_nurture_workflow_execution(self, processor, sample_context, sample_assessment):
        """Test nurture workflow execution"""
        with patch.object(processor.nurture_manager, 'schedule_nurture_sequence') as mock_nurture:
            mock_nurture.return_value = True
            
            result = await processor._execute_nurture_workflow(sample_context, sample_assessment)
            
            assert result["status"] == "nurture_scheduled"
            assert result["nurture_scheduled"] == True
            mock_nurture.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_qualification_workflow_execution(self, processor, sample_context, sample_assessment):
        """Test qualification workflow execution"""
        with patch('backend.pipeline.universal_lead_processor.get_next_qualification_question') as mock_question:
            mock_question.return_value = "What's your budget range?"
            
            result = await processor._execute_qualification_workflow(sample_context, sample_assessment)
            
            assert result["status"] == "qualification_initiated"
            assert "next_question" in result

class TestResponseGeneration:
    """Test industry-adaptive response generation"""
    
    @pytest.mark.asyncio
    async def test_booking_response_generation(self, processor, sample_context):
        """Test booking response generation"""
        response = await processor._generate_booking_response({
            "user_name": "John",
            "industry_type": "real_estate",
            "workflow": "booking_flow"
        })
        
        assert "John" in response
        assert "schedule" in response.lower()
        assert "consultation" in response.lower()
    
    @pytest.mark.asyncio
    async def test_nurture_response_generation(self, processor, sample_context):
        """Test nurture response generation"""
        response = await processor._generate_nurture_response({
            "user_name": "Sarah",
            "industry_type": "fitness",
            "workflow": "nurture_sequence",
            "value_props": ["personal_training", "nutrition_planning"]
        })
        
        assert "Sarah" in response
        assert "follow up" in response.lower()
    
    @pytest.mark.asyncio
    async def test_industry_specific_responses(self, processor):
        """Test industry-specific response variations"""
        # Real estate response
        real_estate_response = await processor._generate_qualification_response({
            "user_name": "Mike",
            "industry_type": "real_estate"
        })
        assert "budget" in real_estate_response.lower()
        assert "location" in real_estate_response.lower()
        
        # Fitness response
        fitness_response = await processor._generate_qualification_response({
            "user_name": "Lisa",
            "industry_type": "fitness"
        })
        assert "Lisa" in fitness_response

class TestComplianceChecking:
    """Test industry-specific compliance checking"""
    
    @pytest.mark.asyncio
    async def test_compliance_checking(self, processor):
        """Test compliance checking for different industries"""
        message = "Schedule a consultation for property viewing"
        
        # Real estate compliance
        result = await processor._check_compliance(
            message, "real_estate", WorkflowType.BOOKING_FLOW
        )
        assert "passed" in result
        assert result["industry_type"] == "real_estate"
        
        # Fitness compliance
        result = await processor._check_compliance(
            message, "fitness", WorkflowType.BOOKING_FLOW
        )
        assert "passed" in result

class TestErrorHandling:
    """Test comprehensive error handling"""
    
    @pytest.mark.asyncio
    async def test_main_pipeline_error_handling(self, processor):
        """Test error handling in main processing pipeline"""
        with patch.object(processor, '_create_processing_context', side_effect=Exception("Test error")):
            result = await processor.process_message(
                "test_user", "test message", "instagram", "Test User"
            )
            
            assert result["status"] in ["fallback_success", "error"]
            assert "error" in result or "fallback_result" in result
    
    @pytest.mark.asyncio
    async def test_fallback_to_production_processor(self, processor):
        """Test fallback to production processor"""
        with patch.object(processor, '_create_processing_context', side_effect=Exception("Test error")):
            with patch.object(processor.production_processor, 'process_lead_message') as mock_production:
                mock_production.return_value = {
                    "response_message": "Production fallback response",
                    "status": "success"
                }
                
                result = await processor.process_message(
                    "test_user", "test message", "instagram", "Test User"
                )
                
                assert result["status"] == "fallback_success"
                assert result["fallback_result"] is not None
                mock_production.assert_called_once()

class TestIntegration:
    """End-to-end integration tests"""
    
    @pytest.mark.asyncio
    async def test_real_estate_lead_processing(self, processor):
        """Test complete real estate lead processing"""
        with patch.object(processor.channel_manager, 'send_message') as mock_send:
            mock_send.return_value = {"success": True}
            
            result = await processor.process_message(
                "user_123",
                "I'm looking for a 3-bedroom house in downtown with budget $500k",
                "instagram",
                "John Smith"
            )
            
            assert result["status"] == "success"
            assert result["industry_type"] == "real_estate"
            assert "response_message" in result
            assert "workflow_type" in result
            assert result["processing_time_seconds"] > 0
    
    @pytest.mark.asyncio
    async def test_fitness_lead_processing(self, processor):
        """Test complete fitness lead processing"""
        with patch.object(processor.channel_manager, 'send_message') as mock_send:
            mock_send.return_value = {"success": True}
            
            result = await processor.process_message(
                "user_456",
                "I want to join a gym with personal training sessions",
                "instagram",
                "Sarah Johnson"
            )
            
            assert result["status"] == "success"
            assert result["industry_type"] == "fitness"
            assert "response_message" in result
    
    @pytest.mark.asyncio
    async def test_convenience_function(self):
        """Test convenience function for direct access"""
        with patch.object(universal_lead_processor, 'process_message') as mock_process:
            mock_process.return_value = {"status": "success", "response_message": "Test"}
            
            result = await process_message(
                "test_user", "test message", "instagram", "Test User"
            )
            
            assert result["status"] == "success"
            mock_process.assert_called_once_with(
                "test_user", "test message", "instagram", "Test User"
            )

class TestMetricsAndMonitoring:
    """Test processing metrics and monitoring"""
    
    def test_processing_metrics_update(self, processor):
        """Test processing metrics updates"""
        initial_metrics = processor.get_processing_metrics()
        
        # Simulate processing
        processor.processing_metrics['total_processed'] = 10
        processor.processing_metrics['successful_processing'] = 8
        processor.processing_metrics['error_count'] = 2
        
        metrics = processor.get_processing_metrics()
        
        assert metrics['metrics']['total_processed'] == 10
        assert metrics['metrics']['successful_processing'] == 8
        assert metrics['metrics']['error_count'] == 2
        assert "components_status" in metrics
        assert "pipeline_version" in metrics

if __name__ == "__main__":
    pytest.main([__file__])