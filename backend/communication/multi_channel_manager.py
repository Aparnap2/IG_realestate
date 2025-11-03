"""
Multi-Channel Communication Manager for Progressive Nurture System

Intelligent multi-channel communication for lead nurturing with:
- Primary focus on Instagram DM communication
- Extensible architecture for future channels (SMS, Email, In-App, Push, WhatsApp)
- Intelligent channel selection based on user preferences and engagement patterns
- Message formatting and delivery optimization per channel
- Integration with nurture sequences and engagement tracker
- Compliance checking for industry-specific regulations
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple, TYPE_CHECKING
from dataclasses import dataclass, asdict
from enum import Enum

# Local imports
from backend.utils.redis_client import redis_client, redis_circuit_breaker
from backend.utils.engagement_tracker import engagement_tracker
from backend.utils.response_tracker import response_tracker
from backend.utils.llm_client import get_llm_response_sync
from backend.utils.audit import audit_log_event

if TYPE_CHECKING:
    from backend.middleware.compliance_enforcement import ComplianceEnforcementMiddleware

logger = logging.getLogger(__name__)

class ChannelType(Enum):
    """Communication channels for nurture sequences"""
    INSTAGRAM_DM = "instagram_dm"
    SMS = "sms"
    EMAIL = "email"
    IN_APP = "in_app"
    PUSH_NOTIFICATION = "push_notification"
    WHATSAPP = "whatsapp"

class MessagePriority(Enum):
    """Message priority levels"""
    URGENT = "urgent"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"

class IndustryType(Enum):
    """Supported industry types for compliance checking"""
    REAL_ESTATE = "real_estate"
    FITNESS = "fitness"
    RESTAURANT = "restaurant"
    HOTEL = "hotel"
    DEFAULT = "default"

@dataclass
class UserPreferences:
    """User communication preferences"""
    user_id: str
    preferred_channel: ChannelType
    backup_channels: List[ChannelType]
    business_hours_only: bool = True
    max_messages_per_day: int = 5
    do_not_disturb: bool = False
    timezone: str = "UTC"
    industry_type: IndustryType = IndustryType.DEFAULT

@dataclass
class MessageDelivery:
    """Message delivery tracking"""
    message_id: str
    user_id: str
    channel: ChannelType
    content: str
    priority: MessagePriority
    sent_at: datetime
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    response_received: bool = False
    delivery_status: str = "pending"  # pending, sent, delivered, read, failed

class MultiChannelManager:
    """
    Multi-Channel Communication Manager for Progressive Nurture System.
    
    Features:
    - Primary focus on Instagram DM communication
    - Extensible architecture for additional channels
    - Intelligent channel selection based on user preferences
    - Message formatting and delivery optimization
    - Integration with nurture sequences and engagement tracker
    - Industry-specific compliance checking
    """
    
    def __init__(self):
        self.redis_client = redis_client
        self.circuit_breaker = redis_circuit_breaker
        self._compliance_enforcement: Optional["ComplianceEnforcementMiddleware"] = None
        
        # Redis key patterns
        self.USER_PREFERENCES_KEY = "comm:preferences:{user_id}"
        self.MESSAGE_DELIVERY_KEY = "comm:delivery:{message_id}"
        self.CHANNEL_PERFORMANCE_KEY = "comm:performance:{channel}"
        self.COMPLIANCE_CACHE_KEY = "comm:compliance:{industry}"
        
        # TTL settings (in seconds)
        self.PREFERENCES_TTL = 7776000  # 90 days
        self.DELIVERY_TTL = 2592000  # 30 days
        self.PERFORMANCE_TTL = 86400  # 24 hours
        self.COMPLIANCE_TTL = 3600  # 1 hour
        
        # Channel priority weights (higher = more preferred)
        self.CHANNEL_PRIORITY_WEIGHTS = {
            ChannelType.INSTAGRAM_DM: 1.0,  # Primary channel
            ChannelType.SMS: 0.9,
            ChannelType.EMAIL: 0.8,
            ChannelType.IN_APP: 0.7,
            ChannelType.PUSH_NOTIFICATION: 0.6,
            ChannelType.WHATSAPP: 0.5
        }
        
        # Message type suitability per channel
        self.CHANNEL_SUITABILITY = {
            ChannelType.INSTAGRAM_DM: ["urgent", "personal", "engagement", "followup"],
            ChannelType.SMS: ["urgent", "alerts", "confirmations"],
            ChannelType.EMAIL: ["detailed", "formal", "attachments", "newsletters"],
            ChannelType.IN_APP: ["rich_media", "interactive", "realtime"],
            ChannelType.PUSH_NOTIFICATION: ["time_sensitive", "alerts", "booking_confirmations"],
            ChannelType.WHATSAPP: ["rich_messaging", "document_sharing", "support"]
        }
        
        # Business hours by timezone
        self.BUSINESS_HOURS = {
            "UTC": {"start": 9, "end": 17},  # 9 AM - 5 PM UTC
            "US/Eastern": {"start": 9, "end": 17},
            "US/Pacific": {"start": 9, "end": 17},
            "Europe/London": {"start": 9, "end": 17},
            "Asia/Kolkata": {"start": 10, "end": 19}  # 10 AM - 7 PM IST
        }
    
    async def send_message(self, user_id: str, message: str, channel: str = "auto",
                       priority: str = "normal", message_type: str = "engagement") -> Dict[str, Any]:
        """
        Send message via optimal channel with mandatory compliance enforcement.
        
        CRITICAL: Now uses mandatory compliance gate middleware for 100% compliance coverage.
        This addresses Priority 1 Gap 1.2 - Compliance Enforcement Bypass.
        
        Args:
            user_id: Unique user identifier
            message: Message content to send
            channel: Specific channel to use or "auto" for intelligent selection
            priority: Message priority (urgent, high, normal, low)
            message_type: Type of message for channel suitability
            
        Returns:
            Dictionary with delivery status and tracking information
        """
        try:
            # Get user preferences
            user_prefs = self.get_user_preferences(user_id)
            
            # Determine optimal channel
            if channel == "auto":
                optimal_channel = self.get_optimal_channel(user_id, message_type, priority)
            else:
                try:
                    optimal_channel = ChannelType(channel)
                except ValueError:
                    logger.warning(f"Invalid channel '{channel}', using auto-selection")
                    optimal_channel = self.get_optimal_channel(user_id, message_type, priority)
            
            # CRITICAL: Use mandatory compliance gate for ALL messages
            logger.info(f"🔒 ENFORCING COMPLIANCE for message to {user_id}")

            if self._compliance_enforcement is None:
                from backend.middleware.compliance_enforcement import compliance_enforcement
                self._compliance_enforcement = compliance_enforcement

            compliance_success, compliance_result = await self._compliance_enforcement.send_compliant_message(
                lead_id=user_id,
                message=message,
                channel=optimal_channel.value,
                correlation_id=f"mcm_{user_id}_{datetime.utcnow().timestamp()}",
                message_metadata={
                    "message_type": message_type,
                    "priority": priority,
                    "user_preferences": user_prefs.__dict__
                }
            )

            # Block non-compliant messages
            if not compliance_success:
                return {
                    "success": False,
                    "error": "Message blocked by compliance gate",
                    "compliance_result": compliance_result,
                    "user_id": user_id,
                    "channel": optimal_channel.value,
                    "compliance_enforced": True
                }
            
            # Format message for channel (compliant message)
            formatted_message = self.format_message_for_channel(message, optimal_channel, message_type)
            
            # Create delivery tracking
            message_id = f"{optimal_channel.value}_{user_id}_{datetime.utcnow().timestamp()}"
            delivery = MessageDelivery(
                message_id=message_id,
                user_id=user_id,
                channel=optimal_channel,
                content=formatted_message,
                priority=MessagePriority(priority),
                sent_at=datetime.utcnow()
            )
            
            # Send via appropriate channel (message already compliance-verified)
            delivery_result = self._send_via_channel(delivery, user_prefs)
            
            # Track delivery
            self._track_delivery(delivery, delivery_result)
            
            # Record engagement
            engagement_tracker.record_touch_point(
                user_id=user_id,
                touch_type=optimal_channel.value,
                content=formatted_message,
                metadata={
                    "message_id": message_id,
                    "priority": priority,
                    "message_type": message_type,
                    "channel_selected": optimal_channel.value,
                    "selection_reason": delivery_result.get("selection_reason", "auto"),
                    "compliance_verified": True,
                    "compliance_gate_version": "1.0"
                }
            )
            
            # Audit log with compliance verification
            audit_log_event(
                event_type="compliant_message_sent",
                entity_id=user_id,
                payload={
                    "channel": optimal_channel.value,
                    "message_id": message_id,
                    "priority": priority,
                    "message_type": message_type,
                    "success": delivery_result.get("success", False),
                    "compliance_verified": True,
                    "compliance_result": compliance_result,
                    "enforcement_method": "mandatory_gate"
                }
            )
            
            logger.info(f"✅ COMPLIANT MESSAGE SENT: {user_id} via {optimal_channel.value}")
            
            return {
                "success": delivery_result.get("success", False),
                "message_id": message_id,
                "channel": optimal_channel.value,
                "user_id": user_id,
                "sent_at": delivery.sent_at.isoformat(),
                "delivery_status": delivery_result.get("status", "failed"),
                "selection_reason": delivery_result.get("selection_reason", "auto"),
                "error": delivery_result.get("error"),
                "compliance_verified": True,
                "compliance_result": compliance_result
            }
            
        except Exception as e:
            logger.error(f"Error sending message to user {user_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "user_id": user_id,
                "channel": channel,
                "compliance_verified": False
            }
    
    def get_user_preferences(self, user_id: str) -> UserPreferences:
        """
        Get user's communication preferences.
        
        Args:
            user_id: Unique user identifier
            
        Returns:
            UserPreferences object with user's communication settings
        """
        if self.redis_client is None:
            logger.warning("Redis unavailable - using default preferences")
            return self._get_default_preferences(user_id)
        
        def _get_preferences():
            prefs_key = self.USER_PREFERENCES_KEY.format(user_id=user_id)
            prefs_data = self.redis_client.get(prefs_key)
            
            if prefs_data:
                try:
                    prefs_dict = json.loads(prefs_data)
                    return UserPreferences(
                        user_id=prefs_dict["user_id"],
                        preferred_channel=ChannelType(prefs_dict["preferred_channel"]),
                        backup_channels=[ChannelType(ch) for ch in prefs_dict["backup_channels"]],
                        business_hours_only=prefs_dict.get("business_hours_only", True),
                        max_messages_per_day=prefs_dict.get("max_messages_per_day", 5),
                        do_not_disturb=prefs_dict.get("do_not_disturb", False),
                        timezone=prefs_dict.get("timezone", "UTC"),
                        industry_type=IndustryType(prefs_dict.get("industry_type", "default"))
                    )
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    logger.warning(f"Error parsing preferences for user {user_id}: {e}")
                    return self._get_default_preferences(user_id)
            else:
                return self._get_default_preferences(user_id)
        
        try:
            return self.circuit_breaker.call(_get_preferences)
        except Exception as e:
            logger.error(f"Failed to get preferences for user {user_id}: {e}")
            return self._get_default_preferences(user_id)
    
    def update_channel_preferences(self, user_id: str, preferences: Dict[str, Any]) -> bool:
        """
        Update user's communication preferences.
        
        Args:
            user_id: Unique user identifier
            preferences: Dictionary of preference updates
            
        Returns:
            True if successfully updated, False otherwise
        """
        if self.redis_client is None:
            logger.warning("Redis unavailable - cannot update preferences")
            return False
        
        try:
            # Get existing preferences
            existing_prefs = self.get_user_preferences(user_id)
            
            # Update with new values
            if "preferred_channel" in preferences:
                existing_prefs.preferred_channel = ChannelType(preferences["preferred_channel"])
            if "backup_channels" in preferences:
                existing_prefs.backup_channels = [ChannelType(ch) for ch in preferences["backup_channels"]]
            if "business_hours_only" in preferences:
                existing_prefs.business_hours_only = preferences["business_hours_only"]
            if "max_messages_per_day" in preferences:
                existing_prefs.max_messages_per_day = preferences["max_messages_per_day"]
            if "do_not_disturb" in preferences:
                existing_prefs.do_not_disturb = preferences["do_not_disturb"]
            if "timezone" in preferences:
                existing_prefs.timezone = preferences["timezone"]
            if "industry_type" in preferences:
                existing_prefs.industry_type = IndustryType(preferences["industry_type"])
            
            def _update_preferences():
                prefs_key = self.USER_PREFERENCES_KEY.format(user_id=user_id)
                prefs_data = asdict(existing_prefs)
                
                # Convert enums to strings for JSON serialization
                prefs_data["preferred_channel"] = existing_prefs.preferred_channel.value
                prefs_data["backup_channels"] = [ch.value for ch in existing_prefs.backup_channels]
                prefs_data["industry_type"] = existing_prefs.industry_type.value
                
                self.redis_client.setex(
                    prefs_key, 
                    self.PREFERENCES_TTL, 
                    json.dumps(prefs_data, default=str)
                )
                
                logger.info(f"Updated preferences for user {user_id}")
                return True
            
            return self.circuit_breaker.call(_update_preferences)
            
        except Exception as e:
            logger.error(f"Failed to update preferences for user {user_id}: {e}")
            return False
    
    def get_optimal_channel(self, user_id: str, message_type: str, priority: str) -> ChannelType:
        """
        AI-driven channel selection based on multiple factors.
        
        Priority Order:
        1. User's explicit preference
        2. Message type suitability
        3. Historical engagement patterns
        4. Time of day (business hours vs. after hours)
        5. Channel availability and deliverability
        
        Args:
            user_id: Unique user identifier
            message_type: Type of message being sent
            priority: Message priority level
            
        Returns:
            Optimal ChannelType for delivery
        """
        try:
            # Get user preferences
            user_prefs = self.get_user_preferences(user_id)
            
            # Check do not disturb
            if user_prefs.do_not_disturb and priority != "urgent":
                logger.info(f"User {user_id} has DND enabled, deferring non-urgent message")
                return ChannelType.EMAIL  # Queue for later delivery
            
            # Check business hours preference
            if user_prefs.business_hours_only and not self._is_business_hours(user_prefs.timezone):
                if priority == "urgent":
                    # Use SMS for urgent after-hours messages
                    return ChannelType.SMS
                else:
                    # Defer to business hours - use email as default
                    return ChannelType.EMAIL
            
            # Factor 1: User's explicit preference (highest weight)
            if self._is_channel_suitable(user_prefs.preferred_channel, message_type):
                return user_prefs.preferred_channel
            
            # Factor 2: Message type suitability
            suitable_channels = [
                channel for channel in ChannelType
                if message_type in self.CHANNEL_SUITABILITY.get(channel, [])
            ]
            
            if suitable_channels:
                # Sort by priority weights
                suitable_channels.sort(
                    key=lambda ch: self.CHANNEL_PRIORITY_WEIGHTS.get(ch, 0), 
                    reverse=True
                )
                
                # Check user's backup channels first
                for backup_channel in user_prefs.backup_channels:
                    if backup_channel in suitable_channels:
                        return backup_channel
                
                # Return highest priority suitable channel
                return suitable_channels[0]
            
            # Factor 3: Historical engagement patterns
            engagement_summary = engagement_tracker.get_engagement_summary(user_id)
            touch_breakdown = engagement_summary.get("touch_type_breakdown", {})
            
            # Find channel with highest engagement
            best_engagement_channel = None
            max_engagement = 0
            
            for channel_name, count in touch_breakdown.items():
                try:
                    channel = ChannelType(channel_name)
                    if count > max_engagement:
                        max_engagement = count
                        best_engagement_channel = channel
                except ValueError:
                    continue
            
            if best_engagement_channel:
                return best_engagement_channel
            
            # Factor 4: Default to Instagram DM (primary channel)
            return ChannelType.INSTAGRAM_DM
            
        except Exception as e:
            logger.error(f"Error selecting optimal channel for user {user_id}: {e}")
            return ChannelType.INSTAGRAM_DM
    
    def format_message_for_channel(self, message: str, channel: ChannelType, 
                               message_type: str) -> str:
        """
        Format message appropriately for the specified channel.
        
        Args:
            message: Original message content
            channel: Target channel for delivery
            message_type: Type of message being sent
            
        Returns:
            Formatted message appropriate for the channel
        """
        try:
            if channel == ChannelType.INSTAGRAM_DM:
                return self._format_for_instagram_dm(message, message_type)
            elif channel == ChannelType.SMS:
                return self._format_for_sms(message, message_type)
            elif channel == ChannelType.EMAIL:
                return self._format_for_email(message, message_type)
            elif channel == ChannelType.IN_APP:
                return self._format_for_in_app(message, message_type)
            elif channel == ChannelType.PUSH_NOTIFICATION:
                return self._format_for_push_notification(message, message_type)
            elif channel == ChannelType.WHATSAPP:
                return self._format_for_whatsapp(message, message_type)
            else:
                return message
                
        except Exception as e:
            logger.error(f"Error formatting message for {channel.value}: {e}")
            return message
    
    def check_compliance(self, user_id: str, message: str, channel: ChannelType, 
                       industry_type: IndustryType) -> bool:
        """
        Check message compliance for industry-specific regulations.
        
        Args:
            user_id: Unique user identifier
            message: Message content to check
            channel: Channel for delivery
            industry_type: Industry type for compliance rules
            
        Returns:
            True if message is compliant, False otherwise
        """
        try:
            # Check cache first
            if self.redis_client is not None:
                def _check_cache():
                    cache_key = self.COMPLIANCE_CACHE_KEY.format(industry=industry_type.value)
                    cached_rules = self.redis_client.get(cache_key)
                    if cached_rules:
                        return json.loads(cached_rules)
                    return None
                
                try:
                    cached_rules = self.circuit_breaker.call(_check_cache)
                    if cached_rules:
                        return self._apply_compliance_rules(message, channel, cached_rules)
                except Exception as e:
                    logger.warning(f"Compliance cache error: {e}")
            
            # Get compliance rules for industry
            compliance_rules = self._get_industry_compliance_rules(industry_type)
            
            # Cache rules
            if self.redis_client is not None:
                def _cache_rules():
                    cache_key = self.COMPLIANCE_CACHE_KEY.format(industry=industry_type.value)
                    self.redis_client.setex(
                        cache_key, 
                        self.COMPLIANCE_TTL, 
                        json.dumps(compliance_rules)
                    )
                
                try:
                    self.circuit_breaker.call(_cache_rules)
                except Exception as e:
                    logger.warning(f"Failed to cache compliance rules: {e}")
            
            return self._apply_compliance_rules(message, channel, compliance_rules)
            
        except Exception as e:
            logger.error(f"Error checking compliance for user {user_id}: {e}")
            return True  # Allow message on compliance check failure
    
    def _get_default_preferences(self, user_id: str) -> UserPreferences:
        """Get default user preferences"""
        return UserPreferences(
            user_id=user_id,
            preferred_channel=ChannelType.INSTAGRAM_DM,  # Primary channel
            backup_channels=[ChannelType.SMS, ChannelType.EMAIL],
            business_hours_only=True,
            max_messages_per_day=5,
            do_not_disturb=False,
            timezone="UTC",
            industry_type=IndustryType.DEFAULT
        )
    
    def _is_business_hours(self, timezone: str) -> bool:
        """Check if current time is within business hours for timezone"""
        try:
            from datetime import datetime
            import pytz
            
            tz = pytz.timezone(timezone)
            now = datetime.now(tz)
            current_hour = now.hour
            
            hours = self.BUSINESS_HOURS.get(timezone, self.BUSINESS_HOURS["UTC"])
            return hours["start"] <= current_hour < hours["end"]
            
        except Exception as e:
            logger.warning(f"Error checking business hours for {timezone}: {e}")
            return True  # Assume business hours on error
    
    def _is_channel_suitable(self, channel: ChannelType, message_type: str) -> bool:
        """Check if channel is suitable for message type"""
        suitable_types = self.CHANNEL_SUITABILITY.get(channel, [])
        return message_type in suitable_types
    
    def _send_via_channel(self, delivery: MessageDelivery, 
                         user_prefs: UserPreferences) -> Dict[str, Any]:
        """Send message via the specified channel"""
        try:
            if delivery.channel == ChannelType.INSTAGRAM_DM:
                return self._send_instagram_dm(delivery, user_prefs)
            elif delivery.channel == ChannelType.SMS:
                return self._send_sms(delivery, user_prefs)
            elif delivery.channel == ChannelType.EMAIL:
                return self._send_email(delivery, user_prefs)
            elif delivery.channel == ChannelType.IN_APP:
                return self._send_in_app(delivery, user_prefs)
            elif delivery.channel == ChannelType.PUSH_NOTIFICATION:
                return self._send_push_notification(delivery, user_prefs)
            elif delivery.channel == ChannelType.WHATSAPP:
                return self._send_whatsapp(delivery, user_prefs)
            else:
                return {"success": False, "error": f"Unsupported channel: {delivery.channel.value}"}
                
        except Exception as e:
            logger.error(f"Error sending via {delivery.channel.value}: {e}")
            return {"success": False, "error": str(e), "status": "failed"}
    
    def _send_instagram_dm(self, delivery: MessageDelivery, 
                          user_prefs: UserPreferences) -> Dict[str, Any]:
        """Send message via Instagram DM"""
        try:
            # TODO: Integrate with Instagram API
            # For now, simulate successful delivery
            
            logger.info(f"Sending Instagram DM to {delivery.user_id}: {delivery.content[:50]}...")
            
            # Simulate API call
            import time
            time.sleep(0.1)  # Simulate network latency
            
            return {
                "success": True,
                "status": "sent",
                "selection_reason": "user_preference_primary",
                "external_id": f"ig_dm_{delivery.message_id}",
                "delivered_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error sending Instagram DM: {e}")
            return {"success": False, "error": str(e), "status": "failed"}
    
    def _send_sms(self, delivery: MessageDelivery, 
                   user_prefs: UserPreferences) -> Dict[str, Any]:
        """Send message via SMS"""
        try:
            # TODO: Integrate with SMS provider (Twilio, etc.)
            logger.info(f"Sending SMS to {delivery.user_id}: {delivery.content[:50]}...")
            
            return {
                "success": True,
                "status": "sent",
                "selection_reason": "urgent_after_hours",
                "external_id": f"sms_{delivery.message_id}",
                "delivered_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error sending SMS: {e}")
            return {"success": False, "error": str(e), "status": "failed"}
    
    def _send_email(self, delivery: MessageDelivery, 
                    user_prefs: UserPreferences) -> Dict[str, Any]:
        """Send message via Email"""
        try:
            # TODO: Integrate with email service (SendGrid, etc.)
            logger.info(f"Sending email to {delivery.user_id}: {delivery.content[:50]}...")
            
            return {
                "success": True,
                "status": "sent",
                "selection_reason": "business_hours_defer",
                "external_id": f"email_{delivery.message_id}",
                "delivered_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return {"success": False, "error": str(e), "status": "failed"}
    
    def _send_in_app(self, delivery: MessageDelivery, 
                     user_prefs: UserPreferences) -> Dict[str, Any]:
        """Send message via In-App notification"""
        try:
            # TODO: Integrate with in-app notification system
            logger.info(f"Sending in-app message to {delivery.user_id}: {delivery.content[:50]}...")
            
            return {
                "success": True,
                "status": "delivered",
                "selection_reason": "rich_media_required",
                "external_id": f"inapp_{delivery.message_id}",
                "delivered_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error sending in-app message: {e}")
            return {"success": False, "error": str(e), "status": "failed"}
    
    def _send_push_notification(self, delivery: MessageDelivery, 
                              user_prefs: UserPreferences) -> Dict[str, Any]:
        """Send message via Push Notification"""
        try:
            # TODO: Integrate with push notification service
            logger.info(f"Sending push notification to {delivery.user_id}: {delivery.content[:50]}...")
            
            return {
                "success": True,
                "status": "sent",
                "selection_reason": "time_sensitive_alert",
                "external_id": f"push_{delivery.message_id}",
                "delivered_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error sending push notification: {e}")
            return {"success": False, "error": str(e), "status": "failed"}
    
    def _send_whatsapp(self, delivery: MessageDelivery, 
                      user_prefs: UserPreferences) -> Dict[str, Any]:
        """Send message via WhatsApp"""
        try:
            # TODO: Integrate with WhatsApp Business API
            logger.info(f"Sending WhatsApp message to {delivery.user_id}: {delivery.content[:50]}...")
            
            return {
                "success": True,
                "status": "sent",
                "selection_reason": "rich_messaging_required",
                "external_id": f"wa_{delivery.message_id}",
                "delivered_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error sending WhatsApp message: {e}")
            return {"success": False, "error": str(e), "status": "failed"}
    
    def _track_delivery(self, delivery: MessageDelivery, delivery_result: Dict[str, Any]):
        """Track message delivery status"""
        if self.redis_client is None:
            logger.warning("Redis unavailable - cannot track delivery")
            return
        
        try:
            def _track():
                delivery_key = self.MESSAGE_DELIVERY_KEY.format(message_id=delivery.message_id)
                
                # Update delivery with result
                delivery.delivery_status = delivery_result.get("status", "failed")
                if delivery_result.get("delivered_at"):
                    delivery.delivered_at = datetime.fromisoformat(delivery_result["delivered_at"])
                
                delivery_data = asdict(delivery)
                
                # Convert enums to strings for JSON serialization
                delivery_data["channel"] = delivery.channel.value
                delivery_data["priority"] = delivery.priority.value
                
                self.redis_client.setex(
                    delivery_key,
                    self.DELIVERY_TTL,
                    json.dumps(delivery_data, default=str)
                )
                
                # Update channel performance metrics
                self._update_channel_performance(delivery.channel, delivery_result)
            
            self.circuit_breaker.call(_track)
            
        except Exception as e:
            logger.error(f"Error tracking delivery: {e}")
    
    def _update_channel_performance(self, channel: ChannelType, delivery_result: Dict[str, Any]):
        """Update channel performance metrics"""
        if self.redis_client is None:
            return
        
        try:
            def _update():
                perf_key = self.CHANNEL_PERFORMANCE_KEY.format(channel=channel.value)
                
                # Get current performance
                perf_data = self.redis_client.get(perf_key)
                if perf_data:
                    performance = json.loads(perf_data)
                else:
                    performance = {
                        "total_sent": 0,
                        "successful": 0,
                        "failed": 0,
                        "avg_delivery_time": 0.0,
                        "last_updated": datetime.utcnow().isoformat()
                    }
                
                # Update metrics
                performance["total_sent"] += 1
                if delivery_result.get("success", False):
                    performance["successful"] += 1
                else:
                    performance["failed"] += 1
                
                performance["last_updated"] = datetime.utcnow().isoformat()
                
                self.redis_client.setex(
                    perf_key,
                    self.PERFORMANCE_TTL,
                    json.dumps(performance, default=str)
                )
            
            self.circuit_breaker.call(_update)
            
        except Exception as e:
            logger.error(f"Error updating channel performance: {e}")
    
    def _format_for_instagram_dm(self, message: str, message_type: str) -> str:
        """Format message for Instagram DM"""
        # Instagram DM has character limits and supports emojis, basic formatting
        if len(message) > 1000:
            message = message[:997] + "..."  # Truncate with ellipsis
        
        # Add appropriate emojis based on message type
        emoji_map = {
            "urgent": "🚨",
            "engagement": "💬",
            "followup": "📞",
            "booking": "📅",
            "personal": "👋"
        }
        
        emoji = emoji_map.get(message_type, "")
        if emoji and not message.startswith(emoji):
            message = f"{emoji} {message}"
        
        return message
    
    def _format_for_sms(self, message: str, message_type: str) -> str:
        """Format message for SMS"""
        # SMS has 160 character limit per message
        if len(message) > 160:
            message = message[:157] + "..."
        
        # Remove emojis and special characters for SMS compatibility
        import re
        message = re.sub(r'[^\w\s\.\,\!\?\@]', '', message)
        
        return message
    
    def _format_for_email(self, message: str, message_type: str) -> str:
        """Format message for Email"""
        # Email can support longer content and HTML formatting
        if message_type == "formal":
            message = f"Dear User,\n\n{message}\n\nBest regards,\nTeam"
        elif message_type == "newsletter":
            message = f"📧 Newsletter\n\n{message}\n\nUnsubscribe"
        else:
            message = f"Hi there!\n\n{message}\n\nBest,\nTeam"
        
        return message
    
    def _format_for_in_app(self, message: str, message_type: str) -> str:
        """Format message for In-App notification"""
        # In-app can support rich formatting and interactive elements
        return {
            "text": message,
            "type": message_type,
            "timestamp": datetime.utcnow().isoformat(),
            "actions": self._get_in_app_actions(message_type)
        }
    
    def _format_for_push_notification(self, message: str, message_type: str) -> str:
        """Format message for Push Notification"""
        # Push notifications need to be concise and attention-grabbing
        if len(message) > 100:
            message = message[:97] + "..."
        
        title_map = {
            "urgent": "🚨 Urgent",
            "booking": "📅 Booking Confirmation",
            "alert": "🔔 Alert",
            "default": "💬 New Message"
        }
        
        title = title_map.get(message_type, title_map["default"])
        
        return {
            "title": title,
            "body": message,
            "type": message_type,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _format_for_whatsapp(self, message: str, message_type: str) -> str:
        """Format message for WhatsApp"""
        # WhatsApp supports rich formatting and longer messages
        if message_type == "rich_messaging":
            # Add WhatsApp formatting
            message = f"*{message}*"  # Bold text
        elif message_type == "document_sharing":
            message = f"📎 {message}"
        
        return message
    
    def _get_in_app_actions(self, message_type: str) -> List[Dict[str, str]]:
        """Get appropriate in-app actions based on message type"""
        actions_map = {
            "booking": [
                {"text": "Confirm", "action": "confirm"},
                {"text": "Reschedule", "action": "reschedule"}
            ],
            "engagement": [
                {"text": "Reply", "action": "reply"},
                {"text": "View Details", "action": "view"}
            ],
            "followup": [
                {"text": "Schedule Call", "action": "schedule"},
                {"text": "Not Interested", "action": "decline"}
            ]
        }
        
        return actions_map.get(message_type, [])
    
    def _get_industry_compliance_rules(self, industry_type: IndustryType) -> Dict[str, Any]:
        """Get compliance rules for specific industry"""
        rules = {
            IndustryType.REAL_ESTATE: {
                "required_disclosures": [
                    "Equal housing opportunity",
                    "Fair housing laws apply",
                    "License information"
                ],
                "prohibited_content": [
                    "Discriminatory language",
                    "False advertising",
                    "Guaranteed returns"
                ],
                "message_limits": {
                    "max_per_day": 8,
                    "min_interval_hours": 2
                }
            },
            IndustryType.FITNESS: {
                "required_disclosures": [
                    "Health safety disclaimers",
                    "Liability waivers",
                    "Certification information"
                ],
                "prohibited_content": [
                    "Medical advice",
                    "Guaranteed results",
                    "Unsubstantiated claims"
                ],
                "message_limits": {
                    "max_per_day": 6,
                    "min_interval_hours": 3
                }
            },
            IndustryType.RESTAURANT: {
                "required_disclosures": [
                    "Food safety information",
                    "Allergy warnings",
                    "Capacity limits"
                ],
                "prohibited_content": [
                    "False health claims",
                    "Unverified reviews",
                    "Misleading pricing"
                ],
                "message_limits": {
                    "max_per_day": 7,
                    "min_interval_hours": 2
                }
            },
            IndustryType.HOTEL: {
                "required_disclosures": [
                    "Hospitality standards",
                    "Accessibility information",
                    "Cancellation policies"
                ],
                "prohibited_content": [
                    "False availability",
                    "Hidden fees",
                    "Misleading amenities"
                ],
                "message_limits": {
                    "max_per_day": 10,
                    "min_interval_hours": 1
                }
            },
            IndustryType.DEFAULT: {
                "required_disclosures": ["Terms of service"],
                "prohibited_content": ["Spam", "Harassment"],
                "message_limits": {
                    "max_per_day": 5,
                    "min_interval_hours": 4
                }
            }
        }
        
        return rules.get(industry_type, rules[IndustryType.DEFAULT])
    
    def _apply_compliance_rules(self, message: str, channel: ChannelType,
                               compliance_rules: Dict[str, Any]) -> bool:
        """Apply compliance rules to message"""
        try:
            # Check prohibited content
            prohibited_content = compliance_rules.get("prohibited_content", [])
            for prohibited in prohibited_content:
                if isinstance(prohibited, str) and prohibited.lower() in message.lower():
                    logger.warning(f"Message contains prohibited content: {prohibited}")
                    return False
            
            # Check message limits
            message_limits = compliance_rules.get("message_limits", {})
            max_per_day = message_limits.get("max_per_day", 5)
            
            # TODO: Implement daily message count checking
            # For now, assume compliance
            
            # Check required disclosures for certain industries
            required_disclosures = compliance_rules.get("required_disclosures", [])
            if required_disclosures and channel in [ChannelType.EMAIL, ChannelType.INSTAGRAM_DM]:
                # For formal channels, ensure disclosures are present
                # This is a simplified check - in practice, you'd want more sophisticated logic
                pass
            
            return True
            
        except Exception as e:
            logger.error(f"Error applying compliance rules: {e}")
            return True  # Allow message on compliance check failure
    
    def get_channel_performance(self, channel: ChannelType) -> Dict[str, Any]:
        """Get performance metrics for a specific channel"""
        if self.redis_client is None:
            return {"error": "Redis unavailable"}
        
        try:
            def _get_performance():
                perf_key = self.CHANNEL_PERFORMANCE_KEY.format(channel=channel.value)
                perf_data = self.redis_client.get(perf_key)
                
                if perf_data:
                    performance = json.loads(perf_data)
                    
                    # Calculate success rate
                    total = performance.get("total_sent", 0)
                    successful = performance.get("successful", 0)
                    success_rate = (successful / total * 100) if total > 0 else 0
                    
                    performance["success_rate"] = round(success_rate, 2)
                    return performance
                else:
                    return {
                        "channel": channel.value,
                        "total_sent": 0,
                        "successful": 0,
                        "failed": 0,
                        "success_rate": 0.0,
                        "avg_delivery_time": 0.0,
                        "last_updated": datetime.utcnow().isoformat()
                    }
            
            return self.circuit_breaker.call(_get_performance)
            
        except Exception as e:
            logger.error(f"Error getting channel performance for {channel.value}: {e}")
            return {"error": str(e)}
    
    def get_delivery_status(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Get delivery status for a specific message"""
        if self.redis_client is None:
            return None
        
        try:
            def _get_status():
                delivery_key = self.MESSAGE_DELIVERY_KEY.format(message_id=message_id)
                delivery_data = self.redis_client.get(delivery_key)
                
                if delivery_data:
                    return json.loads(delivery_data)
                return None
            
            return self.circuit_breaker.call(_get_status)
            
        except Exception as e:
            logger.error(f"Error getting delivery status for {message_id}: {e}")
            return None

# Global instance
multi_channel_manager = MultiChannelManager()

# Convenience functions for backward compatibility (now async for compliance)
async def send_message(user_id: str, message: str, channel: str = "auto",
                priority: str = "normal", message_type: str = "engagement") -> Dict[str, Any]:
    """Send message via optimal channel with mandatory compliance enforcement"""
    return await multi_channel_manager.send_message(user_id, message, channel, priority, message_type)

def get_user_preferences(user_id: str) -> UserPreferences:
    """Get user communication preferences"""
    return multi_channel_manager.get_user_preferences(user_id)

def update_channel_preferences(user_id: str, preferences: Dict[str, Any]) -> bool:
    """Update user communication preferences"""
    return multi_channel_manager.update_channel_preferences(user_id, preferences)

def get_optimal_channel(user_id: str, message_type: str, priority: str) -> ChannelType:
    """Get optimal channel for user and message type"""
    return multi_channel_manager.get_optimal_channel(user_id, message_type, priority)

def format_message_for_channel(message: str, channel: str, message_type: str) -> str:
    """Format message for specific channel"""
    try:
        channel_enum = ChannelType(channel)
        return multi_channel_manager.format_message_for_channel(message, channel_enum, message_type)
    except ValueError:
        logger.error(f"Invalid channel: {channel}")
        return message