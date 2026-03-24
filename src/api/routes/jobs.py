"""
Job routes - Create and manage backtest jobs.
"""
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from ..database import get_db
from ..models.user import User
from ..models.job import Job, JobStatus
from ..models.strategy import Strategy
from ..routes.auth import get_current_user
from ..websocket.manager import manager

router = APIRouter()


# Schemas
class JobCreate(BaseModel):
    name: str
    description: Optional[str] = None
    strategy_type: str  # sma_bounce, rsi_reversal, etc
    ai_provider: str = "deepseek"
    watchlist_id: int
    target_win_rate: int = 60
    target_profit_factor: int = 150
    target_max_drawdown: int = 20
    max_iterations: int = 10


class JobResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    status: str
    strategy_type: str
    ai_provider: str
    current_iteration: int
    max_iterations: int
    progress_data: dict
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    jobs: list[JobResponse]
    total: int


# Routes
@router.post("/", response_model=JobResponse)
async def create_job(
    data: JobCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new backtest job."""
    job = Job(
        user_id=current_user.id,
        name=data.name,
        description=data.description,
        strategy_type=data.strategy_type,
        ai_provider=data.ai_provider,
        watchlist_id=data.watchlist_id,
        target_win_rate=data.target_win_rate,
        target_profit_factor=data.target_profit_factor,
        target_max_drawdown=data.target_max_drawdown,
        max_iterations=data.max_iterations,
        status=JobStatus.PENDING,
    )
    
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    # TODO: Queue job with Celery
    # task = run_backtest_job.delay(job.id)
    # job.celery_task_id = task.id
    # await db.commit()
    
    return job


@router.get("/", response_model=JobListResponse)
async def list_jobs(
    skip: int = 0,
    limit: int = 20,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List user's jobs."""
    query = select(Job).where(Job.user_id == current_user.id)
    
    if status:
        query = query.where(Job.status == status)
    
    query = query.order_by(Job.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    jobs = result.scalars().all()
    
    # Count total
    count_query = select(Job).where(Job.user_id == current_user.id)
    if status:
        count_query = count_query.where(Job.status == status)
    count_result = await db.execute(count_query)
    total = len(count_result.scalars().all())
    
    return JobListResponse(jobs=jobs, total=total)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get job details."""
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job


@router.post("/{job_id}/cancel")
async def cancel_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Cancel a running job."""
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status not in [JobStatus.PENDING, JobStatus.RUNNING]:
        raise HTTPException(status_code=400, detail="Job cannot be cancelled")
    
    job.status = JobStatus.CANCELLED
    job.completed_at = datetime.utcnow()
    await db.commit()
    
    # TODO: Cancel Celery task
    # if job.celery_task_id:
    #     celery_app.control.revoke(job.celery_task_id, terminate=True)
    
    return {"status": "cancelled"}


@router.get("/{job_id}/strategies")
async def get_job_strategies(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all strategies generated for a job."""
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    result = await db.execute(
        select(Strategy).where(Strategy.job_id == job_id).order_by(Strategy.version)
    )
    strategies = result.scalars().all()
    
    return {"strategies": strategies}


# WebSocket for real-time job updates
@router.websocket("/{job_id}/ws")
async def job_websocket(
    websocket: WebSocket,
    job_id: int,
    db: AsyncSession = Depends(get_db)
):
    """WebSocket connection for real-time job updates."""
    await manager.connect(websocket, f"job_{job_id}")
    
    try:
        while True:
            # Keep connection alive, actual updates sent via manager.broadcast
            data = await websocket.receive_text()
            # Echo for ping/pong
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket, f"job_{job_id}")
