from fastapi import APIRouter, HTTPException
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from utils.health_check import health_check
except ImportError:
    # Fallback health check
    def health_check():
        return {"status": "healthy", "service": "main"}

router = APIRouter()

@router.get("/health")
async def health_status():
    """
    Check the health status of all system components.
    
    Returns:
        dict: Health status of all components
    """
    status = health_check()
    
    # If any component is not OK, raise an HTTP exception
    if any(s != "OK" for s in status.values()):
        raise HTTPException(status_code=503, detail=status)
    
    return status