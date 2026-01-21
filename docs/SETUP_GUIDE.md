# Setup Guide

Complete environment setup guide for High-Win Survival System.

---

## Quick Start

### Option 1: One-Click Setup (Recommended)

```bash
# Bash script (Linux/Mac/WSL)
./scripts/setup.sh
```

This will:
- Check system requirements
- Install Python dependencies
- Create `.env` configuration file
- Setup Docker environment
- Initialize database
- Run tests

### Option 2: Manual Setup

Follow the detailed steps below for manual configuration.

---

## Prerequisites

### Required

- **Python 3.10+**
- **Docker & Docker Compose** (for containerized deployment)
- **Git** (for version control)

### Optional

- PostgreSQL 15+ (if running locally without Docker)

---

## Installation Modes

The setup script supports multiple modes:

### 1. Full Setup (Development + Docker)

```bash
# Setup script
./scripts/setup.sh
```

**Includes:**
- Python dependencies installation
- `.env` file creation
- Docker environment setup
- Log directories creation

### 2. Start Services

```bash
# Start all services
./scripts/start.sh

# Check status
./scripts/start.sh --status

# View logs
./scripts/start.sh --logs

# Stop services
./scripts/start.sh --stop
```

### 3. Run Tests

```bash
# Quick test
./scripts/test.sh

# With coverage
./scripts/test.sh --coverage

# CI mode (lint + type + coverage)
./scripts/test.sh --ci
```

---

## Configuration

### Environment Variables

The setup script will prompt for the following configurations:

#### 1. Bot Configuration

```bash
BOT_NAME=high-win-bot          # Bot instance name
BINANCE_TESTNET=true           # Use Binance Testnet
```

#### 2. Binance API Keys

Get your API keys from [Binance Testnet](https://testnet.binancefuture.com):

```bash
BINANCE_API_KEY=your_binance_api_key
BINANCE_SECRET_KEY=your_binance_secret_key
```

**Steps:**
1. Visit https://testnet.binancefuture.com
2. Sign in with GitHub/Google
3. Navigate to API Management
4. Create new API key
5. Save API Key and Secret Key

#### 3. Gemini AI API Key

Get your API key from [Google AI Studio](https://aistudio.google.com/apikey):

```bash
GEMINI_API_KEY=your_gemini_api_key
```

**Steps:**
1. Visit https://aistudio.google.com/apikey
2. Sign in with Google account
3. Create API key
4. Copy and save the key

#### 4. Discord Webhook

Create a webhook in your Discord server:

```bash
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_URL
```

**Steps:**
1. Open Discord Server Settings
2. Go to Integrations → Webhooks
3. Click "New Webhook"
4. Copy Webhook URL

#### 5. Trading Parameters

```bash
SYMBOL=BTCUSDT                 # Trading pair
LEVERAGE=15                    # Leverage (1-125)
POSITION_SIZE_PCT=0.05         # Position size (5% of balance)
TAKE_PROFIT_PCT=0.004          # Take profit (0.4%)
STOP_LOSS_PCT=0.004            # Stop loss (0.4%)
TIME_CUT_MINUTES=120           # Max position duration (2 hours)
```

#### 6. Database (for future backend)

```bash
DATABASE_URL=postgresql://postgres:postgres@db:5432/trading
```

---

## Database Setup

### Initialize Database

After running the main setup, the database initializes automatically:

```bash
# Start services (includes DB auto-initialization)
./scripts/start.sh

# Or manually with Docker
docker compose -f deploy/docker-compose.yml up -d postgres

# Manual psql initialization
psql -U postgres -f db/init.sql
```

### Database Schema

The database includes tables for:

**Current (Sprint 1):**
- `trades` - Trading history
- `ai_signals` - AI signal history
- `market_data` - Market snapshots
- `bot_status` - Bot state tracking

**Future (Sprint 2+):**
- `users` - User management
- `bot_configs` - Multi-bot configurations
- `notifications` - Alert system

### Connect to Database

```bash
# Docker
docker exec -it trading-db psql -U trading -d trading

# Local
psql -h localhost -p 5432 -U trading -d trading
```

---

## Verification

### 1. Check Installation

```bash
# Python dependencies
python -c "import binance, pandas, ta; print('OK')"

# Docker
docker --version
docker compose --version
```

### 2. Validate Configuration

```bash
# Check .env file
cat .env

# Test configuration loading
python -c "from src.config import get_config; print(get_config())"
```

### 3. Run Tests

```bash
# Full test suite
./scripts/run-tests.sh

# Or with pytest directly
pytest -v

# With coverage
pytest --cov=src --cov-report=html
```

**Expected output:**
```
===================== 64 passed in X.XXs =====================
```

### 4. Test Docker Build

```bash
# Build image
docker compose build

# Check images
docker images | grep trading-bot
```

---

## Running the Bot

### Docker Deployment (Recommended)

```bash
# Start services
./scripts/start.sh

# View logs
./scripts/start.sh --logs

# Check status
./scripts/start.sh --status

# Stop
./scripts/start.sh --stop
```

### Local Execution

```bash
# Run directly with Python
python -m src.main

# Or using Docker Compose
docker compose -f deploy/docker-compose.yml up -d
docker compose -f deploy/docker-compose.yml logs -f trading-bot
```

---

## Directory Structure

After setup, your project will have:

```
Algorithmic-Trading/
├── .env                        # Your configuration (gitignored)
├── .env.example                # Configuration template
├── setup.py                    # Setup script (Python)
├── setup.sh                    # Setup script (Bash)
├── run.py                      # Local execution script
├── run.sh                      # Local execution script (Bash)
├── start-docker.py             # Docker deployment script
├── start-docker.sh             # Docker deployment script (Bash)
├── run-tests.sh                # Test runner
├── pytest.ini                  # Pytest configuration
├── .coveragerc                 # Coverage configuration
│
├── src/                        # Source code
│   ├── config.py               # Configuration management
│   ├── main.py                 # Main trading loop
│   ├── exchange/
│   │   └── binance.py          # Binance API client
│   ├── data/
│   │   └── indicators.py       # Technical indicators
│   ├── ai/
│   │   ├── gemini.py           # Gemini AI client
│   │   ├── signals.py          # Signal parsing
│   │   └── prompts/            # AI prompts
│   └── trading/
│       └── executor.py         # Order execution
│
├── tests/                      # Test suite
│   ├── conftest.py             # Pytest fixtures
│   ├── test_config.py          # Config tests
│   ├── test_indicators.py      # Indicator tests
│   ├── test_signals.py         # Signal tests
│   └── test_executor.py        # Executor tests
│
├── scripts/                    # Utility scripts
│   ├── init-db.sql             # Database schema
│   └── setup-db.sh             # Database setup
│
├── logs/                       # Log files (auto-created)
├── data/                       # Data storage (auto-created)
└── htmlcov/                    # Coverage reports (auto-created)
```

---

## Troubleshooting

### Python Version Error

```
Error: Python 3.10+ required
```

**Solution:**
```bash
# Check version
python3 --version

# Install Python 3.10+
# Ubuntu/Debian
sudo apt update
sudo apt install python3.10

# macOS
brew install python@3.10
```

### Docker Not Running

```
Error: Docker is not running
```

**Solution:**
```bash
# Start Docker daemon
sudo systemctl start docker

# Or on macOS
open -a Docker
```

### Module Not Found

```
ModuleNotFoundError: No module named 'binance'
```

**Solution:**
```bash
# Reinstall dependencies
pip install -r requirements.txt

# Or use virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### Database Connection Error

```
Error: Database connection failed
```

**Solution:**
```bash
# Check if database is running
docker compose ps

# Start database
docker compose up -d db

# Check logs
docker compose logs db

# Verify DATABASE_URL in .env
cat .env | grep DATABASE_URL
```

### API Key Invalid

```
Error: Invalid API key
```

**Solution:**
1. Verify API keys in `.env` file
2. Ensure no extra spaces or quotes
3. Regenerate keys from:
   - Binance: https://testnet.binancefuture.com
   - Gemini: https://aistudio.google.com/apikey

### Permission Denied

```
Permission denied: ./scripts/setup.sh
```

**Solution:**
```bash
# Make scripts executable
chmod +x setup.sh
chmod +x run.sh
chmod +x start-docker.sh
chmod +x run-tests.sh
chmod +x ./scripts/*.sh
```

---

## Advanced Configuration

### Custom Python Version

```bash
# Use specific Python version with virtual environment
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
./scripts/setup.sh
```

### Skip Tests During Setup

```bash
# Setup then run tests separately
./scripts/setup.sh
./scripts/test.sh
```

### Automated Setup (CI/CD)

```bash
# Non-interactive setup with environment variables
export BINANCE_API_KEY="your_key"
export BINANCE_SECRET_KEY="your_secret"
export GEMINI_API_KEY="your_key"
export DISCORD_WEBHOOK_URL="your_webhook"

# Run setup
./scripts/setup.sh
./scripts/test.sh --ci
```

---

## Next Steps

After successful setup:

1. **Review Configuration**
   ```bash
   cat .env
   ```

2. **Run Tests**
   ```bash
   ./scripts/test.sh
   ```

3. **Start Bot**
   ```bash
   ./scripts/start.sh
   ```

4. **Monitor**
   ```bash
   # Logs
   ./scripts/start.sh --logs
   tail -f logs/bot.log

   # Grafana Dashboard
   # http://localhost:3000 (admin/admin123)
   ```

5. **Review Documentation**
   - [README.md](README.md) - Project overview
   - [TEST_GUIDE.md](TEST_GUIDE.md) - Testing guide
   - [.claude/](.claude/) - Development plans

---

## Future: Backend Setup (Sprint 2+)

When implementing the FastAPI backend:

### 1. Install Backend Dependencies

```bash
pip install fastapi uvicorn[standard] sqlalchemy alembic
```

### 2. Initialize Alembic

```bash
alembic init alembic
```

### 3. Update Database Schema

```bash
# Generate migration
alembic revision --autogenerate -m "Add backend tables"

# Apply migration
alembic upgrade head
```

### 4. Run Backend

```bash
# Development
uvicorn src.backend.main:app --reload

# Production
uvicorn src.backend.main:app --host 0.0.0.0 --port 8000
```

The database schema ([db/init.sql](db/init.sql)) already includes tables for:
- User management
- Multi-bot configurations
- Notifications
- API access

---

## Support

If you encounter issues:

1. Check [TEST_GUIDE.md](TEST_GUIDE.md) for testing help
2. Review logs in `logs/` directory
3. Check Docker logs: `docker compose logs`
4. Verify all API keys are correct in `.env`

---

**Setup Status:**
- Setup scripts: ✅
- Database schema: ✅
- Documentation: ✅
- Test suite: ✅ (64+ tests)
- Docker environment: ✅

---

**마지막 업데이트:** 2026-01-21
**상태:** Phase 2 Testnet 검증 진행 중
