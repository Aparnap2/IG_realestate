"""
Multi-Industry Configuration System

This module provides dynamic industry configuration management for the lead qualification system,
supporting real estate, fitness, restaurant, and hotel industries with configurable thresholds,
scoring weights, and business logic.
"""

import os
import json
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class IndustryType(Enum):
    """Supported industry types."""
    REAL_ESTATE = "real_estate"
    FITNESS = "fitness"
    RESTAURANT = "restaurant"
    HOTEL = "hotel"


@dataclass
class IndustryConfig:
    """Configuration for a specific industry."""
    # Thresholds
    conversion_threshold: float
    nurture_threshold: float
    required_touches: int
    
    # Scoring weights
    scoring_weights: Dict[str, float]
    
    # Value propositions
    value_props: List[str]
    
    # Compliance modules
    compliance_modules: List[str]
    
    # Nurture sequence configuration
    nurture_cadence_days: List[int]
    max_nurture_duration_days: int
    
    # Booking configuration
    booking_triggers: List[str]
    booking_windows_days: int
    
    # Channel preferences
    preferred_channels: List[str]
    channel_fallback_order: List[str]


class IndustryConfigManager:
    """
    Manages industry-specific configurations with runtime updates and environment overrides.
    """
    
    def __init__(self, config_file_path: Optional[str] = None):
        """
        Initialize the industry configuration manager.
        
        Args:
            config_file_path: Optional path to JSON configuration file
        """
        self.config_file_path = config_file_path or os.getenv(
            "INDUSTRY_CONFIG_FILE", 
            "backend/config/industry_configs.json"
        )
        
        # Default industry configurations
        self._default_configs = self._load_default_configs()
        
        # Runtime configurations (can be updated)
        self._runtime_configs = {}
        
        # Load custom configurations from file if exists
        self._load_file_configs()
        
        # Apply environment variable overrides
        self._apply_env_overrides()
        
        logger.info(f"IndustryConfigManager initialized with {len(self._default_configs)} industries")
    
    def _load_default_configs(self) -> Dict[str, IndustryConfig]:
        """Load default industry configurations."""
        return {
            IndustryType.REAL_ESTATE.value: IndustryConfig(
                conversion_threshold=0.6,
                nurture_threshold=0.35,
                required_touches=8,
                scoring_weights={
                    "budget": 0.25,
                    "location": 0.20,
                    "timeline": 0.15,
                    "property_type": 0.10,
                    "completeness": 0.15,
                    "engagement": 0.15
                },
                value_props=[
                    "market_insights",
                    "property_recommendations",
                    "investment_analysis"
                ],
                compliance_modules=[
                    "fair_housing",
                    "disclosure_requirements"
                ],
                nurture_cadence_days=[1, 3, 7, 14, 21, 28, 35, 42],
                max_nurture_duration_days=60,
                booking_triggers=[
                    "high_score",
                    "specific_property_inquiry",
                    "financing_discussion"
                ],
                booking_windows_days=30,
                preferred_channels=["email", "phone", "sms"],
                channel_fallback_order=["email", "sms", "phone"]
            ),
            
            IndustryType.FITNESS.value: IndustryConfig(
                conversion_threshold=0.5,
                nurture_threshold=0.3,
                required_touches=6,
                scoring_weights={
                    "goals": 0.25,
                    "timeline": 0.20,
                    "budget": 0.15,
                    "experience": 0.15,
                    "availability": 0.15,
                    "engagement": 0.10
                },
                value_props=[
                    "class_schedules",
                    "facility_tours",
                    "progress_tracking"
                ],
                compliance_modules=[
                    "health_safety",
                    "liability_waivers"
                ],
                nurture_cadence_days=[1, 3, 7, 14, 21, 28],
                max_nurture_duration_days=45,
                booking_triggers=[
                    "tour_request",
                    "trial_class_interest",
                    "membership_inquiry"
                ],
                booking_windows_days=14,
                preferred_channels=["sms", "email", "phone"],
                channel_fallback_order=["sms", "email", "phone"]
            ),
            
            IndustryType.RESTAURANT.value: IndustryConfig(
                conversion_threshold=0.55,
                nurture_threshold=0.35,
                required_touches=7,
                scoring_weights={
                    "party_size": 0.25,
                    "occasion": 0.20,
                    "budget": 0.15,
                    "cuisine": 0.15,
                    "timing": 0.15,
                    "engagement": 0.10
                },
                value_props=[
                    "menu_highlights",
                    "chef_profile",
                    "event_packages"
                ],
                compliance_modules=[
                    "food_safety",
                    "capacity_limits"
                ],
                nurture_cadence_days=[1, 3, 7, 14, 21],
                max_nurture_duration_days=30,
                booking_triggers=[
                    "reservation_request",
                    "event_inquiry",
                    "large_party"
                ],
                booking_windows_days=7,
                preferred_channels=["sms", "email", "phone"],
                channel_fallback_order=["sms", "phone", "email"]
            ),
            
            IndustryType.HOTEL.value: IndustryConfig(
                conversion_threshold=0.65,
                nurture_threshold=0.4,
                required_touches=10,
                scoring_weights={
                    "room_type": 0.25,
                    "dates": 0.20,
                    "budget": 0.15,
                    "amenities": 0.15,
                    "group_size": 0.15,
                    "engagement": 0.10
                },
                value_props=[
                    "room_features",
                    "amenities",
                    "event_packages"
                ],
                compliance_modules=[
                    "hospitality_standards",
                    "accessibility"
                ],
                nurture_cadence_days=[1, 3, 7, 14, 21, 28, 35, 42, 49, 56],
                max_nurture_duration_days=90,
                booking_triggers=[
                    "room_inquiry",
                    "date_availability",
                    "group_booking"
                ],
                booking_windows_days=60,
                preferred_channels=["email", "phone", "sms"],
                channel_fallback_order=["email", "phone", "sms"]
            )
        }
    
    def _load_file_configs(self) -> None:
        """Load configurations from JSON file if exists."""
        try:
            if os.path.exists(self.config_file_path):
                with open(self.config_file_path, 'r') as f:
                    file_configs = json.load(f)
                
                for industry_name, config_data in file_configs.items():
                    if industry_name in self._default_configs:
                        # Merge with default config
                        default_config = asdict(self._default_configs[industry_name])
                        merged_config = {**default_config, **config_data}
                        self._runtime_configs[industry_name] = IndustryConfig(**merged_config)
                        logger.info(f"Loaded custom config for {industry_name}")
        except Exception as e:
            logger.warning(f"Failed to load file configs: {e}")
    
    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides."""
        env_pattern = re.compile(r'INDUSTRY_(?P<industry>[A-Z_]+)_(?P<field>[A-Z_]+)')
        
        for env_var, value in os.environ.items():
            match = env_pattern.match(env_var)
            if match:
                industry = match.group('industry').lower().replace('_', '_')
                field = match.group('field').lower()
                
                if industry in self._default_configs:
                    config = self.get_config(industry)
                    
                    # Handle different field types
                    if hasattr(config, field):
                        current_value = getattr(config, field)
                        
                        # Type conversion based on current value type
                        if isinstance(current_value, bool):
                            value = value.lower() in ('1', 'true', 'yes')
                        elif isinstance(current_value, (int, float)):
                            value = type(current_value)(value)
                        elif isinstance(current_value, list):
                            value = json.loads(value) if value.startswith('[') else value.split(',')
                        elif isinstance(current_value, dict):
                            value = json.loads(value)
                        
                        # Update runtime config
                        if industry not in self._runtime_configs:
                            self._runtime_configs[industry] = config
                        
                        setattr(self._runtime_configs[industry], field, value)
                        logger.info(f"Applied env override: {env_var} for {industry}")
    
    def get_config(self, industry_type: str) -> IndustryConfig:
        """
        Get configuration for a specific industry.
        
        Args:
            industry_type: Industry type identifier
            
        Returns:
            IndustryConfig object
        """
        # Check runtime config first
        if industry_type in self._runtime_configs:
            return self._runtime_configs[industry_type]
        
        # Fall back to default config
        if industry_type in self._default_configs:
            return self._default_configs[industry_type]
        
        # Default to real estate if unknown
        logger.warning(f"Unknown industry type: {industry_type}, defaulting to real_estate")
        return self._default_configs[IndustryType.REAL_ESTATE.value]
    
    def detect_industry_type(
        self, 
        message: str, 
        extracted_info: Dict[str, Any], 
        conversation_history: Optional[List[Dict]] = None
    ) -> str:
        """
        Auto-detect industry type from message content and context.
        
        Args:
            message: Current message content
            extracted_info: Extracted information from message
            conversation_history: Previous conversation messages
            
        Returns:
            Detected industry type
        """
        # Industry keyword mappings
        industry_keywords = {
            IndustryType.REAL_ESTATE.value: [
                'property', 'house', 'home', 'real estate', 'apartment', 'condo',
                'mortgage', 'rent', 'buy', 'sell', 'listing', 'neighborhood',
                'bedroom', 'bathroom', 'square feet', 'investment property'
            ],
            IndustryType.FITNESS.value: [
                'gym', 'fitness', 'workout', 'personal trainer', 'class',
                'membership', 'exercise', 'training', 'yoga', 'pilates',
                'cardio', 'weights', 'health', 'nutrition'
            ],
            IndustryType.RESTAURANT.value: [
                'restaurant', 'reservation', 'table', 'menu', 'dining',
                'cuisine', 'chef', 'booking', 'party size', 'event',
                'catering', 'private dining', 'bar', 'lounge'
            ],
            IndustryType.HOTEL.value: [
                'hotel', 'room', 'booking', 'reservation', 'accommodation',
                'check-in', 'check-out', 'amenities', 'suite', 'lobby',
                'concierge', 'vacation', 'travel', 'stay'
            ]
        }
        
        # Convert message to lowercase for matching
        message_lower = message.lower()
        
        # Score each industry based on keyword matches
        industry_scores = {}
        for industry, keywords in industry_keywords.items():
            score = 0
            for keyword in keywords:
                if keyword in message_lower:
                    score += 1
            industry_scores[industry] = score
        
        # Analyze extracted info for industry-specific fields
        if extracted_info:
            if any(key in extracted_info for key in ['property_type', 'bedrooms', 'location']):
                industry_scores[IndustryType.REAL_ESTATE.value] += 2
            elif any(key in extracted_info for key in ['fitness_goals', 'experience_level']):
                industry_scores[IndustryType.FITNESS.value] += 2
            elif any(key in extracted_info for key in ['party_size', 'cuisine_preference']):
                industry_scores[IndustryType.RESTAURANT.value] += 2
            elif any(key in extracted_info for key in ['room_type', 'check_in', 'check_out']):
                industry_scores[IndustryType.HOTEL.value] += 2
        
        # Analyze conversation history for patterns
        if conversation_history:
            history_text = ' '.join([msg.get('content', '') for msg in conversation_history[-5:]]).lower()
            for industry, keywords in industry_keywords.items():
                for keyword in keywords:
                    if keyword in history_text:
                        industry_scores[industry] += 0.5
        
        # Find industry with highest score
        if industry_scores:
            best_industry = max(industry_scores, key=industry_scores.get)
            if industry_scores[best_industry] > 0:
                logger.info(f"Detected industry: {best_industry} (score: {industry_scores[best_industry]})")
                return best_industry
        
        # Default to real estate if no clear match
        logger.info("No clear industry detected, defaulting to real_estate")
        return IndustryType.REAL_ESTATE.value
    
    def update_config(self, industry_type: str, updates: Dict[str, Any]) -> bool:
        """
        Update configuration for a specific industry at runtime.
        
        Args:
            industry_type: Industry type identifier
            updates: Dictionary of fields to update
            
        Returns:
            True if update successful, False otherwise
        """
        try:
            # Get current config
            current_config = self.get_config(industry_type)
            
            # Create updated config
            current_dict = asdict(current_config)
            updated_dict = {**current_dict, **updates}
            
            # Validate the updated config
            if self.validate_config(industry_type, updated_dict):
                # Update runtime config
                self._runtime_configs[industry_type] = IndustryConfig(**updated_dict)
                logger.info(f"Updated config for {industry_type}: {updates}")
                return True
            else:
                logger.error(f"Invalid config update for {industry_type}: {updates}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to update config for {industry_type}: {e}")
            return False
    
    def validate_config(self, industry_type: str, config: Dict[str, Any]) -> bool:
        """
        Validate configuration integrity.
        
        Args:
            industry_type: Industry type identifier
            config: Configuration dictionary to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Required fields
            required_fields = [
                'conversion_threshold', 'nurture_threshold', 'required_touches',
                'scoring_weights', 'value_props', 'compliance_modules',
                'nurture_cadence_days', 'max_nurture_duration_days',
                'booking_triggers', 'booking_windows_days',
                'preferred_channels', 'channel_fallback_order'
            ]
            
            for field in required_fields:
                if field not in config:
                    logger.error(f"Missing required field: {field}")
                    return False
            
            # Validate thresholds
            if not (0 <= config['conversion_threshold'] <= 1):
                logger.error("conversion_threshold must be between 0 and 1")
                return False
            
            if not (0 <= config['nurture_threshold'] <= 1):
                logger.error("nurture_threshold must be between 0 and 1")
                return False
            
            if config['nurture_threshold'] >= config['conversion_threshold']:
                logger.error("nurture_threshold must be less than conversion_threshold")
                return False
            
            # Validate scoring weights sum to 1.0
            scoring_weights = config['scoring_weights']
            if not abs(sum(scoring_weights.values()) - 1.0) < 0.01:
                logger.error("scoring_weights must sum to 1.0")
                return False
            
            # Validate required_touches is positive
            if config['required_touches'] <= 0:
                logger.error("required_touches must be positive")
                return False
            
            # Validate lists are not empty
            list_fields = [
                'value_props', 'compliance_modules', 'nurture_cadence_days',
                'booking_triggers', 'preferred_channels', 'channel_fallback_order'
            ]
            
            for field in list_fields:
                if not config[field] or len(config[field]) == 0:
                    logger.error(f"{field} cannot be empty")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Config validation error: {e}")
            return False
    
    def get_all_industries(self) -> List[str]:
        """
        Get list of all supported industries.
        
        Returns:
            List of industry type identifiers
        """
        return list(self._default_configs.keys())
    
    def save_configs(self, file_path: Optional[str] = None) -> bool:
        """
        Save current runtime configurations to file.
        
        Args:
            file_path: Optional file path, uses default if not provided
            
        Returns:
            True if save successful, False otherwise
        """
        try:
            save_path = file_path or self.config_file_path
            
            # Prepare configs for serialization
            configs_to_save = {}
            for industry, config in self._runtime_configs.items():
                configs_to_save[industry] = asdict(config)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            # Save to file
            with open(save_path, 'w') as f:
                json.dump(configs_to_save, f, indent=2)
            
            logger.info(f"Saved configs to {save_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save configs: {e}")
            return False
    
    def reset_to_defaults(self, industry_type: Optional[str] = None) -> None:
        """
        Reset configuration(s) to defaults.
        
        Args:
            industry_type: Specific industry to reset, or None for all
        """
        if industry_type:
            if industry_type in self._runtime_configs:
                del self._runtime_configs[industry_type]
                logger.info(f"Reset {industry_type} to defaults")
        else:
            self._runtime_configs.clear()
            logger.info("Reset all industries to defaults")


# Global instance
_config_manager: Optional[IndustryConfigManager] = None


def get_industry_config_manager() -> IndustryConfigManager:
    """Get the global industry configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = IndustryConfigManager()
    return _config_manager


def get_industry_config(industry_type: str) -> IndustryConfig:
    """Get configuration for a specific industry."""
    return get_industry_config_manager().get_config(industry_type)


def detect_industry(
    message: str, 
    extracted_info: Dict[str, Any], 
    conversation_history: Optional[List[Dict]] = None
) -> str:
    """Detect industry type from message and context."""
    return get_industry_config_manager().detect_industry_type(
        message, extracted_info, conversation_history
    )