from fastapi import FastAPI
from .webhooks import app as webhooks_app
from .processing import app as processing_app
from .health import router as health_router

app = FastAPI()

# Include routers
app.include_router(webhooks_app, prefix="/api")
app.include_router(processing_app, prefix="/api")
app.include_router(health_router, prefix="/api")

@app.get("/")
async def root():
    return {"message": "AAA Real Estate Lead Capture Agentic AI System"}