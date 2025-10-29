# Enhanced Lead Scoring System

## Overview

The Enhanced Lead Scoring System integrates response time tracking with industry-adaptive scoring to provide more accurate lead qualification and routing recommendations. This system builds upon the existing lead scoring infrastructure while adding new dimensions for urgency and engagement momentum.

## Key Features

### 🎯 Industry-Adaptive Scoring
- **Real Estate**: conversion_threshold=0.6, nurture_threshold=0.35, required_touches=8
- **Fitness**: conversion_threshold=0.5, nurture_threshold=0.3, required_touches=6  
- **Restaurant**: conversion_threshold=0.55, nurture_threshold=0.35, required_touches=7
- **Hotel**: conversion_threshold=0.65, nurture_threshold=0.4, required_touches=10

### ⚡ Response Time Urgency (20% weight)
- Integrates with `ResponseTimeTracker` for industry-standard 5-minute response window
- Scores based on response time categories:
  - ≤ 5 minutes: 1.0 (Excellent - meets industry standard)
  - ≤ 15 minutes: 0.8 (Good)
  - ≤ 60 minutes: 0.6 (Acceptable)
  - ≤ 4 hours: 0.4 (Poor)
  - > 4 hours: 0.2 (Very poor - qualification drops 10x)

### 📈 Engagement Momentum (20% weight)
- Calculates momentum based on conversation history and touch points
- Factors considered:
  - Multiple user interactions
  - Recent activity (within last hour/day/3 days)
  - Touch point diversity and recency
  - Score progression from previous assessments

### 🔄 Enhanced Scoring Formula
```
enhanced_score = (
    base_score * 0.6 +           # Existing scoring 60%
    urgency_score * 0.2 +          # Response time 20%
    engagement_score * 0.2            # Engagement momentum 20%
) * industry_multiplier
```

## Implementation Details

### Class Structure
```python
class LeadScoringSystem:
    INDUSTRY_CONFIGS = {
        # Industry-specific configurations with realistic thresholds
    }
    
    def __init__(self):
        self.response_tracker = ResponseTimeTracker()
        self.enhanced_scoring_weights = {
            'base_score': 0.6,
            'urgency_score': 0.2,
            'engagement_momentum': 0.2
        }
```

### Key Methods

#### `calculate_enhanced_lead_score()`
Main method for enhanced scoring with industry-adaptive thresholds.

**Parameters:**
- `user_id`: Unique identifier for response time tracking
- `industry_type`: Industry type (real_estate, fitness, restaurant, hotel)
- `budget`, `location`, `timeline`, etc.: Traditional lead data
- `conversation_history`: List of conversation messages with timestamps
- `touch_points`: List of engagement touch points with timestamps

**Returns:**
```python
{
    'enhanced_score': 0.630,
    'base_score': 0.500,
    'urgency_score': 1.000,
    'engagement_momentum_score': 0.650,
    'industry_type': 'real_estate',
    'industry_config': {...},
    'routing_recommendation': {...},
    'qualification_stage': 'qualified',
    'improvement_potential': {...},
    'thresholds': {...}
}
```

#### `_calculate_urgency_score()`
Integrates with ResponseTimeTracker to calculate urgency based on response time.

#### `_calculate_engagement_momentum()`
Calculates engagement momentum from conversation history and touch points.

#### `_determine_enhanced_routing()`
Provides industry-specific routing recommendations based on enhanced scores.

## Usage Examples

### Basic Enhanced Scoring
```python
from backend.utils.lead_scoring import calculate_enhanced_lead_score

lead_data = {
    'budget': 350000,
    'location': 'Downtown Austin, TX',
    'timeline': '3-6 months',
    'email': 'lead@example.com',
    'message': 'Looking for 2-bedroom condo'
}

result = calculate_enhanced_lead_score(
    lead_data,
    user_id='user_123',
    industry_type='real_estate',
    conversation_history=conversation_history,
    touch_points=touch_points
)

print(f"Enhanced Score: {result['enhanced_score']:.3f}")
print(f"Routing: {result['routing_recommendation']['next_agent']}")
```

### Industry-Specific Scoring
```python
# Real Estate - Higher thresholds for longer sales cycle
real_estate_result = calculate_enhanced_lead_score(
    lead_data, industry_type='real_estate', user_id='user_123'
)

# Fitness - Lower thresholds for quicker decisions
fitness_result = calculate_enhanced_lead_score(
    lead_data, industry_type='fitness', user_id='user_456'
)

# Restaurant - Medium thresholds for impulse decisions
restaurant_result = calculate_enhanced_lead_score(
    lead_data, industry_type='restaurant', user_id='user_789'
)

# Hotel - Higher thresholds for complex booking process
hotel_result = calculate_enhanced_lead_score(
    lead_data, industry_type='hotel', user_id='user_999'
)
```

## Backward Compatibility

The enhanced system maintains full backward compatibility with the existing `calculate_lead_score()` function:

```python
from backend.utils.lead_scoring import calculate_lead_score

# Original scoring still works with same interface
original_result = calculate_lead_score(lead_data)
print(f"Original Score: {original_result['final_score']:.3f}")
```

## Integration with Response Time Tracking

The system integrates seamlessly with the `ResponseTimeTracker`:

```python
from backend.utils.response_tracker import track_first_response

# Track first contact time
track_first_response('user_123', datetime.now())

# Enhanced scoring will automatically use response time data
result = calculate_enhanced_lead_score(
    lead_data, user_id='user_123', industry_type='real_estate'
)
```

## Routing Logic

### Industry-Specific Thresholds
- **Real Estate**: ≥0.6 → scheduler, 0.35-0.6 → followup, <0.35 → offramp
- **Fitness**: ≥0.5 → scheduler, 0.3-0.5 → followup, <0.3 → offramp
- **Restaurant**: ≥0.55 → scheduler, 0.35-0.55 → followup, <0.35 → offramp
- **Hotel**: ≥0.65 → scheduler, 0.4-0.65 → followup, <0.4 → offramp

### Routing Recommendations
```python
{
    'next_agent': 'scheduler|followup|offramp',
    'reasoning': 'Detailed explanation with industry context',
    'priority': 'high|medium|low',
    'industry_type': 'Industry description'
}
```

## Improvement Potential Analysis

The system provides actionable insights for score improvement:

```python
{
    'potential': 0.150,
    'focus_areas': ['response_time', 'engagement_momentum'],
    'target_score': 0.6,
    'current_gap': 0.120
}
```

## Error Handling

The system includes comprehensive error handling:
- Graceful fallback when Redis is unavailable
- Safe defaults for missing data
- Detailed error logging for debugging
- Validation of industry types and input parameters

## Testing

Run the test suite to verify functionality:

```bash
cd backend
python3 test_enhanced_scoring_simple.py
```

## Benefits

### 🎯 More Realistic Qualification
- Thresholds based on industry standards (0.5-0.65 instead of academic 0.75)
- Industry-specific multipliers account for different sales cycles

### ⚡ Response Time Integration
- 5-minute industry standard for maximum conversion
- 10x qualification drop for poor response times
- Real-time urgency scoring

### 📈 Engagement Momentum
- Tracks touch point diversity and recency
- Values continued engagement over single interactions
- Identifies warming vs. cooling leads

### 🔄 Backward Compatibility
- Existing `calculate_lead_score()` function unchanged
- Gradual migration path for existing systems
- No breaking changes to current integrations

## Migration Guide

### For Existing Systems
1. **Immediate**: Continue using `calculate_lead_score()` - no changes needed
2. **Enhanced**: Switch to `calculate_enhanced_lead_score()` for new features
3. **Industry**: Add `industry_type` parameter for adaptive scoring
4. **Response Time**: Integrate `track_first_response()` for urgency scoring

### Configuration Updates
```python
# Old configuration
score_threshold = 0.75

# New industry-adaptive configuration
industry_configs = {
    'real_estate': {'conversion_threshold': 0.6, ...},
    'fitness': {'conversion_threshold': 0.5, ...},
    # ...
}
```

## Performance Considerations

- **Redis Dependency**: System gracefully degrades when Redis unavailable
- **Circuit Breaker**: Prevents cascade failures in response tracking
- **Caching**: Response time data cached with appropriate TTL
- **Logging**: Comprehensive logging for monitoring and debugging

## Future Enhancements

- Machine learning models for industry-specific scoring
- Real-time threshold adjustment based on conversion data
- Advanced touch point analytics and patterns
- Integration with additional data sources (CRM, marketing automation)