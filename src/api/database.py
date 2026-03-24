"""
Database configuration and session management.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from .config import get_settings

settings = get_settings()

# Convert sync URL to async
database_url = settings.database_url
if database_url.startswith("sqlite:"):
    database_url = database_url.replace("sqlite:", "sqlite+aiosqlite:", 1)
elif database_url.startswith("postgresql:"):
    database_url = database_url.replace("postgresql:", "postgresql+asyncpg:", 1)

engine = create_async_engine(
    database_url,
    echo=settings.debug,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()


async def init_db():
    """Initialize database tables."""
    from . import models  # Import models to register them
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    """Dependency for getting database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
