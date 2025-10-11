"""
Company Context Middleware for Multi-Tenant Support

This middleware extracts company context from requests and ensures
proper data isolation between companies.
"""
from fastapi import Request, HTTPException, Depends
from typing import Optional, Dict, Any
import logging
import sys
import os

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from utils.supabase_client import supabase
except ImportError:
        # Fallback for testing
        class MockSupabase:
            def table(self, name):
                return self
            def select(self, fields):
                return self
            def eq(self, field, value):
                return self
            def execute(self):
                return type('MockResult', (object,), {'data': []})()
        
        supabase = MockSupabase()

logger = logging.getLogger(__name__)

class CompanyContext:
    """Company context data structure"""
    def __init__(self, company_data: Dict[str, Any]):
        self.id = company_data.get('id')
        self.name = company_data.get('name')
        self.slug = company_data.get('slug')
        self.industry = company_data.get('industry', 'general')
        self.settings = company_data.get('settings', {})
        self.subscription_tier = company_data.get('subscription_tier', 'starter')
        self.is_active = company_data.get('is_active', True)
        self._raw_data = company_data
    
    def get_setting(self, key: str, default=None):
        """Get a setting value with dot notation support"""
        keys = key.split('.')
        value = self.settings
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def has_feature(self, feature: str) -> bool:
        """Check if company has a specific feature enabled"""
        return self.get_setting(f'features.{feature}', False)
    
    def get_limit(self, limit_type: str) -> int:
        """Get a company limit value"""
        return self.get_setting(f'limits.{limit_type}', 0)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return self._raw_data

async def get_company_from_subdomain(host: str) -> Optional[CompanyContext]:
    """Extract company from subdomain (e.g., company.platform.com)"""
    try:
        if not host or "." not in host:
            return None
        
        # Extract subdomain
        parts = host.split(".")
        if len(parts) < 2:
            return None
        
        company_slug = parts[0]
        
        # Skip common subdomains
        if company_slug in ['www', 'api', 'app', 'admin', 'staging', 'dev']:
            return None
        
        # Lookup company by slug
        result = supabase.table("companies")\
            .select("*")\
            .eq("slug", company_slug)\
            .eq("is_active", True)\
            .execute()
        
        if result.data and len(result.data) > 0:
            return CompanyContext(result.data[0])
        
        return None
        
    except Exception as e:
        logger.error(f"Error extracting company from subdomain {host}: {e}")
        return None

async def get_company_from_header(company_id: str) -> Optional[CompanyContext]:
    """Get company from X-Company-ID header"""
    try:
        if not company_id:
            return None
        
        result = supabase.table("companies")\
            .select("*")\
            .eq("id", company_id)\
            .eq("is_active", True)\
            .execute()
        
        if result.data and len(result.data) > 0:
            return CompanyContext(result.data[0])
        
        return None
        
    except Exception as e:
        logger.error(f"Error getting company from header {company_id}: {e}")
        return None

async def get_company_from_path(path: str) -> Optional[CompanyContext]:
    """Extract company from URL path (e.g., /company/slug/...)"""
    try:
        if not path.startswith('/company/'):
            return None
        
        parts = path.split('/')
        if len(parts) < 3:
            return None
        
        company_slug = parts[2]
        
        result = supabase.table("companies")\
            .select("*")\
            .eq("slug", company_slug)\
            .eq("is_active", True)\
            .execute()
        
        if result.data and len(result.data) > 0:
            return CompanyContext(result.data[0])
        
        return None
        
    except Exception as e:
        logger.error(f"Error extracting company from path {path}: {e}")
        return None

async def get_company_context(request: Request) -> CompanyContext:
    """
    Extract company context from request using multiple strategies:
    1. Subdomain: company.platform.com
    2. Header: X-Company-ID
    3. Path: /company/slug/...
    4. Query param: ?company_id=uuid
    """
    company = None
    
    # Strategy 1: Subdomain
    host = request.headers.get("host", "")
    if host:
        company = await get_company_from_subdomain(host)
        if company:
            logger.info(f"Company context from subdomain: {company.slug}")
            return company
    
    # Strategy 2: Header
    company_id = request.headers.get("x-company-id")
    if company_id:
        company = await get_company_from_header(company_id)
        if company:
            logger.info(f"Company context from header: {company.slug}")
            return company
    
    # Strategy 3: Path
    path = str(request.url.path)
    if path:
        company = await get_company_from_path(path)
        if company:
            logger.info(f"Company context from path: {company.slug}")
            return company
    
    # Strategy 4: Query parameter
    company_id = request.query_params.get("company_id")
    if company_id:
        company = await get_company_from_header(company_id)
        if company:
            logger.info(f"Company context from query: {company.slug}")
            return company
    
    # No company context found
    logger.warning("No company context found in request")
    raise HTTPException(
        status_code=400, 
        detail="Company context required. Use subdomain, X-Company-ID header, or company_id parameter."
    )

async def get_optional_company_context(request: Request) -> Optional[CompanyContext]:
    """Get company context without raising an error if not found"""
    try:
        return await get_company_context(request)
    except HTTPException:
        return None

def require_company_context():
    """Dependency to require company context"""
    async def _require_company_context(request: Request) -> CompanyContext:
        return await get_company_context(request)
    return Depends(_require_company_context)

def optional_company_context():
    """Dependency for optional company context"""
    async def _optional_company_context(request: Request) -> Optional[CompanyContext]:
        return await get_optional_company_context(request)
    return Depends(_optional_company_context)

async def verify_user_company_access(user_id: str, company_id: str, required_role: str = "member") -> Dict[str, Any]:
    """
    Verify that a user has access to a company with the required role.
    
    Args:
        user_id: User UUID
        company_id: Company UUID  
        required_role: Minimum required role (viewer < member < admin < owner)
        
    Returns:
        Dict with user access info
        
    Raises:
        HTTPException: If access is denied
    """
    try:
        # Check user has access to company
        result = supabase.table("company_users")\
            .select("role, permissions, is_active")\
            .eq("user_id", user_id)\
            .eq("company_id", company_id)\
            .eq("is_active", True)\
            .execute()
        
        if not result.data or len(result.data) == 0:
            raise HTTPException(
                status_code=403, 
                detail="Access denied: User not associated with this company"
            )
        
        user_access = result.data[0]
        user_role = user_access["role"]
        
        # Role hierarchy: viewer < member < admin < owner
        role_hierarchy = {"viewer": 1, "member": 2, "admin": 3, "owner": 4}
        
        if role_hierarchy.get(user_role, 0) < role_hierarchy.get(required_role, 0):
            raise HTTPException(
                status_code=403,
                detail=f"Access denied: {required_role} role required, user has {user_role}"
            )
        
        return {
            "role": user_role,
            "permissions": user_access.get("permissions", {}),
            "is_active": user_access["is_active"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying user company access: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

class CompanyContextMiddleware:
    """Middleware to inject company context into requests"""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # Add company context to scope if available
            request = Request(scope, receive)
            
            # Skip company context for webhook endpoints to avoid database errors - FIXED
            if "/webhook" in request.url.path:
                logger.info(f"Skipping company context for webhook endpoint: {request.url.path}")
                await self.app(scope, receive, send)
                return
            
            try:
                company = await get_optional_company_context(request)
                if company:
                    scope["company"] = company
                    logger.debug(f"Company context set: {company.slug}")
            except Exception as e:
                logger.error(f"Error in company context middleware: {e}")
        
        await self.app(scope, receive, send)

# Utility functions for common operations
async def get_company_integrations(company_id: str, integration_type: Optional[str] = None) -> list:
    """Get company integrations, optionally filtered by type"""
    try:
        query = supabase.table("company_integrations")\
            .select("*")\
            .eq("company_id", company_id)\
            .eq("is_active", True)
        
        if integration_type:
            query = query.eq("integration_type", integration_type)
        
        result = query.execute()
        return result.data or []
        
    except Exception as e:
        logger.error(f"Error getting company integrations: {e}")
        return []

async def get_company_workflows(company_id: str, is_active: bool = True) -> list:
    """Get company workflows"""
    try:
        query = supabase.table("workflows")\
            .select("*")\
            .eq("company_id", company_id)
        
        if is_active is not None:
            query = query.eq("is_active", is_active)
        
        result = query.execute()
        return result.data or []
        
    except Exception as e:
        logger.error(f"Error getting company workflows: {e}")
        return []

async def get_company_stats(company_id: str) -> Dict[str, Any]:
    """Get company statistics"""
    try:
        # Use the database function we created
        result = supabase.rpc("get_company_stats", {"comp_id": company_id}).execute()
        return result.data or {}
        
    except Exception as e:
        logger.error(f"Error getting company stats: {e}")
        return {
            "total_leads": 0,
            "qualified_leads": 0,
            "scheduled_meetings": 0,
            "active_integrations": 0,
            "active_workflows": 0
        }