#!/usr/bin/env python3
"""
Professional AI Scalping Bot for Binance Futures
Implements high-probability indicators, price-action patterns, DCA strategy, and risk management
"""

import os
import json
import time
import hmac
import hashlib
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlencode
import requests
import numpy as np
import pandas as pd
from dataclasses import dataclass, asdict

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()  # Load .env file if it exists
except ImportError:
    # python-dotenv not installed, will use system environment variables only
    pass


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class BotConfig:
    """Bot configuration parameters"""
    # Binance API
    api_key: str = os.getenv('BINANCE_API_KEY', '')
    api_secret: str = os.getenv('BINANCE_API_SECRET', '')
    base_url: str = 'https://fapi.binance.com'
    
    # Telegram
    telegram_token: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
    telegram_chat_id: str = os.getenv('TELEGRAM_CHAT_ID', '')
    
    # Trading parameters
    symbol: str = 'BTCUSDT'
    symbols_to_scan: List[str] = None  # Will be set to popular futures pairs
    auto_select_volatile_coins: bool = True  # Automatically select most volatile coins
    num_coins_to_scan: int = 20  # Number of most volatile coins to scan
    timeframe: str = '5m'  # 5-minute candles
    leverage: int = 10
    leverage_type: str = 'Cross'  # Cross or Isolated
    auto_trade: bool = False  # Automatically execute trades (False = signals only)
    
    # Risk management
    risk_per_trade: float = 0.02  # 2% of account per trade
    max_positions: int = 3
    max_signals_per_scan: int = 5  # Maximum signals to send per scan
    
    # DCA parameters (Fibonacci levels)
    dca_levels: List[float] = None  # Will be set to [0.236, 0.382, 0.5, 0.618]
    dca_multiplier: float = 1.5  # Position size multiplier for DCA entries
    
    # Indicator parameters
    ema_fast: int = 9
    ema_slow: int = 21
    rsi_period: int = 14
    rsi_overbought: float = 70
    rsi_oversold: float = 30
    atr_period: int = 14
    volume_ma_period: int = 20
    
    # TP/SL parameters
    tp_atr_multiplier: float = 1.5  # Fast scalping: quick take profit
    sl_atr_multiplier: float = 1.0  # Tight stop loss for better R:R (1.5:1)
    
    # Pattern detection
    bos_lookback: int = 20
    liquidity_sweep_threshold: float = 0.001  # 0.1%
    
    # Signal generation
    signal_threshold: int = 6  # Minimum score for signal generation
    market_direction_symbol: str = 'BTCUSDT'  # Symbol to use for overall market direction
    use_market_direction_filter: bool = True  # Filter signals based on market direction
    
    # Operational
    scan_interval: int = 60  # seconds
    order_delay: int = 1  # seconds between order placements
    position_update_frequency: int = 10  # cycles between position updates
    error_retry_delay: int = 60  # seconds to wait after error
    quantity_precision: int = 3  # decimal places for order quantities
    blacklist_file: str = 'blacklist.txt'  # File containing symbols to exclude
    
    def __post_init__(self):
        if self.dca_levels is None:
            self.dca_levels = [0.236, 0.382, 0.5, 0.618]
        if self.symbols_to_scan is None:
            # Popular Binance Futures pairs with good liquidity
            self.symbols_to_scan = [
                'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT',
                'ADAUSDT', 'DOGEUSDT', 'MATICUSDT', 'DOTUSDT', 'AVAXUSDT',
                'LINKUSDT', 'UNIUSDT', 'ATOMUSDT', 'LTCUSDT', 'NEARUSDT',
                'APTUSDT', 'ARBUSDT', 'OPUSDT', 'SUIUSDT', 'INJUSDT'
            ]


# ============================================================================
# LOGGING SETUP
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scalping_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# BINANCE FUTURES API CLIENT
# ============================================================================

class BinanceFuturesClient:
    """Binance Futures API client with authentication"""
    
    def __init__(self, config: BotConfig):
        self.config = config
        self.base_url = config.base_url
        self.api_key = config.api_key
        self.api_secret = config.api_secret
        self.session = requests.Session()
        self.session.headers.update({
            'X-MBX-APIKEY': self.api_key
        })
    
    def _sign(self, params: Dict) -> str:
        """Generate signature for authenticated requests"""
        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def _request(self, method: str, endpoint: str, signed: bool = False, **kwargs) -> Dict:
        """Make API request"""
        url = f"{self.base_url}{endpoint}"
        
        if signed:
            params = kwargs.get('params', {})
            params['timestamp'] = int(time.time() * 1000)
            params['signature'] = self._sign(params)
            kwargs['params'] = params
        
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            error_msg = f"API request error: {e}"
            
            # Extract more specific error information
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    error_code = error_data.get('code', 'Unknown')
                    error_message = error_data.get('msg', str(e))
                    error_msg = f"Binance API Error {error_code}: {error_message}"
                    
                    # Provide helpful hints for common errors
                    if error_code == -2015:
                        error_msg += "\n💡 Hint: Invalid API key. Check your BINANCE_API_KEY in .env file"
                    elif error_code == -1022:
                        error_msg += "\n💡 Hint: Invalid signature. Check your BINANCE_API_SECRET in .env file"
                    elif error_code == -2021:
                        error_msg += "\n💡 Hint: Order would immediately trigger. Adjust your entry price"
                    elif error_code == -4131:
                        error_msg += "\n💡 Hint: Percent price filter check failed. Price too far from market"
                    elif error_code == -1111:
                        error_msg += "\n💡 Hint: Invalid precision. Check quantity decimal places"
                    elif error_code == -2019:
                        error_msg += "\n💡 Hint: Insufficient margin. Add more funds or reduce position size"
                    elif 'IP' in error_message or 'ip' in error_message:
                        error_msg += "\n💡 Hint: IP restriction. Add your IP to API whitelist or remove restrictions"
                    elif 'permission' in error_message.lower():
                        error_msg += "\n💡 Hint: Enable 'Futures Trading' permission in API settings"
                        
                except:
                    if hasattr(e.response, 'text'):
                        error_msg += f"\nResponse: {e.response.text}"
            
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def get_klines(self, symbol: str, interval: str, limit: int = 500) -> List[List]:
        """Get candlestick data"""
        endpoint = '/fapi/v1/klines'
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        return self._request('GET', endpoint, params=params)
    
    def get_account_balance(self) -> float:
        """Get USDT balance"""
        endpoint = '/fapi/v2/balance'
        balances = self._request('GET', endpoint, signed=True)
        for balance in balances:
            if balance['asset'] == 'USDT':
                return float(balance['availableBalance'])
        return 0.0
    
    def get_position(self, symbol: str) -> Optional[Dict]:
        """Get current position for symbol"""
        endpoint = '/fapi/v2/positionRisk'
        positions = self._request('GET', endpoint, signed=True)
        for position in positions:
            if position['symbol'] == symbol:
                pos_amt = float(position['positionAmt'])
                if pos_amt != 0:
                    return {
                        'symbol': symbol,
                        'position_amt': pos_amt,
                        'entry_price': float(position['entryPrice']),
                        'unrealized_pnl': float(position['unRealizedProfit']),
                        'leverage': int(position['leverage']),
                        'side': 'LONG' if pos_amt > 0 else 'SHORT'
                    }
        return None
    
    def get_open_orders(self, symbol: str) -> List[Dict]:
        """Get open orders for symbol"""
        endpoint = '/fapi/v1/openOrders'
        params = {'symbol': symbol}
        return self._request('GET', endpoint, signed=True, params=params)
    
    def set_leverage(self, symbol: str, leverage: int) -> Dict:
        """Set leverage for symbol"""
        endpoint = '/fapi/v1/leverage'
        params = {
            'symbol': symbol,
            'leverage': leverage
        }
        return self._request('POST', endpoint, signed=True, params=params)
    
    def place_order(self, symbol: str, side: str, order_type: str, 
                   quantity: float, price: Optional[float] = None,
                   stop_price: Optional[float] = None,
                   reduce_only: bool = False) -> Dict:
        """Place an order"""
        endpoint = '/fapi/v1/order'
        params = {
            'symbol': symbol,
            'side': side,
            'type': order_type,
            'quantity': quantity
        }
        
        if price:
            params['price'] = price
            params['timeInForce'] = 'GTC'
        
        if stop_price:
            params['stopPrice'] = stop_price
        
        if reduce_only:
            params['reduceOnly'] = 'true'
        
        return self._request('POST', endpoint, signed=True, params=params)
    
    def cancel_all_orders(self, symbol: str) -> Dict:
        """Cancel all open orders for symbol"""
        endpoint = '/fapi/v1/allOpenOrders'
        params = {'symbol': symbol}
        return self._request('DELETE', endpoint, signed=True, params=params)
    
    def get_mark_price(self, symbol: str) -> float:
        """Get current mark price"""
        endpoint = '/fapi/v1/premiumIndex'
        params = {'symbol': symbol}
        data = self._request('GET', endpoint, params=params)
        return float(data['markPrice'])
    
    def get_exchange_info(self) -> Dict:
        """Get exchange trading rules and symbol information"""
        endpoint = '/fapi/v1/exchangeInfo'
        return self._request('GET', endpoint)
    
    def get_24hr_ticker(self) -> List[Dict]:
        """Get 24hr ticker price change statistics for all symbols"""
        endpoint = '/fapi/v1/ticker/24hr'
        return self._request('GET', endpoint)
    
    def get_all_positions(self) -> List[Dict]:
        """Get all current positions"""
        endpoint = '/fapi/v2/positionRisk'
        positions = self._request('GET', endpoint, signed=True)
        active_positions = []
        for position in positions:
            pos_amt = float(position['positionAmt'])
            if pos_amt != 0:
                active_positions.append({
                    'symbol': position['symbol'],
                    'position_amt': pos_amt,
                    'entry_price': float(position['entryPrice']),
                    'unrealized_pnl': float(position['unRealizedProfit']),
                    'leverage': int(position['leverage']),
                    'side': 'LONG' if pos_amt > 0 else 'SHORT'
                })
        return active_positions
    
    def get_all_open_orders(self) -> List[Dict]:
        """Get all open orders"""
        endpoint = '/fapi/v1/openOrders'
        return self._request('GET', endpoint, signed=True)


# ============================================================================
# TELEGRAM NOTIFICATIONS
# ============================================================================

class TelegramNotifier:
    """Send trading alerts to Telegram"""
    
    def __init__(self, config: BotConfig):
        self.token = config.telegram_token
        self.chat_id = config.telegram_chat_id
        self.enabled = bool(self.token and self.chat_id)
    
    def send_message(self, message: str):
        """Send message to Telegram"""
        if not self.enabled:
            logger.warning("Telegram not configured, skipping notification")
            return
        
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        data = {
            'chat_id': self.chat_id,
            'text': message,
            'parse_mode': 'HTML'
        }
        
        try:
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            logger.info("Telegram notification sent successfully")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Telegram notification: {e}")
    
    def send_trade_alert(self, trade_type: str, symbol: str, side: str, 
                        price: float, quantity: float, reason: str):
        """Send trade execution alert"""
        message = (
            f"🤖 <b>{trade_type}</b>\n"
            f"Symbol: {symbol}\n"
            f"Side: {side}\n"
            f"Price: ${price:.2f}\n"
            f"Quantity: {quantity:.4f}\n"
            f"Reason: {reason}\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        self.send_message(message)
    
    def send_position_update(self, symbol: str, pnl: float, pnl_pct: float):
        """Send position update"""
        emoji = "📈" if pnl > 0 else "📉"
        message = (
            f"{emoji} <b>Position Update</b>\n"
            f"Symbol: {symbol}\n"
            f"PnL: ${pnl:.2f} ({pnl_pct:.2f}%)\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        self.send_message(message)
    
    def send_signal_alert(self, symbol: str, direction: str, market_price: float,
                         leverage: int, leverage_type: str, entries: List[float],
                         take_profit: float, stop_loss: float, score: int = None,
                         market_direction: str = None):
        """Send formatted trading signal alert"""
        # Add market direction indicator
        market_emoji = ""
        if market_direction:
            if market_direction == "BULLISH":
                market_emoji = " 📈"
            elif market_direction == "BEARISH":
                market_emoji = " 📉"
            elif market_direction == "NEUTRAL":
                market_emoji = " ↔️"
        
        message = (
            f"⚡⚡ <b>{symbol}</b> ⚡⚡{market_emoji}\n"
            f"Exchange: Binance Futures\n"
            f"Direction: {direction}\n"
            f"Market Price: ${market_price:.4f}\n\n"
            f"Leverage: {leverage_type} {leverage}x\n\n"
            f"<b>Entries:</b>\n"
        )
        
        for i, entry in enumerate(entries, 1):
            if i == 1:
                message += f"{i}. ${entry:.4f} (MARKET - 10%)\n"
            else:
                message += f"{i}. ${entry:.4f} (LIMIT - 30%)\n"
        
        message += (
            f"\n<b>Take Profits:</b>\n"
            f"1. ${take_profit:.4f}\n\n"
            f"<b>Stop Loss:</b>\n"
            f"1. ${stop_loss:.4f}"
        )
        
        if score:
            message += f"\n\n📊 Signal Score: {score} points"
        
        if market_direction:
            message += f"\n🌍 Market: {market_direction}"
        
        self.send_message(message)


# ============================================================================
# TECHNICAL INDICATORS
# ============================================================================

class TechnicalIndicators:
    """Calculate technical indicators"""
    
    @staticmethod
    def ema(data: pd.Series, period: int) -> pd.Series:
        """Exponential Moving Average"""
        return data.ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def rsi(data: pd.Series, period: int = 14) -> pd.Series:
        """Relative Strength Index"""
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """Average True Range"""
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()
    
    @staticmethod
    def vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
        """Volume Weighted Average Price"""
        typical_price = (high + low + close) / 3
        return (typical_price * volume).cumsum() / volume.cumsum()
    
    @staticmethod
    def volume_ma(volume: pd.Series, period: int = 20) -> pd.Series:
        """Volume Moving Average"""
        return volume.rolling(window=period).mean()
    
    @staticmethod
    def bollinger_bands(data: pd.Series, period: int = 20, std_dev: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Bollinger Bands
        Returns (upper_band, middle_band, lower_band)
        """
        middle_band = data.rolling(window=period).mean()
        std = data.rolling(window=period).std()
        upper_band = middle_band + (std * std_dev)
        lower_band = middle_band - (std * std_dev)
        return upper_band, middle_band, lower_band
    
    @staticmethod
    def macd(data: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        MACD (Moving Average Convergence Divergence)
        Returns (macd_line, signal_line, histogram)
        """
        ema_fast = data.ewm(span=fast, adjust=False).mean()
        ema_slow = data.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram
    
    @staticmethod
    def stochastic(high: pd.Series, low: pd.Series, close: pd.Series, k_period: int = 14, d_period: int = 3) -> Tuple[pd.Series, pd.Series]:
        """
        Stochastic Oscillator
        Returns (%K, %D)
        """
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low))
        d_percent = k_percent.rolling(window=d_period).mean()
        return k_percent, d_percent
    
    @staticmethod
    def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """
        ADX (Average Directional Index) - Measures trend strength
        Returns ADX value (0-100, >25 indicates strong trend)
        """
        # Calculate +DM and -DM
        high_diff = high.diff()
        low_diff = -low.diff()
        
        plus_dm = high_diff.where((high_diff > low_diff) & (high_diff > 0), 0)
        minus_dm = low_diff.where((low_diff > high_diff) & (low_diff > 0), 0)
        
        # Calculate ATR
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        # Calculate +DI and -DI
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
        
        # Calculate DX and ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()
        
        return adx
    
    @staticmethod
    def ichimoku_cloud(high: pd.Series, low: pd.Series, close: pd.Series) -> Tuple[pd.Series, pd.Series]:
        """
        Simplified Ichimoku Cloud
        Returns (tenkan_sen, kijun_sen) - conversion and base lines
        """
        # Tenkan-sen (Conversion Line): 9-period
        tenkan_high = high.rolling(window=9).max()
        tenkan_low = low.rolling(window=9).min()
        tenkan_sen = (tenkan_high + tenkan_low) / 2
        
        # Kijun-sen (Base Line): 26-period
        kijun_high = high.rolling(window=26).max()
        kijun_low = low.rolling(window=26).min()
        kijun_sen = (kijun_high + kijun_low) / 2
        
        return tenkan_sen, kijun_sen
    
    @staticmethod
    def cmf(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, period: int = 20) -> pd.Series:
        """
        CMF (Chaikin Money Flow) - Volume-weighted accumulation/distribution
        Positive values indicate buying pressure, negative indicate selling pressure
        """
        mf_multiplier = ((close - low) - (high - close)) / (high - low)
        mf_multiplier = mf_multiplier.fillna(0)  # Handle division by zero
        mf_volume = mf_multiplier * volume
        cmf = mf_volume.rolling(window=period).sum() / volume.rolling(window=period).sum()
        return cmf


# ============================================================================
# PRICE ACTION PATTERNS
# ============================================================================

class PriceActionAnalyzer:
    """Detect price action patterns"""
    
    @staticmethod
    def detect_break_of_structure(df: pd.DataFrame, lookback: int = 20) -> Optional[str]:
        """
        Detect Break of Structure (BOS)
        Returns 'BULLISH' or 'BEARISH' if BOS detected, None otherwise
        """
        if len(df) < lookback:
            return None
        
        recent = df.tail(lookback)
        
        # Bullish BOS: Price breaks above recent swing high
        swing_high = recent['high'].max()
        current_close = df['close'].iloc[-1]
        prev_high = df['high'].iloc[-2]
        
        if current_close > swing_high and prev_high < swing_high:
            return 'BULLISH'
        
        # Bearish BOS: Price breaks below recent swing low
        swing_low = recent['low'].min()
        prev_low = df['low'].iloc[-2]
        
        if current_close < swing_low and prev_low > swing_low:
            return 'BEARISH'
        
        return None
    
    @staticmethod
    def detect_liquidity_sweep(df: pd.DataFrame, threshold: float = 0.001) -> Optional[str]:
        """
        Detect liquidity sweep (stop hunt)
        Returns 'BULLISH' or 'BEARISH' if sweep detected
        """
        if len(df) < 5:
            return None
        
        # Look at last few candles
        recent = df.tail(5)
        
        # Bullish sweep: Wick below support then close above
        prev_low = recent['low'].iloc[-2]
        curr_low = recent['low'].iloc[-1]
        curr_close = recent['close'].iloc[-1]
        
        if curr_low < prev_low * (1 - threshold) and curr_close > prev_low:
            return 'BULLISH'
        
        # Bearish sweep: Wick above resistance then close below
        prev_high = recent['high'].iloc[-2]
        curr_high = recent['high'].iloc[-1]
        
        if curr_high > prev_high * (1 + threshold) and curr_close < prev_high:
            return 'BEARISH'
        
        return None
    
    @staticmethod
    def detect_pullback(df: pd.DataFrame, ema_fast: pd.Series, ema_slow: pd.Series) -> Optional[str]:
        """
        Detect pullback to moving average in trending market
        Returns 'BULLISH' or 'BEARISH' if valid pullback
        """
        if len(df) < 10:
            return None
        
        current_close = df['close'].iloc[-1]
        ema_fast_val = ema_fast.iloc[-1]
        ema_slow_val = ema_slow.iloc[-1]
        
        # Bullish pullback: Uptrend, price pulls back to EMA
        if ema_fast_val > ema_slow_val:
            if abs(current_close - ema_fast_val) / current_close < 0.005:  # Within 0.5%
                return 'BULLISH'
        
        # Bearish pullback: Downtrend, price pulls back to EMA
        if ema_fast_val < ema_slow_val:
            if abs(current_close - ema_fast_val) / current_close < 0.005:
                return 'BEARISH'
        
        return None


# ============================================================================
# TRADE SIGNAL GENERATOR
# ============================================================================

class SignalGenerator:
    """Generate trading signals based on indicators and patterns"""
    
    def __init__(self, config: BotConfig):
        self.config = config
        self.indicators = TechnicalIndicators()
        self.pattern_analyzer = PriceActionAnalyzer()
        self.market_direction = None  # Cache market direction
        self.market_direction_updated = 0  # Timestamp of last update
    
    def detect_market_direction(self, klines: List[List]) -> str:
        """
        Detect overall market direction (BULLISH, BEARISH, or NEUTRAL)
        Uses multiple timeframe analysis and trend indicators
        """
        try:
            # Convert klines to DataFrame
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])
            
            df['close'] = df['close'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            df['open'] = df['open'].astype(float)
            
            # Calculate trend indicators
            ema_fast = self.indicators.ema(df['close'], self.config.ema_fast)
            ema_slow = self.indicators.ema(df['close'], self.config.ema_slow)
            ema_long = self.indicators.ema(df['close'], 50)  # Longer term trend
            
            # Current values
            current_price = df['close'].iloc[-1]
            ema_fast_val = ema_fast.iloc[-1]
            ema_slow_val = ema_slow.iloc[-1]
            ema_long_val = ema_long.iloc[-1]
            
            # Price trend over last 20 candles
            price_20_ago = df['close'].iloc[-20]
            price_change_pct = ((current_price - price_20_ago) / price_20_ago) * 100
            
            # Direction scoring
            bullish_score = 0
            bearish_score = 0
            
            # Fast EMA above Slow EMA (short-term trend)
            if ema_fast_val > ema_slow_val:
                bullish_score += 2
            elif ema_fast_val < ema_slow_val:
                bearish_score += 2
            
            # Price above/below long EMA (long-term trend)
            if current_price > ema_long_val:
                bullish_score += 2
            elif current_price < ema_long_val:
                bearish_score += 2
            
            # Recent price momentum
            if price_change_pct > 1:  # More than 1% up
                bullish_score += 1
            elif price_change_pct < -1:  # More than 1% down
                bearish_score += 1
            
            # EMA alignment (all EMAs in order)
            if ema_fast_val > ema_slow_val > ema_long_val:
                bullish_score += 2
            elif ema_fast_val < ema_slow_val < ema_long_val:
                bearish_score += 2
            
            # Determine direction
            if bullish_score >= 4 and bullish_score > bearish_score:
                direction = 'BULLISH'
            elif bearish_score >= 4 and bearish_score > bullish_score:
                direction = 'BEARISH'
            else:
                direction = 'NEUTRAL'
            
            logger.info(f"Market direction detected: {direction} (Bullish: {bullish_score}, Bearish: {bearish_score}, Price change: {price_change_pct:.2f}%)")
            
            return direction
            
        except Exception as e:
            logger.error(f"Error detecting market direction: {e}")
            return 'NEUTRAL'
    
    def analyze_market(self, klines: List[List]) -> Tuple[Optional[str], Dict]:
        """
        Analyze market and generate trading signal
        Returns: (signal, analysis_data)
        signal: 'LONG', 'SHORT', or None
        """
        # Convert klines to DataFrame
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        
        df['close'] = df['close'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['open'] = df['open'].astype(float)
        df['volume'] = df['volume'].astype(float)
        
        # Calculate indicators
        ema_fast = self.indicators.ema(df['close'], self.config.ema_fast)
        ema_slow = self.indicators.ema(df['close'], self.config.ema_slow)
        rsi = self.indicators.rsi(df['close'], self.config.rsi_period)
        atr = self.indicators.atr(df['high'], df['low'], df['close'], self.config.atr_period)
        vwap = self.indicators.vwap(df['high'], df['low'], df['close'], df['volume'])
        volume_ma = self.indicators.volume_ma(df['volume'], self.config.volume_ma_period)
        bb_upper, bb_middle, bb_lower = self.indicators.bollinger_bands(df['close'], period=20, std_dev=2.0)
        
        # New advanced indicators
        macd_line, macd_signal, macd_histogram = self.indicators.macd(df['close'])
        stoch_k, stoch_d = self.indicators.stochastic(df['high'], df['low'], df['close'])
        adx = self.indicators.adx(df['high'], df['low'], df['close'])
        tenkan_sen, kijun_sen = self.indicators.ichimoku_cloud(df['high'], df['low'], df['close'])
        cmf = self.indicators.cmf(df['high'], df['low'], df['close'], df['volume'])
        
        # Current values
        current_price = df['close'].iloc[-1]
        current_rsi = rsi.iloc[-1]
        current_atr = atr.iloc[-1]
        current_volume = df['volume'].iloc[-1]
        current_volume_ma = volume_ma.iloc[-1]
        ema_fast_val = ema_fast.iloc[-1]
        ema_slow_val = ema_slow.iloc[-1]
        vwap_val = vwap.iloc[-1]
        bb_upper_val = bb_upper.iloc[-1]
        bb_middle_val = bb_middle.iloc[-1]
        bb_lower_val = bb_lower.iloc[-1]
        
        # New indicator current values
        macd_line_val = macd_line.iloc[-1]
        macd_signal_val = macd_signal.iloc[-1]
        macd_histogram_val = macd_histogram.iloc[-1]
        stoch_k_val = stoch_k.iloc[-1]
        stoch_d_val = stoch_d.iloc[-1]
        adx_val = adx.iloc[-1]
        tenkan_val = tenkan_sen.iloc[-1]
        kijun_val = kijun_sen.iloc[-1]
        cmf_val = cmf.iloc[-1]
        
        # Detect patterns
        bos = self.pattern_analyzer.detect_break_of_structure(df, self.config.bos_lookback)
        liquidity_sweep = self.pattern_analyzer.detect_liquidity_sweep(df, self.config.liquidity_sweep_threshold)
        pullback = self.pattern_analyzer.detect_pullback(df, ema_fast, ema_slow)
        
        # Analysis data
        analysis = {
            'price': current_price,
            'rsi': current_rsi,
            'atr': current_atr,
            'ema_fast': ema_fast_val,
            'ema_slow': ema_slow_val,
            'vwap': vwap_val,
            'volume': current_volume,
            'volume_ma': current_volume_ma,
            'bb_upper': bb_upper_val,
            'bb_middle': bb_middle_val,
            'bb_lower': bb_lower_val,
            'bos': bos,
            'liquidity_sweep': liquidity_sweep,
            'pullback': pullback,
            # New advanced indicators
            'macd_line': macd_line_val,
            'macd_signal': macd_signal_val,
            'macd_histogram': macd_histogram_val,
            'stoch_k': stoch_k_val,
            'stoch_d': stoch_d_val,
            'adx': adx_val,
            'tenkan': tenkan_val,
            'kijun': kijun_val,
            'cmf': cmf_val
        }
        
        # Generate signal and score (pass market direction if available)
        signal, score = self._generate_signal(analysis, market_direction=self.market_direction)
        analysis['signal_score'] = score
        analysis['market_direction'] = self.market_direction
        
        return signal, analysis
    
    def _generate_signal(self, analysis: Dict, market_direction: str = None) -> Tuple[Optional[str], int]:
        """Generate trading signal based on analysis and market direction. Returns (signal, score)"""
        price = analysis['price']
        rsi = analysis['rsi']
        ema_fast = analysis['ema_fast']
        ema_slow = analysis['ema_slow']
        vwap_val = analysis['vwap']
        volume = analysis['volume']
        volume_ma = analysis['volume_ma']
        bb_upper = analysis['bb_upper']
        bb_middle = analysis['bb_middle']
        bb_lower = analysis['bb_lower']
        bos = analysis['bos']
        liquidity_sweep = analysis['liquidity_sweep']
        pullback = analysis['pullback']
        
        # New advanced indicators
        macd_line = analysis['macd_line']
        macd_signal = analysis['macd_signal']
        macd_histogram = analysis['macd_histogram']
        stoch_k = analysis['stoch_k']
        stoch_d = analysis['stoch_d']
        adx = analysis['adx']
        tenkan = analysis['tenkan']
        kijun = analysis['kijun']
        cmf = analysis['cmf']
        
        # Calculate price position within Bollinger Bands
        bb_range = bb_upper - bb_lower
        if bb_range > 0:
            bb_position = (price - bb_lower) / bb_range  # 0 = at lower band, 1 = at upper band
        else:
            bb_position = 0.5  # Middle if no range
        
        # Check for extreme positions (at or near Bollinger Band extremes)
        at_lower_band = bb_position <= 0.1  # Price at or below 10% of BB range (oversold extreme)
        at_upper_band = bb_position >= 0.9  # Price at or above 90% of BB range (overbought extreme)
        
        # Score for LONG signal
        long_score = 0
        
        # CRITICAL: Block LONG signals at overbought extremes (upper Bollinger Band)
        if at_upper_band:
            logger.debug(f"Price at upper Bollinger Band ({bb_position:.2f}) - blocking LONG signal to avoid buying at extreme")
            return None, 0
        
        # EMA alignment (uptrend)
        if ema_fast > ema_slow:
            long_score += 2
        
        # Price above VWAP
        if price > vwap_val:
            long_score += 1
        
        # RSI conditions
        if rsi < self.config.rsi_oversold:
            long_score += 2
        elif rsi < 50:
            long_score += 1
        
        # Bonus: Price near lower Bollinger Band (potential bounce)
        if at_lower_band and rsi < 40:
            long_score += 2
            logger.debug(f"Price at lower Bollinger Band ({bb_position:.2f}) with RSI {rsi:.1f} - potential oversold bounce")
        
        # MACD bullish signals
        if macd_line > macd_signal and macd_histogram > 0:
            long_score += 2  # MACD crossover and positive momentum
        elif macd_line > macd_signal:
            long_score += 1  # MACD crossover
        
        # Stochastic oversold bounce
        if stoch_k < 20 and stoch_d < 20:
            long_score += 2  # Strong oversold
        elif stoch_k < 30:
            long_score += 1  # Mild oversold
        
        # ADX trend strength (only add if strong trend exists)
        if adx > 25:
            long_score += 1  # Strong trend confirmation
        
        # Ichimoku bullish signal (Tenkan above Kijun = bullish)
        if tenkan > kijun:
            long_score += 1
        
        # CMF buying pressure
        if cmf > 0.1:
            long_score += 2  # Strong buying pressure
        elif cmf > 0:
            long_score += 1  # Mild buying pressure
        
        # Volume confirmation
        if volume > volume_ma * 1.2:
            long_score += 1
        
        # Pattern confirmations
        if bos == 'BULLISH':
            long_score += 2
        if liquidity_sweep == 'BULLISH':
            long_score += 2
        if pullback == 'BULLISH':
            long_score += 1
        
        # Score for SHORT signal
        short_score = 0
        
        # NOTE: Removed BB lower band blocking for SHORT signals
        # User strategy: Allow shorts at lower BB with tight SL and fast TP for scalping
        
        # EMA alignment (downtrend)
        if ema_fast < ema_slow:
            short_score += 2
        
        # Price below VWAP
        if price < vwap_val:
            short_score += 1
        
        # RSI conditions
        if rsi > self.config.rsi_overbought:
            short_score += 2
        elif rsi > 50:
            short_score += 1
        
        # Bonus: Price near upper Bollinger Band (potential rejection)
        if at_upper_band and rsi > 60:
            short_score += 2
            logger.debug(f"Price at upper Bollinger Band ({bb_position:.2f}) with RSI {rsi:.1f} - potential overbought rejection")
        
        # MACD bearish signals
        if macd_line < macd_signal and macd_histogram < 0:
            short_score += 2  # MACD crossover and negative momentum
        elif macd_line < macd_signal:
            short_score += 1  # MACD crossover
        
        # Stochastic overbought rejection
        if stoch_k > 80 and stoch_d > 80:
            short_score += 2  # Strong overbought
        elif stoch_k > 70:
            short_score += 1  # Mild overbought
        
        # ADX trend strength (only add if strong trend exists)
        if adx > 25:
            short_score += 1  # Strong trend confirmation
        
        # Ichimoku bearish signal (Tenkan below Kijun = bearish)
        if tenkan < kijun:
            short_score += 1
        
        # CMF selling pressure
        if cmf < -0.1:
            short_score += 2  # Strong selling pressure
        elif cmf < 0:
            short_score += 1  # Mild selling pressure
        
        # Volume confirmation
        if volume > volume_ma * 1.2:
            short_score += 1
        
        # Pattern confirmations
        if bos == 'BEARISH':
            short_score += 2
        if liquidity_sweep == 'BEARISH':
            short_score += 2
        if pullback == 'BEARISH':
            short_score += 1
        
        # Apply market direction filter if enabled
        if self.config.use_market_direction_filter and market_direction:
            if market_direction == 'BULLISH':
                # In bullish market, only consider LONG signals
                short_score = 0
                logger.debug(f"Market is BULLISH - filtering out SHORT signals")
            elif market_direction == 'BEARISH':
                # In bearish market, only consider SHORT signals
                long_score = 0
                logger.debug(f"Market is BEARISH - filtering out LONG signals")
            # NEUTRAL market: allow both directions
        
        # Use configurable threshold for signal generation
        if long_score >= self.config.signal_threshold and long_score > short_score:
            return 'LONG', long_score
        elif short_score >= self.config.signal_threshold and short_score > long_score:
            return 'SHORT', short_score
        
        return None, max(long_score, short_score)


# ============================================================================
# POSITION MANAGER
# ============================================================================

class PositionManager:
    """Manage positions with DCA, TP, and SL"""
    
    def __init__(self, config: BotConfig, client: BinanceFuturesClient, notifier: TelegramNotifier):
        self.config = config
        self.client = client
        self.notifier = notifier
    
    def calculate_position_size(self, entry_price: float, stop_loss: float, balance: float) -> float:
        """Calculate position size based on risk management"""
        risk_amount = balance * self.config.risk_per_trade
        price_diff = abs(entry_price - stop_loss)
        quantity = risk_amount / price_diff
        
        # Round to configured precision
        quantity = round(quantity, self.config.quantity_precision)
        
        return quantity
    
    def calculate_dca_levels(self, entry_price: float, side: str, atr: float) -> List[float]:
        """Calculate DCA entry levels using Fibonacci ratios"""
        dca_prices = []
        
        for level in self.config.dca_levels:
            if side == 'LONG':
                # For LONG, DCA levels are below entry
                dca_price = entry_price - (atr * level * 2)
            else:
                # For SHORT, DCA levels are above entry
                dca_price = entry_price + (atr * level * 2)
            
            dca_prices.append(round(dca_price, 2))
        
        return dca_prices
    
    def calculate_tp_sl(self, entry_price: float, side: str, atr: float) -> Tuple[float, float]:
        """Calculate Take Profit and Stop Loss levels"""
        tp_distance = atr * self.config.tp_atr_multiplier
        sl_distance = atr * self.config.sl_atr_multiplier
        
        if side == 'LONG':
            take_profit = entry_price + tp_distance
            stop_loss = entry_price - sl_distance
        else:
            take_profit = entry_price - tp_distance
            stop_loss = entry_price + sl_distance
        
        return round(take_profit, 2), round(stop_loss, 2)
    
    def open_position(self, signal: str, entry_price: float, atr: float, analysis: Dict, symbol: str = None):
        """Open new position with DCA entries"""
        try:
            # Use provided symbol or fall back to config symbol
            if symbol is None:
                symbol = self.config.symbol
            
            # Get account balance
            balance = self.client.get_account_balance()
            logger.info(f"Account balance: ${balance:.2f}")
            
            # Calculate SL first
            side = 'BUY' if signal == 'LONG' else 'SELL'
            tp_price, sl_price = self.calculate_tp_sl(entry_price, signal, atr)
            
            # Calculate position size
            quantity = self.calculate_position_size(entry_price, sl_price, balance)
            
            if quantity <= 0:
                logger.warning("Calculated quantity is 0, skipping trade")
                return
            
            # DCA STRATEGY:
            # Entry 1: Market order (10% of total position) - Immediate fill at current price
            # Entries 2-4: Limit orders (30% each) - Fibonacci-based DCA levels below/above entry
            entry1_qty = round(quantity * 0.1, self.config.quantity_precision)
            
            # Place market order for immediate entry
            logger.info(f"Placing {side} market order for {symbol}: {entry1_qty} @ market")
            order = self.client.place_order(
                symbol=symbol,
                side=side,
                order_type='MARKET',
                quantity=entry1_qty
            )
            
            logger.info(f"Entry order placed: {order}")
            
            # Send Telegram notification
            reason = f"Signal: {signal}, RSI: {analysis['rsi']:.1f}, BOS: {analysis['bos']}, Sweep: {analysis['liquidity_sweep']}"
            self.notifier.send_trade_alert(
                'ENTRY 1/4', symbol, side, entry_price, entry1_qty, reason
            )
            
            # Calculate DCA levels
            dca_levels = self.calculate_dca_levels(entry_price, signal, atr)
            
            # Place DCA limit orders (30% each)
            dca_qty = round(quantity * 0.3, self.config.quantity_precision)
            
            for i, dca_price in enumerate(dca_levels, 2):
                try:
                    logger.info(f"Placing DCA {i} limit order for {symbol}: {dca_qty} @ ${dca_price}")
                    dca_order = self.client.place_order(
                        symbol=symbol,
                        side=side,
                        order_type='LIMIT',
                        quantity=dca_qty,
                        price=dca_price
                    )
                    logger.info(f"DCA {i} order placed: {dca_order}")
                except Exception as e:
                    logger.error(f"Failed to place DCA {i} order: {e}")
            
            # Place Take Profit order (reduce only)
            time.sleep(self.config.order_delay)
            total_qty = quantity
            
            try:
                tp_side = 'SELL' if signal == 'LONG' else 'BUY'
                logger.info(f"Placing TP order for {symbol}: {total_qty} @ ${tp_price}")
                tp_order = self.client.place_order(
                    symbol=symbol,
                    side=tp_side,
                    order_type='LIMIT',
                    quantity=total_qty,
                    price=tp_price,
                    reduce_only=True
                )
                logger.info(f"TP order placed: {tp_order}")
            except Exception as e:
                logger.error(f"Failed to place TP order: {e}")
            
            # Place Stop Loss order (reduce only)
            time.sleep(self.config.order_delay)
            
            try:
                logger.info(f"Placing SL order for {symbol}: {total_qty} @ ${sl_price}")
                sl_order = self.client.place_order(
                    symbol=symbol,
                    side=tp_side,
                    order_type='STOP_MARKET',
                    quantity=total_qty,
                    stop_price=sl_price,
                    reduce_only=True
                )
                logger.info(f"SL order placed: {sl_order}")
            except Exception as e:
                logger.error(f"Failed to place SL order: {e}")
            
            logger.info(f"Position opened successfully: {signal} {symbol} @ ${entry_price:.2f}")
            logger.info(f"TP: ${tp_price:.2f}, SL: ${sl_price:.2f}")
            logger.info(f"DCA levels: {dca_levels}")
            
        except Exception as e:
            logger.error(f"Failed to open position: {e}")
            self.notifier.send_message(f"❌ Failed to open position: {e}")


# ============================================================================
# MAIN BOT
# ============================================================================

class ScalpingBot:
    """Main AI Scalping Bot"""
    
    def __init__(self, config: BotConfig):
        self.config = config
        self.client = BinanceFuturesClient(config)
        self.notifier = TelegramNotifier(config)
        self.signal_generator = SignalGenerator(config)
        self.position_manager = PositionManager(config, self.client, self.notifier)
        
        logger.info("Scalping Bot initialized")
    
    def load_blacklist(self) -> List[str]:
        """Load blacklisted symbols from file"""
        blacklist = []
        try:
            if os.path.exists(self.config.blacklist_file):
                with open(self.config.blacklist_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        # Skip comments and empty lines
                        if line and not line.startswith('#'):
                            blacklist.append(line.upper())
                
                if blacklist:
                    logger.info(f"Loaded {len(blacklist)} symbols from blacklist: {', '.join(blacklist)}")
                else:
                    logger.info("Blacklist file exists but is empty")
            else:
                logger.info(f"Blacklist file '{self.config.blacklist_file}' not found, no symbols blacklisted")
        except Exception as e:
            logger.error(f"Error loading blacklist: {e}")
        
        return blacklist
    
    def check_existing_positions(self) -> bool:
        """Check if there are existing positions or orders"""
        try:
            # Check open position
            position = self.client.get_position(self.config.symbol)
            if position:
                logger.info(f"Existing position found: {position}")
                return True
            
            # Check open orders
            orders = self.client.get_open_orders(self.config.symbol)
            if orders:
                logger.info(f"Open orders found: {len(orders)} orders")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking positions: {e}")
            return False
    
    def setup_account(self):
        """Setup account settings"""
        try:
            # Get initial balance
            balance = self.client.get_account_balance()
            logger.info(f"Initial balance: ${balance:.2f}")
            
            mode_str = "Auto-trade ENABLED" if self.config.auto_trade else "Signals only"
            coin_selection = f"Auto-selecting top {self.config.num_coins_to_scan} volatile coins" if self.config.auto_select_volatile_coins else f"Scanning {len(self.config.symbols_to_scan)} pre-configured pairs"
            
            self.notifier.send_message(
                f"🤖 <b>Multi-Symbol Scanner Started</b>\n"
                f"Mode: {mode_str}\n"
                f"Coin selection: {coin_selection}\n"
                f"Leverage: {self.config.leverage_type} {self.config.leverage}x\n"
                f"Balance: ${balance:.2f}\n"
                f"Risk per trade: {self.config.risk_per_trade*100}%\n"
                f"Max signals: {self.config.max_signals_per_scan} per scan\n"
                f"Scan interval: {self.config.scan_interval}s"
            )
            
        except Exception as e:
            logger.error(f"Failed to setup account: {e}")
    
    def get_most_volatile_symbols(self, num_symbols: int = 20) -> List[str]:
        """Get most volatile symbols based on 24hr price change percentage"""
        try:
            logger.info("Fetching 24hr ticker data to find most volatile symbols...")
            tickers = self.client.get_24hr_ticker()
            
            # Filter USDT pairs and calculate volatility score
            usdt_pairs = []
            for ticker in tickers:
                symbol = ticker['symbol']
                if symbol.endswith('USDT') and not symbol.startswith('USDT'):
                    try:
                        # Volatility score = abs(price change %) + (volume in USDT / 1M)
                        price_change_pct = abs(float(ticker.get('priceChangePercent', 0)))
                        volume = float(ticker.get('quoteVolume', 0))
                        volume_score = volume / 1000000  # Normalize volume
                        
                        volatility_score = price_change_pct + (volume_score * 0.1)  # Weight volume 10%
                        
                        usdt_pairs.append({
                            'symbol': symbol,
                            'volatility_score': volatility_score,
                            'price_change_pct': price_change_pct,
                            'volume': volume
                        })
                    except (ValueError, KeyError) as e:
                        continue
            
            # Sort by volatility score (highest first)
            usdt_pairs.sort(key=lambda x: x['volatility_score'], reverse=True)
            
            # Get top N symbols
            top_symbols = [pair['symbol'] for pair in usdt_pairs[:num_symbols]]
            
            logger.info(f"Top {len(top_symbols)} volatile symbols:")
            for i, pair in enumerate(usdt_pairs[:num_symbols], 1):
                logger.info(f"  {i}. {pair['symbol']}: {pair['price_change_pct']:.2f}% change, "
                           f"${pair['volume']/1e6:.2f}M volume")
            
            return top_symbols
            
        except Exception as e:
            logger.error(f"Error getting volatile symbols: {e}")
            # Fallback to default symbols
            return [
                'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT',
                'ADAUSDT', 'DOGEUSDT', 'MATICUSDT', 'DOTUSDT', 'AVAXUSDT',
                'LINKUSDT', 'UNIUSDT', 'ATOMUSDT', 'LTCUSDT', 'NEARUSDT',
                'APTUSDT', 'ARBUSDT', 'OPUSDT', 'SUIUSDT', 'INJUSDT'
            ]
    
    def get_symbols_with_positions_or_orders(self) -> set:
        """Get set of symbols that have open positions or orders"""
        symbols_to_skip = set()
        
        try:
            # Get all positions
            positions = self.client.get_all_positions()
            for position in positions:
                symbols_to_skip.add(position['symbol'])
                logger.info(f"Skipping {position['symbol']} - has open position")
            
            # Get all open orders
            orders = self.client.get_all_open_orders()
            for order in orders:
                symbol = order['symbol']
                symbols_to_skip.add(symbol)
                if symbol not in [p['symbol'] for p in positions]:
                    logger.info(f"Skipping {symbol} - has open orders")
            
        except Exception as e:
            logger.error(f"Error checking positions/orders: {e}")
        
        return symbols_to_skip
    
    def scan_symbols_for_signals(self) -> List[Dict]:
        """Scan multiple symbols and find best trading opportunities"""
        signals = []
        
        # Detect overall market direction if enabled
        if self.config.use_market_direction_filter:
            try:
                logger.info(f"Detecting market direction using {self.config.market_direction_symbol}...")
                direction_klines = self.client.get_klines(
                    self.config.market_direction_symbol, 
                    self.config.timeframe, 
                    limit=500
                )
                market_direction = self.signal_generator.detect_market_direction(direction_klines)
                self.signal_generator.market_direction = market_direction
                
                # Send notification about market direction
                direction_emoji = "📈" if market_direction == "BULLISH" else "📉" if market_direction == "BEARISH" else "↔️"
                logger.info(f"{direction_emoji} Market Direction: {market_direction}")
                
            except Exception as e:
                logger.error(f"Failed to detect market direction: {e}")
                self.signal_generator.market_direction = 'NEUTRAL'
        
        # Get symbols to scan
        if self.config.auto_select_volatile_coins:
            symbols_to_scan = self.get_most_volatile_symbols(self.config.num_coins_to_scan)
        else:
            symbols_to_scan = self.config.symbols_to_scan
        
        # Load blacklist and filter out blacklisted symbols
        blacklist = self.load_blacklist()
        if blacklist:
            symbols_before = len(symbols_to_scan)
            symbols_to_scan = [s for s in symbols_to_scan if s not in blacklist]
            blacklisted_count = symbols_before - len(symbols_to_scan)
            if blacklisted_count > 0:
                logger.info(f"Filtered out {blacklisted_count} blacklisted symbols")
        
        # Get symbols with existing positions/orders to skip
        symbols_to_skip = self.get_symbols_with_positions_or_orders()
        
        # Filter out symbols with positions/orders
        symbols_to_scan = [s for s in symbols_to_scan if s not in symbols_to_skip]
        
        logger.info(f"Scanning {len(symbols_to_scan)} symbols for trading signals...")
        if symbols_to_skip:
            logger.info(f"Skipped {len(symbols_to_skip)} symbols with open positions/orders")
        
        for symbol in symbols_to_scan:
            try:
                # Get market data
                klines = self.client.get_klines(symbol, self.config.timeframe, limit=500)
                
                # Analyze market
                signal, analysis = self.signal_generator.analyze_market(klines)
                
                if signal:
                    # Calculate entry levels and TP/SL
                    current_price = analysis['price']
                    atr = analysis['atr']
                    
                    # Calculate DCA entry prices
                    entries = [current_price]  # First entry at market
                    for level in self.config.dca_levels[:3]:  # Only use first 3 DCA levels for signal
                        if signal == 'LONG':
                            entry_price = current_price - (atr * level * 2)
                        else:
                            entry_price = current_price + (atr * level * 2)
                        entries.append(entry_price)
                    
                    # Calculate TP and SL
                    if signal == 'LONG':
                        take_profit = current_price + (atr * self.config.tp_atr_multiplier)
                        stop_loss = current_price - (atr * self.config.sl_atr_multiplier)
                    else:
                        take_profit = current_price - (atr * self.config.tp_atr_multiplier)
                        stop_loss = current_price + (atr * self.config.sl_atr_multiplier)
                    
                    signal_data = {
                        'symbol': symbol,
                        'direction': signal,
                        'market_price': current_price,
                        'entries': entries,
                        'take_profit': take_profit,
                        'stop_loss': stop_loss,
                        'score': analysis['signal_score'],
                        'rsi': analysis['rsi'],
                        'atr': atr,
                        'bos': analysis['bos'],
                        'liquidity_sweep': analysis['liquidity_sweep'],
                        'analysis': analysis,
                        'market_direction': analysis.get('market_direction')
                    }
                    
                    signals.append(signal_data)
                    logger.info(f"✓ Signal found for {symbol}: {signal} (Score: {analysis['signal_score']})")
                    
                    # Send signal immediately if it meets threshold
                    if analysis['signal_score'] >= self.config.signal_threshold:
                        try:
                            self.notifier.send_signal_alert(
                                symbol=symbol,
                                direction=signal,
                                market_price=current_price,
                                leverage=self.config.leverage,
                                leverage_type=self.config.leverage_type,
                                entries=entries,
                                take_profit=take_profit,
                                stop_loss=stop_loss,
                                score=analysis['signal_score'],
                                market_direction=analysis.get('market_direction')
                            )
                            logger.info(f"📤 Signal sent immediately for {symbol}")
                            
                            # Execute trade if auto_trade is enabled
                            if self.config.auto_trade:
                                logger.info(f"Auto-trade enabled, executing trade for {symbol}")
                                self.execute_signal(signal_data)
                        except Exception as send_error:
                            logger.error(f"Error sending immediate signal for {symbol}: {send_error}")
                
            except Exception as e:
                logger.error(f"Error scanning {symbol}: {e}")
                continue
        
        # Sort by score (highest first) for summary
        signals.sort(key=lambda x: x['score'], reverse=True)
        
        logger.info(f"Scan complete. Found {len(signals)} total signals")
        
        # Return empty list since signals were already sent
        return []
    
    def send_signals_to_telegram(self, signals: List[Dict]):
        """
        Legacy batch method - kept for compatibility but no longer used.
        Signals are now sent immediately when found during scanning for faster delivery.
        """
        if not signals:
            logger.info("No signals to send")
            return
        
        for signal_data in signals:
            try:
                # Send signal to Telegram
                self.notifier.send_signal_alert(
                    symbol=signal_data['symbol'],
                    direction=signal_data['direction'],
                    market_price=signal_data['market_price'],
                    leverage=self.config.leverage,
                    leverage_type=self.config.leverage_type,
                    entries=signal_data['entries'],
                    take_profit=signal_data['take_profit'],
                    stop_loss=signal_data['stop_loss'],
                    score=signal_data['score'],
                    market_direction=signal_data.get('market_direction')
                )
                logger.info(f"Signal sent for {signal_data['symbol']}")
                
                # Execute trade if auto_trade is enabled
                if self.config.auto_trade:
                    logger.info(f"Auto-trade enabled, executing trade for {signal_data['symbol']}")
                    self.execute_signal(signal_data)
                
            except Exception as e:
                logger.error(f"Error sending signal for {signal_data['symbol']}: {e}")
            except Exception as e:
                logger.error(f"Error sending signal for {signal_data['symbol']}: {e}")
    
    def execute_signal(self, signal_data: Dict):
        """Execute a trading signal automatically"""
        try:
            symbol = signal_data['symbol']
            direction = signal_data['direction']
            
            # Set leverage for the symbol
            try:
                self.client.set_leverage(symbol, self.config.leverage)
                logger.info(f"Set leverage {self.config.leverage}x for {symbol}")
            except Exception as e:
                logger.warning(f"Could not set leverage for {symbol}: {e}")
            
            # Execute the trade using position manager
            self.position_manager.open_position(
                signal=direction,
                entry_price=signal_data['market_price'],
                atr=signal_data['atr'],
                analysis=signal_data['analysis'],
                symbol=symbol  # Pass symbol explicitly
            )
            
            logger.info(f"✅ Trade executed successfully for {symbol}")
            self.notifier.send_message(f"✅ Trade executed: {direction} {symbol}")
            
        except Exception as e:
            logger.error(f"Failed to execute trade for {signal_data['symbol']}: {e}")
            self.notifier.send_message(f"❌ Trade execution failed for {signal_data['symbol']}: {e}")
    
    def run_cycle(self):
        """Run one trading cycle - scan multiple symbols and send signals immediately"""
        try:
            # Scan all symbols for trading signals (signals sent immediately when found)
            logger.info("Starting multi-symbol scan...")
            self.scan_symbols_for_signals()
            logger.info("Scan cycle complete")
            
        except Exception as e:
            logger.error(f"Error in trading cycle: {e}", exc_info=True)
            self.notifier.send_message(f"❌ Error in trading cycle: {e}")
    
    def run_cycle_single_symbol(self):
        """Run one trading cycle for single symbol (legacy mode)"""
        try:
            # Check for existing positions to prevent duplicates
            if self.check_existing_positions():
                logger.info("Position or orders already exist, skipping new entries")
                
                # Monitor existing position
                position = self.client.get_position(self.config.symbol)
                if position:
                    pnl = position['unrealized_pnl']
                    entry_price = position['entry_price']
                    pnl_pct = (pnl / (abs(position['position_amt']) * entry_price)) * 100
                    
                    logger.info(f"Position PnL: ${pnl:.2f} ({pnl_pct:.2f}%)")
                    
                    # Send periodic updates
                    if not hasattr(self, 'update_counter'):
                        self.update_counter = 0
                    
                    self.update_counter += 1
                    if self.update_counter >= self.config.position_update_frequency:
                        self.notifier.send_position_update(self.config.symbol, pnl, pnl_pct)
                        self.update_counter = 0
                
                return
            
            # Get market data
            logger.info(f"Fetching market data for {self.config.symbol}")
            klines = self.client.get_klines(
                self.config.symbol,
                self.config.timeframe,
                limit=500
            )
            
            # Analyze market and generate signal
            signal, analysis = self.signal_generator.analyze_market(klines)
            
            logger.info(f"Market analysis - Price: ${analysis['price']:.2f}, "
                       f"RSI: {analysis['rsi']:.1f}, "
                       f"Score: {analysis['signal_score']}, "
                       f"BOS: {analysis['bos']}, "
                       f"Sweep: {analysis['liquidity_sweep']}, "
                       f"Pullback: {analysis['pullback']}")
            
            # Execute trade if signal generated
            if signal:
                logger.info(f"🎯 Trading signal generated: {signal}")
                self.position_manager.open_position(
                    signal,
                    analysis['price'],
                    analysis['atr'],
                    analysis
                )
            else:
                logger.info("No trading signal generated")
            
        except Exception as e:
            logger.error(f"Error in trading cycle: {e}", exc_info=True)
            self.notifier.send_message(f"❌ Error in trading cycle: {e}")
    
    def run(self):
        """Main bot loop"""
        logger.info("Starting Scalping Bot...")
        
        # Setup account
        self.setup_account()
        
        # Main loop
        cycle_count = 0
        while True:
            try:
                cycle_count += 1
                logger.info(f"\n{'='*60}")
                logger.info(f"Trading Cycle #{cycle_count}")
                logger.info(f"{'='*60}")
                
                self.run_cycle()
                
                # Wait before next cycle
                logger.info(f"Waiting {self.config.scan_interval} seconds until next cycle...")
                time.sleep(self.config.scan_interval)
                
            except KeyboardInterrupt:
                logger.info("Bot stopped by user")
                self.notifier.send_message("🛑 Bot stopped by user")
                break
            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
                time.sleep(self.config.error_retry_delay)


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point"""
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║         AI SCALPING BOT - BINANCE FUTURES                 ║
    ║              Professional Trading System                  ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    
    # Load configuration
    config = BotConfig()
    
    # Validate configuration
    if not config.api_key or not config.api_secret:
        logger.error("Binance API credentials not configured!")
        print("\n❌ Error: Binance API credentials not found!")
        print("Please set environment variables:")
        print("  - BINANCE_API_KEY")
        print("  - BINANCE_API_SECRET")
        print("  - TELEGRAM_BOT_TOKEN (optional)")
        print("  - TELEGRAM_CHAT_ID (optional)")
        return
    
    # Show configuration
    print(f"\n📊 Configuration:")
    print(f"  Auto-select volatile coins: {config.auto_select_volatile_coins}")
    if config.auto_select_volatile_coins:
        print(f"  Number of coins to scan: {config.num_coins_to_scan}")
    else:
        print(f"  Symbols to scan: {len(config.symbols_to_scan)} pairs")
    print(f"  Timeframe: {config.timeframe}")
    print(f"  Leverage: {config.leverage_type} {config.leverage}x")
    print(f"  Auto-trade: {'ENABLED' if config.auto_trade else 'DISABLED (signals only)'}")
    print(f"  Risk per trade: {config.risk_per_trade*100}%")
    print(f"  Max signals per scan: {config.max_signals_per_scan}")
    print(f"  Signal threshold: {config.signal_threshold} points")
    print(f"  DCA Levels: {config.dca_levels}")
    print(f"  TP/SL Multipliers: {config.tp_atr_multiplier}x / {config.sl_atr_multiplier}x ATR")
    print(f"  Scan Interval: {config.scan_interval}s")
    print(f"  Telegram: {'Enabled' if config.telegram_token else 'Disabled'}")
    
    # Show trading mode
    if config.auto_select_volatile_coins:
        print(f"\n📈 Trading Mode:")
        print(f"  Bot will automatically select the {config.num_coins_to_scan} most volatile coins")
        print(f"  Selection refreshes every scan cycle")
        print(f"  Coins with open positions/orders are automatically skipped")
    
    # Confirm start
    print("\n⚠️  WARNING: This bot will scan and send signals!")
    print("Note:")
    print("  1. Bot scans for best opportunities every 60 seconds")
    print("  2. Automatically selects most volatile coins if enabled")
    print("  3. Skips coins with existing positions/orders")
    print("  4. Signals sent to Telegram with entry/TP/SL levels")
    if config.auto_trade:
        print("  5. ⚠️  AUTO-TRADE ENABLED - Will execute trades automatically!")
    else:
        print("  5. AUTO-TRADE DISABLED - Signals only (manual execution)")
    
    response = input("\nType 'START' to begin trading: ")
    if response.upper() != 'START':
        print("Bot startup cancelled")
        return
    
    # Create and run bot
    bot = ScalpingBot(config)
    bot.run()


if __name__ == '__main__':
    main()
