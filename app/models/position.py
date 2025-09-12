from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, Enum, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base
import enum
from datetime import datetime

class PositionSide(enum.Enum):
    LONG = "long"
    SHORT = "short"

class PositionStatus(enum.Enum):
    OPEN = "open"
    CLOSED = "closed"
    PARTIALLY_CLOSED = "partially_closed"

class Position(Base):
    __tablename__ = "positions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("trading_sessions.id"), nullable=False)
    
    # Position identification
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(Enum(PositionSide), nullable=False)
    status = Column(Enum(PositionStatus), default=PositionStatus.OPEN)
    
    # Quantities
    quantity = Column(Float, nullable=False)
    remaining_quantity = Column(Float, nullable=False)
    
    # Entry details
    entry_price = Column(Float, nullable=False)
    entry_value = Column(Float, nullable=False)  # Total value at entry
    entry_fees = Column(Float, default=0.0)
    
    # Exit details (populated when position is closed)
    exit_price = Column(Float, nullable=True)
    exit_value = Column(Float, nullable=True)
    exit_fees = Column(Float, default=0.0)
    
    # P&L calculations
    unrealized_pnl = Column(Float, default=0.0)
    realized_pnl = Column(Float, default=0.0)
    total_pnl = Column(Float, default=0.0)
    
    # Current market data
    current_price = Column(Float, nullable=True)
    last_price_update = Column(DateTime(timezone=True), nullable=True)
    
    # Risk management
    stop_loss_price = Column(Float, nullable=True)
    take_profit_price = Column(Float, nullable=True)
    stop_loss_order_id = Column(Integer, nullable=True)
    take_profit_order_id = Column(Integer, nullable=True)
    
    # Strategy context
    strategy_name = Column(String(50), nullable=True)
    entry_signal = Column(Text, nullable=True)  # JSON string with entry signal details
    exit_signal = Column(Text, nullable=True)   # JSON string with exit signal details
    
    # Timestamps
    opened_at = Column(DateTime(timezone=True), server_default=func.now())
    closed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Risk metrics
    max_drawdown = Column(Float, default=0.0)
    max_runup = Column(Float, default=0.0)
    
    def __repr__(self):
        return f"<Position(id={self.id}, symbol={self.symbol}, side={self.side.value}, quantity={self.quantity}, pnl={self.total_pnl})>"
    
    @property
    def is_open(self) -> bool:
        return self.status in [PositionStatus.OPEN, PositionStatus.PARTIALLY_CLOSED]
    
    @property
    def is_long(self) -> bool:
        return self.side == PositionSide.LONG
    
    @property
    def is_short(self) -> bool:
        return self.side == PositionSide.SHORT
    
    @property
    def duration_minutes(self) -> int:
        if not self.opened_at:
            return 0
        
        end_time = self.closed_at or datetime.utcnow()
        duration = end_time - self.opened_at
        return int(duration.total_seconds() / 60)
    
    def update_unrealized_pnl(self, current_price: float):
        """Update unrealized P&L based on current market price"""
        self.current_price = current_price
        self.last_price_update = datetime.utcnow()
        
        if self.is_long:
            price_diff = current_price - self.entry_price
        else:
            price_diff = self.entry_price - current_price
        
        self.unrealized_pnl = (price_diff * self.remaining_quantity) - self.entry_fees
        self.total_pnl = self.realized_pnl + self.unrealized_pnl
        
        # Update risk metrics
        if self.total_pnl < 0 and abs(self.total_pnl) > self.max_drawdown:
            self.max_drawdown = abs(self.total_pnl)
        elif self.total_pnl > 0 and self.total_pnl > self.max_runup:
            self.max_runup = self.total_pnl
    
    def close_position(self, exit_price: float, exit_quantity: float, exit_fees: float = 0.0):
        """Close position partially or fully"""
        if exit_quantity >= self.remaining_quantity:
            # Full close
            self.status = PositionStatus.CLOSED
            self.remaining_quantity = 0
            self.closed_at = datetime.utcnow()
        else:
            # Partial close
            self.status = PositionStatus.PARTIALLY_CLOSED
            self.remaining_quantity -= exit_quantity
        
        # Calculate realized P&L for the closed quantity
        if self.is_long:
            price_diff = exit_price - self.entry_price
        else:
            price_diff = self.entry_price - exit_price
        
        realized_pnl_for_exit = (price_diff * exit_quantity) - exit_fees
        self.realized_pnl += realized_pnl_for_exit
        
        # Update exit details
        if self.status == PositionStatus.CLOSED:
            self.exit_price = exit_price
            self.exit_value = exit_price * exit_quantity
            self.exit_fees += exit_fees
            self.unrealized_pnl = 0
        
        self.total_pnl = self.realized_pnl + self.unrealized_pnl
    
    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "status": self.status.value,
            "quantity": self.quantity,
            "remaining_quantity": self.remaining_quantity,
            "entry_price": self.entry_price,
            "entry_value": self.entry_value,
            "exit_price": self.exit_price,
            "exit_value": self.exit_value,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "total_pnl": self.total_pnl,
            "current_price": self.current_price,
            "stop_loss_price": self.stop_loss_price,
            "take_profit_price": self.take_profit_price,
            "strategy_name": self.strategy_name,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "duration_minutes": self.duration_minutes,
            "max_drawdown": self.max_drawdown,
            "max_runup": self.max_runup
        }