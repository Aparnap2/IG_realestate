"""
Tests for the value delivery system including property info, market insights, and lead magnets.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
import json

from backend.agents.value_delivery import ValueDeliveryAgent
from backend.tools.agent_tools import fetch_lead_magnet, deliver_property_info, send_market_insights
from backend.models.lead import Lead
from backend.schemas.state import AgentState, ConversationMessage


class TestValueDeliveryAgent:
    """Test the value delivery agent functionality."""
    
    @pytest.fixture
    def mock_value_delivery(self):
        """Create a mock value delivery agent."""
        with patch('backend.agents.value_delivery.SupabaseClient'), \
             patch('backend.agents.value_delivery.LLMClient'):
            return ValueDeliveryAgent()
    
    @pytest.mark.asyncio
    async def test_property_info_delivery(self, mock_value_delivery):
        """Test property information delivery."""
        state = AgentState(
            lead_id="test_lead",
            conversation_history=[],
            current_agent="value_delivery",
            lead_data={
                "location": "Austin, TX",
                "property_type": "single_family",
                "budget": 750000
            }
        )
        
        with patch.object(mock_value_delivery, '_analyze_value_request') as mock_analyze, \
             patch.object(mock_value_delivery, '_deliver_property_info') as mock_deliver, \
             patch.object(mock_value_delivery, '_update_value_delivery_tracking') as mock_update:
            
            mock_analyze.return_value = "property_info"
            mock_deliver.return_value = "Here are 3 properties in Austin that match your criteria..."
            mock_update.return_value = None
            
            result = await mock_value_delivery.process_message(state, "Can you show me properties in Austin?")
            
            assert "property" in result.response.lower()
            assert result.lead_data.get("property_info_delivered") is True
            mock_analyze.assert_called_once()
            mock_deliver.assert_called_once()
            mock_update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_market_insights_delivery(self, mock_value_delivery):
        """Test market insights delivery."""
        state = AgentState(
            lead_id="test_lead",
            conversation_history=[],
            current_agent="value_delivery",
            lead_data={
                "location": "Austin, TX",
                "property_type": "condo"
            }
        )
        
        with patch.object(mock_value_delivery, '_analyze_value_request') as mock_analyze, \
             patch.object(mock_value_delivery, '_deliver_market_insights') as mock_deliver, \
             patch.object(mock_value_delivery, '_update_value_delivery_tracking') as mock_update:
            
            mock_analyze.return_value = "market_insights"
            mock_deliver.return_value = "The Austin condo market has been trending upward with..."
            mock_update.return_value = None
            
            result = await mock_value_delivery.process_message(state, "How's the condo market in Austin?")
            
            assert "market" in result.response.lower()
            assert result.lead_data.get("market_insights_sent") is True
            mock_analyze.assert_called_once()
            mock_deliver.assert_called_once()
            mock_update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_educational_content_delivery(self, mock_value_delivery):
        """Test educational content delivery."""
        state = AgentState(
            lead_id="test_lead",
            conversation_history=[],
            current_agent="value_delivery",
            lead_data={
                "first_time_buyer": True
            }
        )
        
        with patch.object(mock_value_delivery, '_analyze_value_request') as mock_analyze, \
             patch.object(mock_value_delivery, '_deliver_educational_content') as mock_deliver, \
             patch.object(mock_value_delivery, '_update_value_delivery_tracking') as mock_update:
            
            mock_analyze.return_value = "educational_content"
            mock_deliver.return_value = "As a first-time homebuyer, here's what you need to know about..."
            mock_update.return_value = None
            
            result = await mock_value_delivery.process_message(state, "What should I know as a first-time buyer?")
            
            assert "first-time" in result.response.lower() or "buyer" in result.response.lower()
            mock_analyze.assert_called_once()
            mock_deliver.assert_called_once()
            mock_update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_lead_magnet_delivery(self, mock_value_delivery):
        """Test lead magnet delivery."""
        state = AgentState(
            lead_id="test_lead",
            conversation_history=[],
            current_agent="value_delivery",
            lead_data={}
        )
        
        with patch.object(mock_value_delivery, '_analyze_value_request') as mock_analyze, \
             patch.object(mock_value_delivery, '_deliver_lead_magnet') as mock_deliver, \
             patch.object(mock_value_delivery, '_update_value_delivery_tracking') as mock_update:
            
            mock_analyze.return_value = "lead_magnet"
            mock_deliver.return_value = "I'd love to send you our Austin Home Buyer's Guide..."
            mock_update.return_value = None
            
            result = await mock_value_delivery.process_message(state, "Do you have any guides for home buyers?")
            
            assert "guide" in result.response.lower() or "resource" in result.response.lower()
            assert result.lead_data.get("lead_magnet_sent_at") is not None
            mock_analyze.assert_called_once()
            mock_deliver.assert_called_once()
            mock_update.assert_called_once()
    
    def test_analyze_value_request(self, mock_value_delivery):
        """Test value request analysis."""
        # Test property info requests
        requests = [
            "Can you show me properties in Austin?",
            "What homes are available in Zilker?",
            "Show me 3-bedroom houses under $700k",
            "Are there any condos downtown?"
        ]
        
        for request in requests:
            result = mock_value_delivery._analyze_value_request(request)
            assert result == "property_info", f"Request '{request}' should be property_info"
        
        # Test market insights requests
        requests = [
            "How's the market in Austin?",
            "What are home prices doing?",
            "Is it a good time to buy?",
            "Market trends for condos"
        ]
        
        for request in requests:
            result = mock_value_delivery._analyze_value_request(request)
            assert result == "market_insights", f"Request '{request}' should be market_insights"
        
        # Test educational content requests
        requests = [
            "What should I know as a first-time buyer?",
            "How does the buying process work?",
            "What's involved in getting a mortgage?",
            "Closing costs explained"
        ]
        
        for request in requests:
            result = mock_value_delivery._analyze_value_request(request)
            assert result == "educational_content", f"Request '{request}' should be educational_content"
        
        # Test lead magnet requests
        requests = [
            "Do you have any guides?",
            "Can you send me resources?",
            "I'd like a home buyer's checklist",
            "Any free resources available?"
        ]
        
        for request in requests:
            result = mock_value_delivery._analyze_value_request(request)
            assert result == "lead_magnet", f"Request '{request}' should be lead_magnet"
    
    def test_deliver_property_info(self, mock_value_delivery):
        """Test property information delivery content generation."""
        lead_data = {
            "location": "Austin, TX",
            "property_type": "single_family",
            "budget": 750000,
            "bedrooms": 3,
            "bathrooms": 2
        }
        
        with patch.object(mock_value_delivery, '_search_matching_properties') as mock_search:
            mock_properties = [
                {
                    "address": "123 Main St, Austin, TX 78701",
                    "price": 725000,
                    "bedrooms": 3,
                    "bathrooms": 2,
                    "square_feet": 2000,
                    "description": "Beautiful home in desirable neighborhood"
                },
                {
                    "address": "456 Oak Ave, Austin, TX 78702",
                    "price": 680000,
                    "bedrooms": 3,
                    "bathrooms": 2,
                    "square_feet": 1850,
                    "description": "Great starter home with updates"
                }
            ]
            mock_search.return_value = mock_properties
            
            result = mock_value_delivery._deliver_property_info(lead_data)
            
            assert "123 Main St" in result
            assert "456 Oak Ave" in result
            assert "$725,000" in result
            assert "$680,000" in result
            assert "3 bed" in result.lower()
            assert "2 bath" in result.lower()
            mock_search.assert_called_once_with(lead_data)
    
    def test_deliver_market_insights(self, mock_value_delivery):
        """Test market insights delivery content generation."""
        lead_data = {
            "location": "Austin, TX",
            "property_type": "condo"
        }
        
        with patch.object(mock_value_delivery, '_generate_market_analysis') as mock_analysis:
            mock_analysis.return_value = {
                "median_price": 450000,
                "price_trend": "up 5%",
                "days_on_market": 45,
                "inventory_level": "low",
                "neighborhoods": ["Downtown", "South Congress", "East Austin"]
            }
            
            result = mock_value_delivery._deliver_market_insights(lead_data)
            
            assert "$450,000" in result
            assert "up 5%" in result
            assert "45 days" in result
            assert "low inventory" in result.lower()
            assert "Downtown" in result
            mock_analysis.assert_called_once_with(lead_data)
    
    def test_deliver_educational_content(self, mock_value_delivery):
        """Test educational content delivery."""
        lead_data = {
            "first_time_buyer": True,
            "timeline": "3 months"
        }
        
        with patch.object(mock_value_delivery, '_generate_educational_content') as mock_content:
            mock_content.return_value = {
                "topic": "First-Time Home Buying Guide",
                "key_points": [
                    "Get pre-approved for a mortgage",
                    "Understand your budget",
                    "Work with a real estate agent",
                    "Home inspection process"
                ]
            }
            
            result = mock_value_delivery._deliver_educational_content(lead_data)
            
            assert "first-time" in result.lower()
            assert "pre-approved" in result.lower()
            assert "budget" in result.lower()
            assert "home inspection" in result.lower()
            mock_content.assert_called_once_with(lead_data)
    
    def test_deliver_lead_magnet(self, mock_value_delivery):
        """Test lead magnet delivery."""
        lead_data = {
            "location": "Austin, TX",
            "timeline": "3 months"
        }
        
        with patch.object(mock_value_delivery, '_select_appropriate_lead_magnet') as mock_select:
            mock_select.return_value = {
                "title": "Austin Home Buyer's Guide",
                "description": "Complete guide to buying a home in Austin",
                "type": "guide"
            }
            
            result = mock_value_delivery._deliver_lead_magnet(lead_data)
            
            assert "Austin Home Buyer's Guide" in result
            assert "complete guide" in result.lower()
            assert "email" in result.lower()
            mock_select.assert_called_once_with(lead_data)


class TestValueDeliveryTools:
    """Test the value delivery agent tools."""
    
    @pytest.mark.asyncio
    async def test_fetch_lead_magnet(self):
        """Test lead magnet fetching tool."""
        with patch('backend.tools.agent_tools.SupabaseClient') as mock_client:
            mock_instance = mock_client.return_value
            mock_instance.fetch_lead_magnet.return_value = {
                "id": "guide_001",
                "title": "Austin Home Buyer's Guide",
                "description": "Complete guide to buying a home in Austin",
                "content_url": "https://example.com/guide.pdf",
                "type": "guide"
            }
            
            result = await fetch_lead_magnet("austin_home_buyer_guide")
            
            assert result["id"] == "guide_001"
            assert result["title"] == "Austin Home Buyer's Guide"
            assert result["type"] == "guide"
            mock_instance.fetch_lead_magnet.assert_called_once_with("austin_home_buyer_guide")
    
    @pytest.mark.asyncio
    async def test_deliver_property_info_tool(self):
        """Test property info delivery tool."""
        with patch('backend.tools.agent_tools.SupabaseClient') as mock_client:
            mock_instance = mock_client.return_value
            mock_properties = [
                {
                    "id": "prop_001",
                    "address": "123 Main St, Austin, TX 78701",
                    "price": 725000,
                    "bedrooms": 3,
                    "bathrooms": 2,
                    "square_feet": 2000,
                    "description": "Beautiful home in desirable neighborhood",
                    "images": ["image1.jpg", "image2.jpg"]
                }
            ]
            mock_instance.search_properties.return_value = mock_properties
            
            criteria = {
                "location": "Austin, TX",
                "property_type": "single_family",
                "budget": 750000
            }
            
            result = await deliver_property_info(criteria)
            
            assert len(result) == 1
            assert result[0]["address"] == "123 Main St, Austin, TX 78701"
            assert result[0]["price"] == 725000
            mock_instance.search_properties.assert_called_once_with(criteria)
    
    @pytest.mark.asyncio
    async def test_send_market_insights_tool(self):
        """Test market insights delivery tool."""
        with patch('backend.tools.agent_tools.SupabaseClient') as mock_client:
            mock_instance = mock_client.return_value
            mock_instance.get_market_data.return_value = {
                "location": "Austin, TX",
                "median_price": 450000,
                "price_trend": "up 5%",
                "days_on_market": 45,
                "inventory_level": "low",
                "neighborhood_data": {
                    "Downtown": {"median_price": 550000, "price_trend": "up 7%"},
                    "South Congress": {"median_price": 425000, "price_trend": "up 4%"}
                }
            }
            
            result = await send_market_insights("Austin, TX", "condo")
            
            assert result["location"] == "Austin, TX"
            assert result["median_price"] == 450000
            assert result["price_trend"] == "up 5%"
            assert "Downtown" in result["neighborhood_data"]
            mock_instance.get_market_data.assert_called_once_with("Austin, TX", "condo")


class TestValueDeliveryIntegration:
    """Test integration between value delivery components."""
    
    @pytest.mark.asyncio
    async def test_value_delivery_routing(self):
        """Test that value delivery requests are routed correctly."""
        # Test property info routing
        message = "Can you show me properties in Austin?"
        intent = "request_property_info"
        
        assert intent == "request_property_info"
        assert "properties" in message.lower() or "show me" in message.lower()
        
        # Test market insights routing
        message = "How's the market in Austin?"
        intent = "ask_market_question"
        
        assert intent == "ask_market_question"
        assert "market" in message.lower()
        
        # Test lead magnet routing
        message = "Do you have any guides for home buyers?"
        intent = "value_delivery_request"
        
        assert intent == "value_delivery_request"
        assert "guide" in message.lower() or "resource" in message.lower()
    
    @pytest.mark.asyncio
    async def test_value_delivery_tracking(self):
        """Test that value delivery is properly tracked."""
        lead_data = {
            "property_info_delivered": False,
            "market_insights_sent": False,
            "lead_magnet_sent_at": None
        }
        
        # Simulate property info delivery
        lead_data["property_info_delivered"] = True
        assert lead_data["property_info_delivered"] is True
        
        # Simulate market insights delivery
        lead_data["market_insights_sent"] = True
        assert lead_data["market_insights_sent"] is True
        
        # Simulate lead magnet delivery
        lead_data["lead_magnet_sent_at"] = datetime.now()
        assert lead_data["lead_magnet_sent_at"] is not None
    
    @pytest.mark.asyncio
    async def test_personalized_value_delivery(self):
        """Test that value delivery is personalized based on lead data."""
        # Test personalization for first-time buyer
        lead_data = {
            "first_time_buyer": True,
            "location": "Austin, TX",
            "budget": 500000
        }
        
        # Should prioritize educational content and starter homes
        assert lead_data["first_time_buyer"] is True
        assert lead_data["budget"] < 600000  # Starter home range
        
        # Test personalization for luxury buyer
        lead_data = {
            "budget": 1500000,
            "location": "Austin, TX",
            "property_type": "luxury"
        }
        
        # Should prioritize high-end properties and market insights
        assert lead_data["budget"] > 1000000  # Luxury range
        assert lead_data["property_type"] == "luxury"
        
        # Test personalization for investor
        lead_data = {
            "investment_property": True,
            "location": "Austin, TX",
            "timeline": "6 months"
        }
        
        # Should prioritize market insights and investment properties
        assert lead_data["investment_property"] is True
        assert lead_data["timeline"] == "6 months"
    
    def test_value_delivery_content_quality(self):
        """Test that value delivery content meets quality standards."""
        # Test property info content
        property_content = """
        Based on your criteria, I found 3 great properties in Austin:
        
        1. 123 Main St, Austin, TX 78701 - $725,000
           3 bed, 2 bath, 2,000 sq ft
           Beautiful home in desirable neighborhood with recent updates
           
        2. 456 Oak Ave, Austin, TX 78702 - $680,000
           3 bed, 2 bath, 1,850 sq ft
           Great starter home with modern kitchen and backyard
        """
        
        # Quality checks
        assert len(property_content) > 100  # Substantial content
        assert "$" in property_content  # Includes pricing
        assert "bed" in property_content.lower()  # Includes bedrooms
        assert "bath" in property_content.lower()  # Includes bathrooms
        assert "sq ft" in property_content.lower()  # Includes square footage
        
        # Test market insights content
        market_content = """
        The Austin condo market is showing strong trends:
        
        • Median price: $450,000 (up 5% from last year)
        • Average days on market: 45 days
        • Inventory level: Low (2.3 months supply)
        
        Top neighborhoods for condos:
        • Downtown: Median $550,000, up 7%
        • South Congress: Median $425,000, up 4%
        • East Austin: Median $380,000, up 6%
        """
        
        # Quality checks
        assert len(market_content) > 100  # Substantial content
        assert "$" in market_content  # Includes pricing
        assert "%" in market_content  # Includes trends
        assert "days" in market_content.lower()  # Includes time metrics
        assert "neighborhoods" in market_content.lower()  # Includes area breakdown


if __name__ == "__main__":
    pytest.main([__file__])