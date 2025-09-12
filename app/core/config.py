from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import yaml
import os
from pathlib import Path

class Settings(BaseSettings):
    # Server Settings
    DEBUG: bool = Field(default=True)
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)
    
    # Database
    DATABASE_URL: str = Field(default="sqlite:///./data/db/trading_bot.db")
    
    # Gemini API
    GEMINI_API_KEY: str = Field(default="")
    GEMINI_API_SECRET: str = Field(default="")
    GEMINI_BASE_URL: str = Field(default="https://api.sandbox.gemini.com")
    GEMINI_WS_URL: str = Field(default="wss://api.sandbox.gemini.com/v1/marketdata")
    GEMINI_SANDBOX: bool = Field(default=True)
    
    # Trading Defaults (overridden by YAML config)
    MAX_POSITIONS: int = Field(default=5)
    MAX_ORDER_SIZE: float = Field(default=1000)
    COOLDOWN_SECONDS: int = Field(default=60)
    DEFAULT_STOP_LOSS_PCT: float = Field(default=0.02)
    DEFAULT_TAKE_PROFIT_PCT: float = Field(default=0.04)
    
    class Config:
        env_file = ".env"
        case_sensitive = True

class TradingConfig:
    def __init__(self, config_path: str = "config/trading_config.yaml"):
        self.config_path = Path(config_path)
        self._config_data = None
        self.load_config()
    
    def load_config(self):
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                self._config_data = yaml.safe_load(f)
        else:
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
    
    def reload_config(self):
        self.load_config()
    
    @property
    def trading(self):
        return self._config_data.get('trading', {})
    
    @property
    def strategies(self):
        return self._config_data.get('strategies', {})
    
    @property
    def session(self):
        return self._config_data.get('session', {})
    
    @property
    def data(self):
        return self._config_data.get('data', {})
    
    def get_strategy_config(self, strategy_name: str):
        return self.strategies.get(strategy_name, {})
    
    def is_strategy_enabled(self, strategy_name: str):
        strategy_config = self.get_strategy_config(strategy_name)
        return strategy_config.get('enabled', False)
    
    def get_allowed_symbols(self):
        return self.trading.get('allowed_symbols', [])
    
    def get_max_positions(self):
        return self.trading.get('max_positions', 5)
    
    def get_position_sizing_config(self):
        return {
            'mode': self.trading.get('position_sizing_mode', 'fixed_risk'),
            'fixed_risk_amount': self.trading.get('fixed_risk_amount', 100.0),
            'fractional_risk': self.trading.get('fractional_risk', 0.02)
        }

# Global instances
settings = Settings()
trading_config = TradingConfig()