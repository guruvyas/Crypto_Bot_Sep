from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime
from app.models.price_bar import PriceBar

class TradingSignal:
    def __init__(
        self,
        signal_type: str,  # "buy", "sell", "hold"
        symbol: str,
        price: float,
        confidence: float,  # 0.0 to 1.0
        quantity: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.signal_type = signal_type
        self.symbol = symbol
        self.price = price
        self.confidence = confidence
        self.quantity = quantity
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.metadata = metadata or {}
        self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_type": self.signal_type,
            "symbol": self.symbol,
            "price": self.price,
            "confidence": self.confidence,
            "quantity": self.quantity,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }

class BaseStrategy(ABC):
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.enabled = config.get("enabled", False)
        self.last_signals: Dict[str, TradingSignal] = {}
        
    @abstractmethod
    async def analyze(self, symbol: str, price_data: List[PriceBar]) -> Optional[TradingSignal]:
        """Analyze price data and generate trading signals"""
        pass
    
    @abstractmethod
    def get_required_indicators(self) -> List[str]:
        """Return list of required technical indicators"""
        pass
    
    def is_enabled(self) -> bool:
        """Check if strategy is enabled"""
        return self.enabled
    
    def get_last_signal(self, symbol: str) -> Optional[TradingSignal]:
        """Get the last signal for a symbol"""
        return self.last_signals.get(symbol)
    
    def _store_signal(self, signal: TradingSignal):
        """Store the generated signal"""
        self.last_signals[signal.symbol] = signal
    
    def calculate_position_size(self, symbol: str, price: float, allocation: float) -> float:
        """Calculate position size based on allocation and risk"""
        # Basic implementation - can be overridden by specific strategies
        sizing_mode = self.config.get("position_sizing", {}).get("mode", "fixed_risk")
        
        if sizing_mode == "fixed_risk":
            risk_amount = self.config.get("position_sizing", {}).get("fixed_risk", 100.0)
            return risk_amount / price
        elif sizing_mode == "fractional":
            fraction = self.config.get("position_sizing", {}).get("fraction", 0.1)
            return (allocation * fraction) / price
        else:
            # Default to $100 position
            return 100.0 / price