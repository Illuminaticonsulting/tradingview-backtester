"""
Watchlist models for symbols management.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime

from ..database import Base


class Watchlist(Base):
    """User watchlist containing symbols to backtest."""
    
    __tablename__ = "watchlists"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Metadata
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    source = Column(String(50), default="manual")  # manual, url, csv
    source_url = Column(String(500), nullable=True)  # Original TradingView URL
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="watchlists")
    symbols = relationship("WatchlistSymbol", back_populates="watchlist", cascade="all, delete-orphan")
    
    @property
    def symbol_count(self) -> int:
        return len(self.symbols)
    
    def __repr__(self):
        return f"<Watchlist {self.name} ({self.symbol_count} symbols)>"


class WatchlistSymbol(Base):
    """Individual symbol in a watchlist."""
    
    __tablename__ = "watchlist_symbols"
    
    id = Column(Integer, primary_key=True, index=True)
    watchlist_id = Column(Integer, ForeignKey("watchlists.id"), nullable=False)
    
    # Symbol info
    symbol = Column(String(50), nullable=False)  # e.g., BTCUSDT.P
    exchange = Column(String(50), nullable=True)  # e.g., BYBIT
    full_symbol = Column(String(100), nullable=False)  # e.g., BYBIT:BTCUSDT.P
    
    # Category
    category = Column(String(50), nullable=True)  # crypto, stocks, forex, etc
    
    # Order in watchlist
    position = Column(Integer, default=0)
    
    # Relationships
    watchlist = relationship("Watchlist", back_populates="symbols")
    
    def __repr__(self):
        return f"<Symbol {self.full_symbol}>"
