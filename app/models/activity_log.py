from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, Enum, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base
import enum
from datetime import datetime

class ActivityType(enum.Enum):
    SESSION_START = "session_start"
    SESSION_PAUSE = "session_pause"
    SESSION_END = "session_end"
    ORDER_SUBMITTED = "order_submitted"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_REJECTED = "order_rejected"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    STOP_LOSS_TRIGGERED = "stop_loss_triggered"
    TAKE_PROFIT_TRIGGERED = "take_profit_triggered"
    STRATEGY_SIGNAL = "strategy_signal"
    RISK_LIMIT_HIT = "risk_limit_hit"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

class ActivityLevel(enum.Enum):
    LOW = "low"      # Routine operations
    MEDIUM = "medium"  # Important events
    HIGH = "high"     # Critical events, errors
    CRITICAL = "critical"  # System failures

class ActivityLog(Base):
    __tablename__ = "activity_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("trading_sessions.id"), nullable=True)
    
    # Activity classification
    activity_type = Column(Enum(ActivityType), nullable=False, index=True)
    level = Column(Enum(ActivityLevel), default=ActivityLevel.LOW)
    
    # Human-readable message
    message = Column(Text, nullable=False)
    
    # Context
    symbol = Column(String(20), nullable=True, index=True)
    strategy_name = Column(String(50), nullable=True)
    
    # Related entity IDs
    order_id = Column(Integer, nullable=True)
    position_id = Column(Integer, nullable=True)
    
    # Structured data (JSON)
    extra_data = Column(Text, nullable=True)  # Additional structured data as JSON
    
    # Timing
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # Error details (if applicable)
    error_code = Column(String(50), nullable=True)
    error_details = Column(Text, nullable=True)
    
    def __repr__(self):
        return f"<ActivityLog(id={self.id}, type={self.activity_type.value}, level={self.level.value}, message='{self.message[:50]}...')>"
    
    @classmethod
    def create_session_start(cls, session_id: int, session_name: str, allocation: float):
        return cls(
            session_id=session_id,
            activity_type=ActivityType.SESSION_START,
            level=ActivityLevel.MEDIUM,
            message=f"Trading session '{session_name}' started with allocation of ${allocation:,.2f}"
        )
    
    @classmethod
    def create_session_end(cls, session_id: int, session_name: str, pnl: float):
        level = ActivityLevel.HIGH if pnl < 0 else ActivityLevel.MEDIUM
        return cls(
            session_id=session_id,
            activity_type=ActivityType.SESSION_END,
            level=level,
            message=f"Trading session '{session_name}' ended with P&L of ${pnl:+,.2f}"
        )
    
    @classmethod
    def create_order_submitted(cls, session_id: int, order_id: int, symbol: str, side: str, 
                              quantity: float, order_type: str, strategy_name: str = None):
        return cls(
            session_id=session_id,
            order_id=order_id,
            symbol=symbol,
            strategy_name=strategy_name,
            activity_type=ActivityType.ORDER_SUBMITTED,
            level=ActivityLevel.LOW,
            message=f"Submitted {order_type} {side} order for {quantity} {symbol}" +
                   (f" via {strategy_name} strategy" if strategy_name else "")
        )
    
    @classmethod
    def create_order_filled(cls, session_id: int, order_id: int, symbol: str, side: str,
                           quantity: float, price: float, strategy_name: str = None):
        return cls(
            session_id=session_id,
            order_id=order_id,
            symbol=symbol,
            strategy_name=strategy_name,
            activity_type=ActivityType.ORDER_FILLED,
            level=ActivityLevel.MEDIUM,
            message=f"Filled {side} order: {quantity} {symbol} at ${price:,.4f}" +
                   (f" via {strategy_name} strategy" if strategy_name else "")
        )
    
    @classmethod
    def create_position_opened(cls, session_id: int, position_id: int, symbol: str, side: str,
                              quantity: float, entry_price: float, strategy_name: str = None):
        return cls(
            session_id=session_id,
            position_id=position_id,
            symbol=symbol,
            strategy_name=strategy_name,
            activity_type=ActivityType.POSITION_OPENED,
            level=ActivityLevel.MEDIUM,
            message=f"Opened {side} position: {quantity} {symbol} at ${entry_price:,.4f}" +
                   (f" via {strategy_name} strategy" if strategy_name else "")
        )
    
    @classmethod
    def create_position_closed(cls, session_id: int, position_id: int, symbol: str, side: str,
                              quantity: float, exit_price: float, pnl: float, strategy_name: str = None):
        pnl_sign = "+" if pnl >= 0 else ""
        return cls(
            session_id=session_id,
            position_id=position_id,
            symbol=symbol,
            strategy_name=strategy_name,
            activity_type=ActivityType.POSITION_CLOSED,
            level=ActivityLevel.MEDIUM,
            message=f"Closed {side} position: {quantity} {symbol} at ${exit_price:,.4f}, P&L: {pnl_sign}${pnl:,.2f}" +
                   (f" via {strategy_name} strategy" if strategy_name else "")
        )
    
    @classmethod
    def create_strategy_signal(cls, session_id: int, strategy_name: str, symbol: str, 
                              signal_type: str, message: str):
        return cls(
            session_id=session_id,
            symbol=symbol,
            strategy_name=strategy_name,
            activity_type=ActivityType.STRATEGY_SIGNAL,
            level=ActivityLevel.LOW,
            message=f"{strategy_name} strategy generated {signal_type} signal for {symbol}: {message}"
        )
    
    @classmethod
    def create_risk_limit_hit(cls, session_id: int, limit_type: str, message: str):
        return cls(
            session_id=session_id,
            activity_type=ActivityType.RISK_LIMIT_HIT,
            level=ActivityLevel.HIGH,
            message=f"Risk limit triggered - {limit_type}: {message}"
        )
    
    @classmethod
    def create_error(cls, session_id: int, message: str, error_code: str = None, 
                    error_details: str = None, symbol: str = None):
        return cls(
            session_id=session_id,
            symbol=symbol,
            activity_type=ActivityType.ERROR,
            level=ActivityLevel.CRITICAL,
            message=f"Error: {message}",
            error_code=error_code,
            error_details=error_details
        )
    
    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "activity_type": self.activity_type.value,
            "level": self.level.value,
            "message": self.message,
            "symbol": self.symbol,
            "strategy_name": self.strategy_name,
            "order_id": self.order_id,
            "position_id": self.position_id,
            "extra_data": self.extra_data,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "error_code": self.error_code,
            "error_details": self.error_details
        }