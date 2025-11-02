import os
from typing import Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Temporary fix for circular import - define placeholder function
def log_settings_initialization(settings, success):
    """Placeholder function to avoid circular import during testing."""
    pass

# Load environment variables from .env file (use as-is, production)
load_dotenv()


class Settings(BaseSettings):
    """
    Production-grade Settings using Pydantic v2.
    Loads from .env as-is, ignores unknown extras to prevent crashes.
    Uppercase attributes are kept for backward compatibility with existing code.
    """

    # Pydantic settings
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    # Supabase
    SUPABASE_URL: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # LLM / OpenRouter
    OPENROUTER_API_KEY: Optional[str] = None
    # Preferred model env name per llm_client usage
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", " nvidia/nemotron-nano-12b-v2-vl:free")
    # Backward-compat alias (some components might read LLM_MODEL)
    LLM_MODEL: Optional[str] = os.getenv("LLM_MODEL", None)
    
    # General environment flags
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "production")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("1", "true", "yes")
    
    # Meta / Instagram
    META_APP_ID: Optional[str] = None
    META_APP_SECRET: Optional[str] = None
    META_ACCESS_TOKEN: Optional[str] = None
    META_PAGE_ACCESS_TOKEN: Optional[str] = None

    # Google Calendar
    GOOGLE_CALENDAR_API_KEY: Optional[str] = None
    GOOGLE_CALENDAR_CLIENT_ID: Optional[str] = None
    GOOGLE_CALENDAR_CLIENT_SECRET: Optional[str] = None

    # HubSpot
    # Prefer access token (as per PRD and integration requirements)
    HUBSPOT_ACCESS_TOKEN: Optional[str] = os.getenv("HUBSPOT_ACCESS_TOKEN", None)
    # Support legacy API key if present
    HUBSPOT_API_KEY: Optional[str] = os.getenv("HUBSPOT_API_KEY", None)
    HUBSPOT_API_BASE: str = os.getenv("HUBSPOT_API_BASE", "https://api.hubapi.com")

    # Feature flags and compliance
    ENABLE_COMPLIANCE_CHECKS: bool = os.getenv("ENABLE_COMPLIANCE_CHECKS", "true").lower() in ("1", "true", "yes")
    
    # Proactive Engagement Kill-Switches (Critical for preventing infinite loops)
    PROACTIVE_ENGAGEMENT_ENABLED: bool = os.getenv("PROACTIVE_ENGAGEMENT_ENABLED", "false").lower() in ("1", "true", "yes")
    LLM_CIRCUIT_OPEN_NOOP: bool = os.getenv("LLM_CIRCUIT_OPEN_NOOP", "true").lower() in ("1", "true", "yes")
    REQUIRE_BOUND_THREAD: bool = os.getenv("REQUIRE_BOUND_THREAD", "true").lower() in ("1", "true", "yes")
    
    # Rate limiting and deduplication
    INTERVENTION_COOLDOWN_MINUTES: int = int(os.getenv("INTERVENTION_COOLDOWN_MINUTES", "15"))
    ENABLE_INTERVENTION_DEDUP: bool = os.getenv("ENABLE_INTERVENTION_DEDUP", "true").lower() in ("1", "true", "yes")
    
    # Qualifier-only mode for pilot
    QUALIFIER_ONLY_MODE: bool = os.getenv("QUALIFIER_ONLY_MODE", "false").lower() in ("1", "true", "yes")
    EXTRACTION_CONFIDENCE_THRESHOLD: float = float(os.getenv("EXTRACTION_CONFIDENCE_THRESHOLD", "0.7"))

    # Celery
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

    # Backward compatibility: map if LLM_MODEL not set but OPENROUTER_MODEL is
    @property
    def EFFECTIVE_LLM_MODEL(self) -> str:
        return self.LLM_MODEL or self.OPENROUTER_MODEL


# Backward-compatible alias for existing imports expecting Config
class Config(Settings):
    pass


# Singleton accessor
_settings_instance: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the singleton settings instance."""
    global _settings_instance
    if _settings_instance is None:
        try:
            _settings_instance = Settings()
            log_settings_initialization(_settings_instance, success=True)
        except Exception as e:
            log_settings_initialization(None, success=False)
            raise e
    return _settings_instance