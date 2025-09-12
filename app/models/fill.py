from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime

class Fill(Base):
    __tablename__ = "fills"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Related entities
    session_id = Column(Integer, ForeignKey("trading_sessions.id"), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    position_id = Column(Integer, ForeignKey("positions.id"), nullable=True)  # May be null for closing fills
    
    # Fill identification
    exchange_fill_id = Column(String(255), nullable=True, index=True)  # Exchange's fill ID
    trade_id = Column(String(255), nullable=True)                      # Exchange's trade ID
    
    # Fill details
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(String(10), nullable=False)  # buy, sell
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    
    # Financial details
    total_value = Column(Float, nullable=False)  # price * quantity
    fee = Column(Float, default=0.0)
    fee_currency = Column(String(10), default="USD")
    
    # Exchange details
    liquidity = Column(String(10), nullable=True)  # maker, taker
    exchange_timestamp = Column(DateTime(timezone=True), nullable=True)
    
    # Local tracking
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Raw exchange data
    exchange_data = Column(Text, nullable=True)  # Raw JSON from exchange
    
    # Relationships
    order = relationship("Order", back_populates="fills")
    
    def __repr__(self):
        return f"<Fill(id={self.id}, symbol={self.symbol}, side={self.side}, quantity={self.quantity}, price={self.price})>"
    
    @property
    def net_proceeds(self) -> float:
        """Calculate net proceeds after fees"""
        if self.side.lower() == "sell":
            return self.total_value - self.fee
        else:
            return -(self.total_value + self.fee)  # Negative for buys (cash outflow)
    
    @property
    def effective_price(self) -> float:
        """Calculate effective price including fees"""
        if self.quantity == 0:
            return self.price
        
        if self.side.lower() == "buy":
            return (self.total_value + self.fee) / self.quantity
        else:
            return (self.total_value - self.fee) / self.quantity
    
    @classmethod
    def from_gemini_fill(cls, session_id: int, order_id: int, gemini_fill_data: dict):
        """Create Fill from Gemini fill data"""
        return cls(
            session_id=session_id,
            order_id=order_id,
            exchange_fill_id=gemini_fill_data.get("tid"),
            trade_id=gemini_fill_data.get("tid"),  # Gemini uses same ID
            symbol=gemini_fill_data.get("symbol", "").upper(),
            side=gemini_fill_data.get("side", "").lower(),
            quantity=float(gemini_fill_data.get("amount", 0)),
            price=float(gemini_fill_data.get("price", 0)),
            total_value=float(gemini_fill_data.get("amount", 0)) * float(gemini_fill_data.get("price", 0)),
            fee=float(gemini_fill_data.get("fee_amount", 0)),
            fee_currency=gemini_fill_data.get("fee_currency", "USD"),
            liquidity="maker" if gemini_fill_data.get("aggressor", False) else "taker",
            exchange_timestamp=datetime.fromtimestamp(int(gemini_fill_data.get("timestampms", 0)) / 1000),
            exchange_data=str(gemini_fill_data),
            processed_at=datetime.utcnow()
        )
    
    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "order_id": self.order_id,
            "position_id": self.position_id,
            "exchange_fill_id": self.exchange_fill_id,
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "total_value": self.total_value,
            "fee": self.fee,
            "fee_currency": self.fee_currency,
            "net_proceeds": self.net_proceeds,
            "effective_price": self.effective_price,
            "liquidity": self.liquidity,
            "exchange_timestamp": self.exchange_timestamp.isoformat() if self.exchange_timestamp else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None
        }