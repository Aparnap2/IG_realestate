"""
Company Management API endpoints for multi-tenant platform.
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import sys
import os

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from middleware.multi_tenant_auth import (
        AuthenticatedUser,
        require_auth,
        require_auth_with_company,
        require_admin,
        require_owner
    )
    from utils.supabase_client import supabase
except ImportError:
    # Fallback for testing
    class AuthenticatedUser:
        def __init__(self):
            self.id = "test"
            self.company = type('obj', (object,), {'id': 'test'})()
    
    def require_auth():
        return lambda: AuthenticatedUser()
    
    def require_auth_with_company(role="member"):
        return lambda: AuthenticatedUser()
    
    def require_admin():
        return lambda: AuthenticatedUser()
    
    def require_owner():
        return lambda: AuthenticatedUser()
    
    class MockSupabase:
        def table(self, name):
            return self
        def select(self, fields):
            return self
        def insert(self, data):
            return self
        def update(self, data):
            return self
        def eq(self, field, value):
            return self
        def execute(self):
            return type('obj', (object,), {'data': []})()
    
    supabase = MockSupabase()

router = APIRouter(prefix="/api/companies", tags=["companies"])

class CompanyCreate(BaseModel):
    name: str
    slug: str
    industry: str
    settings: Optional[Dict[str, Any]] = None

class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None
    subscription_tier: Optional[str] = None
    is_active: Optional[bool] = None

@router.get("/")
async def list_user_companies(user: AuthenticatedUser = require_auth()):
    """Get all companies the user has access to"""
    try:
        result = supabase.rpc("get_user_companies", {"user_uuid": user.id}).execute()
        return {"companies": result.data or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/")
async def create_company(
    company_data: CompanyCreate,
    user: AuthenticatedUser = require_auth()
):
    """Create a new company"""
    try:
        # Create company
        company_result = supabase.table("companies").insert({
            "name": company_data.name,
            "slug": company_data.slug,
            "industry": company_data.industry,
            "settings": company_data.settings or {}
        }).execute()
        
        if not company_result.data:
            raise HTTPException(status_code=400, detail="Failed to create company")
        
        company = company_result.data[0]
        
        # Add user as owner
        supabase.table("company_users").insert({
            "company_id": company["id"],
            "user_id": user.id,
            "role": "owner",
            "is_active": True
        }).execute()
        
        return {"company": company}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{company_id}")
async def get_company(
    company_id: str,
    user: AuthenticatedUser = require_auth_with_company()
):
    """Get company details"""
    if user.company.id != company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        result = supabase.table("companies").select("*").eq("id", company_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Company not found")
        
        return {"company": result.data[0]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{company_id}")
async def update_company(
    company_id: str,
    company_data: CompanyUpdate,
    user: AuthenticatedUser = require_admin()
):
    """Update company details (admin only)"""
    if user.company.id != company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        update_data = {k: v for k, v in company_data.dict().items() if v is not None}
        
        result = supabase.table("companies")\
            .update(update_data)\
            .eq("id", company_id)\
            .execute()
        
        return {"company": result.data[0] if result.data else None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{company_id}/stats")
async def get_company_stats(
    company_id: str,
    user: AuthenticatedUser = require_auth_with_company()
):
    """Get company statistics"""
    if user.company.id != company_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        result = supabase.rpc("get_company_stats", {"comp_id": company_id}).execute()
        return {"stats": result.data or {}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))