"""
Multi-Tenant Authentication Middleware

Combines JWT authentication with company context and role-based access control.
"""
from fastapi import Request, HTTPException, Depends
from typing import Optional, Dict, Any, Callable
import logging
import sys
import os

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from middleware.jwt_auth import verify_supabase_jwt
    from middleware.company_context import (
        CompanyContext, 
        get_company_context, 
        get_optional_company_context,
        verify_user_company_access
    )
except ImportError:
    # Fallback for testing
    async def verify_supabase_jwt(request):
        return {"id": "test-user", "email": "test@example.com"}
    
    class CompanyContext:
        def __init__(self, data):
            self.id = "test-company"
            self.slug = "test"
    
    async def get_company_context(request):
        return CompanyContext({})
    
    async def get_optional_company_context(request):
        return CompanyContext({})
    
    async def verify_user_company_access(user_id, company_id, role):
        return {"role": "admin", "permissions": {}}

logger = logging.getLogger(__name__)

class AuthenticatedUser:
    """Authenticated user with company context"""
    def __init__(self, user_data: Dict[str, Any], company: Optional[CompanyContext] = None, access_info: Optional[Dict[str, Any]] = None):
        self.id = user_data.get('id')
        self.email = user_data.get('email')
        self.user_metadata = user_data.get('user_metadata', {})
        self.app_metadata = user_data.get('app_metadata', {})
        self.company = company
        self.access_info = access_info or {}
        self._raw_data = user_data
    
    @property
    def role(self) -> str:
        """Get user's role in the current company"""
        return self.access_info.get('role', 'viewer')
    
    @property
    def permissions(self) -> Dict[str, Any]:
        """Get user's permissions in the current company"""
        return self.access_info.get('permissions', {})
    
    def has_permission(self, resource: str, action: str) -> bool:
        """Check if user has specific permission"""
        resource_perms = self.permissions.get(resource, {})
        return resource_perms.get(action, False)
    
    def can_read(self, resource: str) -> bool:
        """Check if user can read a resource"""
        return self.has_permission(resource, 'read')
    
    def can_write(self, resource: str) -> bool:
        """Check if user can write to a resource"""
        return self.has_permission(resource, 'write')
    
    def can_delete(self, resource: str) -> bool:
        """Check if user can delete a resource"""
        return self.has_permission(resource, 'delete')
    
    def is_admin(self) -> bool:
        """Check if user is admin or owner"""
        return self.role in ['admin', 'owner']
    
    def is_owner(self) -> bool:
        """Check if user is company owner"""
        return self.role == 'owner'
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            **self._raw_data,
            'company': self.company.to_dict() if self.company else None,
            'role': self.role,
            'permissions': self.permissions
        }

async def authenticate_user(request: Request) -> AuthenticatedUser:
    """Authenticate user with JWT only (no company context required)"""
    try:
        user_data = await verify_supabase_jwt(request)
        return AuthenticatedUser(user_data)
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail="Authentication required")

async def authenticate_user_with_company(
    request: Request, 
    required_role: str = "member"
) -> AuthenticatedUser:
    """
    Authenticate user and verify company access with required role.
    
    Args:
        request: FastAPI request object
        required_role: Minimum required role (viewer, member, admin, owner)
        
    Returns:
        AuthenticatedUser with company context
        
    Raises:
        HTTPException: If authentication or authorization fails
    """
    try:
        # Authenticate user
        user_data = await verify_supabase_jwt(request)
        user_id = user_data.get('id')
        
        # Get company context
        company = await get_company_context(request)
        
        # Verify user has access to company
        access_info = await verify_user_company_access(
            user_id, 
            company.id, 
            required_role
        )
        
        return AuthenticatedUser(user_data, company, access_info)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication with company failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

async def authenticate_user_optional_company(request: Request) -> AuthenticatedUser:
    """Authenticate user with optional company context"""
    try:
        # Authenticate user
        user_data = await verify_supabase_jwt(request)
        user_id = user_data.get('id')
        
        # Try to get company context
        company = await get_optional_company_context(request)
        
        access_info = None
        if company:
            try:
                access_info = await verify_user_company_access(user_id, company.id, "viewer")
            except HTTPException:
                # User doesn't have access to this company, continue without company context
                company = None
        
        return AuthenticatedUser(user_data, company, access_info)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication with optional company failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Dependency factories
def require_auth():
    """Dependency to require authentication only"""
    return Depends(authenticate_user)

def require_auth_with_company(required_role: str = "member"):
    """Dependency to require authentication with company access"""
    async def _require_auth_with_company(request: Request) -> AuthenticatedUser:
        return await authenticate_user_with_company(request, required_role)
    return Depends(_require_auth_with_company)

def require_auth_optional_company():
    """Dependency for authentication with optional company context"""
    return Depends(authenticate_user_optional_company)

# Role-based dependency shortcuts
def require_viewer():
    """Require viewer role or higher"""
    return require_auth_with_company("viewer")

def require_member():
    """Require member role or higher"""
    return require_auth_with_company("member")

def require_admin():
    """Require admin role or higher"""
    return require_auth_with_company("admin")

def require_owner():
    """Require owner role"""
    return require_auth_with_company("owner")

# Permission-based decorators
def require_permission(resource: str, action: str):
    """Decorator to require specific permission"""
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            # Find the authenticated user in the arguments
            user = None
            for arg in args:
                if isinstance(arg, AuthenticatedUser):
                    user = arg
                    break
            
            if not user:
                # Look in kwargs
                for value in kwargs.values():
                    if isinstance(value, AuthenticatedUser):
                        user = value
                        break
            
            if not user:
                raise HTTPException(status_code=500, detail="User context not found")
            
            if not user.has_permission(resource, action):
                raise HTTPException(
                    status_code=403,
                    detail=f"Permission denied: {action} access to {resource} required"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# Middleware class
class MultiTenantAuthMiddleware:
    """Middleware to handle multi-tenant authentication"""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            request = Request(scope, receive)
            
            # Skip auth for health checks and public endpoints
            path = request.url.path
            if path in ["/health", "/", "/docs", "/redoc", "/openapi.json"]:
                await self.app(scope, receive, send)
                return
            
            try:
                # Try to authenticate user with optional company context
                user = await authenticate_user_optional_company(request)
                scope["user"] = user
                
                # Log access for audit
                logger.info(f"User {user.email} accessing {path} for company {user.company.slug if user.company else 'none'}")
                
            except HTTPException as e:
                # Only log if it's not a 401 (expected for public endpoints)
                if e.status_code != 401:
                    logger.warning(f"Auth middleware error for {path}: {e.detail}")
            except Exception as e:
                logger.error(f"Unexpected auth middleware error for {path}: {e}")
        
        await self.app(scope, receive, send)

# Utility functions
async def get_user_companies(user_id: str) -> list:
    """Get all companies a user has access to"""
    try:
        from utils.supabase_client import supabase
        
        result = supabase.rpc("get_user_companies", {"user_uuid": user_id}).execute()
        return result.data or []
        
    except Exception as e:
        logger.error(f"Error getting user companies: {e}")
        return []

async def create_company_user(company_id: str, user_id: str, role: str = "member", invited_by: Optional[str] = None) -> Dict[str, Any]:
    """Add a user to a company"""
    try:
        from utils.supabase_client import supabase
        
        data = {
            "company_id": company_id,
            "user_id": user_id,
            "role": role,
            "is_active": True
        }
        
        if invited_by:
            data["invited_by"] = invited_by
            data["invited_at"] = "now()"
        
        result = supabase.table("company_users").insert(data).execute()
        return result.data[0] if result.data else {}
        
    except Exception as e:
        logger.error(f"Error creating company user: {e}")
        raise HTTPException(status_code=500, detail="Failed to add user to company")

async def update_user_role(company_id: str, user_id: str, new_role: str, updated_by: str) -> bool:
    """Update a user's role in a company"""
    try:
        from utils.supabase_client import supabase
        
        # Verify the updater has permission (admin or owner)
        updater_access = await verify_user_company_access(updated_by, company_id, "admin")
        
        # Owners can't be demoted by admins
        current_user = supabase.table("company_users")\
            .select("role")\
            .eq("company_id", company_id)\
            .eq("user_id", user_id)\
            .execute()
        
        if current_user.data and current_user.data[0]["role"] == "owner" and updater_access["role"] != "owner":
            raise HTTPException(status_code=403, detail="Only owners can modify owner roles")
        
        result = supabase.table("company_users")\
            .update({"role": new_role})\
            .eq("company_id", company_id)\
            .eq("user_id", user_id)\
            .execute()
        
        return bool(result.data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user role: {e}")
        raise HTTPException(status_code=500, detail="Failed to update user role")

async def remove_user_from_company(company_id: str, user_id: str, removed_by: str) -> bool:
    """Remove a user from a company"""
    try:
        from utils.supabase_client import supabase
        
        # Verify the remover has permission
        await verify_user_company_access(removed_by, company_id, "admin")
        
        # Can't remove the last owner
        owners = supabase.table("company_users")\
            .select("user_id")\
            .eq("company_id", company_id)\
            .eq("role", "owner")\
            .eq("is_active", True)\
            .execute()
        
        if len(owners.data) == 1 and owners.data[0]["user_id"] == user_id:
            raise HTTPException(status_code=400, detail="Cannot remove the last owner")
        
        result = supabase.table("company_users")\
            .update({"is_active": False})\
            .eq("company_id", company_id)\
            .eq("user_id", user_id)\
            .execute()
        
        return bool(result.data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing user from company: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove user from company")