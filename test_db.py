#!/usr/bin/env python3
"""
Test script to check database connectivity and table creation
"""
import asyncio
from app.core.database import init_db, AsyncSessionLocal
from app.models.session import TradingSession
from app.core.config import settings
from sqlalchemy import text

async def test_database():
    print(f"Testing database connection: {settings.DATABASE_URL}")
    
    try:
        # Initialize database
        await init_db()
        print("[OK] Database initialized successfully")
        
        # Test database session
        async with AsyncSessionLocal() as db:
            print("[OK] Database session created successfully")
            
            # Test table query
            result = await db.execute(text("SELECT name FROM sqlite_master WHERE type='table';"))
            tables = result.fetchall()
            print(f"[OK] Found {len(tables)} tables:")
            for table in tables:
                print(f"  - {table[0]}")
                
        print("\n[OK] All database tests passed!")
        return True
        
    except Exception as e:
        print(f"[ERROR] Database test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_database())
    if success:
        print("\nDatabase is ready for the trading bot!")
    else:
        print("\nPlease fix database issues before starting the bot.")