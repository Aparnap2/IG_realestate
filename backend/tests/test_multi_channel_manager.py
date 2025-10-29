"""
Tests for Multi-Channel Communication Manager

Tests the intelligent multi-channel communication system for lead nurturing.
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from communication.multi_channel_manager import (
    MultiChannelManager, 
    ChannelType, 
    MessagePriority, 
    IndustryType,
    UserPreferences,
    MessageDelivery,
    multi_channel_manager
)

class TestMultiChannelManager:
    """Test cases for MultiChannelManager"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.manager = MultiChannelManager()
        self.test_user_id = "test_user_123"
        self.test_message = "This is a test message for lead nurturing"
    
    def test_get_default_preferences(self):
        """Test getting default user preferences"""
        prefs = self.manager.get_user_preferences(self.test_user_id)
        
        assert isinstance(prefs, UserPreferences)
        assert prefs.user_id == self.test_user_id
        assert prefs.preferred_channel == ChannelType.INSTAGRAM_DM
        assert prefs.backup_channels == [ChannelType.SMS, ChannelType.EMAIL]
        assert prefs.business_hours_only is True
        assert prefs.max_messages_per_day == 5
        assert prefs.do_not_disturb is False
        assert prefs.timezone == "UTC"
        assert prefs.industry_type == IndustryType.DEFAULT
    
    @patch('communication.multi_channel_manager.redis_client')
    def test_update_channel_preferences(self, mock_redis):
        """Test updating user channel preferences"""
        # Mock Redis operations
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True
        
        # Update preferences
        new_prefs = {
            "preferred_channel": "sms",
            "backup_channels": ["email", "instagram_dm"],
            "business_hours_only": False,
            "max_messages_per_day": 10,
            "timezone": "US/Eastern"
        }
        
        result = self.manager.update_channel_preferences(self.test_user_id, new_prefs)
        
        assert result is True
        mock_redis.setex.assert_called_once()
        
        # Verify the call arguments
        call_args = mock_redis.setex.call_args
        prefs_data = json.loads(call_args[0][1])  # Second argument is the data
        
        assert prefs_data["preferred_channel"] == "sms"
        assert prefs_data["backup_channels"] == ["email", "instagram_dm"]
        assert prefs_data["business_hours_only"] is False
        assert prefs_data["max_messages_per_day"] == 10
        assert prefs_data["timezone"] == "US/Eastern"
    
    def test_get_optimal_channel_user_preference(self):
        """Test channel selection based on user preference"""
        # Create user with Instagram DM preference
        user_prefs = UserPreferences(
            user_id=self.test_user_id,
            preferred_channel=ChannelType.INSTAGRAM_DM,
            backup_channels=[ChannelType.SMS, ChannelType.EMAIL],
            business_hours_only=False,
            do_not_disturb=False
        )
        
        with patch.object(self.manager, 'get_user_preferences', return_value=user_prefs):
            channel = self.manager.get_optimal_channel(self.test_user_id, "engagement", "normal")
            
            assert channel == ChannelType.INSTAGRAM_DM
    
    def test_get_optimal_channel_message_type_suitability(self):
        """Test channel selection based on message type suitability"""
        # Create user with email preference but message type suitable for SMS
        user_prefs = UserPreferences(
            user_id=self.test_user_id,
            preferred_channel=ChannelType.EMAIL,
            backup_channels=[ChannelType.SMS, ChannelType.INSTAGRAM_DM],
            business_hours_only=False,
            do_not_disturb=False
        )
        
        with patch.object(self.manager, 'get_user_preferences', return_value=user_prefs):
            # Urgent message should prefer SMS over email
            channel = self.manager.get_optimal_channel(self.test_user_id, "urgent", "urgent")
            
            # SMS should be selected for urgent messages
            assert channel in [ChannelType.SMS, ChannelType.INSTAGRAM_DM]
    
    def test_get_optimal_channel_business_hours(self):
        """Test channel selection based on business hours"""
        # Create user who only wants messages during business hours
        user_prefs = UserPreferences(
            user_id=self.test_user_id,
            preferred_channel=ChannelType.INSTAGRAM_DM,
            backup_channels=[ChannelType.SMS, ChannelType.EMAIL],
            business_hours_only=True,
            do_not_disturb=False,
            timezone="UTC"
        )
        
        with patch.object(self.manager, 'get_user_preferences', return_value=user_prefs):
            # Mock current time as after business hours (8 PM UTC)
            with patch('communication.multi_channel_manager.datetime') as mock_datetime:
                mock_datetime.utcnow.return_value = datetime(2023, 1, 1, 20, 0, 0)
                
                # Normal message should be deferred to email
                channel = self.manager.get_optimal_channel(self.test_user_id, "engagement", "normal")
                assert channel == ChannelType.EMAIL
                
                # Urgent message should use SMS
                channel = self.manager.get_optimal_channel(self.test_user_id, "urgent", "urgent")
                assert channel == ChannelType.SMS
    
    def test_get_optimal_channel_do_not_disturb(self):
        """Test channel selection with do not disturb enabled"""
        # Create user with DND enabled
        user_prefs = UserPreferences(
            user_id=self.test_user_id,
            preferred_channel=ChannelType.INSTAGRAM_DM,
            backup_channels=[ChannelType.SMS, ChannelType.EMAIL],
            business_hours_only=False,
            do_not_disturb=True
        )
        
        with patch.object(self.manager, 'get_user_preferences', return_value=user_prefs):
            # Non-urgent message should be deferred
            channel = self.manager.get_optimal_channel(self.test_user_id, "engagement", "normal")
            assert channel == ChannelType.EMAIL
            
            # Urgent message should still be delivered
            channel = self.manager.get_optimal_channel(self.test_user_id, "urgent", "urgent")
            assert channel == ChannelType.SMS
    
    def test_format_message_for_instagram_dm(self):
        """Test message formatting for Instagram DM"""
        long_message = "This is a very long message that exceeds the 1000 character limit for Instagram DM messages and should be truncated appropriately with an ellipsis at the end to indicate that there is more content that could not be displayed in this particular message."
        
        formatted = self.manager.format_message_for_channel(long_message, ChannelType.INSTAGRAM_DM, "engagement")
        
        # Should be truncated to 1000 characters with ellipsis
        assert len(formatted) <= 1000
        assert formatted.endswith("...")
        assert "💬" in formatted  # Engagement emoji should be added
    
    def test_format_message_for_sms(self):
        """Test message formatting for SMS"""
        long_message = "This is a very long message that exceeds the 160 character limit for SMS messages and should be truncated appropriately with an ellipsis at the end."
        
        formatted = self.manager.format_message_for_channel(long_message, ChannelType.SMS, "urgent")
        
        # Should be truncated to 160 characters with ellipsis
        assert len(formatted) <= 160
        assert formatted.endswith("...")
        
        # Should remove emojis and special characters
        assert "🚨" not in formatted  # Urgent emoji should be removed for SMS
    
    def test_format_message_for_email(self):
        """Test message formatting for Email"""
        message = "Please confirm your booking for tomorrow."
        
        formatted = self.manager.format_message_for_channel(message, ChannelType.EMAIL, "formal")
        
        # Should include formal email structure
        assert "Dear User," in formatted
        assert "Best regards," in formatted
        assert message in formatted
    
    def test_format_message_for_push_notification(self):
        """Test message formatting for Push Notifications"""
        long_message = "This is a very long message that exceeds the 100 character limit for push notifications and should be truncated appropriately."
        
        formatted = self.manager.format_message_for_channel(long_message, ChannelType.PUSH_NOTIFICATION, "alert")
        
        # Should be a dictionary with title and body
        assert isinstance(formatted, dict)
        assert "title" in formatted
        assert "body" in formatted
        assert len(formatted["body"]) <= 100
        assert formatted["title"] == "🔔 Alert"
    
    def test_check_compliance_real_estate(self):
        """Test compliance checking for real estate industry"""
        compliant_message = "We have several properties available that meet your criteria. All properties are offered in accordance with equal housing opportunity laws."
        non_compliant_message = "We guarantee returns on all our real estate investments!"
        
        # Test compliant message
        result = self.manager.check_compliance(
            self.test_user_id, 
            compliant_message, 
            ChannelType.EMAIL, 
            IndustryType.REAL_ESTATE
        )
        assert result is True
        
        # Test non-compliant message (guaranteed returns)
        result = self.manager.check_compliance(
            self.test_user_id, 
            non_compliant_message, 
            ChannelType.EMAIL, 
            IndustryType.REAL_ESTATE
        )
        assert result is False
    
    def test_check_compliance_fitness(self):
        """Test compliance checking for fitness industry"""
        compliant_message = "Our certified trainers can help you achieve your fitness goals. Please consult with a doctor before starting any new exercise program."
        non_compliant_message = "Our program guarantees you'll lose 20 pounds in 2 weeks!"
        
        # Test compliant message
        result = self.manager.check_compliance(
            self.test_user_id, 
            compliant_message, 
            ChannelType.EMAIL, 
            IndustryType.FITNESS
        )
        assert result is True
        
        # Test non-compliant message (guaranteed results)
        result = self.manager.check_compliance(
            self.test_user_id, 
            non_compliant_message, 
            ChannelType.EMAIL, 
            IndustryType.FITNESS
        )
        assert result is False
    
    @patch('communication.multi_channel_manager.redis_client')
    @patch('communication.multi_channel_manager.engagement_tracker')
    @patch('communication.multi_channel_manager.audit_log_event')
    def test_send_message_success(self, mock_audit, mock_engagement, mock_redis):
        """Test successful message sending"""
        # Mock Redis operations
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True
        mock_redis.zadd.return_value = True
        
        # Mock engagement tracker
        mock_engagement.record_touch_point.return_value = True
        
        result = self.manager.send_message(
            user_id=self.test_user_id,
            message=self.test_message,
            channel="instagram_dm",
            priority="normal",
            message_type="engagement"
        )
        
        assert result["success"] is True
        assert result["channel"] == "instagram_dm"
        assert result["user_id"] == self.test_user_id
        assert "message_id" in result
        assert result["delivery_status"] == "sent"
        
        # Verify engagement tracking was called
        mock_engagement.record_touch_point.assert_called_once()
        
        # Verify audit logging was called
        mock_audit.assert_called_once()
    
    @patch('communication.multi_channel_manager.redis_client')
    def test_send_message_compliance_failure(self, mock_redis):
        """Test message sending failure due to compliance"""
        # Mock Redis operations
        mock_redis.get.return_value = None
        
        non_compliant_message = "We guarantee you'll get rich quick!"
        
        result = self.manager.send_message(
            user_id=self.test_user_id,
            message=non_compliant_message,
            channel="instagram_dm",
            priority="normal",
            message_type="engagement"
        )
        
        assert result["success"] is False
        assert "compliance" in result["error"].lower()
    
    @patch('communication.multi_channel_manager.redis_client')
    def test_get_channel_performance(self, mock_redis):
        """Test getting channel performance metrics"""
        # Mock Redis performance data
        performance_data = {
            "total_sent": 100,
            "successful": 95,
            "failed": 5,
            "avg_delivery_time": 0.5,
            "last_updated": datetime.utcnow().isoformat()
        }
        mock_redis.get.return_value = json.dumps(performance_data)
        
        result = self.manager.get_channel_performance(ChannelType.INSTAGRAM_DM)
        
        assert result["total_sent"] == 100
        assert result["successful"] == 95
        assert result["failed"] == 5
        assert result["success_rate"] == 95.0  # 95/100 * 100
        assert "channel" in result
    
    @patch('communication.multi_channel_manager.redis_client')
    def test_get_delivery_status(self, mock_redis):
        """Test getting delivery status for a message"""
        # Mock Redis delivery data
        delivery_data = {
            "message_id": "test_message_123",
            "user_id": self.test_user_id,
            "channel": "instagram_dm",
            "delivery_status": "delivered",
            "sent_at": datetime.utcnow().isoformat(),
            "delivered_at": datetime.utcnow().isoformat()
        }
        mock_redis.get.return_value = json.dumps(delivery_data)
        
        result = self.manager.get_delivery_status("test_message_123")
        
        assert result is not None
        assert result["message_id"] == "test_message_123"
        assert result["user_id"] == self.test_user_id
        assert result["delivery_status"] == "delivered"
    
    def test_channel_priority_weights(self):
        """Test channel priority weights are correctly configured"""
        weights = self.manager.CHANNEL_PRIORITY_WEIGHTS
        
        # Instagram DM should have highest priority
        assert weights[ChannelType.INSTAGRAM_DM] == 1.0
        
        # All channels should have weights
        for channel in ChannelType:
            assert channel in weights
            assert 0 <= weights[channel] <= 1.0
    
    def test_channel_suitability_mapping(self):
        """Test channel suitability mapping"""
        suitability = self.manager.CHANNEL_SUITABILITY
        
        # Instagram DM should be suitable for engagement messages
        assert "engagement" in suitability[ChannelType.INSTAGRAM_DM]
        
        # SMS should be suitable for urgent messages
        assert "urgent" in suitability[ChannelType.SMS]
        
        # Email should be suitable for detailed messages
        assert "detailed" in suitability[ChannelType.EMAIL]
    
    def test_business_hours_configuration(self):
        """Test business hours configuration"""
        hours = self.manager.BUSINESS_HOURS
        
        # UTC should have standard business hours
        assert hours["UTC"]["start"] == 9
        assert hours["UTC"]["end"] == 17
        
        # IST should have extended business hours
        assert hours["Asia/Kolkata"]["start"] == 10
        assert hours["Asia/Kolkata"]["end"] == 19
    
    @patch('communication.multi_channel_manager.redis_client')
    def test_send_instagram_dm(self, mock_redis):
        """Test Instagram DM sending functionality"""
        # Mock Redis operations
        mock_redis.get.return_value = None
        mock_redis.setex.return_value = True
        
        delivery = MessageDelivery(
            message_id="test_ig_123",
            user_id=self.test_user_id,
            channel=ChannelType.INSTAGRAM_DM,
            content="Test Instagram DM message",
            priority=MessagePriority.NORMAL,
            sent_at=datetime.utcnow()
        )
        
        user_prefs = self.manager.get_user_preferences(self.test_user_id)
        result = self.manager._send_via_channel(delivery, user_prefs)
        
        assert result["success"] is True
        assert result["status"] == "sent"
        assert result["selection_reason"] == "user_preference_primary"
        assert "external_id" in result
    
    def test_industry_compliance_rules(self):
        """Test industry-specific compliance rules"""
        # Real estate rules
        real_estate_rules = self.manager._get_industry_compliance_rules(IndustryType.REAL_ESTATE)
        assert "required_disclosures" in real_estate_rules
        assert "Equal housing opportunity" in real_estate_rules["required_disclosures"]
        assert "prohibited_content" in real_estate_rules
        assert "Guaranteed returns" in str(real_estate_rules["prohibited_content"])
        
        # Fitness rules
        fitness_rules = self.manager._get_industry_compliance_rules(IndustryType.FITNESS)
        assert "Health safety disclaimers" in fitness_rules["required_disclosures"]
        assert "Guaranteed results" in str(fitness_rules["prohibited_content"])


class TestConvenienceFunctions:
    """Test convenience functions"""
    
    def test_send_message_function(self):
        """Test convenience send_message function"""
        with patch('communication.multi_channel_manager.multi_channel_manager.send_message') as mock_send:
            mock_send.return_value = {"success": True}
            
            result = send_message("user123", "test message")
            
            mock_send.assert_called_once_with("user123", "test message", "auto", "normal", "engagement")
    
    def test_get_user_preferences_function(self):
        """Test convenience get_user_preferences function"""
        with patch('communication.multi_channel_manager.multi_channel_manager.get_user_preferences') as mock_get:
            mock_get.return_value = {"preferred_channel": "instagram_dm"}
            
            result = get_user_preferences("user123")
            
            mock_get.assert_called_once_with("user123")
    
    def test_update_channel_preferences_function(self):
        """Test convenience update_channel_preferences function"""
        with patch('communication.multi_channel_manager.multi_channel_manager.update_channel_preferences') as mock_update:
            mock_update.return_value = True
            
            result = update_channel_preferences("user123", {"preferred_channel": "sms"})
            
            mock_update.assert_called_once_with("user123", {"preferred_channel": "sms"})
    
    def test_get_optimal_channel_function(self):
        """Test convenience get_optimal_channel function"""
        with patch('communication.multi_channel_manager.multi_channel_manager.get_optimal_channel') as mock_get:
            mock_get.return_value = ChannelType.INSTAGRAM_DM
            
            result = get_optimal_channel("user123", "engagement", "normal")
            
            mock_get.assert_called_once_with("user123", "engagement", "normal")
    
    def test_format_message_for_channel_function(self):
        """Test convenience format_message_for_channel function"""
        with patch('communication.multi_channel_manager.multi_channel_manager.format_message_for_channel') as mock_format:
            mock_format.return_value = "formatted message"
            
            result = format_message_for_channel("test message", "instagram_dm", "engagement")
            
            mock_format.assert_called_once_with("test message", ChannelType.INSTAGRAM_DM, "engagement")


if __name__ == "__main__":
    pytest.main([__file__])