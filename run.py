#!/usr/bin/env python3
"""
Startup script for the Crypto Trading Bot
"""
import uvicorn
import asyncio
import os
from app.core.config import settings

def main():
    """Main entry point for the trading bot"""
    
    # Ensure data directories exist
    os.makedirs("data/db", exist_ok=True)
    os.makedirs("data/exports", exist_ok=True)
    
    # Check environment variables
    if not settings.GEMINI_API_KEY or not settings.GEMINI_API_SECRET:
        print("WARNING: Gemini API credentials not found in environment variables!")
        print("Please set GEMINI_API_KEY and GEMINI_API_SECRET in your .env file")
        print("Using sandbox environment for testing...")
    else:
        # Mask the credentials for security
        masked_key = f"{settings.GEMINI_API_KEY[:10]}...{settings.GEMINI_API_KEY[-4:]}"
        masked_secret = f"{settings.GEMINI_API_SECRET[:6]}...{settings.GEMINI_API_SECRET[-4:]}"
        print(f"[OK] Gemini API Key loaded: {masked_key}")
        print(f"[OK] Gemini API Secret loaded: {masked_secret}")
        print(f"[INFO] Sandbox mode: {settings.GEMINI_SANDBOX}")
    
    print(f"\n[STARTUP] Starting Crypto Trading Bot on {settings.HOST}:{settings.PORT}")
    print(f"[DB] Database: {settings.DATABASE_URL}")
    print(f"[CONFIG] Debug mode: {settings.DEBUG}")
    print(f"[API] Gemini URL: {settings.GEMINI_BASE_URL}")
    print(f"[WS] WebSocket URL: {settings.GEMINI_WS_URL}")
    print("\n" + "="*60)
    
    # Start the FastAPI server
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info" if not settings.DEBUG else "debug"
    )

if __name__ == "__main__":
    main()