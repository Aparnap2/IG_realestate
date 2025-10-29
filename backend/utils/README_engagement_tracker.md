# Engagement Tracker System

Comprehensive touch point tracking system for conversion prediction and enhanced lead scoring.

## Overview

The Engagement Tracker system tracks every user interaction (touch points) and calculates engagement momentum to predict conversion readiness. It provides the engagement momentum factor (20% weight) for the enhanced lead scoring system and enables intelligent nurture sequence triggering.

## Features

- **Touch Point Tracking**: Records every interaction with detailed metadata
- **Engagement Momentum Calculation**: Multi-factor scoring system (0-1 scale)
- **Conversion Prediction**: Industry-specific conversion readiness prediction
- **Real-time Analytics**: Live engagement metrics and insights
- **Redis Integration**: High-performance caching with circuit breaker pattern
- **Comprehensive Error Handling**: Graceful degradation and resilience

## Industry-Specific Touch Requirements

| Industry | Touches Required for Conversion |
|----------|--------------------------------|
| Real Estate | 8 touches |
| Fitness | 6 touches |
| Restaurant | 7 touches |
| Hotel | 10 touches |
| Default | 8 touches |

## Touch Point Types

| Type | Weight | Description |
|------|--------|-------------|
| `text` | 1.0 | SMS/text messages |
| `email` | 0.8 | Email communications |
| `call` | 1.5 | Phone calls/video calls |
| `property_view` | 1.2 | Property listing views |
| `website_visit` | 0.6 | Website interactions |
| `social_engagement` | 0.7 | Social media interactions |
| `booking_attempt` | 1.8 | Booking/booking attempts |
| `form_submission` | 1.3 | Form completions |

## Engagement Momentum Factors

The engagement momentum score (0-1) is calculated using five weighted factors:

### 1. Recency Score (30% weight)
More recent touches are weighted higher:
- Today: 1.0x
- Yesterday: 0.9x
- 2 days ago: 0.8x
- 3 days ago: 0.7x
- Week ago: 0.5x
- 2 weeks ago: 0.3x
- Month ago: 0.1x

### 2. Frequency Score (25% weight)
Measures consistency of engagement over time:
- Consistency: Days with touches / total days in range
- Average touches per active day (capped at 3/day)

### 3. Diversity Score (20% weight)
Evaluates variety of interaction types:
- Ratio of unique touch types used
- Bonus for using 3+ different types

### 4. Progression Score (15% weight)
Tracks movement through qualification stages:
- Initial Contact: 0.2
- Qualification: 0.4
- Consideration: 0.6
- Intent: 0.8
- Decision: 1.0

### 5. Response Rate Score (10% weight)
Measures user responsiveness:
- Response rate percentage
- Bonus for quick responses (<24 hours)

## Installation

```bash
# Ensure Redis is running
redis-server

# Install dependencies
pip install redis

# The engagement tracker is ready to use
```

## Quick Start

```python
from backend.utils.engagement_tracker import engagement_tracker

# Record a touch point
engagement_tracker.record_touch_point(
    user_id="user_123",
    touch_type="email",
    content="Follow-up about property listing",
    metadata={"property_id": "prop_456", "stage": "consideration"}
)

# Calculate engagement momentum
momentum = engagement_tracker.calculate_engagement_momentum("user_123")
print(f"Engagement momentum: {momentum:.3f}")

# Predict conversion readiness
should_convert = engagement_tracker.should_convert_soon("user_123", "real_estate")
print(f"Ready to convert: {should_convert}")

# Get engagement summary
summary = engagement_tracker.get_engagement_summary("user_123")
print(f"Total touches: {summary['total_touches_30_days']}")
```

## API Reference

### Core Methods

#### `record_touch_point(user_id, touch_type, content, metadata=None)`
Record a touch point interaction.

**Parameters:**
- `user_id` (str): Unique user identifier
- `touch_type` (str): Type of touch (see Touch Point Types)
- `content` (str): Content/description of interaction
- `metadata` (dict, optional): Additional context data

**Returns:**
- `bool`: True if successfully recorded, False otherwise

**Example:**
```python
engagement_tracker.record_touch_point(
    user_id="user_123",
    touch_type="call",
    content="Phone consultation about property",
    metadata={
        "property_id": "prop_456",
        "stage": "consideration",
        "call_duration": 300,
        "agent_id": "agent_789"
    }
)
```

#### `get_touch_count(user_id, days=30)`
Get the number of touch points within a timeframe.

**Parameters:**
- `user_id` (str): Unique user identifier
- `days` (int): Number of days to look back (default: 30)

**Returns:**
- `int`: Number of touch points in the timeframe

#### `calculate_engagement_momentum(user_id)`
Calculate engagement momentum score (0-1).

**Parameters:**
- `user_id` (str): Unique user identifier

**Returns:**
- `float`: Engagement momentum score between 0 and 1

#### `should_convert_soon(user_id, industry_type)`
Predict if a user is ready to convert.

**Parameters:**
- `user_id` (str): Unique user identifier
- `industry_type` (str): Industry type for touch requirements

**Returns:**
- `bool`: True if user is likely to convert soon, False otherwise

#### `get_touch_history(user_id, limit=50)`
Get recent touch point history.

**Parameters:**
- `user_id` (str): Unique user identifier
- `limit` (int): Maximum number of touch points to return

**Returns:**
- `list`: List of touch point dictionaries ordered by most recent first

### Advanced Methods

#### `mark_response_received(user_id, touch_timestamp, response_time_seconds)`
Mark that a user responded to a touch point.

**Parameters:**
- `user_id` (str): Unique user identifier
- `touch_timestamp` (datetime): Timestamp of original touch
- `response_time_seconds` (int): Time taken to respond in seconds

**Returns:**
- `bool`: True if successfully updated, False otherwise

#### `get_engagement_summary(user_id)`
Get comprehensive engagement summary.

**Parameters:**
- `user_id` (str): Unique user identifier

**Returns:**
- `dict`: Comprehensive engagement metrics and insights

## Usage Patterns

### 1. Real-time Lead Scoring

```python
# After each interaction
engagement_tracker.record_touch_point(
    user_id=lead_id,
    touch_type="form_submission",
    content="Property inquiry form",
    metadata={"property_id": prop_id, "stage": "qualification"}
)

# Update lead score with engagement momentum
momentum = engagement_tracker.calculate_engagement_momentum(lead_id)
lead_score = base_score + (momentum * 0.2)  # 20% weight for engagement
```

### 2. Nurture Sequence Triggering

```python
# Check if user is ready for next stage
momentum = engagement_tracker.calculate_engagement_momentum(user_id)
touch_count = engagement_tracker.get_touch_count(user_id, days=7)

if momentum > 0.7 and touch_count >= 3:
    # Trigger next nurture sequence
    trigger_nurture_sequence(user_id, "advanced_consideration")
elif momentum > 0.4:
    # Send reminder
    send_reminder_email(user_id)
```

### 3. Conversion Prediction

```python
# Predict conversion for different industries
for industry in ["real_estate", "fitness", "restaurant"]:
    should_convert = engagement_tracker.should_convert_soon(user_id, industry)
    if should_convert:
        # Prioritize for sales team
        prioritize_lead(user_id, industry)
        break
```

### 4. Response Tracking

```python
# Record outreach
touch_time = datetime.utcnow()
engagement_tracker.record_touch_point(
    user_id=user_id,
    touch_type="email",
    content="Property follow-up email"
)

# When user responds
response_time = (datetime.utcnow() - touch_time).total_seconds()
engagement_tracker.mark_response_received(
    user_id=user_id,
    touch_timestamp=touch_time,
    response_time_seconds=int(response_time)
)
```

## Redis Key Structure

The engagement tracker uses the following Redis key patterns:

- `engagement:touch_points:{user_id}` - Sorted set of all touch points
- `engagement:touch_count:{user_id}:{touch_type}` - Counter per touch type
- `engagement:momentum:{user_id}` - Cached momentum score (TTL: 24h)
- `engagement:conversion_prediction:{user_id}` - Cached prediction (TTL: 1h)

## TTL Settings

- Touch points: 30 days
- Momentum cache: 24 hours
- Conversion prediction: 1 hour

## Error Handling

The system includes comprehensive error handling:

- **Circuit Breaker**: Prevents cascade failures when Redis is unavailable
- **Graceful Degradation**: Continues operation with default values when Redis fails
- **Retry Logic**: Automatic retries with exponential backoff
- **Fallback Values**: Returns sensible defaults when calculations fail

## Performance Considerations

- **Caching**: Momentum and predictions are cached to reduce computation
- **Batch Operations**: Uses Redis pipelines for multiple operations
- **Efficient Queries**: Sorted sets for time-based queries
- **Memory Management**: Automatic cleanup with TTL

## Monitoring

The system provides comprehensive logging:

```python
import logging
logging.getLogger('backend.utils.engagement_tracker').setLevel(logging.INFO)
```

Key metrics to monitor:
- Touch point recording success rate
- Momentum calculation frequency
- Conversion prediction accuracy
- Redis connection health

## Testing

Run the comprehensive test suite:

```bash
# Run unit tests
pytest backend/tests/test_engagement_tracker.py -v

# Run integration examples
python backend/examples/engagement_tracker_integration.py
```

## Integration with Lead Scoring

The engagement tracker integrates with the enhanced lead scoring system:

```python
from backend.utils.lead_scoring import calculate_enhanced_lead_score
from backend.utils.engagement_tracker import engagement_tracker

# Get engagement momentum (20% weight)
momentum = engagement_tracker.calculate_engagement_momentum(user_id)

# Calculate enhanced lead score
score = calculate_enhanced_lead_score(
    user_id=user_id,
    base_score=base_score,
    engagement_momentum=momentum,
    response_rate=response_rate,
    qualification_score=qualification_score
)
```

## Best Practices

1. **Consistent Touch Recording**: Record every interaction, no matter how small
2. **Rich Metadata**: Include relevant context (stage, property, agent, etc.)
3. **Response Tracking**: Always mark when users respond to outreach
4. **Regular Monitoring**: Monitor momentum trends and conversion predictions
5. **Industry Awareness**: Use appropriate industry types for accurate predictions

## Troubleshooting

### Common Issues

**Q: Momentum score is always 0.0**
A: Check that touch points are being recorded with valid timestamps and touch types.

**Q: Conversion prediction is always False**
A: Verify the user has sufficient touches for the industry and high enough momentum (>0.7).

**Q: Redis connection errors**
A: The system will continue operating with degraded functionality. Check Redis server status.

### Debug Mode

Enable debug logging:

```python
import logging
logging.getLogger('backend.utils.engagement_tracker').setLevel(logging.DEBUG)
```

## Contributing

When contributing to the engagement tracker:

1. Add comprehensive tests for new features
2. Update documentation and examples
3. Follow existing error handling patterns
4. Consider performance implications
5. Test with various industry types

## License

This module is part of the IG Real Estate project and follows the project's licensing terms.