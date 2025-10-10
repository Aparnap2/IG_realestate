"""
JWT Authentication Middleware for Supabase

This module handles JWT token verification for Supabase authentication.
"""
from fastapi import Request, HTTPException
import jwt
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Supabase JWT configuration
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
SUPABASE_URL = os.getenv("SUPABASE_URL")

async def verify_supabase_jwt(request: Request) -> Dict[str, Any]:
    """
    Verify Supabase JWT token from Authorization header.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Dict containing user information
        
    Raises:
        HTTPException: If token is invalid or missing
    """
    try:
        # Get token from Authorization header
        authorization = request.headers.get("Authorization")
        if not authorization:
            raise HTTPException(status_code=401, detail="Authorization header missing")
        
        # Extract token (format: "Bearer <token>")
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid authorization format")
        
        token = authorization[7:]  # Remove "Bearer " prefix
        
        # For development, allow bypass
        if os.getenv("ENVIRONMENT") == "development" and token == "dev-token":
            return {
                "id": "dev-user-id",
                "email": "dev@example.com",
                "user_metadata": {},
                "app_metadata": {}
            }
        
        # Verify JWT token
        if not SUPABASE_JWT_SECRET:
            logger.warning("SUPABASE_JWT_SECRET not configured, using fallback verification")
            # Fallback: basic token validation without signature verification
            try:
                # Decode without verification (not recommended for production)
                payload = jwt.decode(token, options={"verify_signature": False})
                return {
                    "id": payload.get("sub"),
                    "email": payload.get("email"),
                    "user_metadata": payload.get("user_metadata", {}),
                    "app_metadata": payload.get("app_metadata", {})
                }
            except jwt.InvalidTokenError as e:
                raise HTTPException(status_code=401, detail="Invalid token format")
        
        # Verify with secret
        try:
            payload = jwt.decode(
                token,
                SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated"
            )
            
            return {
                "id": payload.get("sub"),
                "email": payload.get("email"),
                "user_metadata": payload.get("user_metadata", {}),
                "app_metadata": payload.get("app_metadata", {})
            }
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidTokenError as e:
            raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in JWT verification: {e}")
        raise HTTPException(status_code=500, detail="Internal authentication error")

def get_user_from_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Extract user information from JWT token without request context.
    
    Args:
        token: JWT token string
        
    Returns:
        User information dict or None if invalid
    """
    try:
        if os.getenv("ENVIRONMENT") == "development" and token == "dev-token":
            return {
                "id": "dev-user-id",
                "email": "dev@example.com",
                "user_metadata": {},
                "app_metadata": {}
            }
        
        if not SUPABASE_JWT_SECRET:
            # Fallback: decode without verification
            payload = jwt.decode(token, options={"verify_signature": False})
        else:
            payload = jwt.decode(
                token,
                SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated"
            )
        
        return {
            "id": payload.get("sub"),
            "email": payload.get("email"),
            "user_metadata": payload.get("user_metadata", {}),
            "app_metadata": payload.get("app_metadata", {})
        }
        
    except Exception as e:
        logger.error(f"Error extracting user from token: {e}")
        return None