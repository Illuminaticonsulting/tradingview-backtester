"""
Strategy model for generated Pine Scripts.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float, JSON
from sqlalchemy.orm import relationship
from datetime import datetime

from ..database import Base


class Strategy(Base):
    """Generated Pine Script strategy with metrics."""
    
    __tablename__ = "strategies"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    
    # Version within job
    version = Column(Integer, default=1)
    
    # Pine Script code
    name = Column(String(200), nullable=False)
    pine_script = Column(Text, nullable=False)
    
    # AI reasoning
    ai_reasoning = Column(Text, nullable=True)
    changes_made = Column(Text, nullable=True)
    
    # Backtest metrics
    win_rate = Column(Float, nullable=True)
    profit_factor = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=True)
    net_profit = Column(Float, nullable=True)
    total_trades = Column(Integer, nullable=True)
    sharpe_ratio = Column(Float, nullable=True)
    
    # Composite score (calculated)
    score = Column(Float, nullable=True)
    
    # Per-symbol metrics (JSON)
    symbol_metrics = Column(JSON, default=dict)
    
    # Screenshot path
    screenshot_path = Column(String(500), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    job = relationship("Job", back_populates="strategies", foreign_keys=[job_id])
    
    def __repr__(self):
        return f"<Strategy {self.name} v{self.version} (score: {self.score})>"
    
    def calculate_score(self) -> float:
        """Calculate composite score from metrics."""
        if not all([self.win_rate, self.profit_factor, self.max_drawdown]):
            return 0.0
        
        # Weighted score: 40% win rate, 35% profit factor, 25% drawdown
        wr_score = min(self.win_rate / 70, 1.0) * 40  # 70% = full points
        pf_score = min(self.profit_factor / 2.0, 1.0) * 35  # 2.0 = full points
        dd_score = max(0, (30 - self.max_drawdown) / 30) * 25  # <30% = full points
        
        self.score = wr_score + pf_score + dd_score
        return self.score
