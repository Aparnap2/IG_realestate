# Config package initialization
from .settings import *
from .settings import get_settings
from .industry_configs import (
    IndustryConfigManager,
    IndustryConfig,
    IndustryType,
    get_industry_config_manager,
    get_industry_config,
    detect_industry
)