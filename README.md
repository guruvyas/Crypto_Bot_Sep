# Crypto Trading Bot - Gemini Sandbox

A comprehensive FastAPI-based cryptocurrency trading bot designed for the Gemini Sandbox environment. This bot provides automated trading capabilities with session management, risk controls, and multiple trading strategies.

## Features

### Core Capabilities
- **Session Management**: Complete lifecycle control with start/pause/end functionality
- **Order Management**: Deterministic order IDs, bracket orders, retry logic with exponential backoff
- **Position Tracking**: Real-time P&L calculation and position monitoring
- **Risk Management**: Configurable guardrails including max positions, max loss, position sizing
- **Real-time Data**: WebSocket integration for live market data
- **Activity Logging**: Comprehensive plain-English logging of all trading activities
- **Configuration Management**: YAML-based config with environment variable secrets

### Trading Strategies (V1)
- **Trend Following**: Moving average crossovers with RSI confirmation
- **Mean Reversion**: Bollinger Bands with RSI (framework in place)
- **Breakout**: Price and volume breakout detection (framework in place)

### Data Persistence
- **SQLite Database**: All session data, orders, positions, fills, and activity logs
- **JSON/CSV Export**: Automatic session summary export
- **Configuration Snapshots**: Version control for trading configurations

## Project Structure

```
app/
├── main.py                 # FastAPI application entry point
├── core/
│   ├── config.py          # Configuration management
│   └── database.py        # Database setup and session management
├── models/                # SQLAlchemy database models
│   ├── session.py         # Trading session model
│   ├── order.py           # Order model with status tracking
│   ├── position.py        # Position model with P&L calculation
│   ├── fill.py            # Trade fill model
│   ├── activity_log.py    # Activity logging model
│   ├── price_bar.py       # OHLCV price data model
│   └── config_snapshot.py # Configuration versioning model
├── services/              # Business logic services
│   ├── session_manager.py # Session lifecycle management
│   ├── order_manager.py   # Order execution and management
│   ├── gemini_client.py   # Gemini REST API client
│   └── gemini_websocket.py # WebSocket client for real-time data
├── api/                   # FastAPI route handlers
│   ├── dashboard.py       # Dashboard and portfolio endpoints
│   └── session_control.py # Session management endpoints
└── strategies/            # Trading strategy implementations
    ├── base_strategy.py   # Abstract base strategy class
    └── trend_strategy.py  # Trend following strategy implementation

config/
└── trading_config.yaml    # Trading configuration file

data/
├── db/                    # SQLite database files
└── exports/               # Session export files (JSON/CSV)
```

## Setup Instructions

### 1. Environment Setup

```bash
# Clone or download the project
cd Crypto_Bot_Sep

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
```

### 2. Configure Environment Variables

Your Gemini Sandbox credentials are already configured in the `.env` file:

- **API Key**: `your-gemini-sandbox-api-key` 
- **API Secret**: `your-gemini-sandbox-api-secret`
- **Sandbox Mode**: Enabled

The `.env` file contains all necessary configuration. If you need to modify any settings, you can edit this file directly.

### 3. Configure Trading Parameters

Edit `config/trading_config.yaml` to customize:
- Risk management settings
- Position sizing rules
- Strategy parameters
- Allowed trading symbols

### 4. Run the Application

```bash
# Start the trading bot
python run.py

# Or run directly with uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## API Endpoints

### Session Management
- `POST /api/session/start` - Start a new trading session
- `POST /api/session/pause` - Pause current session
- `POST /api/session/resume` - Resume paused session
- `POST /api/session/end` - End current session
- `GET /api/session/current` - Get current session info
- `GET /api/session/history` - Get session history

### Dashboard & Monitoring
- `GET /api/dashboard` - Complete dashboard data
- `GET /api/portfolio/performance` - Portfolio performance charts
- `GET /api/positions/{id}` - Position details
- `GET /api/orders/{id}` - Order details

### Health Check
- `GET /health` - Application health status

## Usage Examples

### Starting a Session

```bash
curl -X POST "http://localhost:8000/api/session/start" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Session",
    "starting_balance": 10000.0,
    "session_allocation": 1000.0,
    "mode": "session_amount",
    "max_loss_limit": 500.0
  }'
```

### Getting Dashboard Data

```bash
curl "http://localhost:8000/api/dashboard"
```

### Ending a Session

```bash
curl -X POST "http://localhost:8000/api/session/end?reason=Testing complete"
```

## Key Design Principles

1. **Single Process Architecture**: Only one trading session active at a time with lock guards
2. **Deterministic Order IDs**: Consistent order identification for tracking and recovery
3. **Comprehensive Logging**: Every action logged in plain English for audit trails
4. **Risk-First Design**: Multiple layers of risk management and guardrails
5. **Configuration Driven**: Behavior controlled via YAML config files
6. **Dry Run Capability**: Test strategies without actual trades

## Risk Management Features

- **Position Limits**: Maximum number of concurrent positions
- **Loss Limits**: Session and total loss limits with automatic session termination
- **Position Sizing**: Configurable position sizing (fixed risk or fractional)
- **Cooldown Periods**: Prevent rapid-fire trading
- **Symbol Whitelist**: Restrict trading to approved symbols only
- **Hard Stops**: Automatic stop-loss and take-profit orders

## Database Schema

The bot uses SQLite with the following key entities:
- **TradingSession**: Session lifecycle and P&L tracking
- **Order**: Order management with retry and status tracking
- **Position**: Position tracking with real-time P&L
- **Fill**: Individual trade execution records
- **ActivityLog**: Comprehensive activity and event logging
- **PriceBar**: OHLCV price data with technical indicators
- **ConfigSnapshot**: Configuration versioning and audit

## Development Status

### Completed Components ✅
- FastAPI application structure
- Database models and migrations
- Session management system
- Gemini API client (REST + WebSocket)
- Order management with bracket orders
- Basic dashboard API
- Configuration management
- Activity logging framework
- Basic trend strategy implementation

### Remaining Tasks 🚧
- Complete P&L calculation service
- Implement Mean Reversion and Breakout strategies
- Add technical indicator calculations
- Implement risk management service
- Add comprehensive error handling
- Create strategy backtesting framework
- Add position management enhancements
- Implement market data caching
- Add monitoring and alerting
- Create comprehensive test suite

## Security Notes

- API keys are stored in environment variables, never in code
- Database contains no sensitive credentials
- All API communications use HTTPS (sandbox environment)
- Session summaries exclude sensitive information

## Contributing

This is a prototype trading bot for educational and testing purposes. When extending:

1. Follow the existing architectural patterns
2. Add comprehensive logging for all new features
3. Include proper error handling and recovery
4. Update configuration schemas as needed
5. Add tests for critical trading logic

## Disclaimer

This software is for educational and testing purposes only. Use in sandbox environments only. Always test thoroughly before any live trading. Trading cryptocurrency involves substantial risk of loss.