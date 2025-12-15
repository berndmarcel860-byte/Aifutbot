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
    timeframe: str = '5m'  # 5-minute candles
    leverage: int = 10
    
    # Risk management
    risk_per_trade: float = 0.02  # 2% of account per trade
    max_positions: int = 3
    
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
    tp_atr_multiplier: float = 2.5
    sl_atr_multiplier: float = 1.5
    
    # Pattern detection
    bos_lookback: int = 20
    liquidity_sweep_threshold: float = 0.001  # 0.1%
    
    # Operational
    scan_interval: int = 60  # seconds
    
    def __post_init__(self):
        if self.dca_levels is None:
            self.dca_levels = [0.236, 0.382, 0.5, 0.618]


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
            logger.error(f"API request error: {e}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response: {e.response.text}")
            raise
    
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
        
        # Current values
        current_price = df['close'].iloc[-1]
        current_rsi = rsi.iloc[-1]
        current_atr = atr.iloc[-1]
        current_volume = df['volume'].iloc[-1]
        current_volume_ma = volume_ma.iloc[-1]
        ema_fast_val = ema_fast.iloc[-1]
        ema_slow_val = ema_slow.iloc[-1]
        vwap_val = vwap.iloc[-1]
        
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
            'bos': bos,
            'liquidity_sweep': liquidity_sweep,
            'pullback': pullback
        }
        
        # Generate signal
        signal = self._generate_signal(analysis)
        
        return signal, analysis
    
    def _generate_signal(self, analysis: Dict) -> Optional[str]:
        """Generate trading signal based on analysis"""
        price = analysis['price']
        rsi = analysis['rsi']
        ema_fast = analysis['ema_fast']
        ema_slow = analysis['ema_slow']
        vwap_val = analysis['vwap']
        volume = analysis['volume']
        volume_ma = analysis['volume_ma']
        bos = analysis['bos']
        liquidity_sweep = analysis['liquidity_sweep']
        pullback = analysis['pullback']
        
        # Score for LONG signal
        long_score = 0
        
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
        
        # Threshold for signal generation (need at least 6 points)
        SIGNAL_THRESHOLD = 6
        
        if long_score >= SIGNAL_THRESHOLD and long_score > short_score:
            return 'LONG'
        elif short_score >= SIGNAL_THRESHOLD and short_score > long_score:
            return 'SHORT'
        
        return None


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
        
        # Round to appropriate precision (0.001 for most futures)
        quantity = round(quantity, 3)
        
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
    
    def open_position(self, signal: str, entry_price: float, atr: float, analysis: Dict):
        """Open new position with DCA entries"""
        try:
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
            
            # Entry 1: Main entry (40% of total)
            entry1_qty = round(quantity * 0.4, 3)
            
            # Place market order for immediate entry
            logger.info(f"Placing {side} market order: {entry1_qty} @ market")
            order = self.client.place_order(
                symbol=self.config.symbol,
                side=side,
                order_type='MARKET',
                quantity=entry1_qty
            )
            
            logger.info(f"Entry order placed: {order}")
            
            # Send Telegram notification
            reason = f"Signal: {signal}, RSI: {analysis['rsi']:.1f}, BOS: {analysis['bos']}, Sweep: {analysis['liquidity_sweep']}"
            self.notifier.send_trade_alert(
                'ENTRY 1/4', self.config.symbol, side, entry_price, entry1_qty, reason
            )
            
            # Calculate DCA levels
            dca_levels = self.calculate_dca_levels(entry_price, signal, atr)
            
            # Place DCA limit orders (20% each)
            dca_qty = round(quantity * 0.2, 3)
            
            for i, dca_price in enumerate(dca_levels, 2):
                try:
                    logger.info(f"Placing DCA {i} limit order: {dca_qty} @ ${dca_price}")
                    dca_order = self.client.place_order(
                        symbol=self.config.symbol,
                        side=side,
                        order_type='LIMIT',
                        quantity=dca_qty,
                        price=dca_price
                    )
                    logger.info(f"DCA {i} order placed: {dca_order}")
                except Exception as e:
                    logger.error(f"Failed to place DCA {i} order: {e}")
            
            # Place Take Profit order (reduce only)
            time.sleep(1)  # Small delay
            total_qty = quantity
            
            try:
                tp_side = 'SELL' if signal == 'LONG' else 'BUY'
                logger.info(f"Placing TP order: {total_qty} @ ${tp_price}")
                tp_order = self.client.place_order(
                    symbol=self.config.symbol,
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
            time.sleep(1)
            
            try:
                logger.info(f"Placing SL order: {total_qty} @ ${sl_price}")
                sl_order = self.client.place_order(
                    symbol=self.config.symbol,
                    side=tp_side,
                    order_type='STOP_MARKET',
                    quantity=total_qty,
                    stop_price=sl_price,
                    reduce_only=True
                )
                logger.info(f"SL order placed: {sl_order}")
            except Exception as e:
                logger.error(f"Failed to place SL order: {e}")
            
            logger.info(f"Position opened successfully: {signal} @ ${entry_price:.2f}")
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
            # Set leverage
            logger.info(f"Setting leverage to {self.config.leverage}x")
            self.client.set_leverage(self.config.symbol, self.config.leverage)
            
            # Get initial balance
            balance = self.client.get_account_balance()
            logger.info(f"Initial balance: ${balance:.2f}")
            
            self.notifier.send_message(
                f"🤖 <b>Bot Started</b>\n"
                f"Symbol: {self.config.symbol}\n"
                f"Leverage: {self.config.leverage}x\n"
                f"Balance: ${balance:.2f}\n"
                f"Risk per trade: {self.config.risk_per_trade*100}%"
            )
            
        except Exception as e:
            logger.error(f"Failed to setup account: {e}")
    
    def run_cycle(self):
        """Run one trading cycle"""
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
                    
                    # Send periodic updates (every 10 cycles = ~10 minutes)
                    if not hasattr(self, 'update_counter'):
                        self.update_counter = 0
                    
                    self.update_counter += 1
                    if self.update_counter >= 10:
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
                time.sleep(60)  # Wait a minute before retrying


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
    print(f"  Symbol: {config.symbol}")
    print(f"  Timeframe: {config.timeframe}")
    print(f"  Leverage: {config.leverage}x")
    print(f"  Risk per trade: {config.risk_per_trade*100}%")
    print(f"  DCA Levels: {config.dca_levels}")
    print(f"  TP/SL Multipliers: {config.tp_atr_multiplier}x / {config.sl_atr_multiplier}x ATR")
    print(f"  Scan Interval: {config.scan_interval}s")
    print(f"  Telegram: {'Enabled' if config.telegram_token else 'Disabled'}")
    
    # Confirm start
    print("\n⚠️  WARNING: This bot will trade with real funds!")
    print("Make sure you have:")
    print("  1. Tested on Binance Testnet first")
    print("  2. Set appropriate risk limits")
    print("  3. Monitored initial trades closely")
    
    response = input("\nType 'START' to begin trading: ")
    if response.upper() != 'START':
        print("Bot startup cancelled")
        return
    
    # Create and run bot
    bot = ScalpingBot(config)
    bot.run()


if __name__ == '__main__':
    main()
