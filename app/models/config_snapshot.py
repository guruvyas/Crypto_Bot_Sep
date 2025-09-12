from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from app.core.database import Base
import json
from datetime import datetime

class ConfigSnapshot(Base):
    __tablename__ = "config_snapshots"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Snapshot metadata
    session_id = Column(Integer, nullable=True)  # Associated session, if any
    name = Column(String(255), nullable=False)   # Descriptive name
    description = Column(Text, nullable=True)    # Optional description
    
    # Configuration data (stored as JSON)
    trading_config = Column(Text, nullable=False)      # YAML config as JSON
    environment_config = Column(Text, nullable=False)  # Environment variables
    strategy_configs = Column(Text, nullable=True)     # Strategy-specific configs
    
    # Metadata
    config_version = Column(String(50), nullable=True)  # Version/tag of the config
    created_by = Column(String(100), default="system")  # Who/what created this snapshot
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<ConfigSnapshot(id={self.id}, name='{self.name}', created_at={self.created_at})>"
    
    @classmethod
    def create_from_current_config(cls, trading_config_obj, settings_obj, name: str, 
                                  session_id: int = None, description: str = None):
        """Create a config snapshot from current configuration objects"""
        
        # Serialize trading config
        trading_config_dict = trading_config_obj._config_data
        
        # Serialize environment settings (excluding secrets)
        env_config = {
            "DEBUG": settings_obj.DEBUG,
            "HOST": settings_obj.HOST,
            "PORT": settings_obj.PORT,
            "DATABASE_URL": settings_obj.DATABASE_URL,
            "GEMINI_BASE_URL": settings_obj.GEMINI_BASE_URL,
            "GEMINI_WS_URL": settings_obj.GEMINI_WS_URL,
            "MAX_POSITIONS": settings_obj.MAX_POSITIONS,
            "MAX_ORDER_SIZE": settings_obj.MAX_ORDER_SIZE,
            "COOLDOWN_SECONDS": settings_obj.COOLDOWN_SECONDS,
            "DEFAULT_STOP_LOSS_PCT": settings_obj.DEFAULT_STOP_LOSS_PCT,
            "DEFAULT_TAKE_PROFIT_PCT": settings_obj.DEFAULT_TAKE_PROFIT_PCT,
            # Note: API keys are NOT included for security
        }
        
        return cls(
            session_id=session_id,
            name=name,
            description=description,
            trading_config=json.dumps(trading_config_dict, indent=2),
            environment_config=json.dumps(env_config, indent=2),
            strategy_configs=json.dumps(trading_config_dict.get('strategies', {}), indent=2),
            created_by="trading_bot"
        )
    
    def get_trading_config(self) -> dict:
        """Get trading config as dictionary"""
        return json.loads(self.trading_config)
    
    def get_environment_config(self) -> dict:
        """Get environment config as dictionary"""
        return json.loads(self.environment_config)
    
    def get_strategy_configs(self) -> dict:
        """Get strategy configs as dictionary"""
        if self.strategy_configs:
            return json.loads(self.strategy_configs)
        return {}
    
    def get_strategy_config(self, strategy_name: str) -> dict:
        """Get specific strategy configuration"""
        strategies = self.get_strategy_configs()
        return strategies.get(strategy_name, {})
    
    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "name": self.name,
            "description": self.description,
            "config_version": self.config_version,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "trading_config": self.get_trading_config(),
            "environment_config": self.get_environment_config(),
            "strategy_configs": self.get_strategy_configs()
        }
    
    def export_to_file(self, file_path: str):
        """Export configuration snapshot to a file"""
        export_data = {
            "snapshot_info": {
                "name": self.name,
                "description": self.description,
                "config_version": self.config_version,
                "created_by": self.created_by,
                "created_at": self.created_at.isoformat() if self.created_at else None
            },
            "trading_config": self.get_trading_config(),
            "environment_config": self.get_environment_config(),
            "strategy_configs": self.get_strategy_configs()
        }
        
        with open(file_path, 'w') as f:
            json.dump(export_data, f, indent=2)
    
    @classmethod
    def import_from_file(cls, file_path: str, name: str = None) -> 'ConfigSnapshot':
        """Import configuration snapshot from a file"""
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        snapshot_info = data.get('snapshot_info', {})
        
        return cls(
            name=name or snapshot_info.get('name', 'Imported Config'),
            description=snapshot_info.get('description'),
            config_version=snapshot_info.get('config_version'),
            created_by=snapshot_info.get('created_by', 'import'),
            trading_config=json.dumps(data.get('trading_config', {})),
            environment_config=json.dumps(data.get('environment_config', {})),
            strategy_configs=json.dumps(data.get('strategy_configs', {}))
        )