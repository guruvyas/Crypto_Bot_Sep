import asyncio
import random
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from app.models.session import TradingSession, SessionStatus
from app.models.order import Order, OrderStatus, OrderType, OrderSide
from app.models.fill import Fill
from app.models.position import Position, PositionStatus, PositionSide
from app.models.activity_log import ActivityLog, ActivityType, ActivityLevel
from app.core.database import AsyncSessionLocal
from app.services.gemini_client import gemini_client

logger = logging.getLogger(__name__)

class TradingSimulator:
    def __init__(self):
        self.is_running = False
        self.simulation_task = None
        self._stop_event = asyncio.Event()
        
    async def start_simulation(self):
        """Start the trading simulation in the background"""
        if self.is_running:
            return
            
        self.is_running = True
        self._stop_event.clear()
        self.simulation_task = asyncio.create_task(self._simulation_loop())
        logger.info("Trading simulation started")
        
    async def stop_simulation(self):
        """Stop the trading simulation"""
        if not self.is_running:
            return
            
        self.is_running = False
        self._stop_event.set()
        
        if self.simulation_task:
            await self.simulation_task
            
        logger.info("Trading simulation stopped")
        
    async def _simulation_loop(self):
        """Main simulation loop"""
        while self.is_running:
            try:
                async with AsyncSessionLocal() as db:
                    # Get active sessions
                    result = await db.execute(
                        select(TradingSession).where(TradingSession.status == SessionStatus.ACTIVE)
                    )
                    active_sessions = result.scalars().all()
                    
                    for session in active_sessions:
                        await self._simulate_session_activity(session, db)
                        
                    await db.commit()
                    
            except Exception as e:
                logger.error(f"Error in simulation loop: {e}")
                
            # Wait before next simulation cycle (30-120 seconds)
            wait_time = random.uniform(30, 120)
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=wait_time)
                break  # Stop event was set
            except asyncio.TimeoutError:
                continue  # Continue simulation
                
    async def _simulate_session_activity(self, session: TradingSession, db: AsyncSession):
        """Simulate trading activity for a specific session"""
        
        # 30% chance of generating activity each cycle
        if random.random() > 0.3:
            return
            
        activity_types = [
            "strategy_signal",
            "market_analysis", 
            "position_update",
            "order_simulation"
        ]
        
        activity_type = random.choice(activity_types)
        
        if activity_type == "strategy_signal":
            await self._simulate_strategy_signal(session, db)
        elif activity_type == "market_analysis":
            await self._simulate_market_analysis(session, db)
        elif activity_type == "position_update":
            await self._simulate_position_update(session, db)
        elif activity_type == "order_simulation":
            await self._simulate_order_activity(session, db)
            
    async def _simulate_strategy_signal(self, session: TradingSession, db: AsyncSession):
        """Simulate strategy signal generation"""
        
        symbols = ["BTCUSD", "ETHUSD", "LTCUSD"]
        symbol = random.choice(symbols)
        
        signal_types = [
            ("BUY", "Strong upward momentum detected"),
            ("SELL", "Resistance level reached, taking profits"),
            ("HOLD", "Waiting for better entry point"),
            ("MONITOR", "Watching for breakout pattern")
        ]
        
        signal_type, message = random.choice(signal_types)
        
        activity = ActivityLog(
            session_id=session.id,
            activity_type=ActivityType.INFO,
            level=ActivityLevel.LOW,
            symbol=symbol,
            strategy_name="Momentum Strategy",
            message=f"Strategy Signal: {signal_type} - {message}",
            timestamp=datetime.utcnow()
        )
        
        db.add(activity)
        
    async def _simulate_market_analysis(self, session: TradingSession, db: AsyncSession):
        """Simulate market analysis activities"""
        
        analyses = [
            "Market volatility increased by 15% in last hour",
            "Strong support level holding at current price",
            "Volume spike detected, potential breakout incoming",
            "RSI indicating oversold conditions",
            "Moving averages showing bullish crossover",
            "Order book analysis shows strong bid support"
        ]
        
        analysis = random.choice(analyses)
        
        activity = ActivityLog(
            session_id=session.id,
            activity_type=ActivityType.INFO,
            level=ActivityLevel.LOW,
            message=f"Market Analysis: {analysis}",
            timestamp=datetime.utcnow()
        )
        
        db.add(activity)
        
    async def _simulate_position_update(self, session: TradingSession, db: AsyncSession):
        """Simulate position monitoring updates"""
        
        # Get current positions for this session
        result = await db.execute(
            select(Position).where(
                Position.session_id == session.id,
                Position.status == PositionStatus.OPEN
            )
        )
        positions = result.scalars().all()
        
        if not positions:
            return
            
        position = random.choice(positions)
        
        # Simulate small PnL changes
        pnl_change = random.uniform(-50, 100)
        current_price = position.entry_price * (1 + random.uniform(-0.02, 0.03))
        
        updates = [
            f"Position {position.symbol} updated: Current P&L ${pnl_change:+.2f}",
            f"Position {position.symbol} price update: ${current_price:.2f}",
            f"Stop loss monitoring for {position.symbol} position",
            f"Position {position.symbol} showing {'+' if pnl_change > 0 else ''}${pnl_change:.2f} unrealized P&L"
        ]
        
        update = random.choice(updates)
        
        activity = ActivityLog(
            session_id=session.id,
            activity_type=ActivityType.INFO,
            level=ActivityLevel.LOW,
            position_id=position.id,
            symbol=position.symbol,
            message=update,
            timestamp=datetime.utcnow()
        )
        
        db.add(activity)
        
    async def _simulate_order_activity(self, session: TradingSession, db: AsyncSession):
        """Simulate order placement and monitoring"""
        
        symbols = ["BTCUSD", "ETHUSD", "LTCUSD"]
        symbol = random.choice(symbols)
        
        try:
            # Get current market price from Gemini
            ticker = await gemini_client.get_ticker(symbol)
            current_price = float(ticker.get('last', 50000))
        except:
            current_price = 50000  # Fallback
            
        order_activities = [
            f"Analyzing entry point for {symbol} at ${current_price:,.2f}",
            f"Order parameters calculated for {symbol}: Qty 0.01, Price ${current_price * 0.99:,.2f}",
            f"Risk assessment completed for {symbol} trade",
            f"Waiting for optimal entry conditions on {symbol}",
            f"Order simulation: Would place limit buy for {symbol} at ${current_price * 0.98:,.2f}",
            f"Position sizing calculated: Risk $50 on {symbol} trade"
        ]
        
        order_activity = random.choice(order_activities)
        
        activity = ActivityLog(
            session_id=session.id,
            activity_type=ActivityType.INFO,
            level=ActivityLevel.LOW,
            symbol=symbol,
            strategy_name="Demo Strategy",
            message=f"Order Management: {order_activity}",
            timestamp=datetime.utcnow()
        )
        
        db.add(activity)

# Global simulator instance
trading_simulator = TradingSimulator()