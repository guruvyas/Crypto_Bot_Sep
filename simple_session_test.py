#!/usr/bin/env python3
"""
Direct session creation test to bypass config issues
"""
import asyncio
from datetime import datetime
from app.core.database import init_db, AsyncSessionLocal
from app.models.session import TradingSession, SessionStatus, SessionMode
from app.models.activity_log import ActivityLog

async def create_simple_session():
    print("Creating a simple session directly...")
    
    try:
        await init_db()
        
        async with AsyncSessionLocal() as db:
            # Create session directly without config snapshot
            session = TradingSession(
                name=f"Direct_Session_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                status=SessionStatus.ACTIVE,
                mode=SessionMode.SESSION_AMOUNT,
                starting_balance=10000.0,
                session_allocation=1000.0,
                current_balance=10000.0,
                max_loss_limit=500.0,
                max_positions=5
            )
            
            db.add(session)
            await db.commit()
            await db.refresh(session)
            
            # Add activity log
            activity_log = ActivityLog.create_session_start(
                session.id, session.name, session.session_allocation
            )
            db.add(activity_log)
            await db.commit()
            
            print(f"✅ Session created successfully: {session.name}")
            print(f"   ID: {session.id}")
            print(f"   Status: {session.status.value}")
            print(f"   Allocation: ${session.session_allocation}")
            
            return session.to_dict()
            
    except Exception as e:
        print(f"❌ Error creating session: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    result = asyncio.run(create_simple_session())
    if result:
        print("\n🎉 Session creation successful! You can now test the API.")