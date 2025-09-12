from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.database import init_db
from app.api import dashboard, session_control
import uvicorn

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database on startup
    await init_db()
    yield

app = FastAPI(
    title="Crypto Trading Bot",
    description="FastAPI backend for crypto trading bot with Gemini Sandbox integration",
    version="1.0.0",
    lifespan=lifespan
)

# Include routers
app.include_router(dashboard.router, prefix="/api", tags=["dashboard"])
app.include_router(session_control.router, prefix="/api/session", tags=["session"])

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app", 
        host=settings.HOST, 
        port=settings.PORT, 
        reload=settings.DEBUG
    )