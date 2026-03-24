"""
Backtest worker - Celery task that runs AutonomousAgent.
Emits WebSocket events for real-time progress updates.
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional

from celery import shared_task
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

from .celery_app import celery_app
from ..config import get_settings
from ..models.job import Job, JobStatus
from ..models.strategy import Strategy
from ..models.credential import Credential
from ..models.watchlist import Watchlist, WatchlistSymbol
from ..services.credential_vault import decrypt_credential
from ..websocket.manager import broadcast_job_event

# Import the existing backtester components - handle missing modules gracefully
try:
    from src.tv_backtester.agent import AutonomousAgent
    from src.tv_backtester.ai_generator import StrategyRequest, ClaudeProvider, DeepSeekProvider
    from src.tv_backtester.browser_controller import TradingViewBrowser
    from src.tv_backtester.metric_analyzer import MetricAnalyzer
    BACKTESTER_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Backtester components not fully available: {e}")
    BACKTESTER_AVAILABLE = False
    AutonomousAgent = None
    StrategyRequest = None
    ClaudeProvider = None
    DeepSeekProvider = None
    TradingViewBrowser = None
    MetricAnalyzer = None

logger = logging.getLogger(__name__)
settings = get_settings()


def get_async_session():
    """Create async database session for the worker."""
    database_url = settings.database_url
    if database_url.startswith("sqlite:"):
        database_url = database_url.replace("sqlite:", "sqlite+aiosqlite:", 1)
    elif database_url.startswith("postgresql:"):
        database_url = database_url.replace("postgresql:", "postgresql+asyncpg:", 1)
    
    engine = create_async_engine(database_url)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class WebSocketProgressCallback:
    """Callback that broadcasts progress via WebSocket."""
    
    def __init__(self, job_id: int):
        self.job_id = job_id
    
    async def on_iteration_start(self, iteration: int, total: int):
        await broadcast_job_event(self.job_id, "iteration.start", {
            "iteration": iteration,
            "total": total
        })
    
    async def on_strategy_generated(self, version: int, reasoning: str):
        await broadcast_job_event(self.job_id, "strategy.generated", {
            "version": version,
            "reasoning": reasoning[:500]  # Truncate for WS
        })
    
    async def on_backtest_progress(self, symbol: str, idx: int, total: int):
        await broadcast_job_event(self.job_id, "backtest.progress", {
            "symbol": symbol,
            "current": idx,
            "total": total
        })
    
    async def on_metrics_collected(self, metrics: dict):
        await broadcast_job_event(self.job_id, "metrics.collected", metrics)
    
    async def on_strategy_improved(self, version: int, score: float, metrics: dict):
        await broadcast_job_event(self.job_id, "strategy.improved", {
            "version": version,
            "score": score,
            "metrics": metrics
        })
    
    async def on_error(self, error: str):
        await broadcast_job_event(self.job_id, "error", {"message": error})
    
    async def on_complete(self, best_version: int, summary: dict):
        await broadcast_job_event(self.job_id, "job.complete", {
            "best_version": best_version,
            "summary": summary
        })


async def run_backtest_job_async(job_id: int):
    """Main async function to run the backtest job."""
    SessionLocal = get_async_session()
    callback = WebSocketProgressCallback(job_id)
    
    async with SessionLocal() as db:
        # Load job
        result = await db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()
        
        if not job:
            logger.error(f"Job {job_id} not found")
            return
        
        # Update status to running
        job.status = JobStatus.RUNNING
        job.started_at = datetime.utcnow()
        await db.commit()
        
        try:
            # Check if backtester is available
            if not BACKTESTER_AVAILABLE:
                # For now, mark as completed with a message
                job.status = JobStatus.COMPLETED
                job.completed_at = datetime.utcnow()
                job.progress_data = {"message": "Backtester integration pending"}
                await db.commit()
                await callback.on_complete(0, {"message": "Integration pending"})
                return
            
            # Load user credentials
            creds_result = await db.execute(
                select(Credential).where(Credential.user_id == job.user_id)
            )
            credentials = {c.credential_type: decrypt_credential(c.encrypted_value) 
                          for c in creds_result.scalars()}
            
            # Load watchlist symbols
            wl_result = await db.execute(
                select(WatchlistSymbol).where(WatchlistSymbol.watchlist_id == job.watchlist_id)
            )
            symbols = [s.full_symbol for s in wl_result.scalars()]
            
            if not symbols:
                raise ValueError("No symbols in watchlist")
            
            # Get AI API key based on provider
            if job.ai_provider == "claude":
                api_key = credentials.get("claude_key")
                if not api_key:
                    raise ValueError("Claude API key not configured")
                ai_provider = ClaudeProvider(api_key=api_key)
            else:
                api_key = credentials.get("deepseek_key")
                if not api_key:
                    raise ValueError("DeepSeek API key not configured")
                ai_provider = DeepSeekProvider(api_key=api_key)
            
            # Get TradingView cookies
            tv_cookies = credentials.get("tv_cookies")
            if not tv_cookies:
                raise ValueError("TradingView cookies not configured")
            
            # TODO: Full backtester integration
            # For now, create a placeholder strategy
            strategy = Strategy(
                job_id=job_id,
                version=1,
                name=f"{job.strategy_type}_v1",
                pine_script="// Placeholder - backtester integration in progress",
                ai_reasoning="Backtester integration pending"
            )
            db.add(strategy)
            await db.flush()
            
            job.best_strategy_id = strategy.id
            job.current_iteration = 1
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.progress_data = {
                "current_iteration": 1,
                "message": "Placeholder - full integration pending"
            }
            await db.commit()
            
            await callback.on_complete(1, {"message": "Integration pending"})
            
        except Exception as e:
            logger.exception(f"Job {job_id} failed: {e}")
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            await db.commit()
            await callback.on_error(str(e))


@celery_app.task(bind=True)
def run_backtest_job(self, job_id: int):
    """
    Celery task to run a backtest job.
    
    This wraps the async function in an event loop.
    """
    logger.info(f"Starting backtest job {job_id}")
    
    try:
        asyncio.run(run_backtest_job_async(job_id))
    except Exception as e:
        logger.exception(f"Celery task failed for job {job_id}: {e}")
        raise
    
    logger.info(f"Completed backtest job {job_id}")
