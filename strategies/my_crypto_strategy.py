"""
Crypto Strategy for Freqtrade with CCXT
✅ CORRECTED: Freqtrade already uses CCXT internally (no changes needed to strategy)
Just need proper config for Delta Exchange via CCXT
"""
from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import pandas_ta as pta
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class MyCryptoStrategy(IStrategy):
    """
    Crypto futures strategy - Uses Freqtrade's CCXT integration
    ✅ CCXT automatically handles Delta Exchange API
    """
    
    INTERFACE_VERSION = 3
    
    # ROI (Take Profit) - 10%
    minimal_roi = {
        "0": 0.10
    }
    
    # Stoploss - 0.5%
    stoploss = -0.005
    
    # Trailing stop disabled
    trailing_stop = False
    
    # Timeframe
    timeframe = '15m'
    
    # Can go short
    can_short = True
    
    # Startup candle count
    startup_candle_count: int = 100
    
    # Order types (CCXT handles exchange-specific implementation)
    order_types = {
        'entry': 'limit',
        'exit': 'limit',
        'stoploss': 'market',
        'stoploss_on_exchange': True  # CCXT places SL on Delta Exchange
    }
    
    # Strategy parameters (editable via UI)
    rsi_ema_veryfast = 20
    rsi_ema_fast = 50
    rsi_ema_slow = 100
    rsi_long = 60.0
    rsi_short = 40.0
    atr_period = 25
    st_multiplier = 3.0
    
    # Leverage (CCXT handles via exchange API)
    leverage_num = 8.0  # 8x for crypto futures
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Add all indicators - same as backtest_simple.py
        """
        
        # EMAs
        dataframe['ema05'] = ta.EMA(dataframe, timeperiod=4)
        dataframe['ema5'] = ta.EMA(dataframe, timeperiod=14)
        dataframe['ema20'] = ta.EMA(dataframe, timeperiod=35)
        
        # RSI
        dataframe['rsi14'] = ta.RSI(dataframe, timeperiod=14)
        
        # RSI EMAs
        dataframe['rsi_ema_veryfast'] = ta.EMA(dataframe['rsi14'], timeperiod=self.rsi_ema_veryfast)
        dataframe['rsi_ema_fast'] = ta.EMA(dataframe['rsi14'], timeperiod=self.rsi_ema_fast)
        dataframe['rsi_ema_slow'] = ta.EMA(dataframe['rsi14'], timeperiod=self.rsi_ema_slow)
        
        # RSI momentum flags
        dataframe['rsi_bullish'] = (
            (dataframe['rsi_ema_slow'] > 50) &
            (dataframe['rsi_ema_veryfast'] > dataframe['rsi_ema_fast']) &
            (dataframe['rsi_ema_fast'] > dataframe['rsi_ema_slow'])
        )
        
        dataframe['rsi_bearish'] = (
            (dataframe['rsi_ema_slow'] < 40) &
            (dataframe['rsi_ema_veryfast'] < dataframe['rsi_ema_fast']) &
            (dataframe['rsi_ema_fast'] < dataframe['rsi_ema_slow'])
        )
        
        # SuperTrend
        supertrend = pta.supertrend(
            dataframe['high'],
            dataframe['low'],
            dataframe['close'],
            length=self.atr_period,
            multiplier=self.st_multiplier
        )
        
        dataframe['supertrend'] = supertrend[f'SUPERT_{self.atr_period}_{self.st_multiplier}']
        dataframe['supertrend_direction'] = supertrend[f'SUPERTd_{self.atr_period}_{self.st_multiplier}']
        
        # Previous candle data
        dataframe['prev_high'] = dataframe['high'].shift(1)
        dataframe['prev_low'] = dataframe['low'].shift(1)
        dataframe['prev_close'] = dataframe['close'].shift(1)
        dataframe['prev2_close'] = dataframe['close'].shift(2)
        
        # Candle type
        dataframe['bull_candle'] = dataframe['close'] > dataframe['open']
        dataframe['bear_candle'] = dataframe['close'] < dataframe['open']
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Entry signals - exact same as stock strategy
        """
        
        # Long entry
        dataframe.loc[
            (
                # EMA alignment
                (dataframe['ema5'] > dataframe['ema20']) &
                (dataframe['ema05'] > dataframe['ema5']) &
                
                # RSI condition
                (dataframe['rsi14'] > self.rsi_long) &
                
                # Price action
                (dataframe['close'] > dataframe['prev_high']) &
                (dataframe['prev_close'] > dataframe['prev2_close']) &
                (dataframe['bull_candle']) &
                
                # RSI momentum
                (dataframe['rsi_bullish']) &
                
                # Volume
                (dataframe['volume'] > 0)
            ),
            ['enter_long', 'enter_tag']
        ] = (1, 'long_signal')
        
        # Short entry
        dataframe.loc[
            (
                # EMA alignment
                (dataframe['ema5'] < dataframe['ema20']) &
                (dataframe['ema05'] < dataframe['ema5']) &
                
                # RSI condition
                (dataframe['rsi14'] < self.rsi_short) &
                
                # Price action
                (dataframe['close'] < dataframe['prev_low']) &
                (dataframe['prev_close'] < dataframe['prev2_close']) &
                (dataframe['bear_candle']) &
                
                # RSI momentum
                (dataframe['rsi_bearish']) &
                
                # Volume
                (dataframe['volume'] > 0)
            ),
            ['enter_short', 'enter_tag']
        ] = (1, 'short_signal')
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Exit signals - SuperTrend (validated by custom_exit)
        """
        
        # SuperTrend exit for longs
        dataframe.loc[
            (
                (dataframe['close'] < dataframe['supertrend']) &
                (dataframe['supertrend_direction'] == -1)
            ),
            ['exit_long', 'exit_tag']
        ] = (1, 'supertrend_signal')
        
        # SuperTrend exit for shorts
        dataframe.loc[
            (
                (dataframe['close'] > dataframe['supertrend']) &
                (dataframe['supertrend_direction'] == 1)
            ),
            ['exit_short', 'exit_tag']
        ] = (1, 'supertrend_signal')
        
        return dataframe
    
    def custom_exit(self, pair: str, trade, current_time, current_rate,
                    current_profit, **kwargs):
        """
        CRITICAL: SuperTrend exit only if profitable after commission
        """
        
        # Commission threshold (Delta: ~0.05% maker + 0.05% taker)
        min_profit_threshold = 0.0015  # 0.15% to cover commissions
        
        # Only check SuperTrend if profitable
        if current_profit > min_profit_threshold:
            
            dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            last_candle = dataframe.iloc[-1].squeeze()
            
            # Long position - check SuperTrend bearish
            if trade.is_long:
                if (last_candle['close'] < last_candle['supertrend'] and 
                    last_candle['supertrend_direction'] == -1):
                    logger.info(f"SuperTrend profitable exit for LONG {pair} at {current_profit:.2%}")
                    return 'supertrend_profitable_exit'
            
            # Short position - check SuperTrend bullish
            elif trade.is_short:
                if (last_candle['close'] > last_candle['supertrend'] and 
                    last_candle['supertrend_direction'] == 1):
                    logger.info(f"SuperTrend profitable exit for SHORT {pair} at {current_profit:.2%}")
                    return 'supertrend_profitable_exit'
        
        return None
    
    def custom_stoploss(self, pair: str, trade, current_time, current_rate,
                       current_profit, **kwargs):
        """
        FIXED stoploss - no trailing
        """
        return self.stoploss
    
    def confirm_trade_entry(self, pair: str, order_type: str, amount: float,
                           rate: float, time_in_force: str, current_time,
                           entry_tag, side: str, **kwargs) -> bool:
        """
        Confirm entry - skip forbidden times (9:15 - 10:00 IST)
        Note: For crypto, this may not be needed as markets are 24/7
        """
        
        # Get current time in IST
        hour = current_time.hour
        minute = current_time.minute
        
        # Forbidden window (optional for crypto)
        if (hour == 9 and minute >= 15) or (hour == 10 and minute == 0):
            logger.info(f"Entry rejected for {pair} - forbidden time window")
            return False
        
        return True
    
    def leverage(self, pair: str, current_time, current_rate,
                 proposed_leverage: float, max_leverage: float, side: str,
                 **kwargs) -> float:
        """
        Set leverage to 8x for crypto futures
        ✅ CCXT automatically applies this via exchange API
        """
        return self.leverage_num


# ============================================================================
# ✅ CCXT CONFIGURATION HELPER
# ============================================================================

def get_ccxt_config_for_delta(mode='paper'):
    """
    Returns Freqtrade config with proper CCXT setup for Delta Exchange
    ✅ CCXT handles all Delta Exchange API calls internally
    
    Args:
        mode: 'backtest', 'paper' (dry_run), or 'live'
    
    Returns:
        dict: Configuration dictionary
    """
    
    config = {
        "strategy": "MyCryptoStrategy",
        "max_open_trades": 3,
        "stake_currency": "USDT",
        "stake_amount": "unlimited",
        "tradable_balance_ratio": 0.99,
        
        # Mode
        "dry_run": mode != 'live',
        "dry_run_wallet": 10000 if mode == 'paper' else None,
        
        # ✅ CCXT Exchange Configuration for Delta
        "exchange": {
            "name": "delta",  # CCXT exchange ID
            
            # API credentials (from environment variables)
            "key": "${DELTA_API_KEY}",
            "secret": "${DELTA_API_SECRET}",
            
            # ✅ CCXT-specific configuration
            "ccxt_config": {
                "enableRateLimit": True,  # Respect rate limits
                "rateLimit": 50,  # ms between requests
                "timeout": 30000,  # Request timeout
                
                # Delta Exchange specific options
                "options": {
                    "defaultType": "future",  # Trade futures by default
                    "adjustForTimeDifference": True  # Handle time sync
                }
            },
            
            # Async CCXT config
            "ccxt_async_config": {
                "enableRateLimit": True,
                "rateLimit": 50
            },
            
            # Trading pairs (CCXT format for Delta perpetual futures)
            "pair_whitelist": [
                "BTC/USDT:USDT",  # BTC perpetual futures
                "ETH/USDT:USDT"   # ETH perpetual futures
            ],
            "pair_blacklist": []
        },
        
        # Order types (CCXT handles exchange-specific implementation)
        "order_types": {
            "entry": "limit",
            "exit": "limit",
            "stoploss": "market",
            "stoploss_on_exchange": True,  # CCXT places SL on exchange
            "stoploss_on_exchange_interval": 60  # Check every 60s
        },
        
        # Entry pricing (CCXT fetches from exchange)
        "entry_pricing": {
            "price_side": "same",
            "use_order_book": True,
            "order_book_top": 1,
            "check_depth_of_market": {
                "enabled": False
            }
        },
        
        # Exit pricing (CCXT fetches from exchange)
        "exit_pricing": {
            "price_side": "same",
            "use_order_book": True,
            "order_book_top": 1
        },
        
        # Telegram notifications
        "telegram": {
            "enabled": True,
            "token": "${TELEGRAM_BOT_TOKEN}",
            "chat_id": "${TELEGRAM_CHAT_ID}",
            "notification_settings": {
                "status": "on",
                "warning": "on",
                "startup": "on",
                "entry": "on",
                "entry_fill": "on",
                "exit": "on",
                "exit_fill": "on",
                "protection_trigger": "on"
            }
        },
        
        # API server (for UI access)
        "api_server": {
            "enabled": True,
            "listen_ip_address": "0.0.0.0",
            "listen_port": 8080,
            "cors_allowed_origins": [],
            "username": "${FREQTRADE_API_USERNAME}",
            "password": "${FREQTRADE_API_PASSWORD}",
            "jwt_secret_key": "${FREQTRADE_JWT_SECRET}",
            "ws_token": "${FREQTRADE_WS_TOKEN}"
        },
        
        # Bot settings
        "bot_name": "CryptoTradingBot",
        "initial_state": "running",
        "force_entry_enable": True,
        "internals": {
            "process_throttle_secs": 5
        }
    }
    
    return config


# ============================================================================
# ✅ CCXT EXCHANGE TEST
# ============================================================================

def test_ccxt_delta_connection():
    """
    Test CCXT connection to Delta Exchange
    Run this to verify your API keys work
    """
    import ccxt
    import os
    
    print("Testing CCXT connection to Delta Exchange...")
    
    try:
        # Initialize CCXT Delta exchange
        exchange = ccxt.delta({
            'apiKey': os.getenv('DELTA_API_KEY'),
            'secret': os.getenv('DELTA_API_SECRET'),
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future'
            }
        })
        
        # Test: Fetch balance
        balance = exchange.fetch_balance()
        print(f"✅ Connected! USDT Balance: {balance['USDT']['free']}")
        
        # Test: Fetch ticker
        ticker = exchange.fetch_ticker('BTC/USDT:USDT')
        print(f"✅ BTC/USDT Price: ${ticker['last']}")
        
        # Test: Fetch markets
        markets = exchange.load_markets()
        print(f"✅ Available markets: {len(markets)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


if __name__ == "__main__":
    # Test CCXT connection
    test_ccxt_delta_connection()
