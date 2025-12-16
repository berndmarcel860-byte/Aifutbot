# API Troubleshooting Guide

## Common Binance API Errors and Solutions

### Error: "Invalid API" or Error Code -2015

**Problem:** Your API key is invalid, expired, or incorrectly configured.

**Solutions:**
1. **Verify API key is correct:**
   ```bash
   # Check your .env file
   cat .env
   
   # Make sure BINANCE_API_KEY matches exactly from Binance
   ```

2. **Regenerate API key:**
   - Go to https://www.binance.com/en/my/settings/api-management
   - Delete the old API key
   - Create a new one
   - Update your `.env` file with new credentials

3. **Check API key permissions:**
   - ✅ Enable "Enable Futures" permission
   - ✅ Enable "Enable Reading" permission  
   - ✅ Enable "Enable Spot & Margin Trading" (if needed)
   - ⚠️ "Enable Withdrawals" (NOT recommended - keep disabled)

---

### Error Code -1022: Invalid Signature

**Problem:** API secret doesn't match the API key, or there's a timing issue.

**Solutions:**
1. **Verify API secret:**
   ```bash
   # Check .env file has matching API key and secret pair
   python check_env.py
   ```

2. **Ensure no extra spaces:**
   ```bash
   # WRONG (has space after =):
   BINANCE_API_KEY= your_key
   
   # CORRECT (no spaces):
   BINANCE_API_KEY=your_key
   ```

3. **Check system time:**
   ```bash
   # Your system clock must be synchronized
   date
   
   # If off by more than 1 second, sync it:
   sudo ntpdate -s time.nist.gov
   ```

---

### Error: IP Restriction or "API-key format invalid"

**Problem:** Your IP address is not whitelisted for the API key.

**Solutions:**
1. **Check current IP:**
   ```bash
   curl ifconfig.me
   ```

2. **Update Binance API whitelist:**
   - Go to API Management → Edit API
   - Add your IP address to whitelist
   - OR remove IP restriction for testing (less secure)

3. **For dynamic IPs:**
   - Consider using "Unrestricted" (less secure)
   - Or use a VPS with static IP

---

### Error Code -2019: Insufficient Margin

**Problem:** Not enough balance to open the position.

**Solutions:**
1. **Check balance:**
   ```bash
   # The bot logs your balance when attempting trade
   grep "Account balance" scalping_bot.log
   ```

2. **Add more funds:**
   - Deposit USDT to your Futures wallet
   - Transfer from Spot to Futures wallet

3. **Reduce position size:**
   - Lower `risk_per_trade` in config (default: 0.02 = 2%)
   - Reduce leverage (default: 10x)

---

### Error Code -1111: Precision Error

**Problem:** Quantity has too many decimal places for the symbol.

**Solutions:**
1. **Check symbol precision:**
   - Most symbols: 3 decimal places
   - Some low-price coins: 0-1 decimal places

2. **Adjust in config:**
   ```python
   quantity_precision: int = 3  # Change to 0, 1, 2, or 3
   ```

3. **Check Binance exchange info:**
   ```bash
   curl https://fapi.binance.com/fapi/v1/exchangeInfo | grep -A 20 "XRPUSDT"
   ```

---

### Error Code -4131: Percent Price Filter

**Problem:** Your limit order price is too far from the current market price.

**Solutions:**
1. **Check current market price:**
   ```python
   # The bot uses ATR-based calculations which should be safe
   # But in very volatile markets, prices can move fast
   ```

2. **Reduce ATR multiplier:**
   ```python
   # In BotConfig, reduce these:
   tp_atr_multiplier: float = 2.5  # Try 2.0
   sl_atr_multiplier: float = 1.5  # Try 1.2
   ```

3. **Wait for market stabilization:**
   - During extreme volatility, wait for calmer conditions

---

### Error Code -2021: Order Would Immediately Trigger

**Problem:** Your limit order price is set such that it would execute immediately (like a market order).

**Solutions:**
1. **This is normal for DCA orders:**
   - If market moved past your DCA level before order placed
   - Binance rejects to prevent accidental market execution

2. **Solution:**
   - Bot should handle this gracefully (logs error, continues)
   - DCA orders that can't be placed will be skipped

---

### Error: "Permission Denied" or "This action is unauthorized"

**Problem:** API key doesn't have required permissions.

**Solutions:**
1. **Enable Futures Trading:**
   - Go to API Management → Edit
   - Check "Enable Futures"
   - Save changes

2. **Enable Trading permission:**
   - Check "Enable Spot & Margin Trading"
   - Or "Enable Futures Trading"

3. **Regenerate API after changing permissions:**
   - Sometimes permissions don't apply immediately
   - Safest to delete and recreate API key

---

## Testing Your API Setup

### Step 1: Verify Environment Variables

```bash
# Run the check script
python check_env.py

# Should show:
# ✅ BINANCE_API_KEY: OvtT... (64 characters)
# ✅ BINANCE_API_SECRET: 78Ax... (64 characters)
```

### Step 2: Test API Connection

Create `test_api.py`:

```python
import os
from dotenv import load_dotenv
load_dotenv()

from ai_scalping_bot import BinanceFuturesClient, BotConfig

# Create config and client
config = BotConfig()
client = BinanceFuturesClient(config)

print("Testing API connection...")

try:
    # Test 1: Get account balance
    balance = client.get_account_balance()
    print(f"✅ Balance: ${balance:.2f}")
    
    # Test 2: Get BTC price
    klines = client.get_klines('BTCUSDT', '5m', limit=10)
    print(f"✅ Got {len(klines)} candles for BTCUSDT")
    
    # Test 3: Check open positions
    positions = client.get_all_positions()
    print(f"✅ Open positions: {len(positions)}")
    
    print("\n🎉 All API tests passed!")
    print("Your API is configured correctly.")
    
except Exception as e:
    print(f"\n❌ API test failed: {e}")
    print("\nCheck the error message above and refer to the troubleshooting guide.")
```

Run it:
```bash
python test_api.py
```

### Step 3: Test with Binance Testnet (Recommended)

**Why use testnet:**
- No real money at risk
- Test all bot features safely
- Same API as production

**Setup testnet:**

1. Get testnet API keys: https://testnet.binancefuture.com/

2. Update `.env`:
   ```bash
   BINANCE_API_KEY=your_testnet_api_key
   BINANCE_API_SECRET=your_testnet_api_secret
   ```

3. Update `ai_scalping_bot.py` (or set via environment):
   ```python
   base_url: str = 'https://testnet.binancefuture.com'
   ```

4. Run bot:
   ```bash
   python ai_scalping_bot.py
   ```

---

## API Best Practices

### Security

1. **Never share API keys:**
   - Don't post in comments, forums, or chat
   - Don't commit to git (use .env)
   - Regenerate if accidentally exposed

2. **Use IP restrictions:**
   - Add your server/home IP to whitelist
   - More secure than unrestricted

3. **Minimal permissions:**
   - Only enable what you need
   - Never enable "Enable Withdrawals" unless absolutely necessary

4. **Regular key rotation:**
   - Regenerate API keys every few months
   - Update `.env` file with new keys

### Performance

1. **Rate limits:**
   - Binance has rate limits (1200 req/min)
   - Bot respects these with delays
   - Don't run multiple instances with same key

2. **Order delays:**
   - Bot uses `order_delay` between orders
   - Default: 1 second
   - Increase if getting rate limit errors

### Monitoring

1. **Check logs:**
   ```bash
   tail -f scalping_bot.log
   ```

2. **Monitor Telegram:**
   - Bot sends all important notifications
   - Trade entries, errors, signals

3. **Check Binance app:**
   - Verify positions match expectations
   - Monitor PnL
   - Check for unexpected orders

---

## Still Having Issues?

### Diagnostic Information

Run these commands and share the output (hide sensitive data):

```bash
# 1. Check environment
python check_env.py

# 2. Check bot can start
python ai_scalping_bot.py --help  # If available

# 3. Check logs
tail -n 50 scalping_bot.log

# 4. Check Binance API status
curl https://fapi.binance.com/fapi/v1/ping
```

### Common Mistakes Checklist

- [ ] API key copied correctly (no extra spaces)
- [ ] API secret copied correctly (no extra spaces)
- [ ] Futures trading enabled in API settings
- [ ] IP whitelisted (or restrictions removed)
- [ ] System time synchronized (within 1 second)
- [ ] Sufficient balance in Futures wallet
- [ ] `.env` file in same directory as bot
- [ ] `python-dotenv` installed (`pip install python-dotenv`)
- [ ] Running bot in same directory as `.env`

---

## Quick Reference

| Error Code | Meaning | Quick Fix |
|------------|---------|-----------|
| -2015 | Invalid API key | Check BINANCE_API_KEY in .env |
| -1022 | Invalid signature | Check BINANCE_API_SECRET in .env |
| -2019 | Insufficient margin | Add funds or reduce position size |
| -1111 | Precision error | Adjust quantity_precision |
| -4131 | Price filter | Reduce ATR multipliers |
| -2021 | Would trigger immediately | Normal for fast-moving markets |

---

**Remember:** Always test on **Binance Futures Testnet** first before using real funds!
