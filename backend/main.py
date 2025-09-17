from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from .api import app as api_app

app = FastAPI(title="AAA Real Estate Lead Capture Agentic AI System")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_app)

@app.get("/")
async def root():
    return {"message": "AAA Real Estate Lead Capture Agentic AI System"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)