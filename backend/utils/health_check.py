from config.settings import Config
from utils.supabase_client import supabase
from utils.redis_client import redis_client

def validate_config():
    """
    Validate that all required configuration values are present.
    
    Raises:
        ValueError: If any required configuration is missing
    """
    missing_configs = []
    
    if not Config.SUPABASE_URL:
        missing_configs.append("SUPABASE_URL")
    
    if not Config.SUPABASE_KEY:
        missing_configs.append("SUPABASE_KEY")
    
    if not Config.OPENROUTER_API_KEY:
        missing_configs.append("OPENROUTER_API_KEY")
    
    if not Config.META_APP_SECRET:
        missing_configs.append("META_APP_SECRET")
    
    if not Config.META_ACCESS_TOKEN and not Config.META_PAGE_ACCESS_TOKEN:
        missing_configs.append("META_ACCESS_TOKEN or META_PAGE_ACCESS_TOKEN")
    
    if missing_configs:
        raise ValueError(f"Missing required configuration: {', '.join(missing_configs)}")

def check_database_connection():
    """
    Check if the database connection is working.
    
    Returns:
        bool: True if connection is successful, False otherwise
    """
    try:
        # Try a simple query to check connection
        response = supabase.table("leads").select("id").limit(1).execute()
        return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False

def check_redis_connection():
    """
    Check if the Redis connection is working.
    
    Returns:
        bool: True if connection is successful, False otherwise
    """
    try:
        # Try a simple ping to check connection
        redis_client.ping()
        return True
    except Exception as e:
        print(f"Redis connection failed: {e}")
        return False

def health_check():
    """
    Perform a health check of all system components.
    
    Returns:
        dict: Health status of all components
    """
    try:
        validate_config()
        config_status = "OK"
    except ValueError as e:
        config_status = str(e)
    
    db_status = "OK" if check_database_connection() else "Failed"
    redis_status = "OK" if check_redis_connection() else "Failed"
    
    return {
        "config": config_status,
        "database": db_status,
        "redis": redis_status
    }