# Progressive Nurture System - Automated Follow-up Sequences

## Overview

The Progressive Nurture System implements industry-specific automated follow-up sequences using LangGraph orchestration. This system enables the industry-standard 6-24 month nurture cycles critical for achieving 2-5% conversion rates, with 90% reduction in manual follow-up work through automation.

## Features

### 🎯 Industry-Specific Sequences
- **Real Estate**: High/Low intent sequences with property-focused messaging
- **Fitness**: High intent sequences with membership-focused messaging  
- **Restaurant**: High intent sequences with event-focused messaging
- **Hotel**: Planned sequences for hospitality industry

### 🔄 LangGraph Workflow Orchestration
- Dynamic task scheduling with dependencies
- Human-in-the-loop capabilities for critical touch points
- State persistence and recovery
- Parallel execution support
- Intelligent workflow adaptation based on user responses

### 📱 Multi-Channel Communication
- **SMS**: Quick updates and reminders
- **Email**: Detailed content and attachments
- **In-App**: Real-time notifications
- **Call**: High-touch personal outreach

### 🎨 Template-Based Personalization
- Industry-specific message templates
- Dynamic content generation using LLM
- Compliance-checked content
- A/B testing capabilities

### 📊 Integration & Analytics
- Engagement tracker integration for touch recording
- Redis-based scheduling and state management
- Comprehensive logging and error handling
- Progress tracking and conversion readiness

## Quick Start

### Basic Usage

```python
from automation.nurture_sequences import schedule_nurture_sequence

# Schedule nurture sequence for a real estate lead
lead_data = {
    "user_id": "user_123",
    "first_name": "Sarah",
    "budget": 750000,
    "location": "Miami",
    "timeline": "3 months"
}

success = schedule_nurture_sequence(
    user_id="user_123",
    lead_score=0.8,  # High intent
    industry_type="real_estate",
    lead_data=lead_data
)
```

### Advanced Usage

```python
from automation.nurture_sequences import NurtureSequenceManager

manager = NurtureSequenceManager()

# Get next scheduled touch point
next_touch = manager.get_next_touch_point("user_123")
if next_touch:
    print(f"Next touch: Day {next_touch['day']} - {next_touch['channel']}")

# Update sequence progress after touch completion
manager.update_sequence_progress("user_123", touch_completed=True)

# Cancel sequence if needed
manager.cancel_nurture_sequence("user_123")
```

## Industry-Specific Sequences

### Real Estate

**High Intent (Score ≥ 0.6)**
- Day 1: SMS - Market insights for target areas
- Day 3: Email - Property listings matching budget
- Day 7: SMS - Neighborhood guide with amenities
- Day 14: Call - Consultation booking offer
- Day 21: Email - Market update and new listings

**Low Intent (Score < 0.6)**
- Day 2: SMS - Budget education and financing options
- Day 5: Email - Market trends and inventory
- Day 10: SMS - Timeline check and urgency

### Fitness

**High Intent (Score ≥ 0.5)**
- Day 1: SMS - Class schedule availability
- Day 2: Email - Facility tour invitation
- Day 5: SMS - Trial reminder and benefits
- Day 10: Call - Membership offer

### Restaurant

**High Intent (Score ≥ 0.55)**
- Day 1: SMS - Menu highlights and specialties
- Day 3: Email - Event packages and pricing
- Day 7: SMS - Chef profile and cuisine details
- Day 14: Call - Table reservation offer

## Message Templates

### Template Structure

```python
template = {
    "template": "Hi {first_name}! Here are the latest market insights for {target_area}: {market_data}",
    "personalization_fields": ["first_name", "target_area", "market_data"],
    "compliance_required": True
}
```

### Personalization Fields

Each template supports dynamic personalization using:
- `{first_name}` - User's first name
- `{location}` - Target location/area
- `{budget}` - User's budget range
- `{timeline}` - Purchase/timeline preferences
- Industry-specific fields (e.g., `{property_type}`, `{membership_type}`)

### Content Generation

The system uses LLM-powered content generation to:
- Create natural, personalized messages
- Adapt tone based on channel (SMS vs Email)
- Include relevant details from user data
- Ensure compliance with industry regulations

## LangGraph Workflow

### Workflow Components

1. **Content Generation Task**: Creates personalized messages
2. **Scheduling Task**: Manages touch point timing
3. **Response Waiting Task**: Handles user interactions
4. **Progress Update Task**: Tracks completion status

### Human-in-the-Loop

Critical touch points (like calls) can trigger human intervention:
```python
# Example: Call scheduling interrupt
if touch_point.channel == ChannelType.CALL:
    return interrupt({
        "action": "schedule_call",
        "touch_point": asdict(touch_point),
        "user_id": user_id,
        "instructions": f"Call user for {touch_point.template_key}"
    })
```

## API Reference

### Core Functions

#### `schedule_nurture_sequence(user_id, lead_score, industry_type, lead_data)`
Schedule automated nurture sequence for a user.

**Parameters:**
- `user_id` (str): Unique user identifier
- `lead_score` (float): Qualification score (0-1)
- `industry_type` (str): Industry type for sequence selection
- `lead_data` (dict): Lead information for personalization

**Returns:** `bool` - True if successfully scheduled

#### `get_next_touch_point(user_id)`
Get next scheduled touch point for a user.

**Parameters:**
- `user_id` (str): Unique user identifier

**Returns:** `dict` or `None` - Next touch point data

#### `cancel_nurture_sequence(user_id)`
Cancel active nurture sequence for a user.

**Parameters:**
- `user_id` (str): Unique user identifier

**Returns:** `bool` - True if successfully cancelled

#### `update_sequence_progress(user_id, touch_completed)`
Update sequence progress after touch point completion.

**Parameters:**
- `user_id` (str): Unique user identifier
- `touch_completed` (bool): Whether touch was completed successfully

**Returns:** `bool` - True if successfully updated

### Manager Class

#### `NurtureSequenceManager`
Main class for managing nurture sequences.

**Methods:**
- `schedule_nurture_sequence()` - Schedule new sequence
- `get_next_touch_point()` - Get next touch point
- `cancel_nurture_sequence()` - Cancel active sequence
- `update_sequence_progress()` - Update progress
- `_create_sequence_workflow()` - Create LangGraph workflow
- `_generate_initial_schedule()` - Generate touch point schedule

## Configuration

### Redis Keys

- `nurture:sequence:{user_id}` - Sequence configuration
- `nurture:schedule:{user_id}` - Touch point schedule
- `nurture:progress:{user_id}` - Progress tracking

### TTL Settings

- Sequence TTL: 90 days (7,776,000 seconds)
- Schedule TTL: 90 days (7,776,000 seconds)
- Progress TTL: 90 days (7,776,000 seconds)

### Intent Thresholds

- Real Estate: 0.6
- Fitness: 0.5
- Restaurant: 0.55
- Hotel: 0.7

## Integration Points

### Engagement Tracker

All touch points are automatically recorded with the engagement tracker:

```python
engagement_tracker.record_touch_point(
    user_id=user_id,
    channel=touch_point.channel,
    touch_type="nurture_sequence",
    content=personalized_content,
    metadata={
        "sequence_id": sequence_id,
        "touch_day": touch_point.day,
        "template_key": touch_point.template_key,
        "industry_type": industry_type
    }
)
```

### Compliance System

All content is checked for compliance before delivery:
- Real estate: Property advertising regulations
- Fitness: Membership disclosure requirements
- Restaurant: Event promotion guidelines

### Error Handling

The system includes comprehensive error handling:
- Circuit breaker pattern for Redis operations
- Fallback scheduling when LangGraph unavailable
- Graceful degradation for missing dependencies
- Detailed logging for troubleshooting

## Testing

### Running Tests

```bash
# Run all nurture sequence tests
cd backend && python -m pytest tests/test_nurture_sequences.py -v

# Run with coverage
cd backend && python -m pytest tests/test_nurture_sequences.py --cov=automation.nurture_sequences
```

### Test Coverage

The test suite covers:
- Industry sequence initialization
- Message template personalization
- Scheduling and progress tracking
- LangGraph workflow creation
- Integration with engagement tracker
- Error handling and fallback scenarios
- Compliance requirements

## Examples

### Complete Integration Example

```python
from automation.nurture_sequences import (
    schedule_nurture_sequence,
    get_next_touch_point,
    update_sequence_progress,
    cancel_nurture_sequence
)
from utils.engagement_tracker import engagement_tracker

# 1. Schedule sequence for high-intent real estate lead
lead_data = {
    "user_id": "realestate_user_001",
    "first_name": "Sarah",
    "budget": 750000,
    "location": "Miami",
    "timeline": "3 months",
    "property_type": "3BHK"
}

success = schedule_nurture_sequence(
    user_id=lead_data["user_id"],
    lead_score=0.8,  # High intent
    industry_type="real_estate",
    lead_data=lead_data
)

# 2. Check next scheduled touch
next_touch = get_next_touch_point(lead_data["user_id"])
if next_touch:
    print(f"Next touch: Day {next_touch['day']} - {next_touch['channel'].upper()}")
    print(f"Template: {next_touch['template_key']}")

# 3. After executing touch, update progress
update_sequence_progress(lead_data["user_id"], touch_completed=True)

# 4. Check engagement summary
engagement_summary = engagement_tracker.get_engagement_summary(lead_data["user_id"])
print(f"Total touches: {engagement_summary.get('total_touches_30_days', 0)}")

# 5. Cancel if needed (e.g., user converts)
cancel_nurture_sequence(lead_data["user_id"])
```

## Performance Impact

### Expected Results

- **90% reduction** in manual follow-up work
- **8-12 touch sequences** per lead (industry standard)
- **6-24 month nurture cycles** for optimal conversion
- **2-5% conversion rates** with consistent nurturing

### Resource Usage

- Redis memory: ~1KB per active sequence
- LLM calls: 1-2 per touch point for content generation
- Database writes: 1-2 per touch point completion
- Network overhead: Minimal (batch operations)

## Troubleshooting

### Common Issues

1. **LangGraph Not Available**
   ```
   WARNING: LangGraph not available. Install with: pip install langgraph langchain
   ```
   **Solution:** Install LangGraph dependencies or use fallback mode

2. **Redis Connection Failed**
   ```
   ERROR: Failed to schedule nurture sequence: Redis connection failed
   ```
   **Solution:** Check Redis server status and connection settings

3. **No Sequence Found**
   ```
   ERROR: No sequence found for industry X with intent level Y
   ```
   **Solution:** Verify industry type and lead score thresholds

### Debug Logging

Enable debug logging for detailed troubleshooting:

```python
import logging
logging.getLogger('automation.nurture_sequences').setLevel(logging.DEBUG)
```

## Future Enhancements

### Planned Features

1. **Advanced A/B Testing**: Multi-variant message testing
2. **Predictive Scheduling**: AI-powered optimal timing
3. **Cross-Channel Orchestration**: Coordinated multi-channel campaigns
4. **Dynamic Sequence Adaptation**: Real-time sequence modification
5. **Advanced Analytics**: Conversion attribution and ROI tracking

### Extension Points

The system is designed for easy extension:
- Add new industries by extending `IndustryType` enum
- Create new channels by extending `ChannelType` enum
- Implement custom templates in `_initialize_message_templates()`
- Add new workflow tasks in `_create_sequence_workflow()`

## Contributing

When contributing to the nurture sequences system:

1. Follow existing code patterns and naming conventions
2. Add comprehensive tests for new features
3. Update documentation for API changes
4. Ensure compliance with industry regulations
5. Test with both LangGraph and fallback modes

## License

This module is part of the IG Real Estate automation system and follows the project's licensing terms.