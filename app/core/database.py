from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import MetaData
from app.core.config import settings
import os

class Base(DeclarativeBase):
    metadata = MetaData()

# Convert sqlite URL to async
database_url = settings.DATABASE_URL
if database_url.startswith("sqlite:///"):
    database_url = database_url.replace("sqlite:///", "sqlite+aiosqlite:///")

engine = create_async_engine(
    database_url,
    echo=settings.DEBUG,
    future=True
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def init_db():
    # Ensure data directory exists
    os.makedirs("data/db", exist_ok=True)
    
    # Import all models to ensure they're registered
    from app.models import session, order, position, fill, activity_log, price_bar, config_snapshot
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db_session():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()