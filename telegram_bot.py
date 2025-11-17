"""
Telegram Bot for Trade Alerts and Notifications
Sends real-time alerts for:
- Entry/exit signals
- TP/SL hits
- Daily P&L summary
- Bot status changes
"""
import os
import json
from telegram import Bot
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import asyncio
from datetime import datetime

class TradingTelegramBot:
    """Telegram bot for trading alerts"""
    
    def __init__(self, token, chat_id):
        """
        Initialize Telegram bot
        
        Args:
            token: Bot token from @BotFather
            chat_id: Your Telegram chat ID
        """
        self.token = token
        self.chat_id = chat_id
        self.bot = Bot(token=token)
    
    async def send_message(self, message, parse_mode='Markdown'):
        """Send message to user"""
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode=parse_mode
            )
            return True
        except Exception as e:
            print(f"Error sending message: {e}")
            return False
    
    async def send_entry_alert(self, trade_data):
        """
        Send entry alert
        
        Args:
            trade_data: dict with keys:
                - symbol, side, entry_price, tp_price, sl_price, quantity
        """
        emoji = "🟢" if trade_data['side'] == 'LONG' else "🔴"
        
        message = f"""
{emoji} *{trade_data['side']} ENTRY*

📊 Symbol: `{trade_data['symbol']}`
💰 Entry: ₹{trade_data['entry_price']:,.2f}
🎯 Target: ₹{trade_data['tp_price']:,.2f}
🛡️ Stop Loss: ₹{trade_data['sl_price']:,.2f}
📦 Quantity: {trade_data['quantity']}

⏰ Time: {datetime.now().strftime('%H:%M:%S')}
"""
        
        await self.send_message(message)
    
    async def send_exit_alert(self, trade_data):
        """
        Send exit alert
        
        Args:
            trade_data: dict with keys:
                - symbol, side, entry_price, exit_price, profit, reason
        """
        emoji = "✅" if trade_data['profit'] > 0 else "❌"
        profit_pct = (trade_data['profit'] / (trade_data['entry_price'] * trade_data['quantity'])) * 100
        
        message = f"""
{emoji} *POSITION CLOSED*

📊 Symbol: `{trade_data['symbol']}`
📍 Side: {trade_data['side']}
📥 Entry: ₹{trade_data['entry_price']:,.2f}
📤 Exit: ₹{trade_data['exit_price']:,.2f}
💵 P&L: ₹{trade_data['profit']:,.2f} ({profit_pct:+.2f}%)
🏷️ Reason: {trade_data['reason']}

⏰ Time: {datetime.now().strftime('%H:%M:%S')}
"""
        
        await self.send_message(message)
    
    async def send_daily_summary(self, summary_data):
        """
        Send daily P&L summary
        
        Args:
            summary_data: dict with daily stats
        """
        message = f"""
📊 *DAILY SUMMARY*
{datetime.now().strftime('%Y-%m-%d')}

💰 Total P&L: ₹{summary_data['total_pnl']:,.2f}
📈 Wins: {summary_data['wins']}
📉 Losses: {summary_data['losses']}
📊 Win Rate: {summary_data['win_rate']:.1f}%
🎯 Total Trades: {summary_data['total_trades']}

*By Asset:*
• Crypto: ₹{summary_data.get('crypto_pnl', 0):,.2f}
• Stocks: ₹{summary_data.get('stocks_pnl', 0):,.2f}
• Options: ₹{summary_data.get('options_pnl', 0):,.2f}

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
        
        await self.send_message(message)
    
    async def send_bot_status(self, status, message_text=""):
        """
        Send bot status alert
        
        Args:
            status: 'started', 'stopped', 'error', 'warning'
            message_text: Additional message
        """
        emoji_map = {
            'started': '✅',
            'stopped': '🛑',
            'error': '⚠️',
            'warning': '⚠️'
        }
        
        emoji = emoji_map.get(status, 'ℹ️')
        
        message = f"""
{emoji} *BOT STATUS: {status.upper()}*

{message_text}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        await self.send_message(message)
    
    async def send_milestone_alert(self, milestone_data):
        """
        Send milestone achievements
        
        Args:
            milestone_data: dict with milestone info
        """
        message = f"""
🎉 *MILESTONE ACHIEVED!*

{milestone_data['title']}

{milestone_data['description']}

⏰ {datetime.now().strftime('%H:%M:%S')}
"""
        
        await self.send_message(message)


# ============================================================================
# TELEGRAM BOT COMMANDS (for user interaction)
# ============================================================================

class TradingBotCommands:
    """Handle Telegram bot commands"""
    
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.updater = Updater(token=bot_instance.token, use_context=True)
        self.dispatcher = self.updater.dispatcher
        
        # Add command handlers
        self.dispatcher.add_handler(CommandHandler("start", self.start))
        self.dispatcher.add_handler(CommandHandler("status", self.status))
        self.dispatcher.add_handler(CommandHandler("pnl", self.pnl))
        self.dispatcher.add_handler(CommandHandler("positions", self.positions))
        self.dispatcher.add_handler(CommandHandler("stop", self.stop_bot))
    
    def start(self, update, context):
        """Handle /start command"""
        message = """
👋 *Welcome to Trading Bot!*

Available commands:
/status - Bot status
/pnl - Today's P&L
/positions - Active positions
/stop - Stop trading bot

You'll receive real-time alerts for all trades!
"""
        update.message.reply_text(message, parse_mode='Markdown')
    
    def status(self, update, context):
        """Handle /status command"""
        # Fetch current bot status
        message = """
✅ *Bot Status*

Mode: Paper Trading
Status: Running
Uptime: 2h 34m
Active Positions: 2
"""
        update.message.reply_text(message, parse_mode='Markdown')
    
    def pnl(self, update, context):
        """Handle /pnl command"""
        # Fetch P&L from database/API
        message = """
💰 *Today's P&L*

Total: ₹1,234 (+0.62%)

By Asset:
• Crypto: ₹890
• Stocks: ₹344
"""
        update.message.reply_text(message, parse_mode='Markdown')
    
    def positions(self, update, context):
        """Handle /positions command"""
        # Fetch active positions
        message = """
📊 *Active Positions*

1. BTCUSDT LONG
   Entry: ₹65,432
   Current: ₹65,890
   P&L: ₹458 (+0.70%)

2. NIFTY FUT LONG
   Entry: ₹23,560
   Current: ₹23,620
   P&L: ₹60 (+0.25%)
"""
        update.message.reply_text(message, parse_mode='Markdown')
    
    def stop_bot(self, update, context):
        """Handle /stop command"""
        # Implement bot stop logic
        message = "🛑 Stopping trading bot..."
        update.message.reply_text(message)
    
    def run(self):
        """Start the bot"""
        self.updater.start_polling()
        self.updater.idle()


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

async def example_usage():
    """Example of how to use the Telegram bot"""
    
    # Initialize bot
    TOKEN = "YOUR_BOT_TOKEN"  # From @BotFather
    CHAT_ID = "YOUR_CHAT_ID"  # Your Telegram chat ID
    
    bot = TradingTelegramBot(TOKEN, CHAT_ID)
    
    # Send entry alert
    await bot.send_entry_alert({
        'symbol': 'BTCUSDT',
        'side': 'LONG',
        'entry_price': 65432,
        'tp_price': 71975,
        'sl_price': 65105,
        'quantity': 0.1
    })
    
    # Send exit alert
    await bot.send_exit_alert({
        'symbol': 'BTCUSDT',
        'side': 'LONG',
        'entry_price': 65432,
        'exit_price': 67123,
        'profit': 1691,
        'quantity': 0.1,
        'reason': 'TP'
    })
    
    # Send daily summary
    await bot.send_daily_summary({
        'total_pnl': 2345,
        'wins': 15,
        'losses': 7,
        'win_rate': 68.2,
        'total_trades': 22,
        'crypto_pnl': 1500,
        'stocks_pnl': 845,
        'options_pnl': 0
    })
    
    # Send bot status
    await bot.send_bot_status('started', 'Paper trading mode activated')
    
    # Send milestone
    await bot.send_milestone_alert({
        'title': '100 Trades Completed! 🎉',
        'description': 'Total P&L: ₹25,000\nWin Rate: 67%'
    })


# ============================================================================
# INTEGRATION WITH TRADING SYSTEM
# ============================================================================

class TelegramIntegration:
    """Integrate Telegram bot with trading system"""
    
    def __init__(self, config_file='settings.json'):
        """Load Telegram config from settings"""
        with open(config_file, 'r') as f:
            settings = json.load(f)
        
        telegram_config = settings.get('telegram', {})
        
        if telegram_config.get('enabled'):
            self.bot = TradingTelegramBot(
                token=telegram_config['token'],
                chat_id=telegram_config['chat_id']
            )
            self.enabled = True
        else:
            self.bot = None
            self.enabled = False
    
    async def notify_entry(self, trade_data):
        """Send entry notification"""
        if self.enabled:
            await self.bot.send_entry_alert(trade_data)
    
    async def notify_exit(self, trade_data):
        """Send exit notification"""
        if self.enabled:
            await self.bot.send_exit_alert(trade_data)
    
    async def notify_daily_summary(self, summary_data):
        """Send daily summary"""
        if self.enabled:
            await self.bot.send_daily_summary(summary_data)
    
    async def notify_status(self, status, message=""):
        """Send status update"""
        if self.enabled:
            await self.bot.send_bot_status(status, message)


# ============================================================================
# HOW TO GET BOT TOKEN AND CHAT ID
# ============================================================================

"""
SETUP INSTRUCTIONS:

1. Create Bot:
   - Open Telegram
   - Search for @BotFather
   - Send /newbot
   - Choose a name and username
   - Copy the token

2. Get Chat ID:
   - Start a chat with your bot
   - Send any message
   - Visit: https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
   - Look for "chat":{"id":123456789}
   - Copy the ID

3. Add to settings.json:
   {
     "telegram": {
       "enabled": true,
       "token": "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz",
       "chat_id": "123456789"
     }
   }

4. Test:
   python telegram_bot.py
"""

if __name__ == "__main__":
    # Run example
    asyncio.run(example_usage())
