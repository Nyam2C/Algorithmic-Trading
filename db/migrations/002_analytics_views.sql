-- =============================================================================
-- Migration 002: Analytics Views and Functions
-- =============================================================================
-- Phase 4 AI 메모리 시스템을 위한 분석용 뷰 및 함수
-- 실행: psql -d trading -f db/migrations/002_analytics_views.sql
-- =============================================================================

BEGIN;

-- =============================================================================
-- 1. trades_with_signals 뷰 (거래 + AI 신호 조인)
-- =============================================================================

CREATE OR REPLACE VIEW trades_with_signals AS
SELECT
    t.id AS trade_id,
    t.bot_id,
    t.symbol,
    t.side,
    t.entry_price,
    t.exit_price,
    t.quantity,
    t.leverage,
    t.pnl,
    t.pnl_pct,
    t.exit_reason,
    t.entry_time,
    t.exit_time,
    t.duration_minutes,
    t.status,
    -- AI 신호 정보
    s.id AS signal_id,
    s.signal AS ai_signal,
    s.confidence AS ai_confidence,
    s.rsi AS signal_rsi,
    s.volume_ratio AS signal_volume_ratio,
    s.model_name,
    -- 계산된 필드
    CASE WHEN t.pnl > 0 THEN TRUE ELSE FALSE END AS is_winner,
    EXTRACT(HOUR FROM t.entry_time) AS entry_hour,
    -- RSI 구간 분류
    CASE
        WHEN s.rsi < 30 THEN 'oversold'
        WHEN s.rsi >= 30 AND s.rsi < 40 THEN 'low'
        WHEN s.rsi >= 40 AND s.rsi < 60 THEN 'neutral'
        WHEN s.rsi >= 60 AND s.rsi < 70 THEN 'high'
        WHEN s.rsi >= 70 THEN 'overbought'
        ELSE 'unknown'
    END AS rsi_zone
FROM trades t
LEFT JOIN ai_signals s ON t.id = s.trade_id
WHERE t.status = 'CLOSED';

-- =============================================================================
-- 2. RSI 구간별 성과 함수
-- =============================================================================

CREATE OR REPLACE FUNCTION get_rsi_performance(
    p_bot_id UUID DEFAULT NULL,
    p_days INT DEFAULT 7
)
RETURNS TABLE (
    rsi_zone VARCHAR(20),
    side VARCHAR(10),
    total_trades BIGINT,
    winning_trades BIGINT,
    losing_trades BIGINT,
    win_rate DECIMAL(5, 2),
    avg_pnl DECIMAL(20, 8),
    total_pnl DECIMAL(20, 8),
    avg_duration_minutes DECIMAL(10, 2)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        CASE
            WHEN s.rsi < 30 THEN 'oversold'::VARCHAR(20)
            WHEN s.rsi >= 30 AND s.rsi < 40 THEN 'low'::VARCHAR(20)
            WHEN s.rsi >= 40 AND s.rsi < 60 THEN 'neutral'::VARCHAR(20)
            WHEN s.rsi >= 60 AND s.rsi < 70 THEN 'high'::VARCHAR(20)
            WHEN s.rsi >= 70 THEN 'overbought'::VARCHAR(20)
            ELSE 'unknown'::VARCHAR(20)
        END AS rsi_zone,
        t.side::VARCHAR(10),
        COUNT(*)::BIGINT AS total_trades,
        SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END)::BIGINT AS winning_trades,
        SUM(CASE WHEN t.pnl <= 0 THEN 1 ELSE 0 END)::BIGINT AS losing_trades,
        ROUND(
            CASE WHEN COUNT(*) > 0
            THEN SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END)::DECIMAL / COUNT(*) * 100
            ELSE 0 END, 2
        )::DECIMAL(5, 2) AS win_rate,
        COALESCE(ROUND(AVG(t.pnl), 8), 0)::DECIMAL(20, 8) AS avg_pnl,
        COALESCE(ROUND(SUM(t.pnl), 8), 0)::DECIMAL(20, 8) AS total_pnl,
        COALESCE(ROUND(AVG(t.duration_minutes), 2), 0)::DECIMAL(10, 2) AS avg_duration_minutes
    FROM trades t
    LEFT JOIN ai_signals s ON t.id = s.trade_id
    WHERE t.status = 'CLOSED'
        AND t.exit_time >= NOW() - (p_days || ' days')::INTERVAL
        AND (p_bot_id IS NULL OR t.bot_id = p_bot_id)
        AND s.rsi IS NOT NULL
    GROUP BY
        CASE
            WHEN s.rsi < 30 THEN 'oversold'
            WHEN s.rsi >= 30 AND s.rsi < 40 THEN 'low'
            WHEN s.rsi >= 40 AND s.rsi < 60 THEN 'neutral'
            WHEN s.rsi >= 60 AND s.rsi < 70 THEN 'high'
            WHEN s.rsi >= 70 THEN 'overbought'
            ELSE 'unknown'
        END,
        t.side
    ORDER BY win_rate DESC, total_trades DESC;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- 3. 시간대별 성과 함수
-- =============================================================================

CREATE OR REPLACE FUNCTION get_hourly_performance(
    p_bot_id UUID DEFAULT NULL,
    p_days INT DEFAULT 7
)
RETURNS TABLE (
    hour_of_day INT,
    side VARCHAR(10),
    total_trades BIGINT,
    winning_trades BIGINT,
    losing_trades BIGINT,
    win_rate DECIMAL(5, 2),
    avg_pnl DECIMAL(20, 8),
    total_pnl DECIMAL(20, 8)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        EXTRACT(HOUR FROM t.entry_time)::INT AS hour_of_day,
        t.side::VARCHAR(10),
        COUNT(*)::BIGINT AS total_trades,
        SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END)::BIGINT AS winning_trades,
        SUM(CASE WHEN t.pnl <= 0 THEN 1 ELSE 0 END)::BIGINT AS losing_trades,
        ROUND(
            CASE WHEN COUNT(*) > 0
            THEN SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END)::DECIMAL / COUNT(*) * 100
            ELSE 0 END, 2
        )::DECIMAL(5, 2) AS win_rate,
        COALESCE(ROUND(AVG(t.pnl), 8), 0)::DECIMAL(20, 8) AS avg_pnl,
        COALESCE(ROUND(SUM(t.pnl), 8), 0)::DECIMAL(20, 8) AS total_pnl
    FROM trades t
    WHERE t.status = 'CLOSED'
        AND t.exit_time >= NOW() - (p_days || ' days')::INTERVAL
        AND (p_bot_id IS NULL OR t.bot_id = p_bot_id)
    GROUP BY EXTRACT(HOUR FROM t.entry_time), t.side
    ORDER BY hour_of_day, t.side;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- 4. 연승/연패 계산 함수
-- =============================================================================

CREATE OR REPLACE FUNCTION get_current_streak(
    p_bot_id UUID DEFAULT NULL
)
RETURNS TABLE (
    streak_type VARCHAR(10),
    streak_count INT,
    last_trade_time TIMESTAMP WITH TIME ZONE
) AS $$
DECLARE
    v_last_pnl DECIMAL;
    v_streak_type VARCHAR(10);
    v_streak_count INT := 0;
    v_last_trade_time TIMESTAMP WITH TIME ZONE;
    rec RECORD;
BEGIN
    -- 최근 거래부터 순회하며 연승/연패 계산
    FOR rec IN
        SELECT t.pnl, t.exit_time
        FROM trades t
        WHERE t.status = 'CLOSED'
            AND (p_bot_id IS NULL OR t.bot_id = p_bot_id)
        ORDER BY t.exit_time DESC
        LIMIT 50
    LOOP
        IF v_streak_count = 0 THEN
            -- 첫 거래
            v_last_pnl := rec.pnl;
            v_last_trade_time := rec.exit_time;
            v_streak_type := CASE WHEN rec.pnl > 0 THEN 'WIN' ELSE 'LOSS' END;
            v_streak_count := 1;
        ELSIF (rec.pnl > 0 AND v_streak_type = 'WIN') OR
              (rec.pnl <= 0 AND v_streak_type = 'LOSS') THEN
            -- 연속
            v_streak_count := v_streak_count + 1;
        ELSE
            -- 연속 끊김
            EXIT;
        END IF;
    END LOOP;

    -- 결과 반환
    streak_type := v_streak_type;
    streak_count := v_streak_count;
    last_trade_time := v_last_trade_time;
    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- 5. 종합 성과 통계 함수
-- =============================================================================

CREATE OR REPLACE FUNCTION get_trading_summary(
    p_bot_id UUID DEFAULT NULL,
    p_days INT DEFAULT 7
)
RETURNS TABLE (
    total_trades BIGINT,
    winning_trades BIGINT,
    losing_trades BIGINT,
    win_rate DECIMAL(5, 2),
    total_pnl DECIMAL(20, 8),
    avg_pnl DECIMAL(20, 8),
    avg_win DECIMAL(20, 8),
    avg_loss DECIMAL(20, 8),
    profit_factor DECIMAL(10, 4),
    avg_duration_minutes DECIMAL(10, 2),
    best_trade_pnl DECIMAL(20, 8),
    worst_trade_pnl DECIMAL(20, 8),
    long_trades BIGINT,
    short_trades BIGINT,
    long_win_rate DECIMAL(5, 2),
    short_win_rate DECIMAL(5, 2)
) AS $$
DECLARE
    v_gross_profit DECIMAL(20, 8);
    v_gross_loss DECIMAL(20, 8);
BEGIN
    -- 손익 합계 계산
    SELECT
        COALESCE(SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END), 0),
        COALESCE(SUM(CASE WHEN pnl < 0 THEN ABS(pnl) ELSE 0 END), 0)
    INTO v_gross_profit, v_gross_loss
    FROM trades
    WHERE status = 'CLOSED'
        AND exit_time >= NOW() - (p_days || ' days')::INTERVAL
        AND (p_bot_id IS NULL OR bot_id = p_bot_id);

    RETURN QUERY
    SELECT
        COUNT(*)::BIGINT AS total_trades,
        SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END)::BIGINT AS winning_trades,
        SUM(CASE WHEN t.pnl <= 0 THEN 1 ELSE 0 END)::BIGINT AS losing_trades,
        ROUND(
            CASE WHEN COUNT(*) > 0
            THEN SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END)::DECIMAL / COUNT(*) * 100
            ELSE 0 END, 2
        )::DECIMAL(5, 2) AS win_rate,
        COALESCE(SUM(t.pnl), 0)::DECIMAL(20, 8) AS total_pnl,
        COALESCE(AVG(t.pnl), 0)::DECIMAL(20, 8) AS avg_pnl,
        COALESCE(AVG(CASE WHEN t.pnl > 0 THEN t.pnl END), 0)::DECIMAL(20, 8) AS avg_win,
        COALESCE(AVG(CASE WHEN t.pnl < 0 THEN t.pnl END), 0)::DECIMAL(20, 8) AS avg_loss,
        CASE WHEN v_gross_loss > 0
            THEN ROUND(v_gross_profit / v_gross_loss, 4)
            ELSE 0
        END::DECIMAL(10, 4) AS profit_factor,
        COALESCE(AVG(t.duration_minutes), 0)::DECIMAL(10, 2) AS avg_duration_minutes,
        COALESCE(MAX(t.pnl), 0)::DECIMAL(20, 8) AS best_trade_pnl,
        COALESCE(MIN(t.pnl), 0)::DECIMAL(20, 8) AS worst_trade_pnl,
        SUM(CASE WHEN t.side = 'LONG' THEN 1 ELSE 0 END)::BIGINT AS long_trades,
        SUM(CASE WHEN t.side = 'SHORT' THEN 1 ELSE 0 END)::BIGINT AS short_trades,
        ROUND(
            CASE WHEN SUM(CASE WHEN t.side = 'LONG' THEN 1 ELSE 0 END) > 0
            THEN SUM(CASE WHEN t.side = 'LONG' AND t.pnl > 0 THEN 1 ELSE 0 END)::DECIMAL /
                 SUM(CASE WHEN t.side = 'LONG' THEN 1 ELSE 0 END) * 100
            ELSE 0 END, 2
        )::DECIMAL(5, 2) AS long_win_rate,
        ROUND(
            CASE WHEN SUM(CASE WHEN t.side = 'SHORT' THEN 1 ELSE 0 END) > 0
            THEN SUM(CASE WHEN t.side = 'SHORT' AND t.pnl > 0 THEN 1 ELSE 0 END)::DECIMAL /
                 SUM(CASE WHEN t.side = 'SHORT' THEN 1 ELSE 0 END) * 100
            ELSE 0 END, 2
        )::DECIMAL(5, 2) AS short_win_rate
    FROM trades t
    WHERE t.status = 'CLOSED'
        AND t.exit_time >= NOW() - (p_days || ' days')::INTERVAL
        AND (p_bot_id IS NULL OR t.bot_id = p_bot_id);
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- 6. 청산 사유별 통계 함수
-- =============================================================================

CREATE OR REPLACE FUNCTION get_exit_reason_stats(
    p_bot_id UUID DEFAULT NULL,
    p_days INT DEFAULT 7
)
RETURNS TABLE (
    exit_reason VARCHAR(20),
    side VARCHAR(10),
    total_trades BIGINT,
    winning_trades BIGINT,
    win_rate DECIMAL(5, 2),
    avg_pnl DECIMAL(20, 8),
    total_pnl DECIMAL(20, 8),
    avg_duration_minutes DECIMAL(10, 2)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        t.exit_reason::VARCHAR(20),
        t.side::VARCHAR(10),
        COUNT(*)::BIGINT AS total_trades,
        SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END)::BIGINT AS winning_trades,
        ROUND(
            CASE WHEN COUNT(*) > 0
            THEN SUM(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END)::DECIMAL / COUNT(*) * 100
            ELSE 0 END, 2
        )::DECIMAL(5, 2) AS win_rate,
        COALESCE(ROUND(AVG(t.pnl), 8), 0)::DECIMAL(20, 8) AS avg_pnl,
        COALESCE(ROUND(SUM(t.pnl), 8), 0)::DECIMAL(20, 8) AS total_pnl,
        COALESCE(ROUND(AVG(t.duration_minutes), 2), 0)::DECIMAL(10, 2) AS avg_duration_minutes
    FROM trades t
    WHERE t.status = 'CLOSED'
        AND t.exit_time >= NOW() - (p_days || ' days')::INTERVAL
        AND (p_bot_id IS NULL OR t.bot_id = p_bot_id)
        AND t.exit_reason IS NOT NULL
    GROUP BY t.exit_reason, t.side
    ORDER BY total_trades DESC, win_rate DESC;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- 7. 인덱스 추가 (성능 최적화)
-- =============================================================================

-- 거래 조회 최적화 인덱스
CREATE INDEX IF NOT EXISTS idx_trades_exit_time ON trades(exit_time DESC);
CREATE INDEX IF NOT EXISTS idx_trades_bot_exit_time ON trades(bot_id, exit_time DESC);
CREATE INDEX IF NOT EXISTS idx_trades_status_exit_time ON trades(status, exit_time DESC);

-- AI 신호 조인 최적화
CREATE INDEX IF NOT EXISTS idx_ai_signals_trade_id ON ai_signals(trade_id);

-- =============================================================================
-- Migration Complete
-- =============================================================================

COMMIT;

SELECT 'Migration 002_analytics_views completed successfully!' AS status;
