
# Industry Configuration System

The Industry Configuration System provides dynamic, multi-industry support for the lead qualification platform. It enables runtime configuration management, automatic industry detection, and industry-specific business logic without requiring code changes.

## Overview

The system supports four primary industries:
- **Real Estate**: Property sales, rentals, and investment
- **Fitness**: Gym memberships, personal training, and classes
- **Restaurant**: Reservations, events, and dining experiences
- **Hotel**: Accommodations, bookings, and hospitality services

## Features

### 1. Industry-Specific Configurations
Each industry has tailored configurations for:
- Conversion and nurture thresholds
- Scoring weights for qualification factors
- Value propositions and compliance modules
- Nurture sequence cadences and durations
- Booking triggers and windows
- Channel preferences and fallback orders

### 2. Dynamic Industry Detection
Automatic industry identification based on:
- Keyword analysis from message content
- Context analysis from extracted information
- Conversation history pattern recognition
- Fallback to default industry when uncertain

### 3. Runtime Configuration Management
- Update configurations without code deployment
- Validate configuration integrity
- Save and load configurations from files
- Environment variable overrides for deployment flexibility

### 4. Integration Points
- Enhanced lead scoring with adaptive thresholds
- Industry-appropriate nurture sequences
- Smart booking engine triggers
- Multi-channel compliance management

## Quick Start

### Basic Usage

```python
from config.industry_configs import get_industry_config, detect_industry

# Get industry-specific configuration
config = get_industry_config("real_estate")
print(f"Conversion threshold: {config.conversion_threshold}")
print(f"Scoring weights: {config.scoring_weights}")

# Auto-detect industry from message
message = "I'm looking for a 3-bedroom house in downtown"
extracted_info = {"property_type": "house", "bedrooms": 3}
industry = detect_industry(message, extracted_info)
print(f"Detected industry: {industry}")
```

### Configuration Management

```python
from config.industry_configs import get_industry_config_manager

manager = get_industry_config_manager()

# Update configuration at runtime
updates = {
    "conversion_threshold": 0.75,
    "required_touches": 10
}
success = manager.update_config("real_estate", updates)

# Save configurations to file
manager.save_configs("custom_configs.json")

# Reset to defaults
manager.reset_to_defaults("real_estate")
```

## Industry Configurations

### Real Estate

**Thresholds:**
- Conversion: 0.6
- Nurture: 0.35
- Required Touches: 8

**Scoring Weights:**
- Budget: 25%
- Location: 20%
- Timeline: 15%
- Property Type: 10%
- Completeness: 15%
- Engagement: 15%

**Value Propositions:**
- Market insights
- Property recommendations
- Investment analysis

**Compliance Modules:**
- Fair housing
- Disclosure requirements

### Fitness

**Thresholds:**
- Conversion: 0.5
- Nurture: 0.3
- Required Touches: 6

**Scoring Weights:**
- Goals: 25%
- Timeline: 20%
- Budget: 15%
- Experience: 15%
- Availability: 15%
- Engagement: 10%

**Value Propositions:**
- Class schedules
- Facility tours
- Progress tracking

**Compliance Modules:**
- Health safety
- Liability waivers

### Restaurant

**Thresholds:**
- Conversion: 0.55
- Nurture: 0.35
- Required Touches: 7

**Scoring Weights:**
- Party Size: 25%
- Occasion: 20%
- Budget: 15%
- Cuisine: 15%
- Timing: 15%
- Engagement: 10%

**Value Propositions:**
- Menu highlights
- Chef profile
- Event packages

**Compliance Modules:**
- Food safety
- Capacity limits

### Hotel

**Thresholds:**
- Conversion: 0.65
- Nurture: 0.4
- Required Touches: 10

**Scoring Weights:**
- Room Type: 25%
- Dates: 20%
- Budget: 15%
- Amenities: 15%
- Group Size: 15%
- Engagement: 10%

**Value Propositions:**
- Room features
- Amenities
- Event packages

**Compliance Modules:**
- Hospitality standards
- Accessibility

## API Reference

### IndustryConfigManager

The main class for managing industry configurations.

#### Methods

##### `get_config(industry_type: str) -> IndustryConfig`
Get configuration for a specific industry.

**Parameters:**
- `industry_type`: Industry type identifier

**Returns:**
- `IndustryConfig` object

##### `detect_industry_type(message: str, extracted_info: Dict, conversation_history: List) -> str`
Auto-detect industry type from message content and context.

**Parameters:**
- `message`: Current message content
- `extracted_info`: Extracted information from message
- `conversation_history`: Previous conversation messages (optional)

**Returns:**
- Detected industry type string

##### `update_config(industry_type: str, updates: Dict) -> bool`
Update configuration for a specific industry at runtime.

**Parameters:**
- `industry_type`: Industry type identifier
- `updates`: Dictionary of fields to update

**Returns:**
- `True` if update successful, `False` otherwise

##### `validate_config(industry_type: str, config: Dict) -> bool`
Validate configuration integrity.

**Parameters:**
- `industry_type`: Industry type identifier
- `config`: Configuration dictionary to validate

**Returns:**
- `True` if valid, `False` otherwise

##### `get_all_industries() -> List[str]`
Get list of all supported industries.

**Returns:**
- List of industry type identifiers

##### `save_configs(file_path: Optional[str]) -> bool`
Save current runtime configurations to file.

**Parameters:**
- `file_path`: Optional file path, uses default if not provided

**Returns:**
- `True` if save successful, `False` otherwise

##### `reset_to_defaults(industry_type: Optional[str]) -> None`
Reset configuration(s) to defaults.

**Parameters:**
- `industry_type`: Specific industry to reset, or `None` for all

### IndustryConfig

Dataclass containing industry-specific configuration.

#### Fields

- `conversion_threshold`: Score threshold for conversion readiness
- `nurture_threshold`: Score threshold for nurture sequence entry
- `required_touches`: Number of touches before conversion consideration
- `scoring_weights`: Dictionary of factor weights for lead scoring
- `value_props`: List of industry-specific value propositions
- `compliance_modules`: List of required compliance modules
- `nurture_cadence_days`: List of days for nurture touchpoints
- `max_nurture_duration_days`: Maximum duration for nurture sequences
- `booking_triggers`: List of triggers that initiate booking flow
- `booking_windows_days`: Time window for booking completion
- `preferred_channels`: Preferred communication channels
- `channel_fallback_order`: Fallback channel order

### Global Functions

##### `get_industry_config_manager() -> IndustryConfigManager`
Get the global industry configuration manager instance.

##### `get_industry_config(industry_type: str) -> IndustryConfig`
Get configuration for a specific industry.

##### `detect_industry(message: str, extracted_info: Dict, conversation_history: Optional[List]) -> str`
Detect industry type from message and context.

## Environment Variables

Configuration can be overridden using environment variables with the pattern:
`INDUSTRY_{INDUSTRY}_{FIELD}`

**Examples:**
```bash
# Override real estate conversion threshold
INDUSTRY_REAL_ESTATE_CONVERSION_THRESHOLD=0.75

# Override fitness required touches
INDUSTRY_FITNESS_REQUIRED_TOUCHES=12

# Override restaurant value props (JSON format)
INDUSTRY_RESTAURANT_VALUE_PROPS='["special_menu", "private_dining", "catering"]'

# Override hotel booking windows
INDUSTRY_HOTEL_BOOKING_WINDOWS_DAYS=90
```

## File-Based Configuration

Configurations can be loaded from JSON files:

```json
{
  "real_estate": {
    "conversion_threshold": 0.7,
    "required_touches": 9,
    "scoring_weights": {
      "budget": 0.30,
      "location": 0.25,
      "timeline": 0.15,
      "property_type": 0.10,
      "completeness": 0.10,
      "engagement": 0.10
    }
  },
  "fitness": {
    "conversion_threshold": 0.45,
    "nurture_threshold": 0.25,
    "required_touches": 5
  }
}
```

Specify custom config file path:
```python
manager = IndustryConfigManager("path/to/custom_configs.json")
```

Or via environment variable:
```bash
INDUSTRY_CONFIG_FILE=path/to/custom_configs.json
```

## Integration Examples

### Lead Scoring Integration

```python
from config.industry_configs import get_industry_config

def calculate_lead_score(industry: str, lead_data: Dict[str, float]) -> float:
    config = get_industry_config(industry)
    
    score = sum(
        lead_data[factor] * weight
        for factor, weight in config.scoring_weights.items()
    )
    
    return score

def determine_qualification_status(industry: str, score: float) -> str:
    config = get_industry_config(industry)
    
    if score >= config.conversion_threshold:
        return "Ready for Conversion"
    elif score >= config.nurture_threshold:
        return "Nurture Required"
    else:
        return "Not Qualified"
```

### Nurture Sequence Integration

```python
from config.industry_configs import get_industry_config

def get_nurture_schedule(industry: str) -> List[int]:
    config = get_industry_config(industry)
    return config.nurture_cadence_days

def should_continue_nurturing(industry: str, touches: int, days_active: int) -> bool:
    config = get_industry_config(industry)
    
    return (touches < config.required_touches and
            days_active < config.max_nurture_duration_days)
```

### Booking Integration

```python
from config.industry_configs import get_industry_config

def should_trigger_booking(industry: str, trigger: str) -> bool:
    config = get_industry_config(industry)
    return trigger in config.booking_triggers

def get_booking_window(industry: str) -> int:
    config = get_industry_config(industry)
    return config.booking_windows_days
```

### Multi-Channel Integration

```python
from config.industry_configs import get_industry_config

def select_communication_channel(industry: str, available_channels: List[str]) -> str:
    config = get_industry_config(industry)
    
    # Try preferred channels first
    for channel in config.preferred_channels:
        if channel in available_channels:
            return channel
    
    # Fall back to fallback order
    for channel in config.channel_fallback_order:
        if channel in available_channels:
            return channel
    
    return None  # No suitable channel available
```

## Testing

Run the test suite:

```bash
pytest backend/tests/test_industry_configs.py -v
```

Run integration examples:

```bash
python backend/examples/industry_configs_integration.py
```

## Best Practices

1. **Configuration Validation**: Always validate configurations before applying updates
2. **Environment Overrides**: Use environment variables for deployment-specific settings
3. **File Backups**: Save configurations to files for version control and disaster recovery
4. **Industry Detection**: Provide sufficient context for accurate industry detection
5. **Threshold Tuning**: Regularly review and adjust thresholds based on performance data
6. **Compliance**: Ensure compliance modules are up-to-date for each industry

## Troubleshooting

### Common Issues

**Industry Detection Fails to Default**
- Check message content for industry-specific keywords
- Verify extracted_info contains relevant fields
- Review conversation history for context patterns

**Configuration Updates Not Applied**
- Validate configuration structure and values
- Check for type mismatches in field values
- Ensure scoring weights sum to 1.0

**Environment Overrides Not Working**
- Verify environment variable naming pattern
- Check for correct data types (JSON for arrays/objects)
- Restart application to pick up new environment variables

**File-Based Configuration Not Loading**
- Verify file path and permissions
- Check JSON syntax and structure
- Ensure required fields are present

### Debug Logging

Enable debug logging to troubleshoot issues:

```python
import logging
logging.getLogger('config.industry_configs').setLevel(logging.DEBUG)
```

## Future Enhancements

Planned improvements to the industry configuration system:

1. **Machine Learning Detection**: Enhanced industry detection using ML models
2. **A/B Testing Framework**: Built-in support for configuration A/B testing
3. **Performance Analytics**: Configuration performance tracking and optimization
4. **Dynamic Threshold Adjustment**: Automatic threshold tuning based on conversion data
5. **Industry Templates**: Pre-built templates for new industry onboarding
6. **Configuration Versioning**: Version control for configuration changes
7. **Rollback Capabilities**: Quick rollback to previous configuration versions
8. **Multi-Tenant Support**: Separate configurations per tenant/client