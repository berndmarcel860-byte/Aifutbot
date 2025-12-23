#!/usr/bin/env python3
"""
Simple Scalping Bot - Best Strategies Only
Implements the top 3 scalping strategies from TradingStrats file:
1. StochRSIMACD - Quick reversals with triple confirmation
2. Candle Wick - Exhaustion pattern detection
3. Triple EMA Stochastic - Trending scalps

Optimized for fast scalping with 1.5:1 risk/reward ratio.
"""

import os
import logging
import time
import hmac
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import pandas as pd
import numpy as np
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class BotConfig:
    """Simple bot configuration"""
    # API credentials
    api_key: str = os.getenv('BINANCE_API_KEY', '')
    api_secret: str = os.getenv('BINANCE_API_SECRET', '')
    base_url: str = 'https://fapi.binance.com'
    
    # Telegram
    telegram_token: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
    telegram_chat_id: str = os.getenv('TELEGRAM_CHAT_ID', '')
    
    # Trading parameters
    symbol: str = 'BTCUSDT'  # Main symbol to trade (used when auto_select disabled)
    timeframe: str = '5m'    # 5-minute candles for scalping
    leverage: int = 10
    risk_per_trade: float = 0.02  # 2% risk per trade
    
    # Multi-symbol scanning
    auto_select_coins: bool = True  # Automatically select most volatile coins
    num_coins_to_scan: int = 10     # Number of coins to scan
    
    # Strategy parameters
    scan_interval: int = 30   # Scan every 30 seconds
    signal_threshold: int = 2  # Minimum strategies that must agree (2 out of 3)
    max_signals_per_scan: int = 3  # Maximum signals to send per cycle
    min_volume_multiplier: float = 1.5  # Minimum volume requirement
    min_adx_threshold: float = 20  # Minimum ADX for trend strength
    
    # Risk management (optimized for fast scalping)
    tp_atr_multiplier: float = 1.5  # Quick take profit
    sl_atr_multiplier: float = 1.0  # Tight stop loss
    
    # Auto-trading
    auto_trade: bool = False  # Safety first


class BinanceClient:
    """Simplified Binance API client"""
    
    def __init__(self, api_key: str, api_secret: str, base_url: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url
        
    def _sign(self, params: Dict) -> str:
        """Create signature for authenticated requests"""
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def get_klines(self, symbol: str, interval: str, limit: int = 100) -> pd.DataFrame:
        """Get candlestick data"""
        url = f"{self.base_url}/fapi/v1/klines"
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])
            
            # Convert to numeric
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col])
                
            return df
            
        except Exception as e:
            logger.error(f"Error fetching klines: {e}")
            return pd.DataFrame()
    
    def get_most_volatile_symbols(self, num_symbols: int = 10) -> List[str]:
        """Get most volatile USDT pairs for trading"""
        url = f"{self.base_url}/fapi/v1/ticker/24hr"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            tickers = response.json()
            
            # Filter for USDT pairs
            usdt_pairs = [
                t for t in tickers 
                if t['symbol'].endswith('USDT') 
                and not t['symbol'].endswith('DOWNUSDT')
                and not t['symbol'].endswith('UPUSDT')
            ]
            
            # Calculate volatility score
            for ticker in usdt_pairs:
                try:
                    price_change_pct = abs(float(ticker.get('priceChangePercent', 0)))
                    volume = float(ticker.get('quoteVolume', 0))
                    # Score = price change % × log(volume) to favor both volatile AND liquid pairs
                    ticker['volatility_score'] = price_change_pct * np.log10(max(volume, 1))
                except:
                    ticker['volatility_score'] = 0
            
            # Sort by volatility score and get top N
            sorted_pairs = sorted(usdt_pairs, key=lambda x: x['volatility_score'], reverse=True)
            top_symbols = [pair['symbol'] for pair in sorted_pairs[:num_symbols]]
            
            logger.info(f"Selected {len(top_symbols)} most volatile coins: {', '.join(top_symbols[:5])}...")
            return top_symbols
            
        except Exception as e:
            logger.error(f"Error fetching volatile symbols: {e}")
            # Fallback to default list
            return ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT']
    
    def get_open_positions(self) -> List[str]:
        """Get symbols with open positions"""
        url = f"{self.base_url}/fapi/v2/positionRisk"
        timestamp = int(time.time() * 1000)
        
        params = {'timestamp': timestamp}
        params['signature'] = self._sign(params)
        
        headers = {'X-MBX-APIKEY': self.api_key}
        
        try:
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            positions = response.json()
            
            # Filter positions with non-zero amount
            open_symbols = [
                pos['symbol'] for pos in positions
                if float(pos.get('positionAmt', 0)) != 0
            ]
            
            return open_symbols
            
        except Exception as e:
            logger.warning(f"Error fetching open positions: {e}")
            return []
    
    def get_open_orders(self) -> List[str]:
        """Get symbols with open orders"""
        url = f"{self.base_url}/fapi/v1/openOrders"
        timestamp = int(time.time() * 1000)
        
        params = {'timestamp': timestamp}
        params['signature'] = self._sign(params)
        
        headers = {'X-MBX-APIKEY': self.api_key}
        
        try:
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            orders = response.json()
            
            # Get unique symbols with orders
            open_symbols = list(set([order['symbol'] for order in orders]))
            
            return open_symbols
            
        except Exception as e:
            logger.warning(f"Error fetching open orders: {e}")
            return []
    
    def get_symbols_with_positions_or_orders(self) -> List[str]:
        """Get all symbols that have either open positions or open orders"""
        positions = self.get_open_positions()
        orders = self.get_open_orders()
        
        # Combine and deduplicate
        all_symbols = list(set(positions + orders))
        
        if all_symbols:
            logger.info(f"Found {len(all_symbols)} symbols with existing positions/orders: {', '.join(all_symbols)}")
        
        return all_symbols


class TechnicalIndicators:
    """Technical indicators for strategies"""
    
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
    def stochastic(high: pd.Series, low: pd.Series, close: pd.Series, 
                   k_period: int = 14, d_period: int = 3) -> Tuple[pd.Series, pd.Series]:
        """Stochastic Oscillator"""
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        k = 100 * (close - lowest_low) / (highest_high - lowest_low)
        d = k.rolling(window=d_period).mean()
        return k, d
    
    @staticmethod
    def macd(data: pd.Series, fast: int = 12, slow: int = 26, 
             signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """MACD Indicator"""
        ema_fast = data.ewm(span=fast, adjust=False).mean()
        ema_slow = data.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram
    
    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """Average True Range"""
        high_low = high - low
        high_close = np.abs(high - close.shift())
        low_close = np.abs(low - close.shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()


class ScalpingStrategies:
    """Best scalping strategies implementation"""
    
    def __init__(self):
        self.indicators = TechnicalIndicators()
    
    def stoch_rsi_macd(self, df: pd.DataFrame) -> Optional[str]:
        """
        Strategy 1: StochRSIMACD
        Combines Stochastic + RSI + MACD for high-probability reversals
        
        Returns: 'LONG', 'SHORT', or None
        """
        if len(df) < 50:
            return None
            
        # Calculate indicators
        close = df['close']
        high = df['high']
        low = df['low']
        
        rsi = self.indicators.rsi(close, 14)
        stoch_k, stoch_d = self.indicators.stochastic(high, low, close, 14, 3)
        macd_line, macd_signal, _ = self.indicators.macd(close)
        
        # Get current values
        curr_rsi = rsi.iloc[-1]
        curr_k = stoch_k.iloc[-1]
        curr_d = stoch_d.iloc[-1]
        curr_macd = macd_line.iloc[-1]
        curr_macd_sig = macd_signal.iloc[-1]
        
        # Bullish setup
        if curr_k < 20 and curr_d < 20 and curr_rsi > 50 and curr_macd > curr_macd_sig:
            logger.info(f"StochRSIMACD: LONG (K={curr_k:.1f}, D={curr_d:.1f}, RSI={curr_rsi:.1f})")
            return 'LONG'
        
        # Bearish setup
        if curr_k > 80 and curr_d > 80 and curr_rsi < 50 and curr_macd < curr_macd_sig:
            logger.info(f"StochRSIMACD: SHORT (K={curr_k:.1f}, D={curr_d:.1f}, RSI={curr_rsi:.1f})")
            return 'SHORT'
        
        return None
    
    def candle_wick_reversal(self, df: pd.DataFrame) -> Optional[str]:
        """
        Strategy 2: Candle Wick Reversal
        Detects exhaustion after 3 consecutive candles with large rejection wick
        
        Returns: 'LONG', 'SHORT', or None
        """
        if len(df) < 5:
            return None
        
        # Get last 4 candles
        last_4 = df.tail(4)
        
        # Check for 3 consecutive down candles
        if all(last_4['close'].iloc[i] < last_4['open'].iloc[i] for i in range(3)):
            # Check 4th candle for large lower wick
            candle = last_4.iloc[3]
            body = abs(candle['close'] - candle['open'])
            lower_wick = min(candle['open'], candle['close']) - candle['low']
            
            if lower_wick > body * 10:  # Wick is 10x larger than body
                logger.info(f"Candle Wick: LONG (Lower wick reversal detected)")
                return 'LONG'
        
        # Check for 3 consecutive up candles
        if all(last_4['close'].iloc[i] > last_4['open'].iloc[i] for i in range(3)):
            # Check 4th candle for large upper wick
            candle = last_4.iloc[3]
            body = abs(candle['close'] - candle['open'])
            upper_wick = candle['high'] - max(candle['open'], candle['close'])
            
            if upper_wick > body * 10:  # Wick is 10x larger than body
                logger.info(f"Candle Wick: SHORT (Upper wick reversal detected)")
                return 'SHORT'
        
        return None
    
    def triple_ema_stochastic(self, df: pd.DataFrame) -> Optional[str]:
        """
        Strategy 3: Triple EMA Stochastic
        Catches trending scalps with EMA alignment and Stochastic crossover
        
        Returns: 'LONG', 'SHORT', or None
        """
        if len(df) < 50:
            return None
        
        close = df['close']
        high = df['high']
        low = df['low']
        
        # Calculate EMAs
        ema8 = self.indicators.ema(close, 8)
        ema14 = self.indicators.ema(close, 14)
        ema50 = self.indicators.ema(close, 50)
        
        # Calculate Stochastic
        stoch_k, stoch_d = self.indicators.stochastic(high, low, close, 14, 3)
        
        # Current values
        curr_ema8 = ema8.iloc[-1]
        curr_ema14 = ema14.iloc[-1]
        curr_ema50 = ema50.iloc[-1]
        curr_k = stoch_k.iloc[-1]
        curr_d = stoch_d.iloc[-1]
        prev_k = stoch_k.iloc[-2]
        prev_d = stoch_d.iloc[-2]
        
        # Bullish setup: EMA alignment + Stochastic crossover
        if curr_ema8 > curr_ema14 > curr_ema50:
            if curr_k > curr_d and prev_k <= prev_d:  # K crosses above D
                logger.info(f"Triple EMA Stoch: LONG (EMA aligned, K/D crossover)")
                return 'LONG'
        
        # Bearish setup: EMA alignment + Stochastic crossover
        if curr_ema8 < curr_ema14 < curr_ema50:
            if curr_k < curr_d and prev_k >= prev_d:  # K crosses below D
                logger.info(f"Triple EMA Stoch: SHORT (EMA aligned, K/D crossover)")
                return 'SHORT'
        
        return None


class TelegramNotifier:
    """Simple Telegram notifications"""
    
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{token}"
    
    def send_message(self, message: str) -> bool:
        """Send message to Telegram"""
        if not self.token or not self.chat_id:
            logger.warning("Telegram not configured")
            return False
        
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Telegram error: {e}")
            return False
    
    def send_signal(self, symbol: str, direction: str, price: float, 
                    entries: List[float], tp: float, sl: float, strategies: List[str], 
                    strategy_count: int) -> bool:
        """Send formatted trading signal"""
        # Determine market direction emoji
        market_emoji = "📈" if direction == "LONG" else "📉"
        
        message = f"""⚡⚡ {symbol} ⚡⚡ {market_emoji}
Exchange: Binance Futures
Direction: {direction}
Market Price: ${price:.4f}

Leverage: Cross 20x

Entries:
1. ${entries[0]:.4f}
2. ${entries[1]:.4f}
3. ${entries[2]:.4f}
4. ${entries[3]:.4f}

Take Profits:
1. ${tp:.4f}

Stop Loss:
1. ${sl:.4f}
"""
        return self.send_message(message)


class SimpleScalpingBot:
    """Main bot class with best strategies only"""
    
    def __init__(self, config: BotConfig):
        self.config = config
        self.client = BinanceClient(config.api_key, config.api_secret, config.base_url)
        self.strategies = ScalpingStrategies()
        self.notifier = TelegramNotifier(config.telegram_token, config.telegram_chat_id)
        self.indicators = TechnicalIndicators()
        
    def analyze_market(self, symbol: str) -> Optional[Dict]:
        """Analyze market with all 3 strategies"""
        logger.info(f"Analyzing {symbol}...")
        
        # Get market data
        df = self.client.get_klines(symbol, self.config.timeframe, limit=100)
        if df.empty:
            logger.error("No market data received")
            return None
        
        # Run all 3 strategies
        signals = {}
        signals['stoch_rsi_macd'] = self.strategies.stoch_rsi_macd(df)
        signals['candle_wick'] = self.strategies.candle_wick_reversal(df)
        signals['triple_ema'] = self.strategies.triple_ema_stochastic(df)
        
        # Count confirmations
        long_count = sum(1 for s in signals.values() if s == 'LONG')
        short_count = sum(1 for s in signals.values() if s == 'SHORT')
        
        # Determine consensus
        if long_count >= self.config.signal_threshold:
            direction = 'LONG'
            count = long_count
        elif short_count >= self.config.signal_threshold:
            direction = 'SHORT'
            count = short_count
        else:
            logger.info(f"No consensus (LONG: {long_count}, SHORT: {short_count})")
            return None
        
        # Get current price and calculate TP/SL
        current_price = float(df['close'].iloc[-1])
        atr = self.indicators.atr(df['high'], df['low'], df['close']).iloc[-1]
        
        # Calculate 4 DCA entries using Fibonacci levels
        fib_levels = [0.236, 0.382, 0.5, 0.618]
        entries = []
        
        if direction == 'LONG':
            # Entry 1 at market price
            entries.append(current_price)
            # Entries 2-4 below market price
            for level in fib_levels[:3]:
                entry_price = current_price - (atr * level * 3.0)
                entries.append(entry_price)
            
            tp = current_price + (atr * self.config.tp_atr_multiplier)
            # SL must be below the last (4th) entry to avoid same price
            sl = entries[3] - (atr * 0.5)  # Additional buffer below last entry
        else:
            # Entry 1 at market price
            entries.append(current_price)
            # Entries 2-4 above market price
            for level in fib_levels[:3]:
                entry_price = current_price + (atr * level * 3.0)
                entries.append(entry_price)
            
            tp = current_price - (atr * self.config.tp_atr_multiplier)
            # SL must be above the last (4th) entry to avoid same price
            sl = entries[3] + (atr * 0.5)  # Additional buffer above last entry
        
        # Get which strategies triggered
        triggered = [name for name, sig in signals.items() if sig == direction]
        
        return {
            'symbol': symbol,
            'direction': direction,
            'price': current_price,
            'entries': entries,
            'tp': tp,
            'sl': sl,
            'strategies': triggered,
            'count': count,
            'atr': atr
        }
    
    def run_cycle(self):
        """Run one scan cycle - scans multiple symbols"""
        logger.info("="*60)
        logger.info(f"Starting scan cycle at {datetime.now()}")
        logger.info("="*60)
        
        # Check for existing positions/orders first
        symbols_to_skip = self.client.get_symbols_with_positions_or_orders()
        
        # Get symbols to scan
        if self.config.auto_select_coins:
            all_symbols = self.client.get_most_volatile_symbols(self.config.num_coins_to_scan)
        else:
            all_symbols = [self.config.symbol]
        
        # Filter out symbols with existing positions/orders
        symbols = [s for s in all_symbols if s not in symbols_to_skip]
        
        if len(symbols) < len(all_symbols):
            skipped_count = len(all_symbols) - len(symbols)
            logger.info(f"⏭️  Skipped {skipped_count} symbols with existing positions/orders")
        
        logger.info(f"Scanning {len(symbols)} symbols...")
        
        # Scan all symbols and collect signals
        signals_found = []
        for symbol in symbols:
            result = self.analyze_market(symbol)
            if result:
                signals_found.append(result)
                logger.info(f"✅ Signal: {result['direction']} on {result['symbol']} (Score: {result['count']}/3)")
        
        # Sort by strategy count (highest consensus first)
        signals_found.sort(key=lambda x: x['count'], reverse=True)
        
        # Send top N signals
        if signals_found:
            signals_to_send = signals_found[:self.config.max_signals_per_scan]
            logger.info(f"\n📊 Found {len(signals_found)} total signals, sending top {len(signals_to_send)}:")
            
            for result in signals_to_send:
                logger.info(f"\n🎯 {result['symbol']} {result['direction']}")
                logger.info(f"   Entry: ${result['price']:.4f}")
                logger.info(f"   Entries: {[f'${e:.4f}' for e in result['entries']]}")
                logger.info(f"   TP: ${result['tp']:.4f}")
                logger.info(f"   SL: ${result['sl']:.4f}")
                logger.info(f"   Strategies: {result['count']}/3 confirmed")
                
                # Send to Telegram
                self.notifier.send_signal(
                    result['symbol'],
                    result['direction'],
                    result['price'],
                    result['entries'],
                    result['tp'],
                    result['sl'],
                    result['strategies'],
                    result['count']
                )
                
                # Execute trade if auto-trading enabled
                if self.config.auto_trade:
                    logger.warning("Auto-trading is enabled but not implemented yet for safety")
        else:
            logger.info("No signal found this cycle")
    
    def run(self):
        """Main bot loop"""
        logger.info("="*60)
        logger.info("Simple Scalping Bot Started - Multi-Symbol Scanner")
        if self.config.auto_select_coins:
            logger.info(f"Mode: AUTO-SELECT (scanning top {self.config.num_coins_to_scan} volatile coins)")
        else:
            logger.info(f"Mode: SINGLE SYMBOL ({self.config.symbol})")
        logger.info(f"Timeframe: {self.config.timeframe}")
        logger.info(f"Signal Threshold: {self.config.signal_threshold}/3 strategies")
        logger.info(f"Max Signals Per Scan: {self.config.max_signals_per_scan}")
        logger.info(f"Risk:Reward: 1.5:1 (TP: {self.config.tp_atr_multiplier}x ATR, SL: {self.config.sl_atr_multiplier}x ATR)")
        logger.info(f"Auto-Trade: {self.config.auto_trade}")
        logger.info("="*60)
        
        while True:
            try:
                self.run_cycle()
                logger.info(f"\nWaiting {self.config.scan_interval} seconds until next scan...")
                time.sleep(self.config.scan_interval)
            except KeyboardInterrupt:
                logger.info("\n\nBot stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(self.config.scan_interval)


def main():
    """Entry point"""
    config = BotConfig()
    bot = SimpleScalpingBot(config)
    bot.run()


if __name__ == "__main__":
    main()
