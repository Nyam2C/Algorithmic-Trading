-- =============================================================================
-- Database Initialization Script
-- =============================================================================
-- Initial schema for High-Win Survival System
-- Supports both trading bot (Sprint 1) and future backend (Sprint 2+)
-- =============================================================================

-- Create database if not exists (run outside this script)
-- CREATE DATABASE trading;

-- Connect to database
\c trading;

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For text search

-- =============================================================================
-- Core Trading Tables
-- =============================================================================

-- Trades table (주문 기록)
CREATE TABLE IF NOT EXISTS trades (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL CHECK (side IN ('LONG', 'SHORT')),
    entry_price DECIMAL(20, 8) NOT NULL,
    exit_price DECIMAL(20, 8),
    quantity DECIMAL(20, 8) NOT NULL,
    leverage INT NOT NULL,

    -- P&L
    pnl DECIMAL(20, 8),
    pnl_pct DECIMAL(10, 4),
    realized_pnl DECIMAL(20, 8),

    -- Timing
    entry_time TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    exit_time TIMESTAMP WITH TIME ZONE,
    duration_minutes INT,

    -- Exit reason
    exit_reason VARCHAR(20) CHECK (exit_reason IN ('TP', 'SL', 'TIME_CUT', 'MANUAL', 'AI_SIGNAL')),

    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSED', 'CANCELLED')),

    -- Exchange info
    binance_order_id BIGINT,
    binance_client_order_id VARCHAR(50),

    -- Metadata
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- AI Signals table (AI 신호 기록)
CREATE TABLE IF NOT EXISTS ai_signals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL,
    signal VARCHAR(10) NOT NULL CHECK (signal IN ('LONG', 'SHORT', 'WAIT')),
    confidence DECIMAL(5, 2),  -- 0-100

    -- Market data at signal time
    price DECIMAL(20, 8) NOT NULL,
    rsi DECIMAL(10, 2),
    ma_7 DECIMAL(20, 8),
    ma_25 DECIMAL(20, 8),
    ma_99 DECIMAL(20, 8),
    atr DECIMAL(20, 8),
    volume_ratio DECIMAL(10, 4),

    -- AI response
    raw_response TEXT,

    -- Action taken
    action_taken BOOLEAN DEFAULT FALSE,
    trade_id UUID REFERENCES trades(id),

    -- Timing
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- Model info
    model_name VARCHAR(50),
    model_version VARCHAR(20)
);

-- Market Data table (시장 데이터 스냅샷)
CREATE TABLE IF NOT EXISTS market_data (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL,

    -- OHLCV
    open DECIMAL(20, 8) NOT NULL,
    high DECIMAL(20, 8) NOT NULL,
    low DECIMAL(20, 8) NOT NULL,
    close DECIMAL(20, 8) NOT NULL,
    volume DECIMAL(30, 8) NOT NULL,

    -- Indicators
    rsi DECIMAL(10, 2),
    ma_7 DECIMAL(20, 8),
    ma_25 DECIMAL(20, 8),
    ma_99 DECIMAL(20, 8),
    atr DECIMAL(20, 8),

    -- Timing
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    timeframe VARCHAR(10) NOT NULL DEFAULT '5m',

    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Bot Status table (봇 상태 추적)
CREATE TABLE IF NOT EXISTS bot_status (
    id SERIAL PRIMARY KEY,
    bot_name VARCHAR(50) NOT NULL UNIQUE,

    -- Status
    is_running BOOLEAN DEFAULT FALSE,
    current_position VARCHAR(10) CHECK (current_position IN ('LONG', 'SHORT', 'NONE')),
    active_trade_id UUID REFERENCES trades(id),

    -- Stats
    total_trades INT DEFAULT 0,
    winning_trades INT DEFAULT 0,
    losing_trades INT DEFAULT 0,
    total_pnl DECIMAL(20, 8) DEFAULT 0,

    -- Health
    last_heartbeat TIMESTAMP WITH TIME ZONE,
    last_error TEXT,
    error_count INT DEFAULT 0,

    -- Timing
    started_at TIMESTAMP WITH TIME ZONE,
    stopped_at TIMESTAMP WITH TIME ZONE,
    uptime_seconds BIGINT DEFAULT 0,

    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- Future Backend Tables (Sprint 2+)
-- =============================================================================

-- Users table (for future web interface)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,

    -- Profile
    full_name VARCHAR(100),
    role VARCHAR(20) DEFAULT 'user' CHECK (role IN ('admin', 'user', 'viewer')),

    -- API access
    api_key VARCHAR(100) UNIQUE,
    api_secret_hash VARCHAR(255),

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,

    -- Timing
    last_login TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Bot Configurations table (for multiple bot instances)
CREATE TABLE IF NOT EXISTS bot_configs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    bot_name VARCHAR(50) NOT NULL,

    -- Trading config
    symbol VARCHAR(20) NOT NULL,
    leverage INT NOT NULL,
    position_size_pct DECIMAL(5, 4) NOT NULL,
    take_profit_pct DECIMAL(5, 4) NOT NULL,
    stop_loss_pct DECIMAL(5, 4) NOT NULL,
    time_cut_minutes INT,

    -- Exchange
    exchange VARCHAR(20) NOT NULL DEFAULT 'binance',
    is_testnet BOOLEAN DEFAULT TRUE,

    -- Status
    is_active BOOLEAN DEFAULT FALSE,

    -- Timing
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    UNIQUE (user_id, bot_name)
);

-- Notifications table (for alerts and webhooks)
CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,

    -- Content
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    notification_type VARCHAR(20) NOT NULL CHECK (notification_type IN ('TRADE', 'ERROR', 'INFO', 'WARNING')),

    -- Status
    is_read BOOLEAN DEFAULT FALSE,
    is_sent BOOLEAN DEFAULT FALSE,

    -- Channels
    send_discord BOOLEAN DEFAULT FALSE,
    send_email BOOLEAN DEFAULT FALSE,
    send_telegram BOOLEAN DEFAULT FALSE,

    -- Related entities
    trade_id UUID REFERENCES trades(id),
    bot_name VARCHAR(50),

    -- Timing
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    sent_at TIMESTAMP WITH TIME ZONE
);

-- =============================================================================
-- Indexes
-- =============================================================================

-- Trades indexes
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
CREATE INDEX IF NOT EXISTS idx_trades_entry_time ON trades(entry_time DESC);
CREATE INDEX IF NOT EXISTS idx_trades_side ON trades(side);

-- AI Signals indexes
CREATE INDEX IF NOT EXISTS idx_signals_symbol ON ai_signals(symbol);
CREATE INDEX IF NOT EXISTS idx_signals_signal ON ai_signals(signal);
CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON ai_signals(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_signals_trade_id ON ai_signals(trade_id);

-- Market Data indexes
CREATE INDEX IF NOT EXISTS idx_market_data_symbol_timestamp ON market_data(symbol, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_market_data_timeframe ON market_data(timeframe);

-- Bot Status indexes
CREATE INDEX IF NOT EXISTS idx_bot_status_name ON bot_status(bot_name);

-- Users indexes (for future)
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_api_key ON users(api_key);

-- Bot Configs indexes (for future)
CREATE INDEX IF NOT EXISTS idx_bot_configs_user_id ON bot_configs(user_id);

-- Notifications indexes (for future)
CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_is_read ON notifications(is_read);

-- =============================================================================
-- Triggers
-- =============================================================================

-- Update updated_at timestamp automatically
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_trades_updated_at BEFORE UPDATE ON trades
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_bot_status_updated_at BEFORE UPDATE ON bot_status
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_bot_configs_updated_at BEFORE UPDATE ON bot_configs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- Views
-- =============================================================================

-- Trading statistics view
CREATE OR REPLACE VIEW trading_stats AS
SELECT
    symbol,
    COUNT(*) AS total_trades,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) AS winning_trades,
    SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) AS losing_trades,
    ROUND(AVG(pnl), 2) AS avg_pnl,
    ROUND(SUM(pnl), 2) AS total_pnl,
    ROUND(AVG(duration_minutes), 2) AS avg_duration_minutes,
    MAX(entry_time) AS last_trade_time
FROM trades
WHERE status = 'CLOSED'
GROUP BY symbol;

-- Recent signals view
CREATE OR REPLACE VIEW recent_signals AS
SELECT
    s.id,
    s.symbol,
    s.signal,
    s.confidence,
    s.price,
    s.rsi,
    s.timestamp,
    s.action_taken,
    t.id AS trade_id,
    t.pnl
FROM ai_signals s
LEFT JOIN trades t ON s.trade_id = t.id
ORDER BY s.timestamp DESC
LIMIT 100;

-- =============================================================================
-- Initial Data
-- =============================================================================

-- Insert default bot status
INSERT INTO bot_status (bot_name, is_running, current_position)
VALUES ('high-win-bot', FALSE, 'NONE')
ON CONFLICT (bot_name) DO NOTHING;

-- =============================================================================
-- Grants (adjust as needed)
-- =============================================================================

-- Grant permissions to trading user (if using separate user)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO trading_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO trading_user;

-- =============================================================================
-- Success Message
-- =============================================================================

SELECT 'Database initialized successfully!' AS status;
SELECT 'Tables created: ' || COUNT(*) AS tables_count FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
