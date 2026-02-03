-- Migration: 004_signal_tracking.sql
-- Description: 신호 추적 시스템 테이블
-- Created: 2026-02-04

-- ============================================================================
-- signal_history: 모든 AI/규칙 기반 신호 기록
-- ============================================================================

CREATE TABLE IF NOT EXISTS signal_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    bot_id UUID REFERENCES bots(id) ON DELETE CASCADE,
    signal VARCHAR(10) NOT NULL CHECK (signal IN ('LONG', 'SHORT', 'WAIT')),
    source VARCHAR(50) NOT NULL,  -- rule_based, gemini, memory_gemini, ensemble
    market_conditions JSONB DEFAULT '{}',
    trade_result VARCHAR(10) CHECK (trade_result IN ('win', 'loss')),
    pnl DECIMAL(20, 8),
    reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 인덱스: 봇별 조회 최적화
CREATE INDEX IF NOT EXISTS idx_signal_history_bot_id
ON signal_history(bot_id);

-- 인덱스: 시간순 조회 최적화
CREATE INDEX IF NOT EXISTS idx_signal_history_timestamp
ON signal_history(timestamp DESC);

-- 인덱스: 소스별 조회 최적화
CREATE INDEX IF NOT EXISTS idx_signal_history_source
ON signal_history(source);

-- 인덱스: 결과별 조회 최적화 (승률 계산용)
CREATE INDEX IF NOT EXISTS idx_signal_history_result
ON signal_history(trade_result)
WHERE trade_result IS NOT NULL;

-- 복합 인덱스: 봇 + 시간 범위 조회
CREATE INDEX IF NOT EXISTS idx_signal_history_bot_timestamp
ON signal_history(bot_id, timestamp DESC);

-- 복합 인덱스: 소스 + 결과 (소스별 승률 계산용)
CREATE INDEX IF NOT EXISTS idx_signal_history_source_result
ON signal_history(source, trade_result);

-- ============================================================================
-- 통계 함수: 소스별 신호 통계
-- ============================================================================

CREATE OR REPLACE FUNCTION get_signal_stats_by_source(
    p_bot_id UUID DEFAULT NULL,
    p_days INTEGER DEFAULT 7
)
RETURNS TABLE (
    source VARCHAR(50),
    total_signals BIGINT,
    traded_signals BIGINT,
    wins BIGINT,
    losses BIGINT,
    win_rate DECIMAL(5, 2),
    total_pnl DECIMAL(20, 8),
    avg_pnl DECIMAL(20, 8)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        sh.source,
        COUNT(*)::BIGINT as total_signals,
        COUNT(*) FILTER (WHERE sh.trade_result IS NOT NULL)::BIGINT as traded_signals,
        COUNT(*) FILTER (WHERE sh.trade_result = 'win')::BIGINT as wins,
        COUNT(*) FILTER (WHERE sh.trade_result = 'loss')::BIGINT as losses,
        CASE
            WHEN COUNT(*) FILTER (WHERE sh.trade_result IS NOT NULL) > 0
            THEN ROUND(
                (COUNT(*) FILTER (WHERE sh.trade_result = 'win')::DECIMAL /
                 COUNT(*) FILTER (WHERE sh.trade_result IS NOT NULL)) * 100,
                2
            )
            ELSE 0
        END as win_rate,
        COALESCE(SUM(sh.pnl), 0) as total_pnl,
        CASE
            WHEN COUNT(*) FILTER (WHERE sh.trade_result IS NOT NULL) > 0
            THEN ROUND(
                COALESCE(SUM(sh.pnl), 0) /
                COUNT(*) FILTER (WHERE sh.trade_result IS NOT NULL),
                8
            )
            ELSE 0
        END as avg_pnl
    FROM signal_history sh
    WHERE sh.timestamp >= NOW() - (p_days || ' days')::INTERVAL
      AND (p_bot_id IS NULL OR sh.bot_id = p_bot_id)
    GROUP BY sh.source
    ORDER BY win_rate DESC, total_signals DESC;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 통계 함수: 신호 성과 요약
-- ============================================================================

CREATE OR REPLACE FUNCTION get_signal_performance_summary(
    p_bot_id UUID DEFAULT NULL,
    p_source VARCHAR(50) DEFAULT NULL,
    p_days INTEGER DEFAULT 7
)
RETURNS TABLE (
    total_signals BIGINT,
    traded_signals BIGINT,
    wins BIGINT,
    losses BIGINT,
    win_rate DECIMAL(5, 2),
    total_pnl DECIMAL(20, 8),
    avg_pnl DECIMAL(20, 8),
    best_pnl DECIMAL(20, 8),
    worst_pnl DECIMAL(20, 8),
    long_signals BIGINT,
    short_signals BIGINT,
    wait_signals BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*)::BIGINT as total_signals,
        COUNT(*) FILTER (WHERE sh.trade_result IS NOT NULL)::BIGINT as traded_signals,
        COUNT(*) FILTER (WHERE sh.trade_result = 'win')::BIGINT as wins,
        COUNT(*) FILTER (WHERE sh.trade_result = 'loss')::BIGINT as losses,
        CASE
            WHEN COUNT(*) FILTER (WHERE sh.trade_result IS NOT NULL) > 0
            THEN ROUND(
                (COUNT(*) FILTER (WHERE sh.trade_result = 'win')::DECIMAL /
                 COUNT(*) FILTER (WHERE sh.trade_result IS NOT NULL)) * 100,
                2
            )
            ELSE 0
        END as win_rate,
        COALESCE(SUM(sh.pnl), 0) as total_pnl,
        CASE
            WHEN COUNT(*) FILTER (WHERE sh.trade_result IS NOT NULL) > 0
            THEN ROUND(
                COALESCE(SUM(sh.pnl), 0) /
                COUNT(*) FILTER (WHERE sh.trade_result IS NOT NULL),
                8
            )
            ELSE 0
        END as avg_pnl,
        COALESCE(MAX(sh.pnl), 0) as best_pnl,
        COALESCE(MIN(sh.pnl), 0) as worst_pnl,
        COUNT(*) FILTER (WHERE sh.signal = 'LONG')::BIGINT as long_signals,
        COUNT(*) FILTER (WHERE sh.signal = 'SHORT')::BIGINT as short_signals,
        COUNT(*) FILTER (WHERE sh.signal = 'WAIT')::BIGINT as wait_signals
    FROM signal_history sh
    WHERE sh.timestamp >= NOW() - (p_days || ' days')::INTERVAL
      AND (p_bot_id IS NULL OR sh.bot_id = p_bot_id)
      AND (p_source IS NULL OR sh.source = p_source);
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 뷰: 최근 신호 목록 (빠른 조회용)
-- ============================================================================

CREATE OR REPLACE VIEW recent_signals AS
SELECT
    sh.id,
    sh.timestamp,
    sh.bot_id,
    b.name as bot_name,
    sh.signal,
    sh.source,
    sh.trade_result,
    sh.pnl,
    sh.reason,
    sh.market_conditions
FROM signal_history sh
LEFT JOIN bots b ON sh.bot_id = b.id
WHERE sh.timestamp >= NOW() - INTERVAL '24 hours'
ORDER BY sh.timestamp DESC;

-- 마이그레이션 완료 로그
DO $$
BEGIN
    RAISE NOTICE '004_signal_tracking.sql migration completed successfully';
END $$;
