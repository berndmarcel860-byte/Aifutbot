# Environment Setup Guide

## Setting Environment Variables on Linux/Mac

### Method 1: Temporary (Current Session Only)

```bash
export BINANCE_API_KEY="your_actual_api_key_here"
export BINANCE_API_SECRET="your_actual_api_secret_here"
export TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
export TELEGRAM_CHAT_ID="your_telegram_chat_id"
```

**Important:** Replace the placeholder text with your actual credentials (remove quotes if they contain special characters)

### Method 2: Persistent (All Sessions)

Add to `~/.bashrc` or `~/.bash_profile`:

```bash
# Open the file
nano ~/.bashrc

# Add these lines at the end:
export BINANCE_API_KEY="your_actual_api_key_here"
export BINANCE_API_SECRET="your_actual_api_secret_here"
export TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
export TELEGRAM_CHAT_ID="your_telegram_chat_id"

# Save and reload
source ~/.bashrc
```

### Method 3: Using .env File (Recommended)

1. Create a `.env` file in the project directory:

```bash
# Create .env file
cat > .env << 'EOF'
BINANCE_API_KEY=your_actual_api_key_here
BINANCE_API_SECRET=your_actual_api_secret_here
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
EOF
```

2. Load before running the bot:

```bash
# Load environment variables from .env
export $(cat .env | xargs)

# Then run the bot
python ai_scalping_bot.py
```

Or use a single command:
```bash
export $(cat .env | xargs) && python ai_scalping_bot.py
```

## Verification

### Step 1: Check if variables are set

Run the verification script:
```bash
python check_env.py
```

This will show you:
- ✅ Which variables are set correctly
- ❌ Which variables are missing
- The length of each variable (to verify it's not empty)

### Step 2: Manual verification

```bash
# Check if variables are set
echo $BINANCE_API_KEY
echo $BINANCE_API_SECRET

# Should show your actual keys (NOT empty)
```

### Step 3: Test in Python

```bash
python3 << 'EOF'
import os
print("API Key:", os.getenv('BINANCE_API_KEY', 'NOT SET'))
print("API Secret:", os.getenv('BINANCE_API_SECRET', 'NOT SET'))
EOF
```

Should output your keys, not "NOT SET"

## Common Issues & Solutions

### Issue 1: Variables not persisting

**Problem:** Variables work in one terminal but not another

**Solution:** 
- You set them in one terminal session
- They need to be set in EVERY terminal session
- Use Method 2 (add to ~/.bashrc) for persistence

### Issue 2: Bot still shows "credentials not found"

**Problem:** Environment variables are set but bot doesn't see them

**Solutions:**
1. Make sure you export (not just set):
   ```bash
   # WRONG:
   BINANCE_API_KEY="your_key"
   
   # CORRECT:
   export BINANCE_API_KEY="your_key"
   ```

2. Start bot in the SAME terminal where you set variables

3. If using systemd/service, set variables in the service file:
   ```ini
   [Service]
   Environment="BINANCE_API_KEY=your_key"
   Environment="BINANCE_API_SECRET=your_secret"
   ```

### Issue 3: Quotes causing issues

**Problem:** Keys with special characters not working

**Try different quote styles:**
```bash
# Single quotes (preserves everything literally)
export BINANCE_API_KEY='your_key_here'

# Double quotes (allows variable expansion)
export BINANCE_API_KEY="your_key_here"

# No quotes (if key has no spaces/special chars)
export BINANCE_API_KEY=your_key_here
```

### Issue 4: Space after equals sign

**WRONG:**
```bash
export BINANCE_API_KEY= "your_key"  # Space before quote
export BINANCE_API_KEY = "your_key" # Spaces around =
```

**CORRECT:**
```bash
export BINANCE_API_KEY="your_key"   # No spaces
```

## Security Best Practices

1. **Never hardcode credentials in code files**
2. **Add .env to .gitignore**
3. **Use restricted file permissions for .env:**
   ```bash
   chmod 600 .env
   ```
4. **Regenerate API keys if exposed publicly**

## Quick Start Script

Create a `start_bot.sh` script:

```bash
#!/bin/bash

# Load environment variables
export BINANCE_API_KEY="your_actual_api_key"
export BINANCE_API_SECRET="your_actual_api_secret"
export TELEGRAM_BOT_TOKEN="your_telegram_token"
export TELEGRAM_CHAT_ID="your_chat_id"

# Verify they're set
echo "Checking environment..."
python check_env.py

# If check passes, start the bot
if [ $? -eq 0 ]; then
    echo "Starting bot..."
    python ai_scalping_bot.py
else
    echo "Fix environment variables first!"
fi
```

Make it executable and run:
```bash
chmod +x start_bot.sh
./start_bot.sh
```

## Testing with Testnet

For testing, use Binance Futures Testnet:

1. Get testnet API keys from: https://testnet.binancefuture.com/
2. Set environment variables:
   ```bash
   export BINANCE_API_KEY="testnet_key"
   export BINANCE_API_SECRET="testnet_secret"
   ```
3. Update code to use testnet URL (or set via environment):
   ```python
   base_url: str = 'https://testnet.binancefuture.com'
   ```

## Still Having Issues?

Run these diagnostic commands and share the output:

```bash
# 1. Check if variables exist
env | grep BINANCE
env | grep TELEGRAM

# 2. Run the check script
python check_env.py

# 3. Check Python can access them
python3 -c "import os; print('Key length:', len(os.getenv('BINANCE_API_KEY', '')))"

# 4. Show how you're starting the bot
ps aux | grep python
```
