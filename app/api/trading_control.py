from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import logging

from app.services.trading_simulator import trading_simulator

logger = logging.getLogger(__name__)
router = APIRouter()

class TradingResponse(BaseModel):
    success: bool
    message: str
    status: str

@router.post("/start", response_model=TradingResponse)
async def start_trading() -> TradingResponse:
    """Start the trading simulator"""
    
    try:
        if trading_simulator.is_running:
            return TradingResponse(
                success=False,
                message="Trading bot is already running",
                status="running"
            )
        
        await trading_simulator.start_simulation()
        
        return TradingResponse(
            success=True,
            message="Trading bot started successfully",
            status="running"
        )
        
    except Exception as e:
        logger.error(f"Failed to start trading bot: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start trading bot: {e}")

@router.post("/stop", response_model=TradingResponse)
async def stop_trading() -> TradingResponse:
    """Stop the trading simulator"""
    
    try:
        if not trading_simulator.is_running:
            return TradingResponse(
                success=False,
                message="Trading bot is not running",
                status="stopped"
            )
        
        await trading_simulator.stop_simulation()
        
        return TradingResponse(
            success=True,
            message="Trading bot stopped successfully",
            status="stopped"
        )
        
    except Exception as e:
        logger.error(f"Failed to stop trading bot: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop trading bot: {e}")

@router.get("/status", response_model=TradingResponse)
async def get_trading_status() -> TradingResponse:
    """Get current trading bot status"""
    
    try:
        status = "running" if trading_simulator.is_running else "stopped"
        message = f"Trading bot is currently {status}"
        
        return TradingResponse(
            success=True,
            message=message,
            status=status
        )
        
    except Exception as e:
        logger.error(f"Failed to get trading status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get trading status: {e}")