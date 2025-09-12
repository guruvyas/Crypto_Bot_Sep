#!/usr/bin/env python3
"""
Test script to debug the session manager directly
"""
import asyncio
from app.services.session_manager import session_manager
from app.core.database import init_db

async def test_session_manager():
    print("Testing session manager...")
    
    try:
        # Initialize database
        print("1. Initializing database...")
        await init_db()
        print("   Database initialized OK")
        
        # Test getting current session
        print("2. Getting current session...")
        current = await session_manager.get_current_session()
        print(f"   Current session: {current}")
        
        # Test starting a session
        print("3. Starting a new session...")
        session = await session_manager.start_session(
            name="Test Session",
            starting_balance=10000.0,
            session_allocation=1000.0
        )
        print(f"   Session created: {session}")
        
        print("[SUCCESS] Session manager test completed!")
        
    except Exception as e:
        print(f"[ERROR] Session manager test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_session_manager())