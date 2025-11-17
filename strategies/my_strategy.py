"""
Stock/Futures Strategy for Backtrader + OpenAlgo Unified API
CORRECTED: Now uses OpenAlgo's unified API for broker abstraction
Supports: Backtest / Paper / Live modes via UI toggle
"""
import backtrader as bt
from datetime import time as dtime
import json
import os

# OpenAlgo unified API
try:
    from openalgo import api as openalgo_api
except:
    openalgo_api = None

class MyStrategy(bt.Strategy):
    """
    Your exact strategy logic - NOW with OpenAlgo unified API
    """
    
    params = (
        # Strategy parameters (editable via UI)
        ('rsi_ema_veryfast', 20),
        ('rsi_ema_fast', 50),
        ('rsi_ema_slow', 100),
        ('rsi_long', 60.0),
        ('rsi_short', 40.0),
        ('cpr_wide_threshold', 0.015),
        
        # Risk management
        ('stoploss_pct', 0.005),    # 0.5%
        ('takeprofit_pct', 0.10),   # 10%
        ('commission_rate', 0.0001),
        
        # SuperTrend
        ('atr_period', 25),
        ('st_multiplier', 3.0),
        
        # Asset-specific leverage
        ('leverage', 9.0),
        
        # Mode & Broker
        ('mode', 'backtest'),  # 'backtest', 'paper', or 'live'
        ('broker_name', 'angelone'),  # 'angelone', 'groww', etc.
        ('exchange', 'NSE'),  # NSE, NFO, MCX
        ('product', 'MIS'),  # MIS or NRML
        
        # OpenAlgo API instance (will be initialized)
        ('openalgo_client', None),
        
        # Telegram alerts
        ('telegram_enabled', True),
        ('telegram_bot', None),
    )
    
    def __init__(self):
        # Initialize OpenAlgo client for live/paper trading
        if self.p.mode in ['paper', 'live'] and openalgo_api:
            self.p.openalgo_client = openalgo_api(
                api_key=os.getenv('OPENALGO_API_KEY'),
                host=os.getenv('OPENALGO_HOST', 'http://127.0.0.1:5000')
            )
        
        # EMAs
        self.ema05 = bt.indicators.EMA(self.data.close, period=4)
        self.ema5 = bt.indicators.EMA(self.data.close, period=14)
        self.ema20 = bt.indicators.EMA(self.data.close, period=35)
        
        # RSI
        self.rsi14 = bt.indicators.RSI(self.data.close, period=14)
        
        # RSI EMAs
        self.rsi_ema_veryfast = bt.indicators.EMA(self.rsi14, period=self.p.rsi_ema_veryfast)
        self.rsi_ema_fast = bt.indicators.EMA(self.rsi14, period=self.p.rsi_ema_fast)
        self.rsi_ema_slow = bt.indicators.EMA(self.rsi14, period=self.p.rsi_ema_slow)
        
        # SuperTrend (custom)
        self.supertrend = self.calculate_supertrend()
        
        # Order tracking
        self.order = None
        self.openalgo_order_id = None
        
        # Position tracking
        self.entry_price = None
        self.tp_price = None
        self.sl_price = None
    
    def calculate_supertrend(self):
        """Calculate SuperTrend indicator"""
        atr = bt.indicators.ATR(self.data, period=self.p.atr_period)
        hl2 = (self.data.high + self.data.low) / 2
        
        upperband = hl2 + (self.p.st_multiplier * atr)
        lowerband = hl2 - (self.p.st_multiplier * atr)
        
        return lowerband
    
    def notify_order(self, order):
        """Called when order status changes"""
        if order.status in [order.Completed]:
            if order.isbuy():
                self.entry_price = order.executed.price
                
                # Calculate TP and SL prices
                self.tp_price = self.entry_price * (1 + self.p.takeprofit_pct)
                self.sl_price = self.entry_price * (1 - self.p.stoploss_pct)
                
                # Place OCO orders based on mode
                if self.p.mode == 'backtest':
                    # Backtrader's built-in orders
                    self.sell(exectype=bt.Order.Limit, price=self.tp_price)
                    self.sell(exectype=bt.Order.Stop, price=self.sl_price)
                
                elif self.p.mode in ['paper', 'live']:
                    # Use OpenAlgo unified API for bracket orders
                    self.place_bracket_order_openalgo(
                        action='BUY',
                        quantity=abs(order.executed.size)
                    )
                
                # Telegram alert
                if self.p.telegram_enabled and self.p.telegram_bot:
                    import asyncio
                    asyncio.run(self.p.telegram_bot.send_entry_alert({
                        'symbol': self.data._name,
                        'side': 'LONG',
                        'entry_price': self.entry_price,
                        'tp_price': self.tp_price,
                        'sl_price': self.sl_price,
                        'quantity': order.executed.size
                    }))
            
            elif order.issell():
                # Exit executed
                profit = (order.executed.price - self.entry_price) * order.executed.size
                
                # Telegram alert
                if self.p.telegram_enabled and self.p.telegram_bot:
                    import asyncio
                    asyncio.run(self.p.telegram_bot.send_exit_alert({
                        'symbol': self.data._name,
                        'side': 'LONG',
                        'entry_price': self.entry_price,
                        'exit_price': order.executed.price,
                        'profit': profit,
                        'quantity': order.executed.size,
                        'reason': 'Exit'
                    }))
    
    def next(self):
        """Called for each candle"""
        
        # Skip if order pending
        if self.order:
            return
        
        # Skip if not enough data
        if len(self) < self.p.rsi_ema_slow:
            return
        
        # Skip forbidden entry times (9:15 - 10:00)
        current_time = self.data.datetime.time()
        if dtime(9, 15) <= current_time < dtime(10, 0):
            return
        
        # Calculate signals
        rsi_bullish = (
            self.rsi_ema_slow[0] > 50 and
            self.rsi_ema_veryfast[0] > self.rsi_ema_fast[0] and
            self.rsi_ema_fast[0] > self.rsi_ema_slow[0]
        )
        
        rsi_bearish = (
            self.rsi_ema_slow[0] < 40 and
            self.rsi_ema_veryfast[0] < self.rsi_ema_fast[0] and
            self.rsi_ema_fast[0] < self.rsi_ema_slow[0]
        )
        
        # Long signal
        long_signal = (
            self.ema5[0] > self.ema20[0] and
            self.ema05[0] > self.ema5[0] and
            self.rsi14[0] > self.p.rsi_long and
            self.data.close[0] > self.data.high[-1] and
            self.data.close[-1] > self.data.close[-2] and
            self.data.close[0] > self.data.open[0] and
            rsi_bullish
        )
        
        # Short signal
        short_signal = (
            self.ema5[0] < self.ema20[0] and
            self.ema05[0] < self.ema5[0] and
            self.rsi14[0] < self.p.rsi_short and
            self.data.close[0] < self.data.low[-1] and
            self.data.close[-1] < self.data.close[-2] and
            self.data.close[0] < self.data.open[0] and
            rsi_bearish
        )
        
        # Check if in position
        if not self.position:
            # Entry logic
            if long_signal:
                size = self.calculate_position_size()
                self.order = self.buy(size=size)
            
            elif short_signal:
                size = self.calculate_position_size()
                self.order = self.sell(size=size)
        
        else:
            # Exit logic - SuperTrend with commission check
            if self.position.size > 0:  # Long position
                if self.data.close[0] < self.supertrend[0]:
                    if self.is_profitable_exit():
                        self.order = self.close()
            
            elif self.position.size < 0:  # Short position
                if self.data.close[0] > self.supertrend[0]:
                    if self.is_profitable_exit():
                        self.order = self.close()
    
    def calculate_position_size(self):
        """Calculate position size based on leverage"""
        cash = self.broker.getcash()
        price = self.data.close[0]
        
        buying_power = cash * self.p.leverage
        size = int(buying_power / price)
        
        return size
    
    def is_profitable_exit(self):
        """Check if SuperTrend exit would be profitable after commission"""
        if not self.position:
            return False
        
        entry = self.entry_price
        current = self.data.close[0]
        size = abs(self.position.size)
        
        # Calculate gross profit
        if self.position.size > 0:
            gross_profit = (current - entry) * size
        else:
            gross_profit = (entry - current) * size
        
        # Calculate commission
        commission = self.p.commission_rate * (entry + current) * size
        
        # Net profit
        net_profit = gross_profit - commission
        
        return net_profit > 0
    
    def place_bracket_order_openalgo(self, action, quantity):
        """
        ✅ CORRECTED: Use OpenAlgo unified API for bracket orders
        Works with ANY broker (AngelOne, Groww, Zerodha, etc.)
        """
        if not self.p.openalgo_client:
            print("OpenAlgo client not initialized")
            return None
        
        try:
            # OpenAlgo unified order format
            order_response = self.p.openalgo_client.placeorder(
                strategy="MyStrategy",
                symbol=self.data._name,
                action=action,  # BUY or SELL
                exchange=self.p.exchange,  # NSE, NFO, MCX
                price_type="MARKET",
                product=self.p.product,  # MIS or NRML
                quantity=quantity,
                # Bracket order parameters
                order_type="BRACKET",
                target_price=self.tp_price,
                stoploss_price=self.sl_price,
                trailing_stoploss=0  # No trailing (as per requirements)
            )
            
            if order_response.get('status') == 'success':
                self.openalgo_order_id = order_response.get('orderid')
                print(f"✅ Bracket order placed: {self.openalgo_order_id}")
                return order_response
            else:
                print(f"❌ Order failed: {order_response.get('message')}")
                return None
                
        except Exception as e:
            print(f"❌ OpenAlgo order error: {e}")
            return None
    
    def cancel_bracket_orders_openalgo(self):
        """Cancel bracket orders via OpenAlgo"""
        if not self.openalgo_order_id:
            return
        
        try:
            cancel_response = self.p.openalgo_client.cancelorder(
                strategy="MyStrategy",
                orderid=self.openalgo_order_id
            )
            
            if cancel_response.get('status') == 'success':
                print(f"✅ Bracket orders cancelled")
            else:
                print(f"❌ Cancel failed: {cancel_response.get('message')}")
                
        except Exception as e:
            print(f"❌ Cancel error: {e}")


# ============================================================================
# FAILOVER LOGIC - AngelOne → Groww
# ============================================================================

class FailoverStrategy(MyStrategy):
    """
    Strategy with automatic broker failover
    If AngelOne fails → Switch to Groww
    """
    
    params = MyStrategy.params + (
        ('primary_broker', 'angelone'),
        ('backup_broker', 'groww'),
        ('max_retries', 3),
    )
    
    def place_bracket_order_openalgo(self, action, quantity):
        """Try primary broker, failover to backup if fails"""
        
        # Try primary broker
        for attempt in range(self.p.max_retries):
            try:
                # Use primary broker
                self.p.openalgo_client.broker = self.p.primary_broker
                response = super().place_bracket_order_openalgo(action, quantity)
                
                if response and response.get('status') == 'success':
                    return response
                
            except Exception as e:
                print(f"⚠️ Primary broker attempt {attempt + 1} failed: {e}")
        
        # Failover to backup broker
        print(f"🔄 Failing over to {self.p.backup_broker}")
        
        try:
            self.p.openalgo_client.broker = self.p.backup_broker
            response = super().place_bracket_order_openalgo(action, quantity)
            
            if response and response.get('status') == 'success':
                print(f"✅ Failover successful - using {self.p.backup_broker}")
                return response
            else:
                print(f"❌ Backup broker also failed")
                return None
                
        except Exception as e:
            print(f"❌ Backup broker error: {e}")
            return None


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

def run_live_trading_with_openalgo():
    """Example: Run live trading with OpenAlgo unified API"""
    import backtrader as bt
    
    cerebro = bt.Cerebro()
    
    # Add strategy with OpenAlgo configuration
    cerebro.addstrategy(
        FailoverStrategy,  # Use failover strategy
        mode='live',
        broker_name='angelone',  # Primary broker
        backup_broker='groww',   # Backup broker
        exchange='NFO',  # For futures
        product='MIS',
        leverage=9.0,
        telegram_enabled=True
    )
    
    # Set broker parameters
    cerebro.broker.setcash(200000)
    cerebro.broker.setcommission(commission=0.0001)
    
    # Add live data feed (from Historify or broker)
    # data = ... 
    # cerebro.adddata(data)
    
    # Run
    cerebro.run()


def run_backtest_mode():
    """Example: Run backtest (no OpenAlgo needed)"""
    import backtrader as bt
    
    cerebro = bt.Cerebro()
    
    # Add strategy in backtest mode
    cerebro.addstrategy(
        MyStrategy,
        mode='backtest',  # No broker API needed
        leverage=9.0
    )
    
    # Load historical data
    # data = bt.feeds.GenericCSVData(...)
    # cerebro.adddata(data)
    
    cerebro.broker.setcash(200000)
    cerebro.broker.setcommission(commission=0.0001)
    
    # Run
    results = cerebro.run()
    
    return results
