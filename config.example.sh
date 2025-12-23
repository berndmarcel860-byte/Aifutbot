#!/bin/bash
# Environment Configuration Template for AI Scalping Bot
# Copy this file and fill in your actual values

# Binance Futures API Credentials (REQUIRED)
# Get these from: https://www.binance.com/en/my/settings/api-management
export BINANCE_API_KEY="your_binance_api_key_here"
export BINANCE_API_SECRET="your_binance_api_secret_here"

# Telegram Bot Configuration (OPTIONAL - for trade alerts)
# Create bot: https://t.me/botfather
# Get chat ID: https://t.me/userinfobot
export TELEGRAM_BOT_TOKEN="your_telegram_bot_token_here"
export TELEGRAM_CHAT_ID="your_telegram_chat_id_here"

# Note: For production use, consider using a more secure method
# such as a secrets manager or encrypted configuration file
