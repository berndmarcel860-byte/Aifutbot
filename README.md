# AI Scalping Bot for Binance Futures

A professional Python AI scalping bot for Binance Futures that scans multiple trading pairs, uses high-probability technical indicators and price-action patterns to identify best trading opportunities, and sends formatted signals to Telegram. Now with **automatic volatile coin selection**, **market direction filtering**, and **optional auto-trading**.

## 🎯 Features

### 🆕 NEW: Market Direction Filtering
- **Smart Direction Detection**: Analyzes BTC (or configurable symbol) to determine overall market trend
- **Directional Trading**: Only generates LONG signals in bullish markets, SHORT signals in bearish markets
- **Reduces Losses**: Prevents counter-trend trades that often result in losses
- **Configurable**: Can be enabled/disabled and uses customizable reference symbol

### 🆕 Automatic Volatile Coin Selection
- **Dynamic Symbol Selection**: Automatically identifies and scans the most volatile coins every cycle
- **Volatility Scoring**: Ranks coins by price change % and trading volume
- **Fresh Opportunities**: Symbol list refreshes on every scan to catch emerging trends
- **Position-Aware Filtering**: Automatically skips coins with existing positions or orders

### 🆕 NEW: Auto-Trading Mode
- **Optional Automatic Execution**: Enable `auto_trade` to execute signals automatically
- **Safe Default**: Auto-trading is OFF by default (signals-only mode)
- **Full DCA Implementation**: Automatically places all 4 entry orders, TP, and SL
- **Multi-Symbol Support**: Can trade multiple pairs simultaneously

### 🔍 Multi-Symbol Scanner
- **Intelligent Scanning**: Analyzes 20+ pairs simultaneously
- **Instant Signal Delivery**: Signals sent to Telegram immediately when found (no batching delays)
- **Best Opportunities First**: Scores and ranks all signals by quality
- **Smart Filtering**: Skips coins with open positions/orders to prevent conflicts
- **Continuous Monitoring**: Scans all pairs every 60 seconds

### Technical Indicators
- **EMA (Exponential Moving Average)**: Fast (9) and Slow (21) periods for trend identification
- **VWAP (Volume Weighted Average Price)**: Dynamic support/resistance levels
- **RSI (Relative Strength Index)**: Overbought/oversold conditions (14 period)
- **Volume Analysis**: Volume confirmation with 20-period moving average
- **ATR (Average True Range)**: Volatility-based position sizing and TP/SL calculation
- **Bollinger Bands**: 20-period bands with 2 standard deviations to detect extreme price levels
  - **Prevents Counter-Trend Trading**: Blocks SHORT signals at lower band (oversold), LONG signals at upper band (overbought)
  - **Enhances Entry Quality**: Adds bonus points for mean reversion setups at extremes

### 🆕 Advanced Technical Indicators (NEW)
- **MACD (Moving Average Convergence Divergence)**: 
  - Momentum indicator with 12/26/9 periods
  - Identifies trend reversals and momentum shifts
  - **+2 points** for bullish/bearish crossover with strong histogram
  - **+1 point** for simple crossover
- **Stochastic Oscillator**: 
  - 14-period %K and 3-period %D
  - Detects overbought (>80) and oversold (<20) conditions
  - **+2 points** for extreme levels (K&D >80 or <20)
  - **+1 point** for moderate levels
- **ADX (Average Directional Index)**:
  - 14-period trend strength indicator
  - Values >25 indicate strong trending market
  - **+1 point** when ADX >25 (confirms trend validity)
- **Ichimoku Cloud** (Simplified):
  - Tenkan-sen (9-period) and Kijun-sen (26-period)
  - Identifies support/resistance and trend direction
  - **+1 point** when Tenkan above Kijun (bullish) or below (bearish)
- **CMF (Chaikin Money Flow)**:
  - 20-period volume-weighted accumulation/distribution
  - Positive values indicate buying pressure, negative indicate selling
  - **+2 points** for strong pressure (>0.1 or <-0.1)
  - **+1 point** for mild pressure

### Price Action Patterns
- **Break of Structure (BOS)**: Identifies trend shifts and momentum changes
- **Liquidity Sweep**: Detects stop hunts and false breakouts
- **Pullback Detection**: Identifies retracement opportunities in trending markets

### Advanced Trading Strategy
- **4 Fibonacci-Based DCA Entries**: 
  - **Entry 1**: 10% position at **MARKET ORDER** (immediate fill at current price)
  - **Entries 2-4**: 30% each at **LIMIT ORDERS** (Fibonacci levels: 0.236, 0.382, 0.5 below/above entry)
  - Strategy: Enter immediately with small position, average in with larger amounts if price moves favorably
- **Single Take Profit**: 2.5x ATR from entry price (limit order)
- **Single Stop Loss**: 1.5x ATR from entry price (stop market order)
- **Duplicate Order Prevention**: Checks existing positions and open orders
- **Dynamic Risk Management**: 2% risk per trade with leverage support

### 📱 Formatted Telegram Signals
Receive beautifully formatted trading signals with market direction:
```
⚡⚡ BTCUSDT ⚡⚡ 📈
Exchange: Binance Futures
Direction: LONG
Market Price: $43,250.00

Leverage: Cross 10x

Entries:
1. $43,250.00 (MARKET - 10%)
2. $43,150.00 (LIMIT - 30%)
3. $43,100.00 (LIMIT - 30%)
4. $43,050.00 (LIMIT - 30%)

Take Profits:
1. $43,750.00

Stop Loss:
1. $42,900.00

📊 Signal Score: 8 points
🌍 Market: BULLISH
```

**Entry Strategy Explained:**
- **Entry 1** is placed as a MARKET order (executes immediately at best available price)
- **Entries 2-4** are placed as LIMIT orders at Fibonacci-based levels below the entry for LONG (above for SHORT)
- This allows you to enter quickly with 10%, then average in with 30% at each DCA level if price moves in your favor

### 📊 Signal Scoring System

The bot uses a multi-factor scoring system with **maximum possible score of 20+ points**. Default minimum threshold is 6 points.

**LONG Signal Scoring:**
- EMA alignment (fast > slow): +2 points
- Price above VWAP: +1 point
- RSI conditions: +1 to +2 points
- Bollinger Band extreme (oversold bounce): +2 points
- **MACD bullish**: +1 to +2 points
- **Stochastic oversold**: +1 to +2 points
- **ADX strong trend**: +1 point
- **Ichimoku bullish**: +1 point
- **CMF buying pressure**: +1 to +2 points
- Volume spike: +1 point
- Bullish BOS: +2 points
- Bullish liquidity sweep: +2 points
- Bullish pullback: +1 point

**SHORT Signal Scoring:** (inverse logic with same point structure)

**Score Interpretation:**
- **6-8 points**: Minimum quality signal, proceed with caution
- **9-12 points**: Good quality signal with multiple confirmations
- **13-16 points**: High quality signal with strong confluence
- **17+ points**: Exceptional signal with maximum confirmation

**Note:** The 5 new advanced indicators (MACD, Stochastic, ADX, Ichimoku, CMF) add up to 9 additional possible points, significantly improving signal accuracy and profitability.

## 📋 Requirements

- Python 3.8+
- Binance Futures account with API access
- (Optional) Telegram bot for notifications

## 🚀 Installation

1. **Clone the repository**:
```bash
git clone https://github.com/berndmarcel860-byte/Aifutbot.git
cd Aifutbot
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Set up environment variables**:

**Option A: Using .env file (Recommended)**
```bash
# Copy the example file
cp .env.example .env

# Edit .env and add your actual credentials
nano .env
```

Your `.env` file should look like:
```
BINANCE_API_KEY=your_actual_api_key
BINANCE_API_SECRET=your_actual_api_secret
TELEGRAM_BOT_TOKEN=your_telegram_token
TELEGRAM_CHAT_ID=your_chat_id
```

**Option B: Using export commands**
```bash
export BINANCE_API_KEY="your_api_key_here"
export BINANCE_API_SECRET="your_api_secret_here"
export TELEGRAM_BOT_TOKEN="your_telegram_bot_token"  # Optional
export TELEGRAM_CHAT_ID="your_telegram_chat_id"      # Optional
```

**⚠️ Important:** Make sure to actually replace the placeholder text with your real credentials!

**Verify your setup:**
```bash
# Run the environment check script
python check_env.py
```

**Need help?** See [SETUP_GUIDE.md](SETUP_GUIDE.md) for detailed instructions and troubleshooting.

**🔒 Security Note:** If you previously exposed your API keys publicly, see [SECURITY_NOTICE.md](SECURITY_NOTICE.md) for immediate action steps.

**❌ Getting API Errors?** See [API_TROUBLESHOOTING.md](API_TROUBLESHOOTING.md) for detailed solutions to common API issues.

## ⚙️ Configuration

The bot can be configured by modifying the `BotConfig` class in `ai_scalping_bot.py`:

```python
@dataclass
class BotConfig:
    # Market Direction Detection
    use_market_direction_filter: bool = True  # Enable market direction filtering
    market_direction_symbol: str = 'BTCUSDT'  # Symbol to determine market trend
    
    # Coin Selection
    auto_select_volatile_coins: bool = True  # Auto-select most volatile coins
    num_coins_to_scan: int = 20              # Number of coins to scan
    symbols_to_scan: List[str] = None        # Manual symbol list (if auto is False)
    
    # Trading Mode
    auto_trade: bool = False                 # Enable automatic trade execution
    timeframe: str = '5m'                    # Candle timeframe
    leverage: int = 10                       # Leverage (1-125)
    leverage_type: str = 'Cross'             # Cross or Isolated
    
    # Signal filtering
    max_signals_per_scan: int = 5            # Top N signals to send
    signal_threshold: int = 6                # Minimum score (0-20+, recommended: 6-8)
    
    # Risk management
    risk_per_trade: float = 0.02             # 2% risk per trade
    max_positions: int = 3                   # Maximum concurrent positions
    
    # DCA levels (Fibonacci ratios)
    dca_levels: List[float] = [0.236, 0.382, 0.5, 0.618]
    
    # TP/SL (ATR multipliers)
    tp_atr_multiplier: float = 2.5
    sl_atr_multiplier: float = 1.5
    
    # Scan interval
    scan_interval: int = 60                  # Seconds between market scans
```

### Key Configuration Options

**Market Direction Filtering:**
- `use_market_direction_filter = True`: Enables directional filtering (recommended)
- `market_direction_symbol = 'BTCUSDT'`: Symbol used to detect overall market trend
- In **BULLISH** markets: Only generates LONG signals
- In **BEARISH** markets: Only generates SHORT signals  
- In **NEUTRAL** markets: Allows both LONG and SHORT signals

**Volatile Coin Selection:**
- `auto_select_volatile_coins = True`: Bot automatically selects top N most volatile coins
- `num_coins_to_scan = 20`: How many volatile coins to scan each cycle
- Coins are re-selected every scan based on 24hr price change % and volume

**Trading Mode:**
- `auto_trade = False`: **SIGNALS ONLY** - Bot sends signals to Telegram (default, safe)
- `auto_trade = True`: **AUTO-EXECUTE** - Bot automatically executes trades (use with caution!)

**Position Management:**
- Bot automatically checks for existing positions/orders
- Skips coins that already have open positions or orders
- Prevents duplicate positions on the same coin

**Symbol Blacklist:**
- Create a `blacklist.txt` file to exclude specific symbols from signal generation
- Add symbols one per line (e.g., `ETHUSDT`, `BTCUSDT`)
- Lines starting with `#` are treated as comments
- The bot automatically loads and applies the blacklist on every scan
- Useful for avoiding pairs you don't want to trade

Example `blacklist.txt`:
```
# Blacklist for Trading Symbols
# Add symbols one per line
ETHUSDT
BTCUSDT
# BNBUSDT
```

## 🎮 Usage

### Running the Bot

```bash
python ai_scalping_bot.py
```

### Operating Modes

**Mode 1: Signals Only (Default - Recommended)**
- Set `auto_trade = False` in code
- Bot scans markets and sends signals to Telegram
- You manually execute trades based on signals
- Safer for beginners and testing

**Mode 2: Auto-Trading (Advanced)**
- Set `auto_trade = True` in code
- Bot automatically executes all trades
- Places market entry + limit DCA orders + TP/SL
- Monitor closely when enabled!

### What the Bot Does Each Cycle

1. **Detect Market Direction** (if enabled):
   - Fetches data for reference symbol (default: BTCUSDT)
   - Analyzes EMA alignment, price trends, and momentum
   - Determines: BULLISH, BEARISH, or NEUTRAL
   - Logs and displays market direction

2. **Select Coins** (if auto_select_volatile_coins = True):
   - Fetches 24hr ticker data for all USDT pairs
   - Calculates volatility score (price change % + volume)
   - Selects top N most volatile coins

3. **Check Existing Positions**:
   - Gets all open positions from Binance
   - Gets all open orders from Binance
   - Creates exclusion list of coins to skip

4. **Scan Selected Coins**:
   - Analyzes each coin (excluding those with positions)
   - Calculates indicators and patterns
   - Scores opportunities (0-12+ points)
   - **Filters by market direction** (LONG in bullish, SHORT in bearish)

5. **Send Top Signals**:
   - Sorts by score (highest first)
   - Sends top 5 signals to Telegram with market direction indicator
   - If auto_trade enabled, executes trades automatically

6. **Wait and Repeat**:
   - Waits 60 seconds (configurable)
   - Repeats from step 1

### Default Scanned Symbols (20 pairs)
When `auto_select_volatile_coins = False`, uses these pre-configured symbols:
BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, XRPUSDT, ADAUSDT, DOGEUSDT, MATICUSDT, DOTUSDT, AVAXUSDT, LINKUSDT, UNIUSDT, ATOMUSDT, LTCUSDT, NEARUSDT, APTUSDT, ARBUSDT, OPUSDT, SUIUSDT, INJUSDT
4. **Adjust parameters**: Fine-tune based on market conditions

### Safety Checks

The bot includes multiple safety features:
- ✅ Validates API credentials before starting
- ✅ Checks for existing positions to prevent duplicates
- ✅ Implements position size limits based on account balance
- ✅ Uses reduce-only orders for TP/SL
- ✅ Logs all actions to file and console

## 📊 How It Works

### Signal Generation

The bot uses a scoring system to generate high-probability trading signals:

**LONG Signal Requirements** (minimum 6 points):
- EMA alignment (fast > slow): +2 points
- Price above VWAP: +1 point
- RSI oversold (<30): +2 points, or RSI <50: +1 point
- Volume > 1.2x average: +1 point
- Bullish BOS: +2 points
- Bullish liquidity sweep: +2 points
- Bullish pullback: +1 point

**SHORT Signal Requirements** (minimum 6 points):
- EMA alignment (fast < slow): +2 points
- Price below VWAP: +1 point
- RSI overbought (>70): +2 points, or RSI >50: +1 point
- Volume > 1.2x average: +1 point
- Bearish BOS: +2 points
- Bearish liquidity sweep: +2 points
- Bearish pullback: +1 point

### Position Management

1. **Entry 1 (10%)**: Market order for immediate entry
2. **Entry 2-4 (30% each)**: Limit orders at Fibonacci-based DCA levels
3. **Take Profit**: Single limit order at 2.5x ATR (reduce-only)
4. **Stop Loss**: Stop market order at 1.0x ATR (reduce-only) - Optimized for fast scalping

### Risk Management

**Fast Scalping Risk/Reward System (Optimized):**
- **Take Profit**: 1.5x ATR - Quick exits for fast scalping trades
- **Stop Loss**: 1.0x ATR - Tight stops to minimize losses  
- **Risk:Reward Ratio**: 1.5:1 - Optimized for high-frequency trading
- **Strategy**: Allows SHORT positions even at lower Bollinger Band with proper risk management

- Position size calculated based on:
  - Account balance
  - Risk per trade (default 2%)
  - Distance from entry to stop loss
- Maximum leverage: Configurable (default 10x)
- Duplicate prevention: Always checks for existing positions/orders

## 📱 Telegram Setup

1. **Create a Telegram Bot**:
   - Message [@BotFather](https://t.me/botfather) on Telegram
   - Send `/newbot` and follow instructions
   - Copy your bot token

2. **Get Your Chat ID**:
   - Message [@userinfobot](https://t.me/userinfobot)
   - Copy your chat ID

3. **Set Environment Variables**:
```bash
export TELEGRAM_BOT_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="your_chat_id"
```

## 📝 Logging

The bot creates detailed logs in `scalping_bot.log`:
- All market analysis results
- Trade executions
- Position updates
- Errors and warnings

## ⚠️ Risk Warning

**IMPORTANT**: Trading cryptocurrencies with leverage is highly risky. This bot is provided as-is without any guarantees. Use at your own risk.

- ❗ Never invest more than you can afford to lose
- ❗ Always test on testnet first
- ❗ Start with minimal position sizes
- ❗ Monitor the bot regularly
- ❗ Understand the code before using it

## 🔧 Troubleshooting

### Common Issues

1. **API Connection Errors**:
   - Verify API keys are correct
   - Check API permissions (Futures trading enabled)
   - Ensure IP whitelist is configured (if used)

2. **Insufficient Balance**:
   - Deposit more USDT to your Futures account
   - Reduce position size by adjusting risk_per_trade

3. **Order Placement Failures**:
   - Check symbol precision requirements
   - Verify leverage is within allowed range
   - Ensure sufficient margin available

## 📚 Code Structure

The bot is organized into modular classes:

- `BotConfig`: Configuration and settings
- `BinanceFuturesClient`: API communication
- `TelegramNotifier`: Alert system
- `TechnicalIndicators`: Indicator calculations
- `PriceActionAnalyzer`: Pattern detection
- `SignalGenerator`: Trading signal logic
- `PositionManager`: Order execution and management
- `ScalpingBot`: Main bot orchestration

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

This project is open source and available under the MIT License.

## 🙏 Disclaimer

This software is for educational purposes only. Do not risk money which you are afraid to lose. USE THE SOFTWARE AT YOUR OWN RISK. THE AUTHORS AND ALL AFFILIATES ASSUME NO RESPONSIBILITY FOR YOUR TRADING RESULTS.

## 📞 Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Check the logs for detailed error information
- Review the code comments for implementation details

---

**Happy Trading! 🚀**