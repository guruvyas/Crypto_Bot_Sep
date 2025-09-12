from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, Enum
from sqlalchemy.sql import func
from app.core.database import Base
import enum
from datetime import datetime
from typing import Optional

class SessionStatus(enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"

class SessionMode(enum.Enum):
    FULL_ALLOCATION = "full_allocation"
    SESSION_AMOUNT = "session_amount"

class TradingSession(Base):
    __tablename__ = "trading_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    status = Column(Enum(SessionStatus), default=SessionStatus.ACTIVE)
    mode = Column(Enum(SessionMode), default=SessionMode.SESSION_AMOUNT)
    
    # Financial data
    starting_balance = Column(Float, nullable=False)
    session_allocation = Column(Float, nullable=False)
    current_balance = Column(Float, nullable=False)
    total_pnl = Column(Float, default=0.0)
    session_pnl = Column(Float, default=0.0)
    
    # Risk management
    max_loss_limit = Column(Float, nullable=True)
    max_positions = Column(Integer, default=5)
    
    # Timestamps
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    paused_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Configuration snapshot
    config_snapshot_id = Column(Integer, nullable=True)
    
    # Session summary (populated when ended)
    summary_json = Column(Text, nullable=True)
    
    def __repr__(self):
        return f"<TradingSession(name={self.name}, status={self.status.value}, pnl={self.session_pnl})>"
    
    @property
    def is_active(self) -> bool:
        return self.status == SessionStatus.ACTIVE
    
    @property
    def duration_minutes(self) -> Optional[int]:
        if not self.started_at:
            return None
        
        end_time = self.ended_at or datetime.utcnow()
        duration = end_time - self.started_at
        return int(duration.total_seconds() / 60)
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "mode": self.mode.value,
            "starting_balance": self.starting_balance,
            "session_allocation": self.session_allocation,
            "current_balance": self.current_balance,
            "total_pnl": self.total_pnl,
            "session_pnl": self.session_pnl,
            "max_loss_limit": self.max_loss_limit,
            "max_positions": self.max_positions,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "paused_at": self.paused_at.isoformat() if self.paused_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_minutes": self.duration_minutes
        }