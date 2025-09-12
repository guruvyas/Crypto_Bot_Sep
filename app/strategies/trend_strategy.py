from typing import Dict, List, Optional, Any
from app.strategies.base_strategy import BaseStrategy, TradingSignal
from app.models.price_bar import PriceBar

class TrendStrategy(BaseStrategy):
    """Simple trend following strategy using moving averages and RSI"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__("trend", config)
        
        # Strategy parameters
        params = config.get("params", {})
        self.sma_short = params.get("sma_short", 10)
        self.sma_long = params.get("sma_long", 30)
        self.rsi_period = params.get("rsi_period", 14)
        self.rsi_overbought = params.get("rsi_overbought", 70)
        self.rsi_oversold = params.get("rsi_oversold", 30)
        
        # Risk management
        self.stop_loss_pct = params.get("stop_loss_pct", 0.02)
        self.take_profit_pct = params.get("take_profit_pct", 0.04)
    
    def get_required_indicators(self) -> List[str]:
        """Return required technical indicators"""
        return [
            f"sma_{self.sma_short}",
            f"sma_{self.sma_long}",
            f"rsi_{self.rsi_period}"
        ]
    
    async def analyze(self, symbol: str, price_data: List[PriceBar]) -> Optional[TradingSignal]:
        """Analyze price data for trend signals"""
        
        if len(price_data) < max(self.sma_long, self.rsi_period):
            return None
        
        # Get latest bar
        current_bar = price_data[-1]
        previous_bar = price_data[-2] if len(price_data) > 1 else None
        
        # Get moving averages
        sma_short = getattr(current_bar, f"sma_{self.sma_short}", None)
        sma_long = getattr(current_bar, f"sma_{self.sma_long}", None)
        rsi = getattr(current_bar, f"rsi_{self.rsi_period}", None)
        
        # Skip if indicators not available
        if not all([sma_short, sma_long, rsi]):
            return None
        
        # Get previous moving averages for crossover detection
        prev_sma_short = None
        prev_sma_long = None
        if previous_bar:
            prev_sma_short = getattr(previous_bar, f"sma_{self.sma_short}", None)
            prev_sma_long = getattr(previous_bar, f"sma_{self.sma_long}", None)
        
        current_price = current_bar.close_price
        
        # Trend analysis
        is_uptrend = sma_short > sma_long
        is_downtrend = sma_short < sma_long
        
        # Crossover detection
        bullish_crossover = False
        bearish_crossover = False
        
        if prev_sma_short and prev_sma_long:
            # Bullish crossover: short MA crosses above long MA
            if prev_sma_short <= prev_sma_long and sma_short > sma_long:
                bullish_crossover = True
            
            # Bearish crossover: short MA crosses below long MA
            if prev_sma_short >= prev_sma_long and sma_short < sma_long:
                bearish_crossover = True
        
        # Generate signals
        signal = None
        confidence = 0.0
        
        # Buy signal conditions
        if (bullish_crossover or (is_uptrend and rsi < self.rsi_overbought)) and rsi > self.rsi_oversold:
            confidence = 0.7 if bullish_crossover else 0.5
            
            # Adjust confidence based on RSI
            if rsi < 40:  # Strong oversold condition
                confidence += 0.2
            
            confidence = min(confidence, 1.0)
            
            signal = TradingSignal(
                signal_type="buy",
                symbol=symbol,
                price=current_price,
                confidence=confidence,
                stop_loss=current_price * (1 - self.stop_loss_pct),
                take_profit=current_price * (1 + self.take_profit_pct),
                metadata={
                    "strategy": self.name,
                    "sma_short": sma_short,
                    "sma_long": sma_long,
                    "rsi": rsi,
                    "crossover": bullish_crossover,
                    "trend": "up"
                }
            )
        
        # Sell signal conditions
        elif (bearish_crossover or (is_downtrend and rsi > self.rsi_oversold)) and rsi < self.rsi_overbought:
            confidence = 0.7 if bearish_crossover else 0.5
            
            # Adjust confidence based on RSI
            if rsi > 60:  # Strong overbought condition
                confidence += 0.2
            
            confidence = min(confidence, 1.0)
            
            signal = TradingSignal(
                signal_type="sell",
                symbol=symbol,
                price=current_price,
                confidence=confidence,
                stop_loss=current_price * (1 + self.stop_loss_pct),
                take_profit=current_price * (1 - self.take_profit_pct),
                metadata={
                    "strategy": self.name,
                    "sma_short": sma_short,
                    "sma_long": sma_long,
                    "rsi": rsi,
                    "crossover": bearish_crossover,
                    "trend": "down"
                }
            )
        
        # Store and return signal
        if signal:
            self._store_signal(signal)
        
        return signal