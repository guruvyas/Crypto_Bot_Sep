from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from app.core.database import init_db
from app.api import dashboard
from app.api import session_control_simple
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

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers - using the simplified session control
app.include_router(dashboard.router, prefix="/api", tags=["dashboard"])
app.include_router(session_control_simple.router, prefix="/api/session", tags=["session"])

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/")
async def root():
    # Redirect to web interface
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/index.html")

if __name__ == "__main__":
    uvicorn.run(
        "app.main_working:app", 
        host="0.0.0.0", 
        port=8003, 
        reload=False
    )