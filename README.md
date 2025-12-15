# AI Scalping Bot for Binance Futures

A professional Python AI scalping bot for Binance Futures that uses high-probability technical indicators and price-action patterns to execute automated trades with advanced risk management.

## 🎯 Features

### Technical Indicators
- **EMA (Exponential Moving Average)**: Fast (9) and Slow (21) periods for trend identification
- **VWAP (Volume Weighted Average Price)**: Dynamic support/resistance levels
- **RSI (Relative Strength Index)**: Overbought/oversold conditions (14 period)
- **Volume Analysis**: Volume confirmation with 20-period moving average
- **ATR (Average True Range)**: Volatility-based position sizing and TP/SL calculation

### Price Action Patterns
- **Break of Structure (BOS)**: Identifies trend shifts and momentum changes
- **Liquidity Sweep**: Detects stop hunts and false breakouts
- **Pullback Detection**: Identifies retracement opportunities in trending markets

### Advanced Trading Strategy
- **4 Fibonacci-Based DCA Entries**: 
  - Entry 1: 40% position at market (immediate entry)
  - Entries 2-4: 20% each at Fibonacci levels (0.236, 0.382, 0.5, 0.618)
- **Single Take Profit**: 2.5x ATR from entry price
- **Single Stop Loss**: 1.5x ATR from entry price
- **Duplicate Order Prevention**: Checks existing positions and open orders
- **Dynamic Risk Management**: 2% risk per trade with leverage support

### Real-Time Alerts
- **Telegram Integration**: Receive instant notifications for:
  - Trade entries (all DCA levels)
  - Position updates
  - PnL tracking
  - Errors and warnings

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
```bash
export BINANCE_API_KEY="your_api_key_here"
export BINANCE_API_SECRET="your_api_secret_here"
export TELEGRAM_BOT_TOKEN="your_telegram_bot_token"  # Optional
export TELEGRAM_CHAT_ID="your_telegram_chat_id"      # Optional
```

## ⚙️ Configuration

The bot can be configured by modifying the `BotConfig` class in `ai_scalping_bot.py`:

```python
@dataclass
class BotConfig:
    # Trading parameters
    symbol: str = 'BTCUSDT'           # Trading pair
    timeframe: str = '5m'              # Candle timeframe
    leverage: int = 10                 # Leverage (1-125)
    
    # Risk management
    risk_per_trade: float = 0.02       # 2% risk per trade
    max_positions: int = 3             # Maximum concurrent positions
    
    # DCA levels (Fibonacci ratios)
    dca_levels: List[float] = [0.236, 0.382, 0.5, 0.618]
    
    # TP/SL (ATR multipliers)
    tp_atr_multiplier: float = 2.5
    sl_atr_multiplier: float = 1.5
    
    # Indicator periods
    ema_fast: int = 9
    ema_slow: int = 21
    rsi_period: int = 14
    atr_period: int = 14
    
    # Scan interval
    scan_interval: int = 60            # Seconds between market scans
```

## 🎮 Usage

### Running the Bot

```bash
python ai_scalping_bot.py
```

### First-Time Setup

1. **Test on Binance Testnet first**: Use testnet API keys to verify functionality
2. **Start with low leverage**: Begin with 1-3x leverage
3. **Monitor initial trades**: Watch the first few trades closely
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

1. **Entry 1 (40%)**: Market order for immediate entry
2. **Entry 2-4 (20% each)**: Limit orders at Fibonacci-based DCA levels
3. **Take Profit**: Single limit order at 2.5x ATR (reduce-only)
4. **Stop Loss**: Stop market order at 1.5x ATR (reduce-only)

### Risk Management

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