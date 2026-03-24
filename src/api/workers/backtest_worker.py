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

# Import the existing backtester components
from tv_backtester.agent import AutonomousAgent
from tv_backtester.ai_generator import AIStrategyGenerator, StrategyRequest
from tv_backtester.browser_controller import TradingViewBrowser
from tv_backtester.metric_analyzer import MetricAnalyzer

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
            else:
                api_key = credentials.get("deepseek_key")
                if not api_key:
                    raise ValueError("DeepSeek API key not configured")
            
            # Get TradingView cookies
            tv_cookies = credentials.get("tv_cookies")
            if not tv_cookies:
                raise ValueError("TradingView cookies not configured")
            
            # Initialize components
            ai_generator = AIStrategyGenerator(
                provider=job.ai_provider,
                api_key=api_key
            )
            
            browser = TradingViewBrowser(cookies_json=tv_cookies)
            analyzer = MetricAnalyzer()
            
            # Run iterations
            best_strategy = None
            best_score = 0
            
            for iteration in range(1, job.max_iterations + 1):
                await callback.on_iteration_start(iteration, job.max_iterations)
                
                # Check if cancelled
                await db.refresh(job)
                if job.status == JobStatus.CANCELLED:
                    logger.info(f"Job {job_id} was cancelled")
                    return
                
                # Generate or improve strategy
                if iteration == 1:
                    request = StrategyRequest(
                        strategy_type=job.strategy_type,
                        symbols=symbols,
                        target_win_rate=job.target_win_rate,
                        target_profit_factor=job.target_profit_factor / 100,
                        target_max_drawdown=job.target_max_drawdown
                    )
                    response = await ai_generator.generate(request)
                else:
                    # Improve based on previous results
                    response = await ai_generator.improve(
                        current_script=best_strategy.pine_script,
                        metrics={"win_rate": best_strategy.win_rate,
                                "profit_factor": best_strategy.profit_factor,
                                "max_drawdown": best_strategy.max_drawdown},
                        feedback=f"Improve win rate and profit factor"
                    )
                
                await callback.on_strategy_generated(iteration, response.reasoning or "")
                
                # Create strategy record
                strategy = Strategy(
                    job_id=job_id,
                    version=iteration,
                    name=f"{job.strategy_type}_v{iteration}",
                    pine_script=response.pine_script,
                    ai_reasoning=response.reasoning
                )
                db.add(strategy)
                await db.flush()
                
                # Run backtest on symbols
                all_metrics = []
                async with browser:
                    for idx, symbol in enumerate(symbols, 1):
                        await callback.on_backtest_progress(symbol, idx, len(symbols))
                        
                        try:
                            metrics = await browser.backtest_strategy(
                                symbol=symbol,
                                pine_script=response.pine_script
                            )
                            all_metrics.append(metrics)
                        except Exception as e:
                            logger.warning(f"Backtest failed for {symbol}: {e}")
                
                # Aggregate metrics
                if all_metrics:
                    aggregated = analyzer.aggregate(all_metrics)
                    strategy.win_rate = aggregated.get("win_rate")
                    strategy.profit_factor = aggregated.get("profit_factor")
                    strategy.max_drawdown = aggregated.get("max_drawdown")
                    strategy.net_profit = aggregated.get("net_profit")
                    strategy.total_trades = aggregated.get("total_trades")
                    strategy.calculate_score()
                    strategy.symbol_metrics = {"per_symbol": all_metrics}
                    
                    await callback.on_metrics_collected({
                        "win_rate": strategy.win_rate,
                        "profit_factor": strategy.profit_factor,
                        "max_drawdown": strategy.max_drawdown,
                        "score": strategy.score
                    })
                    
                    # Track best
                    if strategy.score > best_score:
                        best_score = strategy.score
                        best_strategy = strategy
                        job.best_strategy_id = strategy.id
                        
                        await callback.on_strategy_improved(
                            iteration, best_score,
                            {"win_rate": strategy.win_rate,
                             "profit_factor": strategy.profit_factor}
                        )
                
                job.current_iteration = iteration
                job.progress_data = {
                    "current_iteration": iteration,
                    "best_score": best_score,
                    "best_version": best_strategy.version if best_strategy else None
                }
                await db.commit()
                
                # Check target metrics
                if best_strategy:
                    targets_met = (
                        (best_strategy.win_rate or 0) >= job.target_win_rate and
                        (best_strategy.profit_factor or 0) >= job.target_profit_factor / 100 and
                        (best_strategy.max_drawdown or 100) <= job.target_max_drawdown
                    )
                    if targets_met:
                        logger.info(f"Job {job_id} met target metrics early!")
                        break
            
            # Complete
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            await db.commit()
            
            await callback.on_complete(
                best_strategy.version if best_strategy else 0,
                {"best_score": best_score,
                 "iterations_run": job.current_iteration}
            )
            
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
