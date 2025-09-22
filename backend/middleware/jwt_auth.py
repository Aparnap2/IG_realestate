from fastapi import HTTPException, Request
from supabase import create_client
import os

# Initialize Supabase client
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

async def verify_supabase_jwt(request: Request):
    """
    Verify Supabase JWT token from Authorization header.
    
    Args:
        request: FastAPI request object
        
    Returns:
        User object if token is valid
        
    Raises:
        HTTPException: If token is invalid or missing
    """
    # Get authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    # Extract token
    try:
        token_type, token = auth_header.split(" ")
        if token_type.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authorization header")
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    
    try:
        # Verify the token with Supabase
        user = supabase.auth.get_user(token)
        return user
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")