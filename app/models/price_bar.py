from sqlalchemy import Column, Integer, String, Float, DateTime, Index
from sqlalchemy.sql import func
from app.core.database import Base
from datetime import datetime

class PriceBar(Base):
    __tablename__ = "price_bars"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Symbol and timeframe
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False)  # 1m, 5m, 15m, 1h, 4h, 1d
    
    # OHLCV data
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    open_price = Column(Float, nullable=False)
    high_price = Column(Float, nullable=False)
    low_price = Column(Float, nullable=False)
    close_price = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    
    # Technical indicators (computed values)
    sma_10 = Column(Float, nullable=True)
    sma_20 = Column(Float, nullable=True)
    sma_50 = Column(Float, nullable=True)
    ema_10 = Column(Float, nullable=True)
    ema_20 = Column(Float, nullable=True)
    rsi_14 = Column(Float, nullable=True)
    
    # Bollinger Bands
    bb_upper = Column(Float, nullable=True)
    bb_middle = Column(Float, nullable=True)
    bb_lower = Column(Float, nullable=True)
    
    # Volume indicators
    volume_sma_20 = Column(Float, nullable=True)
    volume_ratio = Column(Float, nullable=True)  # current volume / 20-period SMA
    
    # Price action metrics
    price_change = Column(Float, nullable=True)
    price_change_pct = Column(Float, nullable=True)
    
    # Data source and quality
    source = Column(String(20), default="gemini")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Composite indexes for efficient querying
    __table_args__ = (
        Index('ix_symbol_timeframe_timestamp', 'symbol', 'timeframe', 'timestamp'),
        Index('ix_symbol_timestamp', 'symbol', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<PriceBar(symbol={self.symbol}, timeframe={self.timeframe}, timestamp={self.timestamp}, close={self.close_price})>"
    
    @property
    def typical_price(self) -> float:
        """Calculate typical price (HLC/3)"""
        return (self.high_price + self.low_price + self.close_price) / 3
    
    @property
    def price_range(self) -> float:
        """Calculate price range (high - low)"""
        return self.high_price - self.low_price
    
    @property
    def price_range_pct(self) -> float:
        """Calculate price range as percentage of close price"""
        if self.close_price == 0:
            return 0
        return (self.price_range / self.close_price) * 100
    
    @property
    def is_green_candle(self) -> bool:
        """True if close > open (bullish candle)"""
        return self.close_price > self.open_price
    
    @property
    def is_red_candle(self) -> bool:
        """True if close < open (bearish candle)"""
        return self.close_price < self.open_price
    
    @property
    def is_doji(self) -> bool:
        """True if open and close are very close (doji pattern)"""
        if self.open_price == 0:
            return False
        body_size_pct = abs(self.close_price - self.open_price) / self.open_price
        return body_size_pct < 0.001  # Less than 0.1% difference
    
    def update_technical_indicators(self, indicator_values: dict):
        """Update technical indicator values from calculated data"""
        for key, value in indicator_values.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def to_dict(self):
        return {
            "id": self.id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "open": self.open_price,
            "high": self.high_price,
            "low": self.low_price,
            "close": self.close_price,
            "volume": self.volume,
            "sma_10": self.sma_10,
            "sma_20": self.sma_20,
            "sma_50": self.sma_50,
            "ema_10": self.ema_10,
            "ema_20": self.ema_20,
            "rsi_14": self.rsi_14,
            "bb_upper": self.bb_upper,
            "bb_middle": self.bb_middle,
            "bb_lower": self.bb_lower,
            "volume_sma_20": self.volume_sma_20,
            "volume_ratio": self.volume_ratio,
            "price_change": self.price_change,
            "price_change_pct": self.price_change_pct,
            "typical_price": self.typical_price,
            "price_range": self.price_range,
            "price_range_pct": self.price_range_pct,
            "is_green_candle": self.is_green_candle,
            "is_red_candle": self.is_red_candle,
            "is_doji": self.is_doji
        }
    
    @classmethod
    def from_gemini_data(cls, symbol: str, timeframe: str, gemini_data: dict):
        """Create PriceBar from Gemini API response data"""
        return cls(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=datetime.fromtimestamp(gemini_data['time'] / 1000),  # Gemini uses milliseconds
            open_price=float(gemini_data['open']),
            high_price=float(gemini_data['high']),
            low_price=float(gemini_data['low']),
            close_price=float(gemini_data['close']),
            volume=float(gemini_data['volume']),
            source="gemini"
        )