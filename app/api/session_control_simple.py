from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
import logging

from app.core.database import get_db_session, AsyncSessionLocal
from app.models.session import TradingSession, SessionMode, SessionStatus
from app.models.activity_log import ActivityLog
from app.services.portfolio_service import portfolio_service
from app.services.trading_simulator import trading_simulator

logger = logging.getLogger(__name__)
router = APIRouter()

class SessionStartRequest(BaseModel):
    name: Optional[str] = None
    starting_balance: float = 10000.0
    session_allocation: float = 1000.0
    mode: SessionMode = SessionMode.SESSION_AMOUNT
    max_loss_limit: Optional[float] = None
    duration_hours: Optional[float] = None

class SessionResponse(BaseModel):
    success: bool
    message: str
    session: Optional[Dict[str, Any]] = None

@router.post("/start", response_model=SessionResponse)
async def start_session_simple(
    request: SessionStartRequest,
    db: AsyncSession = Depends(get_db_session)
) -> SessionResponse:
    """Start a new trading session - simplified version"""
    
    try:
        # Check for existing active session
        result = await db.execute(
            select(TradingSession).where(TradingSession.status == SessionStatus.ACTIVE)
        )
        existing_session = result.scalar_one_or_none()
        
        if existing_session:
            raise HTTPException(
                status_code=400, 
                detail=f"Session '{existing_session.name}' is already active. End it first."
            )
        
        # Get real portfolio balance from Gemini
        try:
            portfolio_value = await portfolio_service.get_total_portfolio_value()
            available_cash = await portfolio_service.get_available_cash()
        except Exception as e:
            raise HTTPException(
                status_code=500, 
                detail=f"Could not fetch portfolio balance from Gemini: {e}"
            )
        
        # Validate session allocation against available balance
        if request.session_allocation > available_cash:
            raise HTTPException(
                status_code=400,
                detail=f"Session allocation ${request.session_allocation:,.2f} exceeds available cash ${available_cash:,.2f}"
            )
        
        # Generate session name if not provided - include microseconds for uniqueness
        if request.name:
            session_name = request.name
        else:
            now = datetime.now()
            session_name = f"Session_{now.strftime('%Y%m%d_%H%M%S')}_{now.microsecond:06d}"
        
        # Create new session with real portfolio data
        new_session = TradingSession(
            name=session_name,
            status=SessionStatus.ACTIVE,
            mode=request.mode,
            starting_balance=portfolio_value,  # Use real portfolio value
            session_allocation=request.session_allocation,
            current_balance=portfolio_value,   # Use real portfolio value
            max_loss_limit=request.max_loss_limit or (request.session_allocation * 0.5),
            max_positions=5,  # Default value
        )
        
        db.add(new_session)
        await db.commit()
        await db.refresh(new_session)
        
        # Log session start with real portfolio data
        activity_log = ActivityLog.create_session_start(
            new_session.id, 
            f"{session_name} with ${portfolio_value:,.2f} portfolio balance", 
            request.session_allocation
        )
        db.add(activity_log)
        await db.commit()
        
        # Start trading simulation
        try:
            await trading_simulator.start_simulation()
        except Exception as e:
            logger.warning(f"Failed to start trading simulator: {e}")
        
        return SessionResponse(
            success=True,
            message=f"Session '{session_name}' started successfully with trading simulation",
            session=new_session.to_dict()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start session: {e}")

@router.get("/current")
async def get_current_session_simple(
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """Get the current active session - simplified version"""
    
    result = await db.execute(
        select(TradingSession)
        .where(TradingSession.status == SessionStatus.ACTIVE)
        .order_by(TradingSession.started_at.desc())
    )
    session = result.scalar_one_or_none()
    
    if not session:
        return {"session": None, "message": "No active session"}
    
    return {"session": session.to_dict(), "message": f"Current session: {session.name}"}

@router.post("/end", response_model=SessionResponse)
async def end_session_simple(
    db: AsyncSession = Depends(get_db_session)
) -> SessionResponse:
    """End the current active session"""
    
    try:
        # Get current active session
        result = await db.execute(
            select(TradingSession).where(TradingSession.status == SessionStatus.ACTIVE)
        )
        current_session = result.scalar_one_or_none()
        
        if not current_session:
            raise HTTPException(status_code=404, detail="No active session to end")
        
        # End the session
        current_session.status = SessionStatus.ENDED
        current_session.ended_at = datetime.now()
        
        await db.commit()
        await db.refresh(current_session)
        
        # Stop trading simulation when session ends
        try:
            await trading_simulator.stop_simulation()
        except Exception as e:
            logger.warning(f"Failed to stop trading simulator: {e}")
        
        # Log session end
        activity_log = ActivityLog.create_session_end(
            current_session.id, 
            current_session.name,
            current_session.session_pnl
        )
        db.add(activity_log)
        await db.commit()
        
        return SessionResponse(
            success=True,
            message=f"Session '{current_session.name}' ended successfully",
            session=current_session.to_dict()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to end session: {e}")