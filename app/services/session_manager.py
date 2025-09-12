import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import json
import os

from app.core.database import AsyncSessionLocal
from app.models.session import TradingSession, SessionStatus, SessionMode
from app.models.activity_log import ActivityLog
from app.models.config_snapshot import ConfigSnapshot
from app.core.config import settings, trading_config

class SessionManager:
    _instance: Optional['SessionManager'] = None
    _current_session: Optional[TradingSession] = None
    _session_lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def get_current_session(self) -> Optional[TradingSession]:
        """Get the currently active session"""
        async with self._session_lock:
            if self._current_session is None:
                # Try to load from database
                async with AsyncSessionLocal() as db:
                    result = await db.execute(
                        select(TradingSession)
                        .where(TradingSession.status == SessionStatus.ACTIVE)
                        .order_by(TradingSession.started_at.desc())
                    )
                    self._current_session = result.scalar_one_or_none()
            
            return self._current_session
    
    async def start_session(
        self,
        name: Optional[str] = None,
        starting_balance: float = 10000.0,
        session_allocation: float = 1000.0,
        mode: SessionMode = SessionMode.SESSION_AMOUNT,
        max_loss_limit: Optional[float] = None
    ) -> TradingSession:
        """Start a new trading session"""
        async with self._session_lock:
            # Check for existing active session
            current = await self.get_current_session()
            if current:
                raise ValueError(f"Session '{current.name}' is already active. End it first.")
            
            # Generate session name if not provided
            if not name:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                name = f"Session_{timestamp}"
            
            # Create config snapshot
            async with AsyncSessionLocal() as db:
                config_snapshot = ConfigSnapshot.create_from_current_config(
                    trading_config, settings, f"Config for {name}"
                )
                db.add(config_snapshot)
                await db.commit()
                await db.refresh(config_snapshot)
                
                # Create new session
                new_session = TradingSession(
                    name=name,
                    status=SessionStatus.ACTIVE,
                    mode=mode,
                    starting_balance=starting_balance,
                    session_allocation=session_allocation,
                    current_balance=starting_balance,
                    max_loss_limit=max_loss_limit or (session_allocation * 0.5),  # Default 50% max loss
                    max_positions=trading_config.get_max_positions(),
                    config_snapshot_id=config_snapshot.id
                )
                
                db.add(new_session)
                await db.commit()
                await db.refresh(new_session)
                
                # Log session start
                activity_log = ActivityLog.create_session_start(
                    new_session.id, name, session_allocation
                )
                db.add(activity_log)
                await db.commit()
                
                self._current_session = new_session
                return new_session
    
    async def pause_session(self, reason: str = "Manual pause") -> TradingSession:
        """Pause the current active session"""
        async with self._session_lock:
            current = await self.get_current_session()
            if not current:
                raise ValueError("No active session to pause")
            
            if current.status != SessionStatus.ACTIVE:
                raise ValueError(f"Session is not active (current status: {current.status.value})")
            
            async with AsyncSessionLocal() as db:
                # Update session
                current.status = SessionStatus.PAUSED
                current.paused_at = datetime.utcnow()
                
                db.add(current)
                
                # Log the pause
                activity_log = ActivityLog(
                    session_id=current.id,
                    activity_type=ActivityLog.ActivityType.SESSION_PAUSE,
                    level=ActivityLog.ActivityLevel.MEDIUM,
                    message=f"Session '{current.name}' paused: {reason}"
                )
                db.add(activity_log)
                
                await db.commit()
                await db.refresh(current)
                
                return current
    
    async def resume_session(self) -> TradingSession:
        """Resume a paused session"""
        async with self._session_lock:
            current = await self.get_current_session()
            if not current:
                raise ValueError("No session to resume")
            
            if current.status != SessionStatus.PAUSED:
                raise ValueError(f"Session is not paused (current status: {current.status.value})")
            
            async with AsyncSessionLocal() as db:
                # Update session
                current.status = SessionStatus.ACTIVE
                current.paused_at = None
                
                db.add(current)
                
                # Log the resume
                activity_log = ActivityLog(
                    session_id=current.id,
                    activity_type=ActivityLog.ActivityType.SESSION_START,
                    level=ActivityLog.ActivityLevel.MEDIUM,
                    message=f"Session '{current.name}' resumed"
                )
                db.add(activity_log)
                
                await db.commit()
                await db.refresh(current)
                
                return current
    
    async def end_session(self, reason: str = "Manual end") -> TradingSession:
        """End the current session"""
        async with self._session_lock:
            current = await self.get_current_session()
            if not current:
                raise ValueError("No active session to end")
            
            async with AsyncSessionLocal() as db:
                # Calculate final P&L and metrics
                # TODO: This will be enhanced when we implement P&L calculation service
                
                # Update session
                current.status = SessionStatus.ENDED
                current.ended_at = datetime.utcnow()
                
                # Create session summary
                summary = {
                    "session_id": current.id,
                    "name": current.name,
                    "started_at": current.started_at.isoformat(),
                    "ended_at": current.ended_at.isoformat(),
                    "duration_minutes": current.duration_minutes,
                    "starting_balance": current.starting_balance,
                    "session_allocation": current.session_allocation,
                    "final_balance": current.current_balance,
                    "session_pnl": current.session_pnl,
                    "total_pnl": current.total_pnl,
                    "end_reason": reason,
                    "config_snapshot_id": current.config_snapshot_id
                }
                
                current.summary_json = json.dumps(summary, indent=2)
                
                db.add(current)
                
                # Log session end
                activity_log = ActivityLog.create_session_end(
                    current.id, current.name, current.session_pnl
                )
                db.add(activity_log)
                
                await db.commit()
                await db.refresh(current)
                
                # Export session summary
                await self._export_session_summary(current)
                
                self._current_session = None
                return current
    
    async def _export_session_summary(self, session: TradingSession):
        """Export session summary to JSON and CSV files"""
        try:
            # Ensure export directory exists
            os.makedirs("data/exports", exist_ok=True)
            
            timestamp = session.ended_at.strftime("%Y%m%d_%H%M%S")
            base_filename = f"session_{session.name}_{timestamp}"
            
            # Export as JSON
            json_path = f"data/exports/{base_filename}.json"
            with open(json_path, 'w') as f:
                f.write(session.summary_json)
            
            # Export as CSV (basic session info)
            csv_path = f"data/exports/{base_filename}.csv"
            with open(csv_path, 'w') as f:
                f.write("Field,Value\n")
                f.write(f"Session ID,{session.id}\n")
                f.write(f"Name,{session.name}\n")
                f.write(f"Started At,{session.started_at}\n")
                f.write(f"Ended At,{session.ended_at}\n")
                f.write(f"Duration (minutes),{session.duration_minutes}\n")
                f.write(f"Starting Balance,{session.starting_balance}\n")
                f.write(f"Session Allocation,{session.session_allocation}\n")
                f.write(f"Final Balance,{session.current_balance}\n")
                f.write(f"Session P&L,{session.session_pnl}\n")
                f.write(f"Total P&L,{session.total_pnl}\n")
                
        except Exception as e:
            # Log error but don't fail the session end
            print(f"Error exporting session summary: {e}")
    
    async def check_session_limits(self) -> bool:
        """Check if current session has hit any limits that require ending"""
        current = await self.get_current_session()
        if not current or not current.is_active:
            return False
        
        # Check max loss limit
        if current.max_loss_limit and current.session_pnl <= -current.max_loss_limit:
            await self.end_session(f"Max loss limit reached: ${current.max_loss_limit}")
            return True
        
        # Check session timeout
        session_config = trading_config.session
        timeout_hours = session_config.get('session_timeout_hours', 8)
        if current.duration_minutes > (timeout_hours * 60):
            await self.end_session(f"Session timeout after {timeout_hours} hours")
            return True
        
        return False
    
    async def update_session_pnl(self, pnl_change: float):
        """Update session P&L (called by P&L calculation service)"""
        current = await self.get_current_session()
        if current and current.is_active:
            async with AsyncSessionLocal() as db:
                current.session_pnl += pnl_change
                current.total_pnl += pnl_change
                current.current_balance = current.starting_balance + current.total_pnl
                
                db.add(current)
                await db.commit()
                
                # Check limits after P&L update
                await self.check_session_limits()

# Global session manager instance
session_manager = SessionManager()