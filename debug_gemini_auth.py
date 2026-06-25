#!/usr/bin/env python3
"""
Debug Gemini API authentication
"""
import httpx
import hmac
import hashlib
import base64
import time
import json
from app.core.config import settings

def debug_gemini_auth():
    print("Debugging Gemini Authentication...")
    print(f"API Key: {settings.GEMINI_API_KEY}")
    print("API Secret: ***redacted***")
    
    # Test the auth signature generation
    endpoint = "/v1/balances"
    nonce = str(int(time.time() * 1000))
    
    payload = {
        "request": endpoint,
        "nonce": nonce
    }
    
    print(f"\nPayload: {payload}")
    
    # Create signature
    payload_str = json.dumps(payload)
    print(f"Payload string: {payload_str}")
    
    encoded_payload = base64.b64encode(payload_str.encode()).decode()
    print(f"Encoded payload: {encoded_payload}")
    
    signature = hmac.new(
        settings.GEMINI_API_SECRET.encode(),
        encoded_payload.encode(),
        hashlib.sha384
    ).hexdigest()
    
    print(f"Signature: {signature}")
    
    headers = {
        "Content-Type": "text/plain",
        "Content-Length": "0",
        "X-GEMINI-APIKEY": settings.GEMINI_API_KEY,
        "X-GEMINI-PAYLOAD": encoded_payload,
        "X-GEMINI-SIGNATURE": signature,
        "Cache-Control": "no-cache"
    }
    
    print(f"Headers: {headers}")
    
    # Make request
    try:
        url = f"{settings.GEMINI_BASE_URL}{endpoint}"
        print(f"\nMaking request to: {url}")
        
        response = httpx.post(url, headers=headers)
        print(f"Response status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        print(f"Response text: {response.text}")
        
        if response.status_code == 200:
            print("[SUCCESS] Authentication working!")
            return json.loads(response.text)
        else:
            print(f"[ERROR] Authentication failed: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"[ERROR] Request failed: {e}")
        return None

if __name__ == "__main__":
    debug_gemini_auth()