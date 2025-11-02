from dotenv import load_dotenv
import os
import logging
from typing import Dict, Any
from pathlib import Path

def load_envs(env_file_path: Path = None, raise_on_error: bool = False) -> bool:
    """
    Load environment variables from .env file with error handling.
    
    Args:
        env_file_path: Custom path to .env file. If None, uses default location.
        raise_on_error: If True, raise exception on loading failure.
        
    Returns:
        bool: True if loading successful, False otherwise.
    """
    logger = logging.getLogger(__name__)
    
    # Determine .env file path
    if env_file_path is None:
        # Default: look for .env in the same directory as this script
        script_dir = Path(__file__).parent
        env_file_path = script_dir / ".env"
    else:
        env_file_path = Path(env_file_path)
    
    try:
        if env_file_path.exists():
            load_dotenv(dotenv_path=str(env_file_path))
            logger.info(f"Environment variables loaded from {env_file_path}")
            
            # Log loaded variables (without sensitive values)
            loaded_vars = []
            sensitive_vars = ["SECRET_KEY", "API_KEY", "PASSWORD", "TOKEN", "KEY"]
            
            for key, value in os.environ.items():
                if not any(sensitive in key.upper() for sensitive in sensitive_vars):
                    loaded_vars.append(key)
                    
            logger.debug(f"Loaded {len(loaded_vars)} environment variables")
            return True
        else:
            error_msg = f"Environment file not found: {env_file_path}"
            logger.warning(error_msg)
            
            if raise_on_error:
                raise FileNotFoundError(error_msg)
            
            return False
            
    except Exception as e:
        error_msg = f"Failed to load environment variables from {env_file_path}: {str(e)}"
        logger.error(error_msg)
        
        if raise_on_error:
            raise RuntimeError(error_msg) from e
            
        return False

def validate_env_file_structure(env_file_path: str = None) -> Dict[str, Any]:
    """
    Validate the structure and content of .env file.
    
    Args:
        env_file_path: Path to .env file to validate.
        
    Returns:
        Dict containing validation results.
    """
    if env_file_path is None:
        script_dir = Path(__file__).parent
        env_file_path = script_dir / ".env"
    else:
        env_file_path = Path(env_file_path)
    
    result = {
        "file_exists": env_file_path.exists(),
        "readable": False,
        "required_vars": [],
        "optional_vars": [],
        "issues": []
    }
    
    if not result["file_exists"]:
        result["issues"].append("Environment file does not exist")
        return result
    
    try:
        with open(env_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            result["readable"] = True
            
        # Parse environment variables
        lines = content.strip().split('\n')
        env_vars = {}
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if line and not line.startswith('#'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
        
        # Define required variables
        required_vars = [
            "SUPABASE_URL",
            "SUPABASE_KEY",
            "ENVIRONMENT"
        ]
        
        # Define optional but recommended variables
        optional_vars = [
            "OPENAI_API_KEY",
            "OPENROUTER_API_KEY",
            "CELERY_BROKER_URL",
            "REDIS_URL",
            "SECRET_KEY"
        ]
        
        # Check required variables
        for var in required_vars:
            if var in env_vars and env_vars[var]:
                result["required_vars"].append(var)
            else:
                result["issues"].append(f"Missing required variable: {var}")
        
        # Check optional variables
        for var in optional_vars:
            if var in env_vars and env_vars[var]:
                result["optional_vars"].append(var)
        
        # Check for common issues
        if "SECRET_KEY" in env_vars:
            secret_value = env_vars["SECRET_KEY"]
            if secret_value in ["your-secret-key-change-in-production", "change-me", "secret"]:
                result["issues"].append("SECRET_KEY appears to be a placeholder value")
        
        if "ENVIRONMENT" in env_vars:
            env_value = env_vars["ENVIRONMENT"].lower()
            if env_value not in ["development", "production", "testing"]:
                result["issues"].append(f"Invalid ENVIRONMENT value: {env_value}")
                
    except Exception as e:
        result["issues"].append(f"Error reading file: {str(e)}")
    
    return result

# Auto-load environment variables when module is imported
try:
    load_envs()
except Exception as e:
    logging.getLogger(__name__).error(f"Failed to auto-load environment variables: {str(e)}")
