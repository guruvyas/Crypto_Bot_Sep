from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, Dict, Any

from app.core.database import get_db_session
from app.models.session import TradingSession, SessionMode
from app.services.session_manager import session_manager

router = APIRouter()

class SessionStartRequest(BaseModel):
    name: Optional[str] = None
    starting_balance: float = 10000.0
    session_allocation: float = 1000.0
    mode: SessionMode = SessionMode.SESSION_AMOUNT
    max_loss_limit: Optional[float] = None

class SessionResponse(BaseModel):
    success: bool
    message: str
    session: Optional[Dict[str, Any]] = None

@router.post("/start", response_model=SessionResponse)
async def start_session(
    request: SessionStartRequest,
    db: AsyncSession = Depends(get_db_session)
) -> SessionResponse:
    """Start a new trading session"""
    
    try:
        session = await session_manager.start_session(
            name=request.name,
            starting_balance=request.starting_balance,
            session_allocation=request.session_allocation,
            mode=request.mode,
            max_loss_limit=request.max_loss_limit
        )
        
        return SessionResponse(
            success=True,
            message=f"Session '{session.name}' started successfully",
            session=session.to_dict()
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start session: {e}")

@router.post("/pause", response_model=SessionResponse)
async def pause_session(
    reason: str = "Manual pause",
    db: AsyncSession = Depends(get_db_session)
) -> SessionResponse:
    """Pause the current active session"""
    
    try:
        session = await session_manager.pause_session(reason)
        
        return SessionResponse(
            success=True,
            message=f"Session '{session.name}' paused successfully",
            session=session.to_dict()
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to pause session: {e}")

@router.post("/resume", response_model=SessionResponse)
async def resume_session(
    db: AsyncSession = Depends(get_db_session)
) -> SessionResponse:
    """Resume a paused session"""
    
    try:
        session = await session_manager.resume_session()
        
        return SessionResponse(
            success=True,
            message=f"Session '{session.name}' resumed successfully",
            session=session.to_dict()
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resume session: {e}")

@router.post("/end", response_model=SessionResponse)
async def end_session(
    reason: str = "Manual end",
    db: AsyncSession = Depends(get_db_session)
) -> SessionResponse:
    """End the current session"""
    
    try:
        session = await session_manager.end_session(reason)
        
        return SessionResponse(
            success=True,
            message=f"Session '{session.name}' ended successfully. P&L: ${session.session_pnl:+,.2f}",
            session=session.to_dict()
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to end session: {e}")

@router.get("/current", response_model=Dict[str, Any])
async def get_current_session(
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """Get the current active session"""
    
    session = await session_manager.get_current_session()
    
    if not session:
        return {
            "session": None,
            "message": "No active session"
        }
    
    return {
        "session": session.to_dict(),
        "message": f"Current session: {session.name}"
    }

@router.get("/history")
async def get_session_history(
    limit: int = 10,
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """Get historical sessions"""
    
    result = await db.execute(
        select(TradingSession)
        .order_by(TradingSession.created_at.desc())
        .limit(limit)
    )
    sessions = result.scalars().all()
    
    return {
        "sessions": [session.to_dict() for session in sessions],
        "total_count": len(sessions)
    }

@router.get("/{session_id}")
async def get_session_by_id(
    session_id: int,
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """Get a specific session by ID"""
    
    result = await db.execute(
        select(TradingSession).where(TradingSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "session": session.to_dict()
    }

@router.get("/status/limits")
async def check_session_limits(
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """Check current session against risk limits"""
    
    session = await session_manager.get_current_session()
    
    if not session:
        return {
            "session": None,
            "limits_ok": True,
            "message": "No active session"
        }
    
    # Check various limits
    limits_status = {
        "max_loss_limit": {
            "current": session.session_pnl,
            "limit": -session.max_loss_limit if session.max_loss_limit else None,
            "ok": not session.max_loss_limit or session.session_pnl > -session.max_loss_limit
        },
        "session_duration": {
            "current_minutes": session.duration_minutes,
            "limit_minutes": 8 * 60,  # Default 8 hours
            "ok": session.duration_minutes < (8 * 60)
        }
    }
    
    overall_ok = all(limit["ok"] for limit in limits_status.values())
    
    return {
        "session_id": session.id,
        "limits_ok": overall_ok,
        "limits_status": limits_status,
        "message": "All limits OK" if overall_ok else "Some limits exceeded"
    }