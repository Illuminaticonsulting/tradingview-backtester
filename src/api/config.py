"""
API Configuration - Environment-based settings
"""
from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # App
    app_name: str = "TradingView AI Backtester"
    debug: bool = False
    secret_key: str = "change-me-in-production-use-openssl-rand-hex-32"
    
    # Database
    database_url: str = "sqlite:///./backtester.db"
    
    # Redis (for Celery)
    redis_url: str = "redis://localhost:6379/0"
    
    # JWT
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24  # 24 hours
    jwt_refresh_expire_days: int = 7
    
    # Encryption key for credentials (Fernet)
    encryption_key: Optional[str] = None
    
    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:8000"
    
    # Rate limiting
    rate_limit_per_minute: int = 60
    
    # AI Providers (defaults, users provide their own)
    default_ai_provider: str = "deepseek"
    
    # TradingView
    tv_base_url: str = "https://www.tradingview.com"
    
    class Config:
        env_file = ".env"
        env_prefix = "BACKTESTER_"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
