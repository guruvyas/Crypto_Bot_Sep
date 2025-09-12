#!/usr/bin/env python3
"""
Test Gemini API connection and portfolio fetching
"""
import asyncio
from app.services.gemini_client import gemini_client
from app.core.config import settings

async def test_gemini_connection():
    print("Testing Gemini API connection...")
    print(f"API Key: {settings.GEMINI_API_KEY[:10]}...{settings.GEMINI_API_KEY[-4:]}")
    print(f"Base URL: {settings.GEMINI_BASE_URL}")
    print(f"Sandbox: {settings.GEMINI_SANDBOX}")
    
    try:
        # Test public endpoint first
        print("\n1. Testing public endpoint (symbols)...")
        symbols = await gemini_client.get_symbols()
        print(f"   Available symbols: {symbols[:5]}...")  # Show first 5
        
        # Test public ticker
        print("\n2. Testing public ticker (BTCUSD)...")
        ticker = await gemini_client.get_ticker("BTCUSD")
        print(f"   BTC price: ${float(ticker.get('last', 0)):,.2f}")
        
        # Test authenticated endpoint (account balance)
        print("\n3. Testing authenticated endpoint (balance)...")
        balance = await gemini_client.get_account_balance()
        print(f"   Account balances:")
        
        total_usd_value = 0
        for asset in balance:
            currency = asset.get('currency', 'Unknown')
            amount = float(asset.get('amount', 0))
            available = float(asset.get('available', 0))
            
            print(f"   - {currency}: {amount:.8f} (Available: {available:.8f})")
            
            # Calculate USD value for major currencies
            if currency == 'USD':
                total_usd_value += amount
            elif currency == 'BTC' and amount > 0:
                try:
                    btc_ticker = await gemini_client.get_ticker("BTCUSD")
                    btc_price = float(btc_ticker.get('last', 0))
                    usd_value = amount * btc_price
                    total_usd_value += usd_value
                    print(f"     (≈ ${usd_value:.2f} USD)")
                except:
                    pass
        
        print(f"\n   Estimated Total Portfolio Value: ${total_usd_value:,.2f}")
        
        return {
            "success": True,
            "portfolio_value": total_usd_value,
            "balances": balance
        }
        
    except Exception as e:
        print(f"[ERROR] Gemini API test failed: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    result = asyncio.run(test_gemini_connection())
    
    if result["success"]:
        print(f"\n[SUCCESS] Gemini API working! Portfolio value: ${result['portfolio_value']:,.2f}")
    else:
        print(f"\n[FAILED] Could not connect to Gemini API: {result['error']}")