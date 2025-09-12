#!/usr/bin/env python3
"""
Test updated Gemini authentication with better error handling
"""
import asyncio
from app.services.gemini_client import GeminiClient

async def test_simple_auth():
    client = GeminiClient()
    
    try:
        print("Testing Gemini authentication...")
        balance = await client.get_account_balance()
        print(f"✓ Success! Got balance data: {len(balance)} currencies")
        for asset in balance:
            print(f"  {asset.get('currency')}: {asset.get('amount')}")
        return balance
        
    except Exception as e:
        print(f"✗ Error: {e}")
        
        # Try to get more detailed error info
        try:
            import httpx
            # Make a direct request to see the exact error
            response = await client.client.post(
                f"{client.base_url}/v1/balances",
                headers=client._get_auth_headers({
                    "request": "/v1/balances",
                    "nonce": client._get_nonce()
                })
            )
            print(f"Response status: {response.status_code}")
            print(f"Response text: {response.text}")
        except Exception as e2:
            print(f"Debug request failed: {e2}")
        
        return None

if __name__ == "__main__":
    asyncio.run(test_simple_auth())