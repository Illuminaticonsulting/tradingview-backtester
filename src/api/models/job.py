"""
Job model for backtest/generation tasks.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from ..database import Base


class JobStatus(str, enum.Enum):
    """Job status enum."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Job(Base):
    """Background job for strategy generation and backtesting."""
    
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Job configuration
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    # AI configuration
    ai_provider = Column(String(50), default="deepseek")  # deepseek, claude
    strategy_type = Column(String(100), nullable=False)  # sma_bounce, rsi_reversal, etc
    
    # Target metrics
    target_win_rate = Column(Integer, default=60)
    target_profit_factor = Column(Integer, default=150)  # 1.50 * 100
    target_max_drawdown = Column(Integer, default=20)
    
    # Execution
    max_iterations = Column(Integer, default=10)
    current_iteration = Column(Integer, default=0)
    
    # Status
    status = Column(Enum(JobStatus), default=JobStatus.PENDING)
    error_message = Column(Text, nullable=True)
    
    # Results
    best_strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=True)
    
    # Progress data (JSON blob for flexibility)
    progress_data = Column(JSON, default=dict)
    
    # Celery task ID
    celery_task_id = Column(String(100), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="jobs")
    strategies = relationship("Strategy", back_populates="job", foreign_keys="Strategy.job_id")
    watchlist_id = Column(Integer, ForeignKey("watchlists.id"), nullable=True)
    watchlist = relationship("Watchlist")
    
    def __repr__(self):
        return f"<Job {self.id}: {self.name} ({self.status.value})>"
