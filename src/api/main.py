"""
TradingView AI Backtester - FastAPI Application
World-class web interface for autonomous strategy generation.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from .config import get_settings
from .routes import auth, jobs, strategies, watchlists, health, credentials
from .database import init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting TradingView AI Backtester API...")
    await init_db()
    logger.info("Database initialized")
    yield
    # Shutdown
    logger.info("Shutting down...")


app = FastAPI(
    title=settings.app_name,
    description="Autonomous AI-powered Pine Script strategy generation and backtesting",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(credentials.router, prefix="/api/credentials", tags=["Credentials"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["Jobs"])
app.include_router(strategies.router, prefix="/api/strategies", tags=["Strategies"])
app.include_router(watchlists.router, prefix="/api/watchlists", tags=["Watchlists"])


@app.get("/")
async def root():
    """Root endpoint - redirect info."""
    return {
        "message": "TradingView AI Backtester API",
        "docs": "/api/docs",
        "health": "/api/health"
    }
