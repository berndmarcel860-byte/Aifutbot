#!/usr/bin/env python3
"""
Simple script to check if environment variables are properly set.
Run this before starting the bot to verify your configuration.

Usage: python check_env.py
"""

import os
import sys

def check_env():
    """Check if required environment variables are set"""
    print("=" * 60)
    print("ENVIRONMENT VARIABLE CHECK")
    print("=" * 60)
    
    # Required variables
    required_vars = {
        'BINANCE_API_KEY': 'Required for trading',
        'BINANCE_API_SECRET': 'Required for trading'
    }
    
    # Optional variables
    optional_vars = {
        'TELEGRAM_BOT_TOKEN': 'Optional for notifications',
        'TELEGRAM_CHAT_ID': 'Optional for notifications'
    }
    
    all_good = True
    
    # Check required
    print("\n🔑 Required Environment Variables:")
    print("-" * 60)
    for var, desc in required_vars.items():
        value = os.getenv(var)
        if value:
            # Mask the value for security
            masked = value[:8] + "..." + value[-4:] if len(value) > 12 else "***"
            print(f"✅ {var}: {masked}")
            print(f"   Length: {len(value)} characters")
        else:
            print(f"❌ {var}: NOT SET")
            print(f"   {desc}")
            all_good = False
    
    # Check optional
    print("\n📱 Optional Environment Variables:")
    print("-" * 60)
    for var, desc in optional_vars.items():
        value = os.getenv(var)
        if value:
            masked = value[:8] + "..." + value[-4:] if len(value) > 12 else "***"
            print(f"✅ {var}: {masked}")
            print(f"   Length: {len(value)} characters")
        else:
            print(f"⚠️  {var}: NOT SET")
            print(f"   {desc}")
    
    # Final verdict
    print("\n" + "=" * 60)
    if all_good:
        print("✅ All required environment variables are set!")
        print("You can now run: python ai_scalping_bot.py")
    else:
        print("❌ Some required environment variables are missing!")
        print("\nTo set them, run:")
        print("  export BINANCE_API_KEY='your_actual_api_key'")
        print("  export BINANCE_API_SECRET='your_actual_api_secret'")
        print("  export TELEGRAM_BOT_TOKEN='your_bot_token'  # Optional")
        print("  export TELEGRAM_CHAT_ID='your_chat_id'      # Optional")
        print("\nThen run this check script again to verify.")
    print("=" * 60)
    
    return all_good

if __name__ == "__main__":
    success = check_env()
    sys.exit(0 if success else 1)
