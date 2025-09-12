import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
from app.services.gemini_client import gemini_client
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class PortfolioService:
    def __init__(self):
        self._cached_balance = None
        self._last_update = None
        self._cache_duration_seconds = 60  # Cache for 1 minute
    
    async def get_portfolio_balance(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get portfolio balance from Gemini or use cached data"""
        
        # Check cache first
        if not force_refresh and self._is_cache_valid():
            return self._cached_balance
        
        try:
            # Try to fetch real balance from Gemini
            balance_data = await self._fetch_real_balance()
            if balance_data:
                self._cached_balance = balance_data
                self._last_update = datetime.utcnow()
                return balance_data
        except Exception as e:
            logger.warning(f"Could not fetch real balance from Gemini: {e}")
        
        # Fallback to sandbox simulation data
        return await self._get_sandbox_balance()
    
    async def _fetch_real_balance(self) -> Optional[Dict[str, Any]]:
        """Attempt to fetch real balance from Gemini API"""
        try:
            balance = await gemini_client.get_account_balance()
            
            total_usd_value = 0
            balances_by_currency = {}
            
            for asset in balance:
                currency = asset.get('currency', 'Unknown')
                amount = float(asset.get('amount', 0))
                available = float(asset.get('available', 0))
                
                balances_by_currency[currency] = {
                    'amount': amount,
                    'available': available,
                    'usd_value': 0
                }
                
                # Calculate USD value
                if currency == 'USD':
                    usd_value = amount
                    total_usd_value += usd_value
                    balances_by_currency[currency]['usd_value'] = usd_value
                elif amount > 0:
                    # Try to get USD value for other currencies
                    try:
                        if currency == 'BTC':
                            ticker = await gemini_client.get_ticker("BTCUSD")
                            price = float(ticker.get('last', 0))
                            usd_value = amount * price
                            total_usd_value += usd_value
                            balances_by_currency[currency]['usd_value'] = usd_value
                    except:
                        pass
            
            return {
                "source": "gemini_live",
                "total_usd_value": total_usd_value,
                "balances": balances_by_currency,
                "last_updated": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error fetching real Gemini balance: {e}")
            return None
    
    async def _get_sandbox_balance(self) -> Dict[str, Any]:
        """Get simulated sandbox balance for testing"""
        
        # Simulate a realistic sandbox portfolio
        try:
            # Get current BTC price for realistic simulation
            ticker = await gemini_client.get_ticker("BTCUSD")
            btc_price = float(ticker.get('last', 60000))
        except:
            btc_price = 60000  # Fallback price
        
        # Simulate portfolio balances
        simulated_balances = {
            "USD": {
                "amount": 25000.0,
                "available": 24500.0,  # Some might be in open orders
                "usd_value": 25000.0
            },
            "BTC": {
                "amount": 0.1,
                "available": 0.08,
                "usd_value": 0.1 * btc_price
            }
        }
        
        total_usd_value = sum(b["usd_value"] for b in simulated_balances.values())
        
        return {
            "source": "sandbox_simulation",
            "total_usd_value": total_usd_value,
            "balances": simulated_balances,
            "last_updated": datetime.utcnow().isoformat(),
            "note": "Simulated sandbox data - replace with real API when authentication is fixed"
        }
    
    def _is_cache_valid(self) -> bool:
        """Check if cached data is still valid"""
        if not self._cached_balance or not self._last_update:
            return False
        
        age_seconds = (datetime.utcnow() - self._last_update).total_seconds()
        return age_seconds < self._cache_duration_seconds
    
    async def get_available_cash(self) -> float:
        """Get available USD cash for trading"""
        balance = await self.get_portfolio_balance()
        usd_balance = balance.get("balances", {}).get("USD", {})
        return usd_balance.get("available", 0.0)
    
    async def get_total_portfolio_value(self) -> float:
        """Get total portfolio value in USD"""
        balance = await self.get_portfolio_balance()
        return balance.get("total_usd_value", 0.0)
    
    async def refresh_balance(self) -> Dict[str, Any]:
        """Force refresh balance from API"""
        return await self.get_portfolio_balance(force_refresh=True)

# Global portfolio service instance
portfolio_service = PortfolioService()