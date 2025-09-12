import httpx
import hmac
import hashlib
import base64
import time
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from app.core.config import settings

class GeminiClient:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.api_secret = settings.GEMINI_API_SECRET
        self.base_url = settings.GEMINI_BASE_URL
        self.client = httpx.AsyncClient(timeout=30.0)
        self._last_nonce = 0
    
    def _get_nonce(self) -> str:
        """Generate a nonce using current Unix timestamp in seconds"""
        import time
        # Gemini expects Unix timestamp in seconds, not milliseconds
        current_time_sec = int(time.time())
        # Ensure nonce is always increasing
        if current_time_sec <= self._last_nonce:
            current_time_sec = self._last_nonce + 1
        self._last_nonce = current_time_sec
        return str(current_time_sec)
    
    def _generate_signature(self, payload: str) -> str:
        """Generate HMAC signature for authenticated requests"""
        encoded_payload = base64.b64encode(payload.encode()).decode()
        signature = hmac.new(
            self.api_secret.encode(),
            encoded_payload.encode(),
            hashlib.sha384
        ).hexdigest()
        return signature
    
    def _get_auth_headers(self, payload: Dict[str, Any]) -> Dict[str, str]:
        """Generate authentication headers for Gemini API"""
        payload_str = json.dumps(payload)
        encoded_payload = base64.b64encode(payload_str.encode()).decode()
        signature = self._generate_signature(payload_str)
        
        return {
            "Content-Type": "text/plain",
            "Content-Length": "0",
            "X-GEMINI-APIKEY": self.api_key,
            "X-GEMINI-PAYLOAD": encoded_payload,
            "X-GEMINI-SIGNATURE": signature,
            "Cache-Control": "no-cache"
        }
    
    async def get_symbols(self) -> List[str]:
        """Get all available trading symbols"""
        try:
            response = await self.client.get(f"{self.base_url}/v1/symbols")
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            raise Exception(f"Error fetching symbols: {e}")
    
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """Get current ticker for a symbol"""
        try:
            response = await self.client.get(f"{self.base_url}/v1/pubticker/{symbol}")
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            raise Exception(f"Error fetching ticker for {symbol}: {e}")
    
    async def get_candles(self, symbol: str, time_frame: str = "1hr") -> List[Dict[str, Any]]:
        """Get historical candle data"""
        try:
            response = await self.client.get(
                f"{self.base_url}/v2/candles/{symbol}/{time_frame}"
            )
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            raise Exception(f"Error fetching candles for {symbol}: {e}")
    
    async def get_order_book(self, symbol: str, limit_bids: int = 50, limit_asks: int = 50) -> Dict[str, Any]:
        """Get order book for a symbol"""
        try:
            params = {
                "limit_bids": limit_bids,
                "limit_asks": limit_asks
            }
            response = await self.client.get(
                f"{self.base_url}/v1/book/{symbol}",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            raise Exception(f"Error fetching order book for {symbol}: {e}")
    
    # Authenticated endpoints
    async def get_account_balance(self) -> List[Dict[str, Any]]:
        """Get account balances"""
        try:
            endpoint = "/v1/balances"
            payload = {
                "request": endpoint,
                "nonce": self._get_nonce(),
                "account": "primary"  # Required for Master API keys
            }
            
            headers = self._get_auth_headers(payload)
            response = await self.client.post(
                f"{self.base_url}{endpoint}",
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            raise Exception(f"Error fetching account balance: {e}")
    
    async def get_active_orders(self) -> List[Dict[str, Any]]:
        """Get all active orders"""
        try:
            endpoint = "/v1/orders"
            payload = {
                "request": endpoint,
                "nonce": self._get_nonce(),
                "account": "primary"  # Required for Master API keys
            }
            
            headers = self._get_auth_headers(payload)
            response = await self.client.post(
                f"{self.base_url}{endpoint}",
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            raise Exception(f"Error fetching active orders: {e}")
    
    async def place_order(
        self,
        symbol: str,
        amount: str,
        price: str,
        side: str,
        order_type: str = "exchange limit",
        client_order_id: Optional[str] = None,
        stop_price: Optional[str] = None
    ) -> Dict[str, Any]:
        """Place a new order"""
        try:
            endpoint = "/v1/order/new"
            payload = {
                "request": endpoint,
                "nonce": self._get_nonce(),
                "account": "primary",  # Required for Master API keys
                "symbol": symbol,
                "amount": amount,
                "price": price,
                "side": side,
                "type": order_type
            }
            
            if client_order_id:
                payload["client_order_id"] = client_order_id
            
            if stop_price and "stop" in order_type.lower():
                payload["stop_price"] = stop_price
            
            headers = self._get_auth_headers(payload)
            response = await self.client.post(
                f"{self.base_url}{endpoint}",
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            raise Exception(f"Error placing order: {e}")
    
    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel an existing order"""
        try:
            endpoint = "/v1/order/cancel"
            payload = {
                "request": endpoint,
                "nonce": self._get_nonce(),
                "account": "primary",  # Required for Master API keys
                "order_id": order_id
            }
            
            headers = self._get_auth_headers(payload)
            response = await self.client.post(
                f"{self.base_url}{endpoint}",
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            raise Exception(f"Error cancelling order {order_id}: {e}")
    
    async def cancel_all_orders(self) -> Dict[str, Any]:
        """Cancel all active orders"""
        try:
            endpoint = "/v1/order/cancel/all"
            payload = {
                "request": endpoint,
                "nonce": self._get_nonce(),
                "account": "primary"  # Required for Master API keys
            }
            
            headers = self._get_auth_headers(payload)
            response = await self.client.post(
                f"{self.base_url}{endpoint}",
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            raise Exception(f"Error cancelling all orders: {e}")
    
    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Get status of a specific order"""
        try:
            endpoint = "/v1/order/status"
            payload = {
                "request": endpoint,
                "nonce": self._get_nonce(),
                "account": "primary",  # Required for Master API keys
                "order_id": order_id
            }
            
            headers = self._get_auth_headers(payload)
            response = await self.client.post(
                f"{self.base_url}{endpoint}",
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            raise Exception(f"Error getting order status for {order_id}: {e}")
    
    async def get_past_trades(self, symbol: str, limit_trades: int = 500) -> List[Dict[str, Any]]:
        """Get past trades for a symbol"""
        try:
            endpoint = "/v1/mytrades"
            payload = {
                "request": endpoint,
                "nonce": self._get_nonce(),
                "account": "primary",  # Required for Master API keys
                "symbol": symbol,
                "limit_trades": limit_trades
            }
            
            headers = self._get_auth_headers(payload)
            response = await self.client.post(
                f"{self.base_url}{endpoint}",
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            raise Exception(f"Error fetching past trades for {symbol}: {e}")
    
    async def get_trade_volume(self) -> List[Dict[str, Any]]:
        """Get 30-day trade volume"""
        try:
            endpoint = "/v1/tradevolume"
            payload = {
                "request": endpoint,
                "nonce": self._get_nonce(),
                "account": "primary"  # Required for Master API keys
            }
            
            headers = self._get_auth_headers(payload)
            response = await self.client.post(
                f"{self.base_url}{endpoint}",
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            raise Exception(f"Error fetching trade volume: {e}")
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

# Global client instance
gemini_client = GeminiClient()