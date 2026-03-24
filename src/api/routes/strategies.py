"""
Strategy routes - View and manage generated strategies.
"""
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from ..database import get_db
from ..models.user import User
from ..models.job import Job
from ..models.strategy import Strategy
from ..routes.auth import get_current_user

router = APIRouter()


# Schemas
class StrategyResponse(BaseModel):
    id: int
    job_id: int
    version: int
    name: str
    pine_script: str
    ai_reasoning: Optional[str]
    win_rate: Optional[float]
    profit_factor: Optional[float]
    max_drawdown: Optional[float]
    net_profit: Optional[float]
    total_trades: Optional[int]
    score: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True


class StrategyListResponse(BaseModel):
    strategies: list[StrategyResponse]
    total: int


# Routes
@router.get("/", response_model=StrategyListResponse)
async def list_strategies(
    skip: int = 0,
    limit: int = 20,
    sort_by: str = "score",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List user's strategies sorted by score."""
    # Get user's job IDs
    job_result = await db.execute(
        select(Job.id).where(Job.user_id == current_user.id)
    )
    job_ids = [j for j in job_result.scalars().all()]
    
    if not job_ids:
        return StrategyListResponse(strategies=[], total=0)
    
    query = select(Strategy).where(Strategy.job_id.in_(job_ids))
    
    if sort_by == "score":
        query = query.order_by(Strategy.score.desc().nullslast())
    elif sort_by == "win_rate":
        query = query.order_by(Strategy.win_rate.desc().nullslast())
    elif sort_by == "profit_factor":
        query = query.order_by(Strategy.profit_factor.desc().nullslast())
    else:
        query = query.order_by(Strategy.created_at.desc())
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    strategies = result.scalars().all()
    
    # Count total
    count_result = await db.execute(
        select(Strategy).where(Strategy.job_id.in_(job_ids))
    )
    total = len(count_result.scalars().all())
    
    return StrategyListResponse(strategies=strategies, total=total)


@router.get("/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(
    strategy_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get strategy details."""
    result = await db.execute(
        select(Strategy).where(Strategy.id == strategy_id)
    )
    strategy = result.scalar_one_or_none()
    
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    # Verify ownership
    job_result = await db.execute(
        select(Job).where(Job.id == strategy.job_id, Job.user_id == current_user.id)
    )
    if not job_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    return strategy


@router.get("/{strategy_id}/download")
async def download_pine_script(
    strategy_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Download strategy as .pine file."""
    result = await db.execute(
        select(Strategy).where(Strategy.id == strategy_id)
    )
    strategy = result.scalar_one_or_none()
    
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    # Verify ownership
    job_result = await db.execute(
        select(Job).where(Job.id == strategy.job_id, Job.user_id == current_user.id)
    )
    if not job_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    filename = f"{strategy.name.replace(' ', '_')}_v{strategy.version}.pine"
    
    return Response(
        content=strategy.pine_script,
        media_type="text/plain",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.get("/compare")
async def compare_strategies(
    ids: str,  # Comma-separated IDs
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Compare multiple strategies side by side."""
    strategy_ids = [int(id.strip()) for id in ids.split(",")]
    
    if len(strategy_ids) < 2 or len(strategy_ids) > 5:
        raise HTTPException(status_code=400, detail="Provide 2-5 strategy IDs to compare")
    
    # Get user's job IDs for ownership check
    job_result = await db.execute(
        select(Job.id).where(Job.user_id == current_user.id)
    )
    job_ids = set(job_result.scalars().all())
    
    result = await db.execute(
        select(Strategy).where(Strategy.id.in_(strategy_ids))
    )
    strategies = result.scalars().all()
    
    # Filter to owned strategies
    strategies = [s for s in strategies if s.job_id in job_ids]
    
    return {
        "strategies": [
            {
                "id": s.id,
                "name": s.name,
                "version": s.version,
                "win_rate": s.win_rate,
                "profit_factor": s.profit_factor,
                "max_drawdown": s.max_drawdown,
                "net_profit": s.net_profit,
                "total_trades": s.total_trades,
                "score": s.score
            }
            for s in strategies
        ],
        "metrics": ["win_rate", "profit_factor", "max_drawdown", "net_profit", "total_trades", "score"]
    }
