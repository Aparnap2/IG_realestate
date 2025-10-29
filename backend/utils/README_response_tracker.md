# Response Time Tracking System

## Overview

The Response Time Tracking System implements industry-standard response time tracking to improve conversion rates by prioritizing leads based on response urgency. This system tracks first contact times for each user and calculates urgency scores based on industry-standard response windows.

## Features

- **First Contact Tracking**: Records initial contact time for each user ID
- **Industry-Standard Scoring**: Implements 5-minute response window standard
- **Redis Integration**: Stores data with appropriate TTL for performance
- **Comprehensive Error Handling**: Graceful degradation when Redis is unavailable
- **Circuit Breaker Pattern**: Resilient Redis operations with fallback

## Industry Standards

The system implements these industry-standard response time thresholds:

| Response Time | Score | Category | Impact |
|---------------|--------|-----------|---------|
| ≤ 5 minutes | 1.0 | Excellent | Meets industry standard |
| ≤ 15 minutes | 0.8 | Good | Minor impact |
| ≤ 60 minutes | 0.6 | Acceptable | Moderate impact |
| ≤ 4 hours | 0.4 | Poor | Significant impact |
| > 4 hours | 0.2 | Very Poor | 10x qualification drop |

## Key Methods

### Core Tracking Methods

```python
# Track first contact for a user
track_first_response(user_id: str, message_timestamp: datetime) -> bool

# Calculate urgency score based on response time
calculate_urgency_score(user_id: str) -> float

# Get response time in minutes
get_response_time_minutes(user_id: str) -> Optional[float]

# Get comprehensive urgency statistics
get_urgency_stats(user_id: str) -> Dict[str, Any]
```

### Advanced Methods

```python
# Update response timestamp
update_response_timestamp(user_id: str, response_timestamp: datetime) -> bool

# Get complete tracking data
get_tracking_data(user_id: str) -> Optional[Dict[str, Any]]
```

## Usage Examples

### Basic Usage

```python
from utils.response_tracker import track_first_response, calculate_urgency_score
from datetime import datetime

# Track first contact when lead reaches out
user_id = "instagram_user_123"
first_contact_time = datetime.now()
track_first_response(user_id, first_contact_time)

# Calculate urgency score for routing decisions
urgency_score = calculate_urgency_score(user_id)
if urgency_score >= 0.8:
    # High priority - route to scheduler
    pass
elif urgency_score >= 0.6:
    # Medium priority - route to followup
    pass
else:
    # Low priority - route to offramp
    pass
```

### Integration with Lead Scoring

```python
from utils.response_tracker import get_urgency_stats
from utils.lead_scoring import calculate_lead_score

# Calculate base lead score
lead_data = {...}  # Your lead data
base_score_result = calculate_lead_score(lead_data)
base_score = base_score_result['final_score']

# Get response time impact
urgency_stats = get_urgency_stats(user_id)
impact_factor = urgency_stats['qualification_impact_factor']

# Apply response time impact
enhanced_score = base_score * impact_factor
```

## Redis Key Structure

The system uses these Redis key patterns:

- `response:first_contact:{user_id}` - First contact timestamp (TTL: 7 days)
- `response:tracking:{user_id}` - Complete tracking data (TTL: 30 days)

## Data Structure

### First Contact Data
```json
{
    "user_id": "user_123",
    "first_contact_timestamp": "2025-10-26T12:00:00",
    "tracked_at": "2025-10-26T12:00:00"
}
```

### Tracking Data
```json
{
    "user_id": "user_123",
    "first_contact_timestamp": "2025-10-26T12:00:00",
    "response_timestamp": "2025-10-26T12:03:00",
    "response_time_minutes": 3.0,
    "urgency_score": 1.0,
    "created_at": "2025-10-26T12:00:00",
    "updated_at": "2025-10-26T12:03:00"
}
```

## Urgency Statistics

The `get_urgency_stats()` method returns comprehensive statistics:

```python
{
    "user_id": "user_123",
    "response_time_minutes": 3.0,
    "urgency_score": 1.0,
    "urgency_category": "excellent",
    "category_description": "Excellent response time (≤ 5 minutes)",
    "tracking_data": {...},
    "industry_standard_met": True,
    "qualification_impact_factor": 1.0,
    "stats_timestamp": "2025-10-26T12:00:00"
}
```

## Error Handling

The system implements comprehensive error handling:

- **Redis Unavailable**: Graceful degradation with logging
- **Circuit Breaker**: Prevents cascade failures
- **Data Validation**: Validates timestamps and user IDs
- **Fallback Behavior**: Returns safe defaults when tracking data unavailable

## Performance Considerations

- **TTL Management**: Automatic cleanup of old data
- **Circuit Breaker**: Prevents Redis overload
- **Efficient Key Patterns**: Optimized Redis key structure
- **Batch Operations**: Minimizes Redis round trips

## Integration Points

### Webhook Integration
```python
# In your webhook handler
def handle_instagram_webhook(webhook_data):
    user_id = webhook_data['user_id']
    message_time = datetime.fromisoformat(webhook_data['timestamp'])
    
    # Track first contact
    track_first_response(user_id, message_time)
    
    # Process message...
```

### Agent Integration
```python
# In your agent workflow
def process_lead(user_id, lead_data):
    # Get urgency stats
    urgency_stats = get_urgency_stats(user_id)
    
    # Update response timestamp when responding
    if should_respond_now():
        update_response_timestamp(user_id, datetime.now())
```

## Testing

Run the comprehensive test suite:

```bash
cd backend
python -m pytest tests/test_response_tracker.py -v
```

Run the integration example:

```bash
cd backend
python examples/response_tracker_integration.py
```

## Configuration

The system uses these configuration values:

- **FIRST_CONTACT_TTL**: 86400 * 7 seconds (7 days)
- **RESPONSE_TRACKING_TTL**: 86400 * 30 seconds (30 days)
- **Redis Connection**: Uses existing Redis client configuration

## Best Practices

1. **Track Early**: Call `track_first_response()` as soon as lead contacts you
2. **Update Promptly**: Call `update_response_timestamp()` when responding
3. **Use in Routing**: Incorporate urgency scores into routing decisions
4. **Monitor Stats**: Use `get_urgency_stats()` for performance metrics
5. **Handle Errors**: Always check return values and handle Redis failures

## Impact on Conversion Rates

Industry research shows:
- **5-minute response**: 80% higher conversion rates
- **10-minute response**: 40% higher conversion rates
- **30-minute response**: 20% higher conversion rates
- **>4 hour response**: 90% lower conversion rates

This system helps ensure you meet the 5-minute industry standard for maximum conversion.