import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from backend.app.api.routes import router
from backend.app.models.database import init_db
from backend.app.services.scheduler import scheduler
from backend.app.core.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    logger.info("Starting Pytheus Watchdog...")
    logger.info(f"Environment: {settings.app_env}")

    # Ensure data directory exists
    Path("./data").mkdir(exist_ok=True)

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Start scheduler
    await scheduler.start()
    logger.info("Monitoring scheduler started")

    yield

    # Shutdown
    logger.info("Shutting down Pytheus Watchdog...")
    scheduler.stop()
    logger.info("Monitoring scheduler stopped")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="Unified system and platform monitoring with AI-powered alert triage",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api")

# Serve static frontend files (if built)
frontend_dist = Path("./frontend/dist")
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "app": settings.app_name,
        "version": "1.0.0",
        "status": "running"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )
