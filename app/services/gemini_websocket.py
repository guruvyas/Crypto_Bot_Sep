import asyncio
import json
import websockets
from typing import Dict, List, Callable, Optional, Any
from datetime import datetime
import logging
from app.core.config import settings
from app.models.price_bar import PriceBar
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

class GeminiWebSocketClient:
    def __init__(self):
        self.ws_url = settings.GEMINI_WS_URL
        self.websocket = None
        self.subscriptions: Dict[str, List[Callable]] = {}
        self.running = False
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5
        self._reconnect_delay = 5
        
    async def connect(self):
        """Connect to Gemini WebSocket"""
        try:
            self.websocket = await websockets.connect(self.ws_url)
            self.running = True
            self._reconnect_attempts = 0
            logger.info("Connected to Gemini WebSocket")
            
            # Start listening for messages
            asyncio.create_task(self._listen())
            
        except Exception as e:
            logger.error(f"Failed to connect to WebSocket: {e}")
            await self._handle_reconnect()
    
    async def disconnect(self):
        """Disconnect from WebSocket"""
        self.running = False
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
        logger.info("Disconnected from Gemini WebSocket")
    
    async def subscribe_to_ticker(self, symbol: str, callback: Optional[Callable] = None):
        """Subscribe to real-time ticker updates for a symbol"""
        subscription_message = {
            "type": "subscribe",
            "subscriptions": [
                {
                    "name": "l2_updates",
                    "symbols": [symbol.upper()]
                }
            ]
        }
        
        await self._send_message(subscription_message)
        
        if callback:
            if symbol not in self.subscriptions:
                self.subscriptions[symbol] = []
            self.subscriptions[symbol].append(callback)
        
        logger.info(f"Subscribed to ticker updates for {symbol}")
    
    async def subscribe_to_trades(self, symbol: str, callback: Optional[Callable] = None):
        """Subscribe to real-time trade updates for a symbol"""
        subscription_message = {
            "type": "subscribe",
            "subscriptions": [
                {
                    "name": "trades",
                    "symbols": [symbol.upper()]
                }
            ]
        }
        
        await self._send_message(subscription_message)
        
        if callback:
            subscription_key = f"{symbol}_trades"
            if subscription_key not in self.subscriptions:
                self.subscriptions[subscription_key] = []
            self.subscriptions[subscription_key].append(callback)
        
        logger.info(f"Subscribed to trade updates for {symbol}")
    
    async def _send_message(self, message: Dict[str, Any]):
        """Send message to WebSocket"""
        if self.websocket and self.running:
            try:
                await self.websocket.send(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending WebSocket message: {e}")
                await self._handle_reconnect()
    
    async def _listen(self):
        """Listen for incoming WebSocket messages"""
        try:
            while self.running and self.websocket:
                try:
                    message = await asyncio.wait_for(
                        self.websocket.recv(), 
                        timeout=30.0
                    )
                    await self._handle_message(json.loads(message))
                    
                except asyncio.TimeoutError:
                    # Send ping to keep connection alive
                    await self._send_message({"type": "heartbeat"})
                    
                except websockets.exceptions.ConnectionClosed:
                    logger.warning("WebSocket connection closed")
                    await self._handle_reconnect()
                    break
                    
                except Exception as e:
                    logger.error(f"Error processing WebSocket message: {e}")
                    
        except Exception as e:
            logger.error(f"Error in WebSocket listener: {e}")
            await self._handle_reconnect()
    
    async def _handle_message(self, message: Dict[str, Any]):
        """Handle incoming WebSocket messages"""
        try:
            msg_type = message.get("type")
            
            if msg_type == "subscription_ack":
                logger.info(f"Subscription acknowledged: {message}")
                
            elif msg_type == "heartbeat":
                # Respond to heartbeat
                await self._send_message({"type": "heartbeat"})
                
            elif msg_type == "l2_updates":
                await self._handle_l2_update(message)
                
            elif msg_type == "trade":
                await self._handle_trade_update(message)
                
            elif msg_type == "auction_open" or msg_type == "auction_result":
                await self._handle_auction_update(message)
                
            else:
                logger.debug(f"Unhandled message type: {msg_type}")
                
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
    
    async def _handle_l2_update(self, message: Dict[str, Any]):
        """Handle Level 2 order book updates"""
        try:
            symbol = message.get("symbol", "").upper()
            changes = message.get("changes", [])
            
            # Process order book changes
            for change in changes:
                side = change[0]  # "buy" or "sell"
                price = float(change[1])
                quantity = float(change[2])
                
                # Call registered callbacks
                if symbol in self.subscriptions:
                    for callback in self.subscriptions[symbol]:
                        try:
                            await callback({
                                "type": "l2_update",
                                "symbol": symbol,
                                "side": side,
                                "price": price,
                                "quantity": quantity,
                                "timestamp": datetime.utcnow()
                            })
                        except Exception as e:
                            logger.error(f"Error in callback for {symbol}: {e}")
                            
        except Exception as e:
            logger.error(f"Error processing L2 update: {e}")
    
    async def _handle_trade_update(self, message: Dict[str, Any]):
        """Handle trade updates"""
        try:
            symbol = message.get("symbol", "").upper()
            price = float(message.get("price", 0))
            quantity = float(message.get("quantity", 0))
            timestamp = datetime.fromtimestamp(int(message.get("timestampms", 0)) / 1000)
            
            trade_data = {
                "type": "trade",
                "symbol": symbol,
                "price": price,
                "quantity": quantity,
                "timestamp": timestamp,
                "raw_message": message
            }
            
            # Store price data for strategy calculations
            await self._store_price_update(symbol, price, timestamp)
            
            # Call registered callbacks
            subscription_key = f"{symbol}_trades"
            if subscription_key in self.subscriptions:
                for callback in self.subscriptions[subscription_key]:
                    try:
                        await callback(trade_data)
                    except Exception as e:
                        logger.error(f"Error in trade callback for {symbol}: {e}")
                        
        except Exception as e:
            logger.error(f"Error processing trade update: {e}")
    
    async def _handle_auction_update(self, message: Dict[str, Any]):
        """Handle auction updates"""
        try:
            symbol = message.get("symbol", "").upper()
            logger.info(f"Auction update for {symbol}: {message.get('type')}")
            
        except Exception as e:
            logger.error(f"Error processing auction update: {e}")
    
    async def _store_price_update(self, symbol: str, price: float, timestamp: datetime):
        """Store price update for real-time calculations"""
        try:
            # This would typically update a cache or trigger position P&L updates
            # For now, we'll just log it
            logger.debug(f"Price update: {symbol} @ {price} at {timestamp}")
            
            # TODO: Implement real-time P&L updates for open positions
            # TODO: Trigger strategy signal calculations
            
        except Exception as e:
            logger.error(f"Error storing price update: {e}")
    
    async def _handle_reconnect(self):
        """Handle WebSocket reconnection"""
        if self._reconnect_attempts >= self._max_reconnect_attempts:
            logger.error("Max reconnection attempts reached. Stopping WebSocket client.")
            self.running = False
            return
        
        self._reconnect_attempts += 1
        logger.info(f"Attempting to reconnect ({self._reconnect_attempts}/{self._max_reconnect_attempts})")
        
        await asyncio.sleep(self._reconnect_delay)
        await self.connect()
    
    def add_callback(self, symbol: str, callback: Callable, subscription_type: str = "ticker"):
        """Add a callback for symbol updates"""
        subscription_key = symbol if subscription_type == "ticker" else f"{symbol}_{subscription_type}"
        
        if subscription_key not in self.subscriptions:
            self.subscriptions[subscription_key] = []
        
        self.subscriptions[subscription_key].append(callback)
    
    def remove_callback(self, symbol: str, callback: Callable, subscription_type: str = "ticker"):
        """Remove a callback for symbol updates"""
        subscription_key = symbol if subscription_type == "ticker" else f"{symbol}_{subscription_type}"
        
        if subscription_key in self.subscriptions:
            if callback in self.subscriptions[subscription_key]:
                self.subscriptions[subscription_key].remove(callback)
    
    async def get_connection_status(self) -> Dict[str, Any]:
        """Get current connection status"""
        return {
            "connected": self.websocket is not None and self.running,
            "reconnect_attempts": self._reconnect_attempts,
            "subscriptions": list(self.subscriptions.keys())
        }

class MarketDataManager:
    """Manages real-time market data subscriptions"""
    
    def __init__(self):
        self.ws_client = GeminiWebSocketClient()
        self.active_symbols: set = set()
        self.price_cache: Dict[str, Dict] = {}
        
    async def start(self):
        """Start the market data manager"""
        await self.ws_client.connect()
        logger.info("Market data manager started")
    
    async def stop(self):
        """Stop the market data manager"""
        await self.ws_client.disconnect()
        logger.info("Market data manager stopped")
    
    async def subscribe_symbol(self, symbol: str):
        """Subscribe to market data for a symbol"""
        if symbol not in self.active_symbols:
            self.active_symbols.add(symbol)
            
            # Subscribe to both ticker and trade updates
            await self.ws_client.subscribe_to_ticker(symbol, self._update_price_cache)
            await self.ws_client.subscribe_to_trades(symbol, self._update_price_cache)
            
            logger.info(f"Subscribed to market data for {symbol}")
    
    async def unsubscribe_symbol(self, symbol: str):
        """Unsubscribe from market data for a symbol"""
        if symbol in self.active_symbols:
            self.active_symbols.remove(symbol)
            
            # Remove from price cache
            if symbol in self.price_cache:
                del self.price_cache[symbol]
            
            logger.info(f"Unsubscribed from market data for {symbol}")
    
    async def _update_price_cache(self, data: Dict[str, Any]):
        """Update the price cache with new data"""
        symbol = data.get("symbol")
        if symbol:
            self.price_cache[symbol] = {
                "price": data.get("price"),
                "timestamp": data.get("timestamp"),
                "type": data.get("type")
            }
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get the current cached price for a symbol"""
        if symbol in self.price_cache:
            return self.price_cache[symbol].get("price")
        return None
    
    def get_price_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get the full cached price data for a symbol"""
        return self.price_cache.get(symbol)

# Global market data manager
market_data_manager = MarketDataManager()