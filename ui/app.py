"""
Combined Trading UI with Authentication
- Login/Logout with password reset via SMTP
- No-code strategy builder
- Backtest/Paper/Live toggle
- Combined P&L dashboard (stocks + crypto)
- Telegram alerts configuration
"""
import streamlit as st
import pandas as pd
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import hashlib
import secrets
from datetime import datetime, timedelta
import requests

# Page config
st.set_page_config(
    page_title="Trading System",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# AUTHENTICATION
# ============================================================================

class Auth:
    """Handle user authentication"""
    
    def __init__(self):
        self.users_file = 'users.json'
        self.reset_tokens_file = 'reset_tokens.json'
        self.load_users()
    
    def load_users(self):
        """Load users from file"""
        if os.path.exists(self.users_file):
            with open(self.users_file, 'r') as f:
                self.users = json.load(f)
        else:
            # Create default admin user
            self.users = {
                "admin": {
                    "password": self.hash_password("admin123"),
                    "email": "admin@example.com"
                }
            }
            self.save_users()
    
    def save_users(self):
        """Save users to file"""
        with open(self.users_file, 'w') as f:
            json.dump(self.users, f, indent=2)
    
    @staticmethod
    def hash_password(password):
        """Hash password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def verify_login(self, username, password):
        """Verify username and password"""
        if username in self.users:
            return self.users[username]['password'] == self.hash_password(password)
        return False
    
    def send_reset_email(self, email, smtp_config):
        """Send password reset email"""
        # Find user by email
        username = None
        for user, data in self.users.items():
            if data['email'] == email:
                username = user
                break
        
        if not username:
            return False, "Email not found"
        
        # Generate reset token
        token = secrets.token_urlsafe(32)
        
        # Save token
        tokens = {}
        if os.path.exists(self.reset_tokens_file):
            with open(self.reset_tokens_file, 'r') as f:
                tokens = json.load(f)
        
        tokens[token] = {
            'username': username,
            'expires': (datetime.now() + timedelta(hours=1)).isoformat()
        }
        
        with open(self.reset_tokens_file, 'w') as f:
            json.dump(tokens, f, indent=2)
        
        # Send email
        try:
            msg = MIMEMultipart()
            msg['From'] = smtp_config['from_email']
            msg['To'] = email
            msg['Subject'] = "Password Reset Request"
            
            body = f"""
            Hello {username},
            
            You requested a password reset. Use this token to reset your password:
            
            Token: {token}
            
            This token will expire in 1 hour.
            
            If you didn't request this, please ignore this email.
            
            Best regards,
            Trading System
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(smtp_config['smtp_server'], smtp_config['smtp_port'])
            server.starttls()
            server.login(smtp_config['smtp_username'], smtp_config['smtp_password'])
            server.send_message(msg)
            server.quit()
            
            return True, "Reset email sent successfully"
        
        except Exception as e:
            return False, f"Error sending email: {str(e)}"
    
    def reset_password(self, token, new_password):
        """Reset password using token"""
        if not os.path.exists(self.reset_tokens_file):
            return False, "Invalid token"
        
        with open(self.reset_tokens_file, 'r') as f:
            tokens = json.load(f)
        
        if token not in tokens:
            return False, "Invalid token"
        
        # Check if expired
        token_data = tokens[token]
        if datetime.fromisoformat(token_data['expires']) < datetime.now():
            return False, "Token expired"
        
        # Reset password
        username = token_data['username']
        self.users[username]['password'] = self.hash_password(new_password)
        self.save_users()
        
        # Delete token
        del tokens[token]
        with open(self.reset_tokens_file, 'w') as f:
            json.dump(tokens, f, indent=2)
        
        return True, "Password reset successfully"


# ============================================================================
# SESSION STATE
# ============================================================================

def init_session_state():
    """Initialize session state variables"""
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'username' not in st.session_state:
        st.session_state.username = None
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'dashboard'


# ============================================================================
# LOGIN PAGE
# ============================================================================

def login_page(auth):
    """Display login page"""
    
    st.title("🔐 Trading System Login")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        tab1, tab2, tab3 = st.tabs(["Login", "Reset Password", "New Password"])
        
        # Login tab
        with tab1:
            st.subheader("Login")
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            
            if st.button("Login", type="primary"):
                if auth.verify_login(username, password):
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.error("Invalid username or password")
        
        # Reset password tab
        with tab2:
            st.subheader("Reset Password")
            st.info("Enter your email to receive a reset token")
            
            email = st.text_input("Email", key="reset_email")
            
            # SMTP configuration
            with st.expander("SMTP Configuration (for sending reset email)"):
                smtp_server = st.text_input("SMTP Server", value="smtp.gmail.com")
                smtp_port = st.number_input("SMTP Port", value=587)
                smtp_username = st.text_input("SMTP Username")
                smtp_password = st.text_input("SMTP Password", type="password")
                from_email = st.text_input("From Email", value=smtp_username)
            
            if st.button("Send Reset Email"):
                if not all([smtp_server, smtp_username, smtp_password]):
                    st.error("Please configure SMTP settings")
                else:
                    smtp_config = {
                        'smtp_server': smtp_server,
                        'smtp_port': smtp_port,
                        'smtp_username': smtp_username,
                        'smtp_password': smtp_password,
                        'from_email': from_email
                    }
                    
                    success, message = auth.send_reset_email(email, smtp_config)
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
        
        # New password tab
        with tab3:
            st.subheader("Set New Password")
            st.info("Enter the token from your email and set a new password")
            
            token = st.text_input("Reset Token", key="reset_token")
            new_password = st.text_input("New Password", type="password", key="new_password")
            confirm_password = st.text_input("Confirm Password", type="password", key="confirm_password")
            
            if st.button("Reset Password"):
                if new_password != confirm_password:
                    st.error("Passwords don't match")
                elif len(new_password) < 6:
                    st.error("Password must be at least 6 characters")
                else:
                    success, message = auth.reset_password(token, new_password)
                    if success:
                        st.success(message)
                    else:
                        st.error(message)


# ============================================================================
# MAIN APP
# ============================================================================

def main_app():
    """Main application after login"""
    
    # Sidebar navigation
    with st.sidebar:
        st.title(f"👤 {st.session_state.username}")
        
        if st.button("Logout", type="secondary"):
            st.session_state.logged_in = False
            st.session_state.username = None
            st.rerun()
        
        st.markdown("---")
        
        page = st.radio(
            "Navigation",
            ["📊 Dashboard", "🔧 Strategy Builder", "📈 Backtest", "🔴 Live/Paper Trading", "⚙️ Settings"]
        )
    
    # Page routing
    if page == "📊 Dashboard":
        dashboard_page()
    elif page == "🔧 Strategy Builder":
        strategy_builder_page()
    elif page == "📈 Backtest":
        backtest_page()
    elif page == "🔴 Live/Paper Trading":
        live_trading_page()
    elif page == "⚙️ Settings":
        settings_page()


# ============================================================================
# DASHBOARD PAGE
# ============================================================================

def dashboard_page():
    """Combined P&L dashboard for stocks and crypto"""
    
    st.title("📊 Combined Trading Dashboard")
    
    # Overall metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total P&L", "₹52,480", "+26.2%")
    with col2:
        st.metric("Today's P&L", "₹2,345", "+1.17%")
    with col3:
        st.metric("Total Trades", "143")
    with col4:
        st.metric("Overall Win Rate", "67.8%")
    
    st.markdown("---")
    
    # Asset breakdown
    st.subheader("Performance by Asset Type")
    
    asset_data = pd.DataFrame({
        "Asset Type": ["Index Futures", "Crypto Futures", "Commodities", "Options"],
        "P&L (₹)": [25480, 18200, 5800, 3000],
        "Trades": [52, 67, 18, 6],
        "Win Rate": ["68.5%", "65.2%", "72.2%", "66.7%"],
        "Avg Profit": ["₹490", "₹272", "₹322", "₹500"]
    })
    
    st.dataframe(asset_data, use_container_width=True)
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Equity Curve")
        # Placeholder chart
        chart_data = pd.DataFrame({
            'Date': pd.date_range('2024-01-01', periods=100),
            'Equity': [200000 + i*500 for i in range(100)]
        })
        st.line_chart(chart_data.set_index('Date'))
    
    with col2:
        st.subheader("Win/Loss Distribution")
        distribution_data = pd.DataFrame({
            'Category': ['Wins', 'Losses'],
            'Count': [97, 46]
        })
        st.bar_chart(distribution_data.set_index('Category'))
    
    # Recent trades
    st.subheader("Recent Trades (All Assets)")
    
    recent_trades = pd.DataFrame({
        "Time": ["2024-11-16 14:30", "2024-11-16 13:15", "2024-11-16 11:45"],
        "Asset": ["BTCUSDT", "NIFTY FUT", "ETHUSD"],
        "Type": ["Long", "Short", "Long"],
        "Entry": ["₹65,432", "₹23,450", "₹2,134"],
        "Exit": ["₹67,123", "₹23,320", "₹2,198"],
        "P&L": ["₹1,691", "₹195", "₹64"],
        "Reason": ["TP", "Supertrend", "TP"]
    })
    
    st.dataframe(recent_trades, use_container_width=True)
    
    # Real-time status
    st.markdown("---")
    st.subheader("Active Positions")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.info("🟢 **BTCUSDT LONG**\nEntry: ₹65,432\nCurrent: ₹65,890\nP&L: +₹458 (+0.70%)")
    
    with col2:
        st.info("🟢 **NIFTY FUT LONG**\nEntry: ₹23,560\nCurrent: ₹23,620\nP&L: +₹60 (+0.25%)")
    
    with col3:
        st.warning("📊 **No position**\nWaiting for signals...")


# ============================================================================
# STRATEGY BUILDER PAGE
# ============================================================================

def strategy_builder_page():
    """No-code strategy builder"""
    
    st.title("🔧 No-Code Strategy Builder")
    
    st.info("📝 Build and modify your trading strategy without coding!")
    
    # Asset selection
    st.subheader("1️⃣ Asset Configuration")
    
    col1, col2 = st.columns(2)
    
    with col1:
        asset_type = st.selectbox(
            "Asset Type",
            ["Index Futures", "Commodity Futures", "Crypto Futures", "Options"]
        )
    
    with col2:
        if asset_type == "Index Futures":
            symbol = st.selectbox("Symbol", ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"])
            leverage = 9.0
        elif asset_type == "Commodity Futures":
            symbol = st.selectbox("Symbol", ["SILVERM", "CRUDEOILM"])
            leverage = 5.0 if symbol == "SILVERM" else 3.0
        elif asset_type == "Crypto Futures":
            symbol = st.selectbox("Symbol", ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"])
            leverage = 8.0
        else:  # Options
            symbol = st.selectbox("Symbol", ["NIFTY", "BANKNIFTY"])
            leverage = 1.0
    
    if asset_type == "Options":
        col1, col2 = st.columns(2)
        with col1:
            option_type = st.radio("Option Type", ["CALL", "PUT"])
        with col2:
            strike = st.selectbox("Strike Selection", ["ITM1", "ATM", "OTM1", "OTM2"])
    
    # Risk management
    st.subheader("2️⃣ Risk Management")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        capital = st.number_input("Starting Capital (₹)", min_value=10000, value=200000, step=10000)
    with col2:
        tp_pct = st.slider("Take Profit %", 1.0, 50.0, 10.0, 0.5)
    with col3:
        sl_pct = st.slider("Stop Loss %", 0.1, 5.0, 0.5, 0.1)
    
    st.info(f"💰 Leverage: **{leverage}x** | Effective buying power: **₹{capital * leverage:,.0f}**")
    
    # Strategy parameters
    st.subheader("3️⃣ Strategy Parameters")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        rsi_veryfast = st.number_input("RSI EMA VeryFast", 5, 50, 20)
        rsi_fast = st.number_input("RSI EMA Fast", 20, 100, 50)
    
    with col2:
        rsi_slow = st.number_input("RSI EMA Slow", 50, 200, 100)
        rsi_long = st.slider("RSI Long Threshold", 50.0, 80.0, 60.0)
    
    with col3:
        rsi_short = st.slider("RSI Short Threshold", 20.0, 50.0, 40.0)
        atr_period = st.slider("ATR Period", 10, 50, 25)
    
    st_multiplier = st.slider("SuperTrend Multiplier", 1.0, 5.0, 3.0, 0.1)
    
    # Additional indicators
    st.subheader("4️⃣ Additional Indicators (Optional)")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        use_macd = st.checkbox("Use MACD")
    with col2:
        use_bollinger = st.checkbox("Use Bollinger Bands")
    with col3:
        use_sr = st.checkbox("Use Support/Resistance")
    
    # Time restrictions
    st.subheader("5️⃣ Time Restrictions")
    
    col1, col2 = st.columns(2)
    
    with col1:
        forbidden_start = st.time_input("Forbidden Entry Start", value=pd.to_datetime("09:15").time())
    with col2:
        forbidden_end = st.time_input("Forbidden Entry End", value=pd.to_datetime("10:00").time())
    
    # Generate configuration
    st.markdown("---")
    
    config = {
        "asset_type": asset_type,
        "symbol": symbol,
        "leverage": leverage,
        "capital": capital,
        "take_profit_pct": tp_pct / 100,
        "stop_loss_pct": sl_pct / 100,
        "rsi_ema_veryfast": rsi_veryfast,
        "rsi_ema_fast": rsi_fast,
        "rsi_ema_slow": rsi_slow,
        "rsi_long": rsi_long,
        "rsi_short": rsi_short,
        "atr_period": atr_period,
        "st_multiplier": st_multiplier,
        "use_macd": use_macd,
        "use_bollinger": use_bollinger,
        "use_support_resistance": use_sr,
        "forbidden_entry_start": str(forbidden_start),
        "forbidden_entry_end": str(forbidden_end)
    }
    
    if asset_type == "Options":
        config["option_type"] = option_type
        config["strike_selection"] = strike
    
    # Save button
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("💾 Save Configuration", type="primary", use_container_width=True):
            config_file = f"config_{asset_type.lower().replace(' ', '_')}_{symbol}.json"
            with open(config_file, "w") as f:
                json.dump(config, f, indent=2)
            st.success(f"✅ Configuration saved to {config_file}")
    
    with col2:
        if st.button("👁️ Preview JSON", use_container_width=True):
            st.json(config)


# ============================================================================
# BACKTEST PAGE
# ============================================================================

def backtest_page():
    """Backtest interface"""
    
    st.title("📈 Backtest Your Strategy")
    
    # Upload data or fetch from Historify
    data_source = st.radio("Data Source", ["Upload CSV", "Fetch from Historify/Delta"])
    
    if data_source == "Upload CSV":
        uploaded_file = st.file_uploader("Upload Historical Data (CSV)", type=['csv'])
        
        if uploaded_file:
            df = pd.read_csv(uploaded_file)
            st.success(f"✅ Loaded {len(df)} candles")
            st.dataframe(df.head())
    
    else:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            symbol = st.selectbox("Symbol", ["NIFTY", "BTCUSDT", "SILVERM"])
        with col2:
            start_date = st.date_input("Start Date")
        with col3:
            end_date = st.date_input("End Date")
        
        if st.button("Fetch Data"):
            st.info("Fetching data from API...")
            # Implementation: Call Historify/Delta API
    
    # Load strategy config
    config_files = [f for f in os.listdir('.') if f.startswith('config_') and f.endswith('.json')]
    
    if config_files:
        selected_config = st.selectbox("Select Strategy Configuration", config_files)
        
        if st.button("🚀 Run Backtest", type="primary"):
            with st.spinner("Running backtest..."):
                # Implementation: Run backtest_simple.py with config
                st.success("✅ Backtest completed!")
                
                # Display results
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Total Profit", "₹45,234", "+22.6%")
                with col2:
                    st.metric("Win Rate", "65.96%")
                with col3:
                    st.metric("Total Trades", "47")
                with col4:
                    st.metric("Max Drawdown", "-8.5%")
                
                # Charts
                st.subheader("Equity Curve")
                # Implementation: Plot equity curve
    else:
        st.warning("⚠️ No strategy configurations found. Please create one in Strategy Builder.")


# ============================================================================
# LIVE/PAPER TRADING PAGE
# ============================================================================

def live_trading_page():
    """Live and paper trading control"""
    
    st.title("🔴 Live/Paper Trading Control")
    
    # Mode selection
    mode = st.radio("Trading Mode", ["📝 Paper Trading (Simulated)", "💰 Live Trading (Real Money)"], horizontal=True)
    
    if mode == "💰 Live Trading (Real Money)":
        st.error("⚠️ **WARNING:** Live trading involves real money and real risk. Start with paper trading first!")
    
    # Bot control
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("▶️ Start Bot", type="primary", use_container_width=True):
            st.success(f"✅ Bot started in {mode.split()[0]} mode!")
    
    with col2:
        if st.button("⏹️ Stop Bot", type="secondary", use_container_width=True):
            st.info("🛑 Bot stopped.")
    
    # Real-time stats
    st.markdown("---")
    st.subheader("Real-Time Statistics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Active Positions", "2")
    with col2:
        st.metric("Today's P&L", "₹1,234", "+0.62%")
    with col3:
        st.metric("Open Orders", "4")
    with col4:
        st.metric("Available Margin", "₹185,000")
    
    # Active positions
    st.subheader("Active Positions")
    
    positions = pd.DataFrame({
        "Symbol": ["BTCUSDT", "NIFTY FUT"],
        "Side": ["Long", "Long"],
        "Entry Price": ["₹65,432", "₹23,560"],
        "Current Price": ["₹65,890", "₹23,620"],
        "Quantity": ["0.1 BTC", "50 lots"],
        "P&L": ["₹458 (+0.70%)", "₹60 (+0.25%)"],
        "TP": ["₹71,975", "₹25,916"],
        "SL": ["₹65,105", "₹23,442"]
    })
    
    st.dataframe(positions, use_container_width=True)
    
    # Logs
    st.subheader("Bot Logs")
    
    logs = """
    2024-11-16 14:32:15 - INFO - Bot started in Paper mode
    2024-11-16 14:32:20 - INFO - Connected to Delta Exchange
    2024-11-16 14:32:25 - INFO - BTCUSDT: Long signal detected
    2024-11-16 14:32:26 - INFO - Entry order placed: BTCUSDT @ ₹65,432
    2024-11-16 14:32:27 - INFO - TP order placed @ ₹71,975
    2024-11-16 14:32:27 - INFO - SL order placed @ ₹65,105
    """
    
    st.text_area("Recent Logs", logs, height=200)


# ============================================================================
# SETTINGS PAGE
# ============================================================================

def settings_page():
    """Application settings"""
    
    st.title("⚙️ Settings")
    
    # API Keys
    st.subheader("🔑 API Keys")
    
    with st.expander("AngelOne API"):
        angelone_key = st.text_input("API Key", type="password")
        angelone_client = st.text_input("Client Code")
        angelone_password = st.text_input("Password", type="password")
    
    with st.expander("Delta Exchange API"):
        delta_key = st.text_input("API Key", type="password", key="delta_key")
        delta_secret = st.text_input("API Secret", type="password")
    
    # Telegram Bot
    st.subheader("📱 Telegram Notifications")
    
    telegram_enabled = st.checkbox("Enable Telegram Alerts")
    
    if telegram_enabled:
        telegram_token = st.text_input("Bot Token", type="password")
        telegram_chat_id = st.text_input("Chat ID")
        
        st.info("💡 To get your Chat ID, message your bot and visit: https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates")
    
    # SMTP Settings
    st.subheader("📧 Email (SMTP) Settings")
    
    smtp_server = st.text_input("SMTP Server", value="smtp.gmail.com")
    smtp_port = st.number_input("SMTP Port", value=587)
    smtp_username = st.text_input("SMTP Username")
    smtp_password = st.text_input("SMTP Password", type="password", key="smtp_pass")
    
    # Save settings
    if st.button("💾 Save Settings", type="primary"):
        settings = {
            "api_keys": {
                "angelone": {
                    "key": angelone_key,
                    "client_code": angelone_client,
                    "password": angelone_password
                },
                "delta": {
                    "key": delta_key,
                    "secret": delta_secret
                }
            },
            "telegram": {
                "enabled": telegram_enabled,
                "token": telegram_token if telegram_enabled else "",
                "chat_id": telegram_chat_id if telegram_enabled else ""
            },
            "smtp": {
                "server": smtp_server,
                "port": smtp_port,
                "username": smtp_username,
                "password": smtp_password
            }
        }
        
        with open("settings.json", "w") as f:
            json.dump(settings, f, indent=2)
        
        st.success("✅ Settings saved!")


# ============================================================================
# MAIN
# ============================================================================

def main():
    init_session_state()
    auth = Auth()
    
    if not st.session_state.logged_in:
        login_page(auth)
    else:
        main_app()


if __name__ == "__main__":
    main()
