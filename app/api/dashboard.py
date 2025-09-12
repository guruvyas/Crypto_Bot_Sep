from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from app.core.database import get_db_session
from app.models.session import TradingSession, SessionStatus
from app.models.order import Order, OrderStatus
from app.models.position import Position, PositionStatus
from app.models.fill import Fill
from app.models.activity_log import ActivityLog, ActivityLevel
from app.services.portfolio_service import portfolio_service

router = APIRouter()

@router.get("/dashboard")
async def get_dashboard_data(
    session_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """Get comprehensive dashboard data for the UI"""
    
    # Get current or specified session
    if session_id:
        result = await db.execute(select(TradingSession).where(TradingSession.id == session_id))
        current_session = result.scalar_one_or_none()
    else:
        result = await db.execute(
            select(TradingSession)
            .where(TradingSession.status == SessionStatus.ACTIVE)
            .order_by(TradingSession.started_at.desc())
        )
        current_session = result.scalar_one_or_none()
    
    if not current_session:
        return {
            "session": None,
            "portfolio": None,
            "positions": [],
            "orders": [],
            "recent_fills": [],
            "activity_feed": [],
            "market_summary": {}
        }
    
    # Get portfolio summary
    portfolio = await _get_portfolio_summary(current_session, db)
    
    # Get detailed coin holdings
    coin_holdings = await _get_coin_holdings(db)
    
    # Get open positions
    positions = await _get_open_positions(current_session.id, db)
    
    # Get active orders
    orders = await _get_active_orders(current_session.id, db)
    
    # Get recent fills
    recent_fills = await _get_recent_fills(current_session.id, db)
    
    # Get activity feed
    activity_feed = await _get_activity_feed(current_session.id, db)
    
    # Get market summary
    market_summary = await _get_market_summary(db)
    
    return {
        "session": current_session.to_dict(),
        "portfolio": portfolio,
        "coin_holdings": coin_holdings,
        "positions": [pos.to_dict() for pos in positions],
        "orders": [order.to_dict() for order in orders],
        "recent_fills": [fill.to_dict() for fill in recent_fills],
        "activity_feed": [activity.to_dict() for activity in activity_feed],
        "market_summary": market_summary
    }

async def _get_portfolio_summary(session: TradingSession, db: AsyncSession) -> Dict[str, Any]:
    """Calculate portfolio summary metrics with real Gemini data"""
    
    # Get real portfolio balance from Gemini
    try:
        real_portfolio_balance = await portfolio_service.get_portfolio_balance()
        current_portfolio_value = real_portfolio_balance.get("total_usd_value", 0.0)
        available_cash = await portfolio_service.get_available_cash()
        portfolio_source = real_portfolio_balance.get("source", "unknown")
    except Exception as e:
        # Fallback to session data if Gemini is unavailable
        current_portfolio_value = session.starting_balance + session.total_pnl
        available_cash = session.session_allocation
        portfolio_source = "session_fallback"
    
    # Get total value of open positions
    result = await db.execute(
        select(func.sum(Position.total_pnl))
        .where(
            and_(
                Position.session_id == session.id,
                Position.status.in_([PositionStatus.OPEN, PositionStatus.PARTIALLY_CLOSED])
            )
        )
    )
    open_positions_pnl = result.scalar() or 0.0
    
    # Get count of open positions
    result = await db.execute(
        select(func.count(Position.id))
        .where(
            and_(
                Position.session_id == session.id,
                Position.status.in_([PositionStatus.OPEN, PositionStatus.PARTIALLY_CLOSED])
            )
        )
    )
    open_positions_count = result.scalar() or 0
    
    # Calculate available buying power based on real cash minus used funds
    used_funds = abs(open_positions_pnl) if open_positions_pnl < 0 else 0
    available_buying_power = max(0, min(available_cash, session.session_allocation) - used_funds)
    
    # Calculate day change based on current vs starting balance
    day_change = current_portfolio_value - session.starting_balance
    day_change_pct = (day_change / session.starting_balance * 100) if session.starting_balance > 0 else 0
    
    return {
        "total_value": current_portfolio_value,
        "session_allocation": session.session_allocation,
        "available_buying_power": available_buying_power,
        "available_cash": available_cash,
        "session_pnl": session.session_pnl,
        "total_pnl": session.total_pnl,
        "day_change": day_change,
        "day_change_pct": day_change_pct,
        "open_positions_count": open_positions_count,
        "open_positions_pnl": open_positions_pnl,
        "session_duration_minutes": session.duration_minutes,
        "max_loss_limit": session.max_loss_limit,
        "risk_utilization_pct": (abs(session.session_pnl) / session.max_loss_limit * 100) if session.max_loss_limit > 0 else 0,
        "portfolio_source": portfolio_source  # Indicate data source
    }

async def _get_open_positions(session_id: int, db: AsyncSession) -> List[Position]:
    """Get all open positions for the session"""
    result = await db.execute(
        select(Position)
        .where(
            and_(
                Position.session_id == session_id,
                Position.status.in_([PositionStatus.OPEN, PositionStatus.PARTIALLY_CLOSED])
            )
        )
        .order_by(Position.opened_at.desc())
    )
    return result.scalars().all()

async def _get_active_orders(session_id: int, db: AsyncSession) -> List[Order]:
    """Get all active orders for the session"""
    result = await db.execute(
        select(Order)
        .where(
            and_(
                Order.session_id == session_id,
                Order.status.in_([
                    OrderStatus.PENDING,
                    OrderStatus.SUBMITTED,
                    OrderStatus.PARTIALLY_FILLED
                ])
            )
        )
        .order_by(Order.created_at.desc())
    )
    return result.scalars().all()

async def _get_recent_fills(session_id: int, db: AsyncSession, limit: int = 10) -> List[Fill]:
    """Get recent fills for the session"""
    result = await db.execute(
        select(Fill)
        .where(Fill.session_id == session_id)
        .order_by(Fill.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()

async def _get_activity_feed(session_id: int, db: AsyncSession, limit: int = 20) -> List[ActivityLog]:
    """Get recent activity for the session"""
    result = await db.execute(
        select(ActivityLog)
        .where(ActivityLog.session_id == session_id)
        .order_by(ActivityLog.timestamp.desc())
        .limit(limit)
    )
    return result.scalars().all()

async def _get_coin_holdings(db: AsyncSession) -> Dict[str, Any]:
    """Get detailed coin holdings from Gemini API"""
    try:
        # Get real portfolio balance from Gemini
        portfolio_balance = await portfolio_service.get_portfolio_balance()
        holdings = portfolio_balance.get("balances", {})
        
        # Format holdings for frontend display
        formatted_holdings = []
        total_usd_value = 0
        
        for currency, data in holdings.items():
            amount = data.get("amount", 0)
            available = data.get("available", 0)
            usd_value = data.get("usd_value", 0)
            
            if amount > 0:  # Only show currencies with balance
                formatted_holdings.append({
                    "currency": currency,
                    "amount": amount,
                    "available": available,
                    "usd_value": usd_value,
                    "percentage": 0  # Will calculate below
                })
                total_usd_value += usd_value
        
        # Calculate percentages
        for holding in formatted_holdings:
            if total_usd_value > 0:
                holding["percentage"] = (holding["usd_value"] / total_usd_value) * 100
        
        # Sort by USD value descending
        formatted_holdings.sort(key=lambda x: x["usd_value"], reverse=True)
        
        return {
            "holdings": formatted_holdings,
            "total_usd_value": total_usd_value,
            "source": portfolio_balance.get("source", "unknown"),
            "last_updated": portfolio_balance.get("last_updated")
        }
        
    except Exception as e:
        # Fallback to empty holdings if API fails
        return {
            "holdings": [],
            "total_usd_value": 0,
            "source": "error",
            "error": str(e),
            "last_updated": datetime.utcnow().isoformat()
        }

async def _get_market_summary(db: AsyncSession) -> Dict[str, Any]:
    """Get market summary data"""
    # This would typically include market statistics, top movers, etc.
    # For now, return basic placeholder data
    return {
        "market_status": "open",  # This would come from market hours check
        "active_symbols": [],     # This would come from active subscriptions
        "last_updated": datetime.utcnow().isoformat()
    }

@router.get("/portfolio/performance")
async def get_portfolio_performance(
    session_id: Optional[int] = None,
    period: str = "1d",  # 1d, 1w, 1m, 3m, 1y, all
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """Get portfolio performance data for charts"""
    
    # Get session
    if session_id:
        result = await db.execute(select(TradingSession).where(TradingSession.id == session_id))
        session = result.scalar_one_or_none()
    else:
        result = await db.execute(
            select(TradingSession)
            .where(TradingSession.status == SessionStatus.ACTIVE)
            .order_by(TradingSession.started_at.desc())
        )
        session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=404, detail="No session found")
    
    # Calculate time range based on period
    end_time = datetime.utcnow()
    if period == "1d":
        start_time = end_time - timedelta(days=1)
    elif period == "1w":
        start_time = end_time - timedelta(weeks=1)
    elif period == "1m":
        start_time = end_time - timedelta(days=30)
    elif period == "3m":
        start_time = end_time - timedelta(days=90)
    elif period == "1y":
        start_time = end_time - timedelta(days=365)
    else:  # all
        start_time = session.started_at
    
    # Get fills in the time range for P&L calculation
    result = await db.execute(
        select(Fill)
        .where(
            and_(
                Fill.session_id == session.id,
                Fill.created_at >= start_time,
                Fill.created_at <= end_time
            )
        )
        .order_by(Fill.created_at)
    )
    fills = result.scalars().all()
    
    # Build performance timeline
    performance_data = []
    cumulative_pnl = 0
    
    for fill in fills:
        cumulative_pnl += fill.net_proceeds
        performance_data.append({
            "timestamp": fill.created_at.isoformat(),
            "cumulative_pnl": cumulative_pnl,
            "fill_value": fill.net_proceeds,
            "symbol": fill.symbol
        })
    
    return {
        "period": period,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "performance_data": performance_data,
        "total_return": cumulative_pnl,
        "total_return_pct": (cumulative_pnl / session.starting_balance * 100) if session.starting_balance > 0 else 0
    }

@router.get("/positions/{position_id}")
async def get_position_details(
    position_id: int,
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """Get detailed information about a specific position"""
    
    result = await db.execute(select(Position).where(Position.id == position_id))
    position = result.scalar_one_or_none()
    
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")
    
    # Get related orders
    result = await db.execute(
        select(Order)
        .where(Order.session_id == position.session_id)
        .where(Order.symbol == position.symbol)
        .order_by(Order.created_at)
    )
    related_orders = result.scalars().all()
    
    # Get related fills
    order_ids = [order.id for order in related_orders]
    result = await db.execute(
        select(Fill)
        .where(Fill.order_id.in_(order_ids))
        .order_by(Fill.created_at)
    )
    related_fills = result.scalars().all()
    
    return {
        "position": position.to_dict(),
        "related_orders": [order.to_dict() for order in related_orders],
        "related_fills": [fill.to_dict() for fill in related_fills]
    }

@router.get("/orders/{order_id}")
async def get_order_details(
    order_id: int,
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """Get detailed information about a specific order"""
    
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Get related fills
    result = await db.execute(
        select(Fill)
        .where(Fill.order_id == order.id)
        .order_by(Fill.created_at)
    )
    fills = result.scalars().all()
    
    return {
        "order": order.to_dict(),
        "fills": [fill.to_dict() for fill in fills]
    }

@router.post("/portfolio/sync")
async def sync_portfolio_balance() -> Dict[str, Any]:
    """Manually sync portfolio balance from Gemini API"""
    
    try:
        # Force refresh portfolio data from Gemini
        fresh_balance = await portfolio_service.refresh_balance()
        
        return {
            "success": True,
            "message": "Portfolio balance synchronized successfully",
            "portfolio_data": fresh_balance,
            "sync_time": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to sync portfolio balance: {e}"
        )

@router.get("/portfolio/status")
async def get_portfolio_status() -> Dict[str, Any]:
    """Get current portfolio status and connection info"""
    
    try:
        balance_data = await portfolio_service.get_portfolio_balance()
        
        return {
            "success": True,
            "portfolio_source": balance_data.get("source", "unknown"),
            "total_usd_value": balance_data.get("total_usd_value", 0.0),
            "last_updated": balance_data.get("last_updated"),
            "balances": balance_data.get("balances", {}),
            "connection_status": "connected" if balance_data.get("source") == "gemini_live" else "sandbox"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "connection_status": "error"
        }