"""
Dynamic configuration for nurture sequences and templates.

This module provides configurable nurture sequences and message templates
that can be easily modified without code changes.
"""

import json
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

class ChannelType(Enum):
    """Communication channels for nurture sequences"""
    SMS = "sms"
    EMAIL = "email"
    IN_APP = "in_app"
    CALL = "call"

class IndustryType(Enum):
    """Supported industry types for nurture sequences"""
    REAL_ESTATE = "real_estate"
    FITNESS = "fitness"
    RESTAURANT = "restaurant"
    HOTEL = "hotel"
    DEFAULT = "default"

@dataclass
class TouchPointConfig:
    """Configuration for a single touch point"""
    day: int
    channel: str
    template_key: str
    content: Optional[str] = None
    personalization_data: Optional[Dict[str, Any]] = None
    compliance_checked: bool = False

@dataclass
class SequenceConfig:
    """Configuration for an industry-specific nurture sequence"""
    intent_threshold: float
    touch_points: List[TouchPointConfig]
    total_duration_days: int
    ab_test_enabled: bool = False

@dataclass
class TemplateConfig:
    """Configuration for a message template"""
    template: str
    personalization_fields: List[str]
    compliance_required: bool = True
    channel_specific: bool = False
    a_b_test_variants: Optional[List[str]] = None

class NurtureConfigLoader:
    """
    Loads and manages nurture sequence configurations from various sources.
    
    Supports loading from:
    - JSON configuration files
    - Environment variables
    - Database storage
    - External APIs
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or os.path.join(
            os.path.dirname(__file__), 
            'config', 
            'nurture_sequences.json'
        )
        self.sequences = {}
        self.templates = {}
        self.load_configurations()
    
    def load_configurations(self):
        """Load sequences and templates from configuration sources"""
        # Try to load from file first
        if os.path.exists(self.config_path):
            self._load_from_file()
        else:
            # Fallback to default configurations
            self._load_default_configurations()
        
        # Override with environment variables if present
        self._load_from_environment()
        
        # Load from database if available
        self._load_from_database()
    
    def _load_from_file(self):
        """Load configurations from JSON file"""
        try:
            with open(self.config_path, 'r') as f:
                config_data = json.load(f)
            
            # Load sequences
            for industry_key, industry_data in config_data.get('sequences', {}).items():
                self.sequences[industry_key] = {}
                for intent_key, sequence_data in industry_data.items():
                    touch_points = [
                        TouchPointConfig(**tp) for tp in sequence_data.get('touch_points', [])
                    ]
                    # Filter out fields that don't exist in SequenceConfig
                    filtered_data = {k: v for k, v in sequence_data.items()
                                   if k in ['intent_threshold', 'total_duration_days', 'ab_test_enabled', 'touch_points']}
                    self.sequences[industry_key][intent_key] = SequenceConfig(
                        touch_points=touch_points,
                        **filtered_data
                    )
            
            # Load templates
            for industry_key, industry_data in config_data.get('templates', {}).items():
                self.templates[industry_key] = {}
                for template_key, template_data in industry_data.items():
                    self.templates[industry_key][template_key] = TemplateConfig(**template_data)
            
            print(f"Loaded configurations from {self.config_path}")
            
        except Exception as e:
            print(f"Error loading config from file: {e}")
            self._load_default_configurations()
    
    def _load_from_environment(self):
        """Load configuration overrides from environment variables"""
        # Example: NURTURE_REAL_ESTATE_HIGH_INTENT_THRESHOLD=0.7
        for industry in IndustryType:
            for intent in ['high_intent', 'low_intent']:
                env_key = f"NURTURE_{industry.value.upper()}_{intent.upper()}_THRESHOLD"
                if env_key in os.environ:
                    if industry.value not in self.sequences:
                        self.sequences[industry.value] = {}
                    if intent not in self.sequences[industry.value]:
                        # Create default sequence if not exists
                        self.sequences[industry.value][intent] = self._get_default_sequence(industry.value, intent)
                    
                    self.sequences[industry.value][intent].intent_threshold = float(os.environ[env_key])
        
        # Template overrides from environment
        # Example: NURTURE_TEMPLATE_REAL_ESTATE_MARKET_INSIGHTS="Custom template {first_name}"
        for env_key, env_value in os.environ.items():
            if env_key.startswith('NURTURE_TEMPLATE_'):
                parts = env_key.replace('NURTURE_TEMPLATE_', '').split('_')
                if len(parts) >= 3:
                    industry = parts[0].lower()
                    template_key = '_'.join(parts[1:]).lower()
                    
                    if industry not in self.templates:
                        self.templates[industry] = {}
                    
                    self.templates[industry][template_key] = TemplateConfig(
                        template=env_value,
                        personalization_fields=self._extract_placeholders(env_value),
                        compliance_required=True
                    )
    
    def _load_from_database(self):
        """Load configurations from database (placeholder for future implementation)"""
        # TODO: Implement database loading
        # This would load from a nurture_configurations table
        pass
    
    def _load_default_configurations(self):
        """Load default hardcoded configurations as fallback"""
        self.sequences = self._get_default_sequences()
        self.templates = self._get_default_templates()
        print("Using default nurture configurations")
    
    def _get_default_sequences(self) -> Dict[str, Dict[str, SequenceConfig]]:
        """Get default sequence configurations"""
        return {
            "real_estate": {
                "high_intent": SequenceConfig(
                    intent_threshold=0.6,
                    touch_points=[
                        TouchPointConfig(1, "sms", "market_insights"),
                        TouchPointConfig(3, "email", "property_listings"),
                        TouchPointConfig(7, "sms", "neighborhood_guide"),
                        TouchPointConfig(14, "call", "consultation_booking"),
                        TouchPointConfig(21, "email", "market_update")
                    ],
                    total_duration_days=21
                ),
                "low_intent": SequenceConfig(
                    intent_threshold=0.6,
                    touch_points=[
                        TouchPointConfig(2, "sms", "budget_education"),
                        TouchPointConfig(5, "email", "market_trends"),
                        TouchPointConfig(10, "sms", "timeline_check")
                    ],
                    total_duration_days=10
                )
            },
            "fitness": {
                "high_intent": SequenceConfig(
                    intent_threshold=0.5,
                    touch_points=[
                        TouchPointConfig(1, "sms", "class_schedule"),
                        TouchPointConfig(2, "email", "facility_tour"),
                        TouchPointConfig(5, "sms", "trial_reminder"),
                        TouchPointConfig(10, "call", "membership_offer")
                    ],
                    total_duration_days=10
                )
            },
            "restaurant": {
                "high_intent": SequenceConfig(
                    intent_threshold=0.55,
                    touch_points=[
                        TouchPointConfig(1, "sms", "menu_highlights"),
                        TouchPointConfig(3, "email", "event_packages"),
                        TouchPointConfig(7, "sms", "chef_profile"),
                        TouchPointConfig(14, "call", "table_reservation")
                    ],
                    total_duration_days=14
                )
            }
        }
    
    def _get_default_templates(self) -> Dict[str, Dict[str, TemplateConfig]]:
        """Get default template configurations"""
        return {
            "real_estate": {
                "market_insights": TemplateConfig(
                    template="Hi {first_name}! Here are the latest market insights for {target_area}: {market_data}",
                    personalization_fields=["first_name", "target_area", "market_data"],
                    compliance_required=True
                ),
                "property_listings": TemplateConfig(
                    template="Hi {first_name}! We found {listing_count} new properties matching your ${budget} budget in {location}. View them here: {listing_url}",
                    personalization_fields=["first_name", "listing_count", "budget", "location", "listing_url"],
                    compliance_required=True
                ),
                "neighborhood_guide": TemplateConfig(
                    template="Hi {first_name}! Here's your neighborhood guide for {location} with top amenities: {amenities}",
                    personalization_fields=["first_name", "location", "amenities"],
                    compliance_required=True
                ),
                "consultation_booking": TemplateConfig(
                    template="Hi {first_name}! Ready to schedule your consultation? Available times: {available_times}",
                    personalization_fields=["first_name", "available_times"],
                    compliance_required=True
                ),
                "market_update": TemplateConfig(
                    template="Hi {first_name}! Market update for {location}: {update_summary} New listings: {new_listings}",
                    personalization_fields=["first_name", "location", "update_summary", "new_listings"],
                    compliance_required=True
                ),
                "budget_education": TemplateConfig(
                    template="Hi {first_name}! Let's discuss financing options for your ${budget} budget. {financing_info}",
                    personalization_fields=["first_name", "budget", "financing_info"],
                    compliance_required=True
                ),
                "market_trends": TemplateConfig(
                    template="Hi {first_name}! Market trends in {location}: {trend_data} Inventory levels: {inventory_info}",
                    personalization_fields=["first_name", "location", "trend_data", "inventory_info"],
                    compliance_required=True
                ),
                "timeline_check": TemplateConfig(
                    template="Hi {first_name}! Just checking in on your {timeline} timeline. Any updates needed?",
                    personalization_fields=["first_name", "timeline"],
                    compliance_required=True
                )
            },
            "fitness": {
                "class_schedule": TemplateConfig(
                    template="Hi {first_name}! Class schedule availability for {membership_type}: {schedule_info}",
                    personalization_fields=["first_name", "membership_type", "schedule_info"],
                    compliance_required=True
                ),
                "facility_tour": TemplateConfig(
                    template="Hi {first_name}! Ready for a facility tour? Available times: {tour_times}",
                    personalization_fields=["first_name", "tour_times"],
                    compliance_required=True
                ),
                "trial_reminder": TemplateConfig(
                    template="Hi {first_name}! Your trial class is scheduled for {trial_time}. Benefits: {trial_benefits}",
                    personalization_fields=["first_name", "trial_time", "trial_benefits"],
                    compliance_required=True
                ),
                "membership_offer": TemplateConfig(
                    template="Hi {first_name}! Special membership offer: {offer_details}. Limited time: {expiry_date}",
                    personalization_fields=["first_name", "offer_details", "expiry_date"],
                    compliance_required=True
                )
            },
            "restaurant": {
                "menu_highlights": TemplateConfig(
                    template="Hi {first_name}! Today's menu highlights: {menu_items}. Chef's special: {chef_special}",
                    personalization_fields=["first_name", "menu_items", "chef_special"],
                    compliance_required=True
                ),
                "event_packages": TemplateConfig(
                    template="Hi {first_name}! Event packages for {party_size}: {package_options}. Pricing: {pricing_info}",
                    personalization_fields=["first_name", "party_size", "package_options", "pricing_info"],
                    compliance_required=True
                ),
                "chef_profile": TemplateConfig(
                    template="Hi {first_name}! Meet our chef {chef_name} - {chef_background}. Today's cuisine: {cuisine_type}",
                    personalization_fields=["first_name", "chef_name", "chef_background", "cuisine_type"],
                    compliance_required=True
                ),
                "table_reservation": TemplateConfig(
                    template="Hi {first_name}! Table reservation available for {party_size} on {date}. Special: {special_offer}",
                    personalization_fields=["first_name", "party_size", "date", "special_offer"],
                    compliance_required=True
                )
            }
        }
    
    def _get_default_sequence(self, industry: str, intent: str) -> SequenceConfig:
        """Get default sequence for industry and intent"""
        default_sequences = self._get_default_sequences()
        if industry in default_sequences and intent in default_sequences[industry]:
            return default_sequences[industry][intent]
        
        # Return minimal default sequence
        return SequenceConfig(
            intent_threshold=0.5,
            touch_points=[TouchPointConfig(1, "sms", "default_touch")],
            total_duration_days=1
        )
    
    def _extract_placeholders(self, template: str) -> List[str]:
        """Extract placeholder variables from template string"""
        import re
        return re.findall(r'\{(\w+)\}', template)
    
    def get_sequence(self, industry: str, intent: str) -> Optional[SequenceConfig]:
        """Get sequence configuration for industry and intent"""
        return self.sequences.get(industry, {}).get(intent)
    
    def get_template(self, industry: str, template_key: str) -> Optional[TemplateConfig]:
        """Get template configuration for industry and template key"""
        return self.templates.get(industry, {}).get(template_key)
    
    def update_sequence(self, industry: str, intent: str, sequence: SequenceConfig):
        """Update sequence configuration"""
        if industry not in self.sequences:
            self.sequences[industry] = {}
        self.sequences[industry][intent] = sequence
    
    def update_template(self, industry: str, template_key: str, template: TemplateConfig):
        """Update template configuration"""
        if industry not in self.templates:
            self.templates[industry] = {}
        self.templates[industry][template_key] = template
    
    def save_configurations(self, file_path: Optional[str] = None):
        """Save current configurations to JSON file"""
        save_path = file_path or self.config_path
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        config_data = {
            "sequences": {},
            "templates": {}
        }
        
        # Convert sequences to dict
        for industry, industry_data in self.sequences.items():
            config_data["sequences"][industry] = {}
            for intent, sequence in industry_data.items():
                config_data["sequences"][industry][intent] = {
                    "intent_threshold": sequence.intent_threshold,
                    "total_duration_days": sequence.total_duration_days,
                    "ab_test_enabled": sequence.ab_test_enabled,
                    "touch_points": [
                        {
                            "day": tp.day,
                            "channel": tp.channel,
                            "template_key": tp.template_key,
                            "content": tp.content,
                            "personalization_data": tp.personalization_data,
                            "compliance_checked": tp.compliance_checked
                        }
                        for tp in sequence.touch_points
                    ]
                }
        
        # Convert templates to dict
        for industry, industry_data in self.templates.items():
            config_data["templates"][industry] = {}
            for template_key, template in industry_data.items():
                config_data["templates"][industry][template_key] = {
                    "template": template.template,
                    "personalization_fields": template.personalization_fields,
                    "compliance_required": template.compliance_required,
                    "channel_specific": template.channel_specific,
                    "a_b_test_variants": template.a_b_test_variants
                }
        
        with open(save_path, 'w') as f:
            json.dump(config_data, f, indent=2)
        
        print(f"Saved configurations to {save_path}")

# Global configuration loader
nurture_config_loader = NurtureConfigLoader()