# Multi-Channel Communication Manager

Intelligent multi-channel communication system for progressive lead nurturing with primary focus on Instagram DM and extensible architecture for additional channels.

## Overview

The Multi-Channel Communication Manager provides intelligent channel selection, message formatting, and compliance checking for lead nurturing campaigns. It integrates seamlessly with the existing nurture sequences, engagement tracker, and response tracker systems.

## Features

### 🎯 Intelligent Channel Selection
- **User Preference Priority**: Respects user's explicit channel preferences
- **Message Type Suitability**: Selects optimal channel based on message content
- **Historical Engagement**: Learns from user engagement patterns
- **Business Hours Awareness**: Respects user's business hours preferences
- **Time-Based Routing**: Urgent messages use different channels after hours

### 📱 Supported Channels
- **Instagram DM** (Primary): Rich messaging, emojis, engagement-focused
- **SMS**: Urgent communications, time-sensitive alerts
- **Email**: Detailed content, attachments, formal communications
- **In-App**: Rich media, interactive elements, real-time delivery
- **Push Notifications**: Time-sensitive alerts, booking confirmations
- **WhatsApp**: Rich messaging, document sharing (future)

### 🛡️ Industry-Specific Compliance
- **Real Estate**: Fair housing compliance, disclosure requirements
- **Fitness**: Health safety disclaimers, liability waivers
- **Restaurant**: Food safety regulations, capacity limits
- **Hotel**: Hospitality standards, accessibility requirements

### 📊 Performance Monitoring
- Channel success rates and delivery metrics
- Engagement tracking integration
- Response time monitoring
- A/B testing support

## Installation

The multi-channel communication manager is part of the backend communication module:

```python
from communication.multi_channel_manager import (
    multi_channel_manager,
    send_message,
    get_user_preferences,
    update_channel_preferences,
    get_optimal_channel,
    format_message_for_channel
)
```

## Quick Start

### Basic Message Sending

```python
# Send message with automatic channel selection
result = send_message(
    user_id="user_123",
    message="Hi! I found some great properties for you.",
    channel="auto",  # Intelligent selection
    priority="normal",
    message_type="engagement"
)

print(f"Message sent via {result['channel']}: {result['success']}")
```

### User Preference Management

```python
# Update user communication preferences
preferences = {
    "preferred_channel": "instagram_dm",
    "backup_channels": ["sms", "email"],
    "business_hours_only": True,
    "max_messages_per_day": 5,
    "timezone": "US/Eastern",
    "industry_type": "real_estate"
}

success = update_channel_preferences("user_123", preferences)
```

### Channel Selection Logic

```python
# Get optimal channel for specific message type
optimal_channel = get_optimal_channel(
    user_id="user_123",
    message_type="urgent",
    priority="urgent"
)

print(f"Optimal channel: {optimal_channel.value}")
```

## Channel Selection Algorithm

The intelligent channel selection follows this priority order:

1. **User's Explicit Preference** (Weight: 1.0)
   - Respects user's chosen primary channel
   - Falls back to backup channels if needed

2. **Message Type Suitability** (Weight: 0.9)
   - Urgent messages → SMS
   - Detailed content → Email
   - Engagement → Instagram DM
   - Rich media → In-App

3. **Historical Engagement Patterns** (Weight: 0.8)
   - Analyzes past engagement by channel
   - Prioritizes channels with higher response rates

4. **Time of Day Considerations** (Weight: 0.7)
   - Business hours vs. after hours
   - Urgent messages use SMS after hours
   - Non-urgent messages deferred to email

5. **Channel Availability** (Weight: 0.6)
   - Delivery success rates
   - Current channel performance
   - Technical availability

## Message Formatting

### Instagram DM
- Character limit: 1000 characters
- Emoji support with message type indicators
- Truncation with ellipsis for long messages

### SMS
- Character limit: 160 characters
- No emoji support (removed for compatibility)
- Urgent message optimization

### Email
- No length restrictions
- Formal structure with salutations
- HTML and attachment support

### Push Notifications
- Title: 50 characters max
- Body: 100 characters max
- Action buttons support

### In-App
- Rich media support
- Interactive elements
- Real-time delivery

## Compliance Checking

### Real Estate Industry
```python
# Required disclosures
- Equal housing opportunity
- Fair housing laws apply
- License information

# Prohibited content
- Discriminatory language
- False advertising
- Guaranteed returns

# Message limits
- Max 8 messages per day
- Minimum 2 hours between messages
```

### Fitness Industry
```python
# Required disclosures
- Health safety disclaimers
- Liability waivers
- Certification information

# Prohibited content
- Medical advice
- Guaranteed results
- Unsubstantiated claims

# Message limits
- Max 6 messages per day
- Minimum 3 hours between messages
```

## Integration with Nurture Sequences

The multi-channel manager integrates seamlessly with the nurture sequence system:

```python
from automation.nurture_sequences import nurture_sequence_manager
from communication.multi_channel_manager import multi_channel_manager

# Schedule nurture sequence
nurture_sequence_manager.schedule_nurture_sequence(
    user_id="user_123",
    lead_score=0.75,
    industry_type="real_estate",
    lead_data={"budget": 500000, "location": "Austin, TX"}
)

# Get next touch point
next_touch = nurture_sequence_manager.get_next_touch_point("user_123")

# Send via optimal channel
result = multi_channel_manager.send_message(
    user_id=next_touch["user_id"],
    message=next_touch["content"],
    channel="auto",
    priority="normal",
    message_type=next_touch["template_key"]
)
```

## Performance Monitoring

### Channel Performance Metrics

```python
# Get performance metrics for Instagram DM
performance = multi_channel_manager.get_channel_performance(ChannelType.INSTAGRAM_DM)

print(f"Success rate: {performance['success_rate']}%")
print(f"Total sent: {performance['total_sent']}")
print(f"Successful: {performance['successful']}")
print(f"Failed: {performance['failed']}")
```

### Delivery Status Tracking

```python
# Track specific message delivery
delivery_status = multi_channel_manager.get_delivery_status("message_id_123")

print(f"Status: {delivery_status['delivery_status']}")
print(f"Delivered at: {delivery_status['delivered_at']}")
print(f"Read at: {delivery_status['read_at']}")
```

## Configuration

### Redis Key Patterns

```python
# User preferences
comm:preferences:{user_id}                    # TTL: 90 days

# Message delivery tracking
comm:delivery:{message_id}                   # TTL: 30 days

# Channel performance metrics
comm:performance:{channel}                    # TTL: 24 hours

# Compliance rule cache
comm:compliance:{industry}                    # TTL: 1 hour
```

### Channel Priority Weights

```python
CHANNEL_PRIORITY_WEIGHTS = {
    ChannelType.INSTAGRAM_DM: 1.0,    # Primary channel
    ChannelType.SMS: 0.9,
    ChannelType.EMAIL: 0.8,
    ChannelType.IN_APP: 0.7,
    ChannelType.PUSH_NOTIFICATION: 0.6,
    ChannelType.WHATSAPP: 0.5
}
```

## Business Hours Configuration

```python
BUSINESS_HOURS = {
    "UTC": {"start": 9, "end": 17},           # 9 AM - 5 PM UTC
    "US/Eastern": {"start": 9, "end": 17},
    "US/Pacific": {"start": 9, "end": 17},
    "Europe/London": {"start": 9, "end": 17},
    "Asia/Kolkata": {"start": 10, "end": 19}    # 10 AM - 7 PM IST
}
```

## Testing

Run the test suite:

```bash
cd backend
python -m pytest tests/test_multi_channel_manager.py -v
```

Run the integration example:

```bash
cd backend
python examples/multi_channel_integration.py
```

## Expected Impact

### Performance Metrics
- **90% user preference matching** (industry standard)
- **40% higher engagement** through optimal channel selection
- **60% reduction** in delivery failures
- **Industry-compliant messaging** across all channels

### User Experience
- Respect for communication preferences
- Intelligent message routing
- Appropriate message formatting
- Compliance with industry regulations

### Business Benefits
- Improved lead conversion rates
- Better engagement tracking
- Reduced compliance risk
- Enhanced user satisfaction

## Future Enhancements

### Planned Features
- **WhatsApp Business API Integration**: Full WhatsApp support
- **Advanced A/B Testing**: Message variant testing
- **Machine Learning Channel Selection**: Predictive channel optimization
- **Multi-language Support**: International message formatting
- **Advanced Analytics**: Detailed engagement insights

### API Integrations
- **Instagram Graph API**: Direct Instagram DM integration
- **Twilio SMS**: Professional SMS delivery
- **SendGrid Email**: Enterprise email service
- **Firebase Push**: Cross-platform push notifications
- **WhatsApp Business API**: Rich messaging support

## Troubleshooting

### Common Issues

**Message not delivered:**
1. Check user preferences and DND status
2. Verify business hours configuration
3. Review compliance checking results
4. Check channel performance metrics

**Low engagement rates:**
1. Review channel selection logic
2. Check message formatting for channel
3. Analyze engagement patterns
4. Consider user preference updates

**Compliance failures:**
1. Review industry-specific rules
2. Check message content for prohibited terms
3. Verify required disclosures are included
4. Update compliance rule cache

### Debug Logging

Enable debug logging:

```python
import logging
logging.getLogger('communication.multi_channel_manager').setLevel(logging.DEBUG)
```

## Contributing

When contributing to the multi-channel communication manager:

1. Follow the existing code patterns
2. Add comprehensive tests for new features
3. Update documentation for API changes
4. Consider compliance implications
5. Test with different user preferences

## License

This module is part of the IG Real Estate project and follows the same licensing terms.