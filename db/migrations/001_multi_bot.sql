-- =============================================================================
-- Migration 001: Multi-Bot Support
-- =============================================================================
-- Phase 3 멀티봇 지원을 위한 스키마 확장
-- 실행: psql -d trading -f db/migrations/001_multi_bot.sql
-- =============================================================================

BEGIN;

-- =============================================================================
-- 1. bot_configs 테이블 확장 (기존 테이블에 컬럼 추가)
-- =============================================================================

-- risk_level 컬럼 추가 (위험도 분류)
ALTER TABLE bot_configs
ADD COLUMN IF NOT EXISTS risk_level VARCHAR(20) DEFAULT 'medium'
CHECK (risk_level IN ('low', 'medium', 'high'));

-- signal parameters 추가 (신호 파라미터)
ALTER TABLE bot_configs
ADD COLUMN IF NOT EXISTS rsi_oversold DECIMAL(5, 2) DEFAULT 35.0;

ALTER TABLE bot_configs
ADD COLUMN IF NOT EXISTS rsi_overbought DECIMAL(5, 2) DEFAULT 65.0;

ALTER TABLE bot_configs
ADD COLUMN IF NOT EXISTS volume_threshold DECIMAL(5, 2) DEFAULT 1.2;

-- API 키 참조 (AWS Secrets Manager 또는 환경변수 참조용)
ALTER TABLE bot_configs
ADD COLUMN IF NOT EXISTS binance_api_key_ref VARCHAR(100);

ALTER TABLE bot_configs
ADD COLUMN IF NOT EXISTS binance_secret_key_ref VARCHAR(100);

-- 봇 설명 필드
ALTER TABLE bot_configs
ADD COLUMN IF NOT EXISTS description TEXT;

-- user_id를 nullable로 변경 (단일 봇 모드에서는 불필요)
ALTER TABLE bot_configs
ALTER COLUMN user_id DROP NOT NULL;

-- unique constraint 수정 (user_id 없이도 bot_name으로 unique)
ALTER TABLE bot_configs DROP CONSTRAINT IF EXISTS bot_configs_user_id_bot_name_key;

-- bot_name만으로 unique constraint 추가 (없으면)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'bot_configs_bot_name_key'
    ) THEN
        ALTER TABLE bot_configs ADD CONSTRAINT bot_configs_bot_name_key UNIQUE (bot_name);
    END IF;
END $$;

-- =============================================================================
-- 2. trades 테이블에 bot_id 추가
-- =============================================================================

ALTER TABLE trades
ADD COLUMN IF NOT EXISTS bot_id UUID REFERENCES bot_configs(id) ON DELETE SET NULL;

-- 인덱스 추가
CREATE INDEX IF NOT EXISTS idx_trades_bot_id ON trades(bot_id);

-- =============================================================================
-- 3. bot_status 테이블에 bot_id 추가
-- =============================================================================

ALTER TABLE bot_status
ADD COLUMN IF NOT EXISTS bot_id UUID REFERENCES bot_configs(id) ON DELETE SET NULL;

-- 인덱스 추가
CREATE INDEX IF NOT EXISTS idx_bot_status_bot_id ON bot_status(bot_id);

-- =============================================================================
-- 4. ai_signals 테이블에 bot_id 추가
-- =============================================================================

ALTER TABLE ai_signals
ADD COLUMN IF NOT EXISTS bot_id UUID REFERENCES bot_configs(id) ON DELETE SET NULL;

-- 인덱스 추가
CREATE INDEX IF NOT EXISTS idx_ai_signals_bot_id ON ai_signals(bot_id);

-- =============================================================================
-- 5. 위험도별 기본 설정 뷰 생성
-- =============================================================================

CREATE OR REPLACE VIEW bot_configs_with_defaults AS
SELECT
    id,
    bot_name,
    symbol,
    risk_level,
    -- risk_level에 따른 기본값 표시
    CASE
        WHEN risk_level = 'low' THEN COALESCE(leverage, 10)
        WHEN risk_level = 'high' THEN COALESCE(leverage, 20)
        ELSE COALESCE(leverage, 15)
    END AS effective_leverage,
    CASE
        WHEN risk_level = 'low' THEN COALESCE(position_size_pct, 0.03)
        WHEN risk_level = 'high' THEN COALESCE(position_size_pct, 0.08)
        ELSE COALESCE(position_size_pct, 0.05)
    END AS effective_position_size_pct,
    CASE
        WHEN risk_level = 'low' THEN COALESCE(take_profit_pct, 0.003)
        WHEN risk_level = 'high' THEN COALESCE(take_profit_pct, 0.006)
        ELSE COALESCE(take_profit_pct, 0.004)
    END AS effective_take_profit_pct,
    CASE
        WHEN risk_level = 'low' THEN COALESCE(stop_loss_pct, 0.003)
        WHEN risk_level = 'high' THEN COALESCE(stop_loss_pct, 0.006)
        ELSE COALESCE(stop_loss_pct, 0.004)
    END AS effective_stop_loss_pct,
    COALESCE(rsi_oversold, 35.0) AS rsi_oversold,
    COALESCE(rsi_overbought, 65.0) AS rsi_overbought,
    COALESCE(volume_threshold, 1.2) AS volume_threshold,
    is_active,
    is_testnet,
    created_at,
    updated_at
FROM bot_configs;

-- =============================================================================
-- 6. 봇별 거래 통계 뷰 확장
-- =============================================================================

CREATE OR REPLACE VIEW bot_trading_stats AS
SELECT
    bc.id AS bot_id,
    bc.bot_name,
    bc.symbol,
    bc.risk_level,
    COUNT(t.id) AS total_trades,
    SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END) AS winning_trades,
    SUM(CASE WHEN t.pnl < 0 THEN 1 ELSE 0 END) AS losing_trades,
    ROUND(
        CASE WHEN COUNT(t.id) > 0
        THEN SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END)::DECIMAL / COUNT(t.id) * 100
        ELSE 0 END, 2
    ) AS win_rate,
    COALESCE(ROUND(AVG(t.pnl)::DECIMAL, 2), 0) AS avg_pnl,
    COALESCE(ROUND(SUM(t.pnl)::DECIMAL, 2), 0) AS total_pnl,
    COALESCE(ROUND(AVG(t.duration_minutes)::DECIMAL, 0), 0) AS avg_duration_minutes,
    MAX(t.entry_time) AS last_trade_time
FROM bot_configs bc
LEFT JOIN trades t ON t.bot_id = bc.id AND t.status = 'CLOSED'
GROUP BY bc.id, bc.bot_name, bc.symbol, bc.risk_level;

-- =============================================================================
-- 7. 예시 봇 설정 삽입 (개발/테스트용)
-- =============================================================================

-- BTC 봇 (보수적)
INSERT INTO bot_configs (
    bot_name, symbol, leverage, position_size_pct,
    take_profit_pct, stop_loss_pct, time_cut_minutes,
    risk_level, rsi_oversold, rsi_overbought, volume_threshold,
    is_testnet, is_active, description
) VALUES (
    'btc-conservative', 'BTCUSDT', 10, 0.03,
    0.003, 0.003, 120,
    'low', 30.0, 70.0, 1.5,
    TRUE, FALSE, 'BTC 보수적 전략 - 낮은 레버리지, 엄격한 진입 조건'
) ON CONFLICT (bot_name) DO UPDATE SET
    symbol = EXCLUDED.symbol,
    leverage = EXCLUDED.leverage,
    risk_level = EXCLUDED.risk_level,
    description = EXCLUDED.description,
    updated_at = NOW();

-- ETH 봇 (중간)
INSERT INTO bot_configs (
    bot_name, symbol, leverage, position_size_pct,
    take_profit_pct, stop_loss_pct, time_cut_minutes,
    risk_level, rsi_oversold, rsi_overbought, volume_threshold,
    is_testnet, is_active, description
) VALUES (
    'eth-balanced', 'ETHUSDT', 15, 0.05,
    0.004, 0.004, 120,
    'medium', 35.0, 65.0, 1.2,
    TRUE, FALSE, 'ETH 균형 전략 - 중간 레버리지, 표준 진입 조건'
) ON CONFLICT (bot_name) DO UPDATE SET
    symbol = EXCLUDED.symbol,
    leverage = EXCLUDED.leverage,
    risk_level = EXCLUDED.risk_level,
    description = EXCLUDED.description,
    updated_at = NOW();

-- SOL 봇 (공격적)
INSERT INTO bot_configs (
    bot_name, symbol, leverage, position_size_pct,
    take_profit_pct, stop_loss_pct, time_cut_minutes,
    risk_level, rsi_oversold, rsi_overbought, volume_threshold,
    is_testnet, is_active, description
) VALUES (
    'sol-aggressive', 'SOLUSDT', 20, 0.08,
    0.006, 0.006, 90,
    'high', 40.0, 60.0, 1.0,
    TRUE, FALSE, 'SOL 공격적 전략 - 높은 레버리지, 완화된 진입 조건'
) ON CONFLICT (bot_name) DO UPDATE SET
    symbol = EXCLUDED.symbol,
    leverage = EXCLUDED.leverage,
    risk_level = EXCLUDED.risk_level,
    description = EXCLUDED.description,
    updated_at = NOW();

-- =============================================================================
-- Migration Complete
-- =============================================================================

COMMIT;

SELECT 'Migration 001_multi_bot completed successfully!' AS status;
