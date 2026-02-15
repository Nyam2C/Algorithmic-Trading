-- Migration: 005_add_exit_reasons.sql
-- Description: exit_reason 제약 조건에 EXCHANGE_SL_TP, UNKNOWN 값 추가
-- Created: 2026-02-16
-- Issue: 거래소 측 SL/TP 체결 및 fallback 시 exit_reason 값이 DB 제약 조건에 없어
--        INSERT 실패 → 거래 종료 미기록 → Discord 내역 조회 불가

-- 기존 제약 조건 삭제 후 재생성
ALTER TABLE trades DROP CONSTRAINT IF EXISTS trades_exit_reason_check;
ALTER TABLE trades ADD CONSTRAINT trades_exit_reason_check
  CHECK (exit_reason IN ('TP', 'SL', 'TIME_CUT', 'MANUAL', 'AI_SIGNAL', 'EXCHANGE_SL_TP', 'UNKNOWN'));

-- 마이그레이션 완료 로그
DO $$
BEGIN
    RAISE NOTICE '005_add_exit_reasons.sql migration completed successfully';
END $$;
