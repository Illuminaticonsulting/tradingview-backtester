"""
Backtest worker - Celery task that runs real TradingView backtests.
Uses Playwright to automate browser and extract actual metrics.
"""
import asyncio
import logging
import json
import tempfile
import os
from datetime import datetime
from typing import Optional, Dict, Any

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

# Import the backtester components
from src.tv_backtester.ai_generator import StrategyRequest, StrategyResponse, ClaudeProvider, DeepSeekProvider
from src.tv_backtester.browser_controller import BrowserController
from src.tv_backtester.metric_analyzer import MetricAnalyzer
from src.tv_backtester.pine_validator import PineValidator, fix_pine_script

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


# Target metrics for strategy evaluation
DEFAULT_TARGET_METRICS = {
    'win_rate': 45.0,
    'profit_factor': 1.3,
    'max_drawdown': 25.0,
    'min_trades': 50,
}


async def run_backtest_job_async(job_id: int):
    """Main async function to run the backtest job with REAL TradingView backtesting."""
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
        
        browser = None
        
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
                    raise ValueError("Claude API key not configured. Add it in Settings.")
                ai_provider = ClaudeProvider(api_key=api_key)
            else:
                api_key = credentials.get("deepseek_key")
                if not api_key:
                    raise ValueError("DeepSeek API key not configured. Add it in Settings.")
                ai_provider = DeepSeekProvider(api_key=api_key)
            
            # Get TradingView cookies
            tv_cookies = credentials.get("tv_cookies")
            
            # Setup target metrics
            target_metrics = {
                'win_rate': job.target_win_rate,
                'profit_factor': job.target_profit_factor,
                'max_drawdown': job.target_max_drawdown,
            }
            analyzer = MetricAnalyzer(target_metrics)
            validator = PineValidator()
            
            # Risk parameters
            risk_params = {
                'sl_atr_mult': 1.8,
                'tp_rr': 2.0,
                'be_trigger_pct': 0.9,
                'trail_trigger_pct': 1.5,
            }
            
            best_strategy = None
            best_score = -float('inf')
            best_metrics = {}
            
            # Start browser
            browser = BrowserController(headless=True)
            await browser.start()
            
            # Load TradingView cookies if available
            if tv_cookies:
                try:
                    cookies = json.loads(tv_cookies)
                    await browser.context.add_cookies(cookies)
                    logger.info("TradingView cookies loaded")
                except Exception as e:
                    logger.warning(f"Failed to load TV cookies: {e}")
            
            # Navigate to chart
            primary_symbol = symbols[0]
            await callback.on_iteration_start(0, job.max_iterations)
            
            if not await browser.navigate_to_chart(primary_symbol, "15"):
                raise ValueError(f"Failed to navigate to chart for {primary_symbol}")
            
            # Iteration loop
            previous_results = None
            current_script = None
            
            for iteration in range(1, job.max_iterations + 1):
                job.current_iteration = iteration
                await db.commit()
                
                await callback.on_iteration_start(iteration, job.max_iterations)
                logger.info(f"=== Iteration {iteration}/{job.max_iterations} ===")
                
                # Generate or improve strategy
                if iteration == 1:
                    # Generate initial strategy
                    request = StrategyRequest(
                        strategy_type=job.strategy_type,
                        timeframe="15",
                        symbol=primary_symbol,
                        risk_params=risk_params,
                        additional_context=job.description or ""
                    )
                    response = ai_provider.generate_strategy(request)
                else:
                    # Improve based on previous results
                    response = ai_provider.improve_strategy(
                        current_strategy=current_script,
                        backtest_results=previous_results,
                        target_metrics=target_metrics
                    )
                
                current_script = response.pine_script
                await callback.on_strategy_generated(iteration, response.reasoning)
                
                # Validate Pine Script
                is_valid, errors = validator.validate(current_script)
                if not is_valid:
                    logger.warning(f"Pine Script validation errors: {errors}")
                    current_script = fix_pine_script(current_script, errors)
                
                # Paste and compile script
                if not await browser.paste_pine_script(current_script):
                    logger.error("Failed to paste Pine Script")
                    continue
                
                success, compile_error = await browser.compile_script()
                if not success:
                    logger.error(f"Compilation failed: {compile_error}")
                    # Let AI fix it in next iteration
                    previous_results = {"error": compile_error, "success": False}
                    continue
                
                # Run backtest on each symbol
                all_metrics = []
                for idx, symbol in enumerate(symbols):
                    await callback.on_backtest_progress(symbol, idx + 1, len(symbols))
                    
                    if symbol != primary_symbol:
                        await browser.change_symbol(symbol)
                        await asyncio.sleep(2)
                    
                    # Get metrics
                    metrics = await browser.get_backtest_metrics()
                    if metrics:
                        metrics['symbol'] = symbol
                        all_metrics.append(metrics)
                        logger.info(f"{symbol}: {metrics}")
                
                if not all_metrics:
                    logger.warning("No metrics extracted")
                    previous_results = {"error": "No metrics extracted", "success": False}
                    continue
                
                # Aggregate metrics
                aggregated = {
                    'win_rate': sum(float(m.get('win_rate', 0)) for m in all_metrics) / len(all_metrics),
                    'profit_factor': sum(float(m.get('profit_factor', 0)) for m in all_metrics) / len(all_metrics),
                    'max_drawdown': max(float(m.get('max_drawdown', 0)) for m in all_metrics),
                    'total_trades': sum(int(m.get('total_trades', 0)) for m in all_metrics),
                    'net_profit': sum(float(m.get('net_profit', '0').replace('$', '').replace(',', '')) for m in all_metrics),
                }
                
                await callback.on_metrics_collected(aggregated)
                
                # Analyze results
                analysis = analyzer.analyze(aggregated)
                score = analysis.overall_score
                
                # Save strategy version
                strategy = Strategy(
                    job_id=job_id,
                    version=iteration,
                    name=f"{response.strategy_name}_v{iteration}",
                    pine_script=current_script,
                    ai_reasoning=response.reasoning,
                    win_rate=aggregated.get('win_rate'),
                    profit_factor=aggregated.get('profit_factor'),
                    max_drawdown=aggregated.get('max_drawdown'),
                    net_profit=aggregated.get('net_profit'),
                    total_trades=aggregated.get('total_trades'),
                    score=score,
                    symbol_metrics={"all": all_metrics},
                )
                db.add(strategy)
                await db.flush()
                
                # Track best
                if score > best_score:
                    best_score = score
                    best_strategy = strategy
                    best_metrics = aggregated
                    job.best_strategy_id = strategy.id
                    await callback.on_strategy_improved(iteration, score, aggregated)
                
                # Check if targets met
                if analysis.meets_targets:
                    logger.info(f"All targets met at iteration {iteration}!")
                    break
                
                # Prepare for next iteration
                previous_results = {
                    "metrics": aggregated,
                    "analysis": {
                        "score": score,
                        "meets_targets": analysis.meets_targets,
                        "suggestions": analysis.recommendations,
                    }
                }
                
                # Navigate back to primary symbol
                if len(symbols) > 1:
                    await browser.change_symbol(primary_symbol)
            
            # Complete job
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.progress_data = {
                "iterations_completed": job.current_iteration,
                "best_score": best_score,
                "best_metrics": best_metrics,
                "symbols_tested": symbols,
            }
            await db.commit()
            
            await callback.on_complete(best_strategy.version if best_strategy else 0, {
                "best_score": best_score,
                "metrics": best_metrics,
            })
            
        except Exception as e:
            logger.exception(f"Job {job_id} failed: {e}")
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            await db.commit()
            await callback.on_error(str(e))
        
        finally:
            if browser:
                await browser.close()


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
