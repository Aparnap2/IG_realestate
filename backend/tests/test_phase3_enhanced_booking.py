"""
Comprehensive Test Suite for Phase 3: Enhanced Booking & CRM Integration

Tests all Phase 3 enhancements including:
1. Dynamic Time Slot Offering with real-time availability
2. Enhanced CRM Integration with HubSpot opportunity creation
3. Booking Attribution & Source Tracking system
4. Meeting Context Preservation features
5. Dashboard booking attribution reporting

Validates end-to-end Phase 3 workflow integration with Phase 1 & 2.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any, List

from backend.booking.dynamic_slot_offering import (
    DynamicSlotOffering, LeadContext, DynamicSlot, SlotPriority
)
from backend.integrations.hubspot_client import get_hubspot_client
from backend.utils.correlation_tracker import (
    BookingAttributionTracker, track_complete_lead_journey
)
from backend.api.dashboard import DashboardMetrics

class TestPhase3DynamicSlotOffering:
    """Test Phase 3 Dynamic Time Slot Offering system"""
    
    @pytest.fixture
    def dynamic_slot_offering(self):
        """Create dynamic slot offering instance"""
        return DynamicSlotOffering()
    
    @pytest.fixture
    def sample_lead_context(self):
        """Create sample lead context for testing"""
        return LeadContext(
            lead_id="test_lead_123",
            intent_score=0.85,
            intent_category="booking_intent",
            qualification_score=0.78,
            qualification_stage="scheduler_ready",
            budget_band="mid_tier",
            urgency_level=SlotPriority.HIGH,
            preferred_times=["morning", "afternoon"],
            constraints={"location_preference": "Miami"},
            source_channel="instagram",
            lead_metadata={"campaign": "spring_launch"}
        )
    
    @pytest.mark.asyncio
    async def test_generate_dynamic_slots(self, dynamic_slot_offering, sample_lead_context):
        """Test dynamic slot generation for high-intent lead"""
        # Mock the scheduling policies
        with patch.object(dynamic_slot_offering, 'scheduling_policies') as mock_policies:
            mock_policy = Mock()
            mock_policy.default_duration_minutes = 60
            mock_policy.min_gap_minutes = 15
            mock_policies.get_policy_for_service.return_value = mock_policy
            
            # Mock availability fetching
            with patch.object(dynamic_slot_offering, '_get_realtime_availability') as mock_availability:
                mock_availability.return_value = [
                    {
                        "start": datetime.now() + timedelta(hours=2),
                        "end": datetime.now() + timedelta(hours=3),
                        "confidence": 0.95,
                        "source": "realtime"
                    },
                    {
                        "start": datetime.now() + timedelta(hours=4),
                        "end": datetime.now() + timedelta(hours=5),
                        "confidence": 0.90,
                        "source": "realtime"
                    }
                ]
                
                # Generate dynamic slots
                slots = await dynamic_slot_offering.generate_dynamic_slots(
                    sample_lead_context, "single_property_tour", "Miami"
                )
                
                # Validate results
                assert len(slots) > 0
                assert all(isinstance(slot, DynamicSlot) for slot in slots)
                assert all(slot.priority_score > 0.5 for slot in slots)
                assert all(slot.urgency_level == SlotPriority.HIGH for slot in slots)
                
                # Test that slots are ranked by priority
                priority_scores = [slot.priority_score for slot in slots]
                assert priority_scores == sorted(priority_scores, reverse=True)
    
    def test_urgency_determination(self, dynamic_slot_offering):
        """Test urgency level determination for different lead types"""
        # Critical urgency - booking signals
        urgency = dynamic_slot_offering.get_urgency_for_lead(
            intent_score=0.9,
            qualification_score=0.8,
            intent_category="booking_intent",
            booking_signals=True
        )
        assert urgency == SlotPriority.CRITICAL
        
        # High urgency - budget mentioned + qualified
        urgency = dynamic_slot_offering.get_urgency_for_lead(
            intent_score=0.7,
            qualification_score=0.78,
            intent_category="budget_inquiry",
            budget_mentioned=True
        )
        assert urgency == SlotPriority.HIGH
        
        # Medium urgency - good scores
        urgency = dynamic_slot_offering.get_urgency_for_lead(
            intent_score=0.65,
            qualification_score=0.65,
            intent_category="property_specific"
        )
        assert urgency == SlotPriority.MEDIUM
        
        # Standard urgency - basic engagement
        urgency = dynamic_slot_offering.get_urgency_for_lead(
            intent_score=0.5,
            qualification_score=0.4,
            intent_category="information_request"
        )
        assert urgency == SlotPriority.STANDARD

class TestPhase3HubSpotIntegration:
    """Test Phase 3 Enhanced HubSpot CRM Integration"""
    
    @pytest.fixture
    def hubspot_client(self):
        """Create HubSpot client instance"""
        with patch('backend.integrations.hubspot_client.settings') as mock_settings:
            mock_settings.HUBSPOT_ACCESS_TOKEN = "test_token"
            mock_settings.HUBSPOT_API_BASE = "https://api.hubapi.com"
            return get_hubspot_client()
    
    @pytest.fixture
    def sample_booking_context(self):
        """Create sample booking context for testing"""
        return {
            "service_type": "single_property_tour",
            "location": "Miami",
            "slot_time": datetime.now() + timedelta(days=1, hours=2).isoformat(),
            "duration_minutes": 60,
            "priority_level": "high",
            "urgency_level": "high"
        }
    
    @pytest.fixture
    def sample_lead_data(self):
        """Create sample lead data for testing"""
        return {
            "user_id": "instagram_12345",
            "name": "John Smith",
            "email": "john@example.com",
            "phone": "+1234567890",
            "budget": 750000,
            "location": "Miami",
            "property_type": "condo",
            "channel": "instagram",
            "instagram_id": "john_smith_ig",
            "session_start": datetime.now().isoformat(),
            "campaign": "spring_launch",
            "engagement_score": 0.85
        }
    
    @pytest.fixture
    def sample_qualification_context(self):
        """Create sample Phase 2 qualification context"""
        return {
            "qualification_score": 0.78,
            "qualification_stage": "scheduler_ready",
            "budget_band": "mid_tier",
            "role_analysis": "decision_maker",
            "readiness_assessment": {"ready_for_scheduler": True},
            "asked_questions": ["budget", "timeline", "location", "role"]
        }
    
    @pytest.fixture
    def sample_intent_analysis(self):
        """Create sample Phase 1 intent analysis"""
        return {
            "intent_category": "booking_intent",
            "intent_score": 0.85,
            "confidence": 0.92,
            "budget_mentioned": True,
            "timeline_urgent": True,
            "booking_signals": True,
            "high_intent_indicators": ["specific_property_inquiry", "budget_discussion"]
        }
    
    @pytest.mark.asyncio
    async def test_create_booking_opportunity_with_context(
        self, hubspot_client, sample_booking_context, sample_lead_data,
        sample_qualification_context, sample_intent_analysis
    ):
        """Test Phase 3 opportunity creation with complete context"""
        # Mock aiohttp session and response
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            # Mock response for opportunity creation
            mock_response = AsyncMock()
            mock_response.status = 201
            mock_response.json.return_value = {"id": "opportunity_123"}
            mock_session.post.return_value = mock_response
            
            # Test opportunity creation
            opportunity_id = await hubspot_client.create_booking_opportunity_with_context(
                contact_id="contact_456",
                booking_context=sample_booking_context,
                lead_data=sample_lead_data,
                qualification_context=sample_qualification_context,
                intent_analysis=sample_intent_analysis
            )
            
            # Validate opportunity was created
            assert opportunity_id == "opportunity_123"
            
            # Verify the request was made with correct data
            assert mock_session.post.called
            call_args = mock_session.post.call_args
            assert "/crm/v3/objects/deals" in call_args[0][0]
            
            # Verify payload contains Phase 3 enhanced properties
            payload = call_args[1]["json"]["properties"]
            assert payload["intent_category"] == "booking_intent"
            assert payload["qualification_score"] == 0.78
            assert payload["qualification_stage"] == "scheduler_ready"
            assert payload["phase_3_enhanced"] == "true"
            assert payload["booking_confirmed"] == "true"
    
    def test_build_meeting_context_note(
        self, hubspot_client, sample_booking_context, sample_lead_data,
        sample_qualification_context, sample_intent_analysis
    ):
        """Test comprehensive meeting context note generation"""
        note_content = hubspot_client._build_meeting_context_note(
            sample_lead_data, sample_booking_context, 
            sample_qualification_context, sample_intent_analysis
        )
        
        # Verify note contains all expected sections
        assert "PHASE 3: ENHANCED BOOKING & CRM INTEGRATION CONTEXT" in note_content
        assert "LEAD INFORMATION:" in note_content
        assert "PHASE 1: AI INTENT ANALYSIS:" in note_content
        assert "PHASE 2: TRANSPARENT QUALIFICATION:" in note_content
        assert "BOOKING CONFIRMATION:" in note_content
        assert "SOURCE ATTRIBUTION:" in note_content
        assert "SALES TEAM CONTEXT:" in note_content
        assert "RECOMMENDED NEXT STEPS:" in note_content
        
        # Verify specific data points are included
        assert "booking_intent" in note_content
        assert "0.85" in note_content  # intent score
        assert "0.78" in note_content  # qualification score
        assert "scheduler_ready" in note_content

class TestPhase3BookingAttribution:
    """Test Phase 3 Booking Attribution & Source Tracking"""
    
    @pytest.fixture
    def booking_attribution_tracker(self):
        """Create booking attribution tracker instance"""
        return BookingAttributionTracker()
    
    @pytest.mark.asyncio
    async def test_track_complete_lead_journey(self, booking_attribution_tracker):
        """Test complete lead journey tracking with full attribution"""
        lead_id = "test_lead_123"
        journey_context = {
            "intent_analysis": {
                "intent_category": "booking_intent",
                "intent_score": 0.85,
                "confidence": 0.92
            },
            "qualification_context": {
                "qualification_score": 0.78,
                "qualification_stage": "scheduler_ready",
                "budget_band": "mid_tier"
            },
            "booking_confirmation": {
                "scheduled_slot": datetime.now() + timedelta(days=1).isoformat(),
                "service_type": "property_tour",
                "priority_level": "high"
            },
            "source_attribution": {
                "campaign": "spring_launch",
                "channel": "instagram",
                "referrer": "direct"
            },
            "conversion_metrics": {
                "journey_time_minutes": 18.5,
                "dropout_rate": 0.0,
                "conversion_rate": 1.0
            }
        }
        
        # Track complete journey
        correlation_id = await booking_attribution_tracker.track_lead_journey_complete(
            lead_id, journey_context
        )
        
        # Validate tracking result
        assert correlation_id.startswith("booking_attribution_")
        assert lead_id in correlation_id
        assert "phase_3_enhanced" in correlation_id.lower()
        
        # Note: In production, this would also test caching functionality
        # For now, we verify the correlation ID was generated correctly

class TestPhase3DashboardIntegration:
    """Test Phase 3 Dashboard Integration"""
    
    @pytest.fixture
    def dashboard_metrics(self):
        """Create dashboard metrics instance"""
        return DashboardMetrics()
    
    @pytest.mark.asyncio
    async def test_booking_attribution_endpoint(self, dashboard_metrics):
        """Test booking attribution metrics endpoint"""
        with patch.object(dashboard_metrics, '_get_booking_attribution_metrics') as mock_method:
            mock_method.return_value = {
                "source_channel_performance": {"instagram": {"bookings": 45}},
                "campaign_attribution_results": {"test_campaign": {"bookings": 10}}
            }
            
            # Call the endpoint
            response = await dashboard_metrics.app.router.routes[5].endpoint()
            
            # Verify response contains expected data structure
            assert "timestamp" in response.body.decode()
            assert "phase_3_enhanced" in response.body.decode()
            assert "instagram" in response.body.decode()
    
    @pytest.mark.asyncio
    async def test_lead_journey_analytics_endpoint(self, dashboard_metrics):
        """Test lead journey analytics endpoint"""
        with patch.object(dashboard_metrics, '_get_lead_journey_analytics') as mock_method:
            mock_method.return_value = {
                "phase_1_intent_detection": {"accuracy_rate": 0.91},
                "phase_2_qualification": {"completion_rate": 0.73},
                "phase_3_booking": {"dynamic_slot_success": 0.87}
            }
            
            # Call the endpoint
            response = await dashboard_metrics.app.router.routes[6].endpoint()
            
            # Verify response contains expected analytics
            assert "analytics_type" in response.body.decode()
            assert "complete_lead_journey" in response.body.decode()
    
    @pytest.mark.asyncio
    async def test_crm_integration_endpoint(self, dashboard_metrics):
        """Test CRM integration metrics endpoint"""
        with patch.object(dashboard_metrics, '_get_crm_integration_metrics') as mock_method:
            mock_method.return_value = {
                "hubspot_integration": {"opportunity_creation_success": 0.94},
                "sales_team_effectiveness": {"meeting_preparation_quality": 8.9}
            }
            
            # Call the endpoint
            response = await dashboard_metrics.app.router.routes[7].endpoint()
            
            # Verify response contains expected integration metrics
            assert "integration_type" in response.body.decode()
            assert "phase_3_enhanced" in response.body.decode()

class TestPhase3EndToEndWorkflow:
    """Test complete Phase 3 end-to-end workflow integration"""
    
    @pytest.mark.asyncio
    async def test_complete_lead_to_booking_workflow(self):
        """Test complete workflow from lead to booking with Phase 3 enhancements"""
        # Simulate complete lead journey
        lead_id = "e2e_test_lead"
        
        # Phase 1: Intent Analysis (simulated)
        intent_analysis = {
            "intent_category": "booking_intent",
            "intent_score": 0.87,
            "confidence": 0.93,
            "budget_mentioned": True,
            "timeline_urgent": True,
            "booking_signals": True
        }
        
        # Phase 2: Qualification (simulated)
        qualification_context = {
            "qualification_score": 0.82,
            "qualification_stage": "scheduler_ready",
            "budget_band": "mid_tier",
            "role_analysis": "decision_maker",
            "readiness_assessment": {"ready_for_scheduler": True},
            "asked_questions": ["budget", "timeline", "location", "role"]
        }
        
        # Phase 3: Dynamic Slot Offering
        lead_context = LeadContext(
            lead_id=lead_id,
            intent_score=intent_analysis["intent_score"],
            intent_category=intent_analysis["intent_category"],
            qualification_score=qualification_context["qualification_score"],
            qualification_stage=qualification_context["qualification_stage"],
            budget_band=qualification_context["budget_band"],
            urgency_level=SlotPriority.HIGH,
            preferred_times=["morning", "afternoon"],
            constraints={},
            source_channel="instagram",
            lead_metadata={}
        )
        
        # Generate dynamic slots
        dynamic_slot_offering = DynamicSlotOffering()
        with patch.object(dynamic_slot_offering, '_get_realtime_availability') as mock_availability:
            mock_availability.return_value = [
                {
                    "start": datetime.now() + timedelta(hours=2),
                    "end": datetime.now() + timedelta(hours=3),
                    "confidence": 0.95,
                    "source": "realtime"
                }
            ]
            
            slots = await dynamic_slot_offering.generate_dynamic_slots(
                lead_context, "single_property_tour", "Miami"
            )
            assert len(slots) > 0
        
        # Phase 3: HubSpot Opportunity Creation
        booking_context = {
            "service_type": "single_property_tour",
            "location": "Miami",
            "slot_time": slots[0].start_time.isoformat(),
            "duration_minutes": 60,
            "priority_level": "high",
            "urgency_level": "high"
        }
        
        lead_data = {
            "user_id": lead_id,
            "name": "Test User",
            "email": "test@example.com",
            "budget": 750000,
            "location": "Miami",
            "channel": "instagram"
        }
        
        # Mock HubSpot client for testing
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            mock_response = AsyncMock()
            mock_response.status = 201
            mock_response.json.return_value = {"id": "opportunity_123"}
            mock_session.post.return_value = mock_response
            
            hubspot_client = get_hubspot_client()
            opportunity_id = await hubspot_client.create_booking_opportunity_with_context(
                contact_id="contact_456",
                booking_context=booking_context,
                lead_data=lead_data,
                qualification_context=qualification_context,
                intent_analysis=intent_analysis
            )
            
            assert opportunity_id == "opportunity_123"
        
        # Phase 3: Booking Attribution Tracking
        journey_context = {
            "intent_analysis": intent_analysis,
            "qualification_context": qualification_context,
            "booking_confirmation": booking_context,
            "source_attribution": {"channel": "instagram", "campaign": "test"},
            "conversion_metrics": {"journey_time_minutes": 15.2}
        }
        
        correlation_id = await track_complete_lead_journey(lead_id, journey_context)
        assert correlation_id.startswith("booking_attribution_")
        
        # Verify complete workflow executed successfully
        assert len(slots) > 0
        assert opportunity_id is not None
        assert correlation_id is not None
    
    @pytest.mark.asyncio
    async def test_phase_3_enhanced_metrics_collection(self):
        """Test that Phase 3 enhancements are properly tracked in metrics"""
        dashboard_metrics = DashboardMetrics()
        
        # Test each Phase 3 metric collection method
        attribution_metrics = await dashboard_metrics._get_booking_attribution_metrics()
        assert "source_channel_performance" in attribution_metrics
        assert "phase_3_enhancements" in attribution_metrics
        
        journey_metrics = await dashboard_metrics._get_lead_journey_analytics()
        assert "phase_1_intent_detection" in journey_metrics
        assert "phase_2_qualification" in journey_metrics
        assert "phase_3_booking" in journey_metrics
        
        crm_metrics = await dashboard_metrics._get_crm_integration_metrics()
        assert "hubspot_integration" in crm_metrics
        assert "sales_team_effectiveness" in crm_metrics

# Test fixtures and utilities for comprehensive testing
@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing"""
    return Mock()

@pytest.fixture
def sample_phase_3_lead_data():
    """Sample lead data representing complete Phase 3 journey"""
    return {
        "lead_id": "phase3_test_lead",
        "user_id": "instagram_98765",
        "name": "Sarah Johnson",
        "email": "sarah.johnson@email.com",
        "phone": "+1987654321",
        "budget": 850000,
        "location": "Miami Beach",
        "property_type": "luxury_condo",
        "channel": "instagram",
        "instagram_id": "sarah_j_miami",
        "session_start": datetime.now().isoformat(),
        "campaign": "luxury_showcase",
        "engagement_score": 0.92,
        "intent_score": 0.89,
        "qualification_score": 0.84,
        "booking_confirmed": True,
        "scheduled_slot": (datetime.now() + timedelta(days=1, hours=2)).isoformat()
    }

# Integration test markers
pytestmark = pytest.mark.asyncio

if __name__ == "__main__":
    # Run the test suite
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "--asyncio-mode=auto"
    ])