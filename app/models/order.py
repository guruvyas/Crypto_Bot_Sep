from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, Enum, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum
from datetime import datetime

class OrderType(enum.Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"

class OrderSide(enum.Enum):
    BUY = "buy"
    SELL = "sell"

class OrderStatus(enum.Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"

class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("trading_sessions.id"), nullable=False)
    
    # Order identification
    client_order_id = Column(String(255), unique=True, nullable=False)
    exchange_order_id = Column(String(255), nullable=True, index=True)
    
    # Order details
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(Enum(OrderSide), nullable=False)
    order_type = Column(Enum(OrderType), nullable=False)
    status = Column(Enum(OrderStatus), default=OrderStatus.PENDING)
    
    # Quantities and prices
    quantity = Column(Float, nullable=False)
    filled_quantity = Column(Float, default=0.0)
    remaining_quantity = Column(Float, nullable=False)
    
    price = Column(Float, nullable=True)  # Null for market orders
    stop_price = Column(Float, nullable=True)  # For stop orders
    average_fill_price = Column(Float, nullable=True)
    
    # Financial
    total_value = Column(Float, nullable=True)  # Total value when filled
    fees = Column(Float, default=0.0)
    
    # Bracket order relationships
    parent_order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    stop_loss_order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    take_profit_order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    
    # Strategy context
    strategy_name = Column(String(50), nullable=True)
    strategy_signal = Column(Text, nullable=True)  # JSON string with signal details
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    filled_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Exchange response
    exchange_response = Column(Text, nullable=True)  # Raw JSON response from exchange
    rejection_reason = Column(Text, nullable=True)
    
    # Retry tracking
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    
    # Relationships
    parent_order = relationship("Order", remote_side=[id], foreign_keys=[parent_order_id])
    stop_loss_order = relationship("Order", remote_side=[id], foreign_keys=[stop_loss_order_id])
    take_profit_order = relationship("Order", remote_side=[id], foreign_keys=[take_profit_order_id])
    fills = relationship("Fill", back_populates="order")
    
    def __repr__(self):
        return f"<Order(id={self.id}, symbol={self.symbol}, side={self.side.value}, status={self.status.value})>"
    
    @property
    def is_filled(self) -> bool:
        return self.status == OrderStatus.FILLED
    
    @property
    def is_active(self) -> bool:
        return self.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED]
    
    @property
    def fill_percentage(self) -> float:
        if self.quantity == 0:
            return 0.0
        return (self.filled_quantity / self.quantity) * 100
    
    def calculate_remaining_quantity(self):
        """Update remaining quantity based on filled quantity"""
        self.remaining_quantity = max(0, self.quantity - self.filled_quantity)
    
    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "client_order_id": self.client_order_id,
            "exchange_order_id": self.exchange_order_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "status": self.status.value,
            "quantity": self.quantity,
            "filled_quantity": self.filled_quantity,
            "remaining_quantity": self.remaining_quantity,
            "price": self.price,
            "stop_price": self.stop_price,
            "average_fill_price": self.average_fill_price,
            "total_value": self.total_value,
            "fees": self.fees,
            "strategy_name": self.strategy_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "filled_at": self.filled_at.isoformat() if self.filled_at else None,
            "fill_percentage": self.fill_percentage
        }