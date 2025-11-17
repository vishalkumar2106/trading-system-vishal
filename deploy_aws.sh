#!/bin/bash
# ============================================================================
# AWS t2.micro Deployment Script
# One-command deployment for complete trading system
# ============================================================================

set -e  # Exit on error

echo "=================================================="
echo "  Trading System - AWS Deployment"
echo "=================================================="
echo ""

# ============================================================================
# Step 1: System Update
# ============================================================================
echo "📦 Updating system packages..."
sudo apt-get update -y
sudo apt-get upgrade -y

# ============================================================================
# Step 2: Install Python and Dependencies
# ============================================================================
echo "🐍 Installing Python 3.10..."
sudo apt-get install -y python3.10 python3.10-venv python3-pip

# Install system dependencies
echo "📚 Installing system dependencies..."
sudo apt-get install -y \
    git \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    postgresql \
    postgresql-contrib \
    nginx \
    supervisor

# ============================================================================
# Step 3: Clone Repository
# ============================================================================
echo "📥 Cloning repository..."
cd /home/ubuntu

if [ -d "trading-system-vishal" ]; then
    echo "Repository already exists, pulling latest changes..."
    cd trading-system-vishal
    git pull
else
    echo "Cloning repository..."
    git clone https://github.com/vishalkumar2106/trading-system-vishal.git
    cd my-trading-system
fi

# Initialize submodules
echo "📦 Initializing submodules..."
git submodule update --init --recursive

# ============================================================================
# Step 4: Setup Python Virtual Environment
# ============================================================================
echo "🔧 Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# ============================================================================
# Step 5: Install Python Dependencies
# ============================================================================
echo "📚 Installing Python packages..."

# Create requirements.txt if not exists
cat > requirements.txt << 'EOF'
# Core trading frameworks
backtrader==1.9.78.123
freqtrade==2024.1
ccxt==4.2.0

# Data and analysis
pandas==2.0.3
numpy==1.24.3
pandas-ta==0.3.14b0
ta-lib==0.4.28

# API and web
requests==2.31.0
flask==3.0.0
flask-cors==4.0.0
flask-login==0.6.3
flask-sqlalchemy==3.1.1

# UI
streamlit==1.28.0

# Telegram
python-telegram-bot==20.7

# Database
psycopg2-binary==2.9.9

# Utilities
python-dotenv==1.0.0
schedule==1.2.0

# OpenAlgo (install from submodule)
# Will be installed separately

# Historify (install from submodule)
# Will be installed separately
EOF

pip install -r requirements.txt

# Install from submodules
echo "📦 Installing from submodules..."
cd openalgo && pip install -e . && cd ..
cd historify && pip install -e . && cd ..
cd freqtrade && pip install -e . && cd ..

# ============================================================================
# Step 6: Setup Environment Variables
# ============================================================================
echo "🔐 Setting up environment variables..."

cat > .env << 'EOF'
# API Keys (REPLACE WITH YOUR ACTUAL KEYS)
ANGELONE_API_KEY=your_angelone_key
ANGELONE_CLIENT_CODE=your_client_code
ANGELONE_PASSWORD=your_password

DELTA_API_KEY=your_delta_key
DELTA_API_SECRET=your_delta_secret

GROWW_API_KEY=your_groww_key

# Telegram
TELEGRAM_BOT_TOKEN=your_telegram_token
TELEGRAM_CHAT_ID=your_chat_id

# Database
DATABASE_URL=postgresql://tradinguser:password@localhost/tradingdb

# SMTP
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password

# Application
SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
FLASK_ENV=production
STREAMLIT_SERVER_PORT=8501
EOF

echo "⚠️  IMPORTANT: Edit .env file and add your actual API keys!"
echo "   nano .env"

# ============================================================================
# Step 7: Setup PostgreSQL Database
# ============================================================================
echo "🗄️  Setting up PostgreSQL database..."

# Start PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database and user
sudo -u postgres psql << EOF
CREATE DATABASE tradingdb;
CREATE USER tradinguser WITH ENCRYPTED PASSWORD 'password';
GRANT ALL PRIVILEGES ON DATABASE tradingdb TO tradinguser;
\q
EOF

# ============================================================================
# Step 8: Setup Systemd Services
# ============================================================================
echo "🔧 Creating systemd services..."

# Freqtrade service (crypto)
sudo tee /etc/systemd/system/freqtrade.service > /dev/null << EOF
[Unit]
Description=Freqtrade Crypto Trading Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/my-trading-system
Environment="PATH=/home/ubuntu/my-trading-system/venv/bin"
EnvironmentFile=/home/ubuntu/my-trading-system/.env
ExecStart=/home/ubuntu/my-trading-system/venv/bin/freqtrade trade --config config/config_crypto.json --strategy MyCryptoStrategy
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# OpenAlgo + Backtrader service (stocks)
sudo tee /etc/systemd/system/backtrader-stocks.service > /dev/null << EOF
[Unit]
Description=Backtrader Stocks Trading Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/my-trading-system
Environment="PATH=/home/ubuntu/my-trading-system/venv/bin"
EnvironmentFile=/home/ubuntu/my-trading-system/.env
ExecStart=/home/ubuntu/my-trading-system/venv/bin/python strategies/my_strategy.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Streamlit UI service
sudo tee /etc/systemd/system/streamlit-ui.service > /dev/null << EOF
[Unit]
Description=Streamlit Trading UI
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/trading-system-vishal
Environment="PATH=/home/ubuntu/trading-system-vishal/venv/bin"
EnvironmentFile=/home/ubuntu/trading-system-vishal/.env
ExecStart=/home/ubuntu/trading-system-vishal/venv/bin/streamlit run ui/app.py --server.port 8501 --server.address 0.0.0.0
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Telegram bot service
sudo tee /etc/systemd/system/telegram-bot.service > /dev/null << EOF
[Unit]
Description=Telegram Trading Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/trading-system-vishal
Environment="PATH=/home/ubuntu/trading-system-vishal/venv/bin"
EnvironmentFile=/home/ubuntu/trading-system-vishal/.env
ExecStart=/home/ubuntu/trading-system-vishal/venv/bin/python telegram_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# ============================================================================
# Step 9: Setup Nginx Reverse Proxy
# ============================================================================
echo "🌐 Configuring Nginx..."

sudo tee /etc/nginx/sites-available/trading-system > /dev/null << 'EOF'
server {
    listen 80;
    server_name _;

    # Streamlit UI
    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Freqtrade API
    location /api/crypto/ {
        proxy_pass http://localhost:8080/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # OpenAlgo API
    location /api/stocks/ {
        proxy_pass http://localhost:5000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

# Enable site
sudo ln -sf /etc/nginx/sites-available/trading-system /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test and restart Nginx
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx

# ============================================================================
# Step 10: Setup Firewall
# ============================================================================
echo "🔒 Configuring firewall..."

sudo ufw allow 22    # SSH
sudo ufw allow 80    # HTTP
sudo ufw allow 443   # HTTPS (for future SSL)
sudo ufw --force enable

# ============================================================================
# Step 11: Enable and Start Services
# ============================================================================
echo "🚀 Starting services..."

# Reload systemd
sudo systemctl daemon-reload

# Enable services (start on boot)
sudo systemctl enable streamlit-ui
sudo systemctl enable telegram-bot

# Start services (but NOT trading bots yet - manual start after config)
sudo systemctl start streamlit-ui
sudo systemctl start telegram-bot

echo ""
echo "=================================================="
echo "  ✅ Deployment Complete!"
echo "=================================================="
echo ""
echo "📊 Access your UI at: http://$(curl -s ifconfig.me)"
echo ""
echo "⚠️  NEXT STEPS:"
echo ""
echo "1. Edit API keys:"
echo "   nano /home/ubuntu/trading-system-vishal/.env"
echo ""
echo "2. Start trading bots (AFTER configuring .env):"
echo "   Paper trading:"
echo "   sudo systemctl start freqtrade"
echo "   sudo systemctl start backtrader-stocks"
echo ""
echo "   Live trading:"
echo "   Edit config files to set dry_run=false first!"
echo ""
echo "3. Check service status:"
echo "   sudo systemctl status streamlit-ui"
echo "   sudo systemctl status freqtrade"
echo "   sudo systemctl status backtrader-stocks"
echo "   sudo systemctl status telegram-bot"
echo ""
echo "4. View logs:"
echo "   sudo journalctl -u streamlit-ui -f"
echo "   sudo journalctl -u freqtrade -f"
echo ""
echo "5. Update code:"
echo "   cd /home/ubuntu/trading-system-vishal"
echo "   git pull"
echo "   sudo systemctl restart <service-name>"
echo ""
echo "=================================================="
echo "  Happy Trading! 🚀"
echo "=================================================="
