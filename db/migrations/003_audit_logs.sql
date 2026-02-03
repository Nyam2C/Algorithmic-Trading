-- Phase 7.3: 감사 로그 테이블
-- 모든 거래 및 봇 이벤트를 기록합니다.

CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    event_type VARCHAR(50) NOT NULL,  -- TRADE_OPEN, TRADE_CLOSE, BOT_PAUSE, etc.
    bot_name VARCHAR(100),
    user_id VARCHAR(100),             -- Discord user ID
    action_details JSONB,
    ip_address VARCHAR(45),
    session_id VARCHAR(100)
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_bot ON audit_logs(bot_name);
CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_id);

-- 이벤트 타입별 최근 로그 조회용 복합 인덱스
CREATE INDEX IF NOT EXISTS idx_audit_bot_event_time
    ON audit_logs(bot_name, event_type, timestamp DESC);

-- 코멘트
COMMENT ON TABLE audit_logs IS 'Phase 7.3: 거래 및 봇 이벤트 감사 로그';
COMMENT ON COLUMN audit_logs.event_type IS '이벤트 유형: TRADE_OPEN, TRADE_CLOSE, BOT_PAUSE, BOT_RESUME, EMERGENCY_CLOSE, CONFIG_CHANGE, RISK_HALT';
COMMENT ON COLUMN audit_logs.action_details IS 'JSON 형식의 이벤트 상세 정보';
COMMENT ON COLUMN audit_logs.user_id IS 'Discord 등 외부 시스템 사용자 ID';
