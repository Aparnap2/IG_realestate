"""
Configuration Management for Vertical Real Estate AI Platform

Centralized configuration with environment-specific settings,
security best practices, and feature flags.
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    """Application settings with validation and type hints."""
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_VERSION: str = "v1"
    
    # Database (Supabase)
    SUPABASE_URL: str
    SUPABASE_KEY: str
    DATABASE_URL: Optional[str] = None  # For direct PostgreSQL access if needed
    
    # Redis (State & Caching)
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0
    
    # LLM Configuration
    OPENROUTER_API_KEY: str
    LLM_MODEL: str = "anthropic/claude-3.5-sonnet"
    LLM_TEMPERATURE: float = 0.3
    LLM_MAX_TOKENS: int = 4000
    LLM_TIMEOUT: int = 30
    
    # Instagram Graph API
    INSTAGRAM_PAGE_ACCESS_TOKEN: str
    INSTAGRAM_VERIFY_TOKEN: str
    INSTAGRAM_APP_SECRET: str
    INSTAGRAM_PAGE_ID: Optional[str] = None
    
    # Google Services
    GOOGLE_CALENDAR_CREDENTIALS_JSON: Optional[str] = None
    GOOGLE_MAPS_API_KEY: Optional[str] = None
    GOOGLE_OAUTH_CLIENT_ID: Optional[str] = None
    GOOGLE_OAUTH_CLIENT_SECRET: Optional[str] = None
    
    # HubSpot CRM
    HUBSPOT_API_KEY: Optional[str] = None
    HUBSPOT_PORTAL_ID: Optional[str] = None
    
    # Neo4j (Temporal Knowledge Graph)
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USERNAME: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    NEO4J_DATABASE: str = "neo4j"
    
    # Observability
    SENTRY_DSN: Optional[str] = None
    LANGFUSE_PUBLIC_KEY: Optional[str] = None
    LANGFUSE_SECRET_KEY: Optional[str] = None
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    AUDIT_SALT: str = "audit-salt-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_BURST: int = 10
    
    # Feature Flags
    ENABLE_ROUTER_AGENT: bool = True
    ENABLE_TEMPORAL_GRAPH: bool = True
    ENABLE_COMPLIANCE_CHECKS: bool = True
    ENABLE_REAL_INSTAGRAM_API: bool = False  # Set to True when ready
    ENABLE_GOOGLE_CALENDAR: bool = False     # Set to True when configured
    ENABLE_HUBSPOT_SYNC: bool = False        # Set to True when configured
    ENABLE_AUDIT_LOGGING: bool = True
    ENABLE_FAIR_HOUSING_LLM: bool = True     # Use LLM for fair housing checks
    
    # Business Logic
    HIGH_VALUE_LEAD_THRESHOLD: int = 500000  # Budget threshold for high-value leads
    QUALIFICATION_SCORE_THRESHOLD: float = 0.7  # Minimum score for scheduling
    MAX_PROPERTIES_PER_QUERY: int = 50
    CACHE_TTL_SECONDS: int = 3600  # 1 hour default cache
    
    # Compliance
    GDPR_RETENTION_DAYS: int = 2555  # 7 years
    TCPA_CONSENT_EXPIRY_DAYS: int = 547  # 18 months
    FAIR_HOUSING_STRICT_MODE: bool = True
    
    # Performance
    MAX_CONCURRENT_AGENTS: int = 10
    AGENT_TIMEOUT_SECONDS: int = 30
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 30
    
    # Monitoring
    HEALTH_CHECK_INTERVAL: int = 60  # seconds
    METRICS_RETENTION_DAYS: int = 90
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra environment variables

class DevelopmentSettings(Settings):
    """Development-specific settings."""
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"
    ENABLE_REAL_INSTAGRAM_API: bool = False
    FAIR_HOUSING_STRICT_MODE: bool = False  # More lenient for testing

class ProductionSettings(Settings):
    """Production-specific settings."""
    DEBUG: bool = False
    LOG_LEVEL: str = "WARNING"
    ENABLE_REAL_INSTAGRAM_API: bool = True
    FAIR_HOUSING_STRICT_MODE: bool = True
    
    # Production security
    SECRET_KEY: str  # Must be set in environment
    AUDIT_SALT: str  # Must be set in environment
    
    # Production performance
    MAX_CONCURRENT_AGENTS: int = 50
    DB_POOL_SIZE: int = 50
    DB_MAX_OVERFLOW: int = 100

class TestingSettings(Settings):
    """Testing-specific settings."""
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"
    
    # Use test databases
    SUPABASE_URL: str = "http://localhost:54321"
    REDIS_URL: str = "redis://localhost:6380"
    NEO4J_URI: str = "bolt://localhost:7688"
    
    # Disable external APIs in tests
    ENABLE_REAL_INSTAGRAM_API: bool = False
    ENABLE_GOOGLE_CALENDAR: bool = False
    ENABLE_HUBSPOT_SYNC: bool = False
    
    # Fast timeouts for tests
    AGENT_TIMEOUT_SECONDS: int = 5
    LLM_TIMEOUT: int = 10

@lru_cache()
def get_settings() -> Settings:
    """
    Get application settings based on environment.
    
    Returns appropriate settings class based on ENVIRONMENT variable.
    """
    environment = os.getenv("ENVIRONMENT", "development").lower()
    
    if environment == "production":
        return ProductionSettings()
    elif environment == "testing":
        return TestingSettings()
    else:
        return DevelopmentSettings()

# Convenience function for common use
settings = get_settings()

# Validation functions
def validate_instagram_config() -> bool:
    """Validate Instagram API configuration."""
    required_fields = [
        settings.INSTAGRAM_PAGE_ACCESS_TOKEN,
        settings.INSTAGRAM_VERIFY_TOKEN,
        settings.INSTAGRAM_APP_SECRET
    ]
    return all(field for field in required_fields)

def validate_google_config() -> bool:
    """Validate Google services configuration."""
    return bool(settings.GOOGLE_CALENDAR_CREDENTIALS_JSON)

def validate_hubspot_config() -> bool:
    """Validate HubSpot configuration."""
    return bool(settings.HUBSPOT_API_KEY)

def validate_neo4j_config() -> bool:
    """Validate Neo4j configuration."""
    required_fields = [
        settings.NEO4J_URI,
        settings.NEO4J_USERNAME,
        settings.NEO4J_PASSWORD
    ]
    return all(field for field in required_fields)

def get_database_url() -> str:
    """Get database URL for SQLAlchemy if needed."""
    if settings.DATABASE_URL:
        return settings.DATABASE_URL
    
    # Convert Supabase URL to PostgreSQL URL if needed
    # This is a simplified conversion - adjust based on your Supabase setup
    return f"postgresql://postgres:[password]@[host]:5432/postgres"

def get_redis_url() -> str:
    """Get Redis URL with authentication if configured."""
    if settings.REDIS_PASSWORD:
        # Parse existing URL and add password
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(settings.REDIS_URL)
        
        # Add password to netloc
        netloc = f":{settings.REDIS_PASSWORD}@{parsed.hostname}:{parsed.port}"
        
        return urlunparse((
            parsed.scheme,
            netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment
        ))
    
    return settings.REDIS_URL

# Export commonly used settings
__all__ = [
    "Settings",
    "DevelopmentSettings", 
    "ProductionSettings",
    "TestingSettings",
    "get_settings",
    "settings",
    "validate_instagram_config",
    "validate_google_config", 
    "validate_hubspot_config",
    "validate_neo4j_config",
    "get_database_url",
    "get_redis_url"
]