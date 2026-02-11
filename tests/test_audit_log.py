"""
Tests for Audit Log

Phase 7.3: 거래 감사 로그
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.storage.audit_log import (
    AuditEventType,
    AuditLog,
    AuditLogManager,
)


class TestAuditEventType:
    """AuditEventType Enum 테스트"""

    def test_trade_open(self):
        """TRADE_OPEN 이벤트 타입"""
        assert AuditEventType.TRADE_OPEN.value == "TRADE_OPEN"

    def test_trade_close(self):
        """TRADE_CLOSE 이벤트 타입"""
        assert AuditEventType.TRADE_CLOSE.value == "TRADE_CLOSE"

    def test_bot_pause(self):
        """BOT_PAUSE 이벤트 타입"""
        assert AuditEventType.BOT_PAUSE.value == "BOT_PAUSE"

    def test_bot_resume(self):
        """BOT_RESUME 이벤트 타입"""
        assert AuditEventType.BOT_RESUME.value == "BOT_RESUME"

    def test_emergency_close(self):
        """EMERGENCY_CLOSE 이벤트 타입"""
        assert AuditEventType.EMERGENCY_CLOSE.value == "EMERGENCY_CLOSE"

    def test_config_change(self):
        """CONFIG_CHANGE 이벤트 타입"""
        assert AuditEventType.CONFIG_CHANGE.value == "CONFIG_CHANGE"

    def test_risk_halt(self):
        """RISK_HALT 이벤트 타입"""
        assert AuditEventType.RISK_HALT.value == "RISK_HALT"


class TestAuditLog:
    """AuditLog 데이터클래스 테스트"""

    def test_create_audit_log(self):
        """AuditLog 생성"""
        log = AuditLog(
            event_type=AuditEventType.TRADE_OPEN,
            bot_name="btc-bot",
            details={"side": "LONG", "price": 50000.0},
        )

        assert log.event_type == AuditEventType.TRADE_OPEN
        assert log.bot_name == "btc-bot"
        assert log.details["side"] == "LONG"
        assert log.timestamp is not None

    def test_audit_log_with_user_id(self):
        """user_id가 있는 AuditLog"""
        log = AuditLog(
            event_type=AuditEventType.BOT_PAUSE,
            bot_name="btc-bot",
            user_id="user_123",
            details={"reason": "manual"},
        )

        assert log.user_id == "user_123"

    def test_audit_log_to_dict(self):
        """AuditLog를 dict로 변환"""
        log = AuditLog(
            event_type=AuditEventType.TRADE_CLOSE,
            bot_name="btc-bot",
            details={"pnl": 100.0},
        )

        data = log.to_dict()
        assert data["event_type"] == "TRADE_CLOSE"
        assert data["bot_name"] == "btc-bot"
        assert data["details"]["pnl"] == 100.0


class TestAuditLogManager:
    """AuditLogManager 테스트"""

    @pytest.fixture
    def manager(self):
        """AuditLogManager 인스턴스"""
        return AuditLogManager()

    @pytest.mark.asyncio
    async def test_log_trade_open(self, manager):
        """TRADE_OPEN 이벤트 로깅"""
        await manager.log_trade_open(
            bot_name="btc-bot",
            side="LONG",
            quantity=0.001,
            entry_price=50000.0,
        )

        # 인메모리 로그에 저장되었는지 확인
        logs = await manager.get_recent_logs(bot_name="btc-bot", limit=1)
        assert len(logs) == 1
        assert logs[0].event_type == AuditEventType.TRADE_OPEN
        assert logs[0].details["side"] == "LONG"

    @pytest.mark.asyncio
    async def test_log_trade_close(self, manager):
        """TRADE_CLOSE 이벤트 로깅"""
        await manager.log_trade_close(
            bot_name="btc-bot",
            side="LONG",
            exit_reason="TP",
            pnl=50.0,
            pnl_pct=0.5,
        )

        logs = await manager.get_recent_logs(bot_name="btc-bot", limit=1)
        assert len(logs) == 1
        assert logs[0].event_type == AuditEventType.TRADE_CLOSE
        assert logs[0].details["exit_reason"] == "TP"
        assert logs[0].details["pnl"] == 50.0

    @pytest.mark.asyncio
    async def test_log_bot_pause(self, manager):
        """BOT_PAUSE 이벤트 로깅"""
        await manager.log_bot_pause(
            bot_name="btc-bot",
            user_id="user_123",
            reason="manual pause",
        )

        logs = await manager.get_recent_logs(bot_name="btc-bot", limit=1)
        assert len(logs) == 1
        assert logs[0].event_type == AuditEventType.BOT_PAUSE
        assert logs[0].user_id == "user_123"

    @pytest.mark.asyncio
    async def test_log_bot_resume(self, manager):
        """BOT_RESUME 이벤트 로깅"""
        await manager.log_bot_resume(
            bot_name="btc-bot",
            user_id="user_123",
        )

        logs = await manager.get_recent_logs(bot_name="btc-bot", limit=1)
        assert len(logs) == 1
        assert logs[0].event_type == AuditEventType.BOT_RESUME

    @pytest.mark.asyncio
    async def test_log_emergency_close(self, manager):
        """EMERGENCY_CLOSE 이벤트 로깅"""
        await manager.log_emergency_close(
            bot_name="btc-bot",
            user_id="user_123",
            reason="manual emergency",
            pnl=-100.0,
        )

        logs = await manager.get_recent_logs(bot_name="btc-bot", limit=1)
        assert len(logs) == 1
        assert logs[0].event_type == AuditEventType.EMERGENCY_CLOSE

    @pytest.mark.asyncio
    async def test_log_risk_halt(self, manager):
        """RISK_HALT 이벤트 로깅"""
        await manager.log_risk_halt(
            bot_name="btc-bot",
            reason="일일 손실 한도 도달: 5.0%",
            daily_pnl=-500.0,
            daily_pnl_pct=-5.0,
        )

        logs = await manager.get_recent_logs(bot_name="btc-bot", limit=1)
        assert len(logs) == 1
        assert logs[0].event_type == AuditEventType.RISK_HALT
        assert "일일 손실 한도" in logs[0].details["reason"]

    @pytest.mark.asyncio
    async def test_log_config_change(self, manager):
        """CONFIG_CHANGE 이벤트 로깅"""
        await manager.log_config_change(
            bot_name="btc-bot",
            user_id="user_123",
            changes={"leverage": {"old": 10, "new": 15}},
        )

        logs = await manager.get_recent_logs(bot_name="btc-bot", limit=1)
        assert len(logs) == 1
        assert logs[0].event_type == AuditEventType.CONFIG_CHANGE

    @pytest.mark.asyncio
    async def test_get_recent_logs_with_limit(self, manager):
        """최근 로그 조회 (limit)"""
        # 여러 로그 생성
        for i in range(5):
            await manager.log_trade_open(
                bot_name="btc-bot",
                side="LONG",
                quantity=0.001,
                entry_price=50000.0 + i * 100,
            )

        # limit으로 조회
        logs = await manager.get_recent_logs(bot_name="btc-bot", limit=3)
        assert len(logs) == 3

    @pytest.mark.asyncio
    async def test_get_recent_logs_by_event_type(self, manager):
        """이벤트 타입으로 필터링"""
        await manager.log_trade_open(
            bot_name="btc-bot", side="LONG", quantity=0.001, entry_price=50000.0
        )
        await manager.log_bot_pause(bot_name="btc-bot", reason="test")

        logs = await manager.get_recent_logs(
            bot_name="btc-bot",
            event_type=AuditEventType.TRADE_OPEN,
        )
        assert len(logs) == 1
        assert logs[0].event_type == AuditEventType.TRADE_OPEN

    @pytest.mark.asyncio
    async def test_get_all_logs(self, manager):
        """모든 봇의 로그 조회"""
        await manager.log_trade_open(
            bot_name="btc-bot", side="LONG", quantity=0.001, entry_price=50000.0
        )
        await manager.log_trade_open(
            bot_name="eth-bot", side="SHORT", quantity=0.01, entry_price=3000.0
        )

        logs = await manager.get_recent_logs(limit=10)
        assert len(logs) == 2


class TestAuditLogPersistence:
    """DB 영속성 테스트 (Mock)"""

    @pytest.fixture
    def db_pool(self):
        """Mock DB Pool"""
        pool = MagicMock()
        return pool

    @pytest.mark.asyncio
    async def test_manager_with_db_pool(self, db_pool):
        """DB 연결이 있는 경우"""
        manager = AuditLogManager(db_pool=db_pool)
        assert manager._db_pool is not None

    @pytest.mark.asyncio
    async def test_manager_without_db_pool(self):
        """DB 연결이 없는 경우 (인메모리)"""
        manager = AuditLogManager()
        assert manager._db_pool is None

        # 인메모리에서도 로깅 가능
        await manager.log_trade_open(
            bot_name="btc-bot", side="LONG", quantity=0.001, entry_price=50000.0
        )
        logs = await manager.get_recent_logs()
        assert len(logs) == 1


# =============================================================================
# AuditLogManager 추가 커버리지 테스트 (from test_storage_coverage.py)
# =============================================================================


class TestAuditLogManagerSaveToDb:
    """_save_to_db 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_save_to_db_with_pool(self):
        """DB 풀이 있을 때 _save_to_db 실행"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()

        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        manager = AuditLogManager(db_pool=mock_pool)

        log = AuditLog(
            event_type=AuditEventType.TRADE_OPEN,
            bot_name="btc-bot",
            details={"side": "LONG", "price": 50000.0},
            user_id="user_123",
            session_id="sess_abc",
        )

        await manager._save_to_db(log)

        mock_conn.execute.assert_called_once()
        # 5개 파라미터: event_type, bot_name, user_id, details_json, session_id
        call_args = mock_conn.execute.call_args
        assert call_args[0][1] == "TRADE_OPEN"
        assert call_args[0][2] == "btc-bot"
        assert call_args[0][3] == "user_123"

    @pytest.mark.asyncio
    async def test_save_to_db_no_pool(self):
        """DB 풀이 없을 때 _save_to_db는 아무것도 안 함"""
        manager = AuditLogManager(db_pool=None)

        log = AuditLog(
            event_type=AuditEventType.TRADE_OPEN,
            bot_name="btc-bot",
            details={},
        )

        # 에러 없이 완료되어야 함
        await manager._save_to_db(log)


class TestAuditLogManagerSaveLogDbError:
    """_save_log에서 DB 저장 실패 시 인메모리에는 저장"""

    @pytest.mark.asyncio
    async def test_save_log_db_error_fallback_to_memory(self):
        """DB 저장 실패 시 인메모리에만 저장"""
        mock_pool = MagicMock()

        manager = AuditLogManager(db_pool=mock_pool)

        # _save_to_db가 예외를 발생시키도록 설정
        with patch.object(manager, "_save_to_db", side_effect=Exception("DB 에러")):
            await manager.log_trade_open(
                bot_name="btc-bot",
                side="LONG",
                quantity=0.001,
                entry_price=50000.0,
            )

        # 인메모리에는 저장됨
        logs = await manager.get_recent_logs(bot_name="btc-bot")
        assert len(logs) == 1


class TestAuditLogManagerMaxMemoryLogs:
    """최대 인메모리 로그 수 초과 테스트"""

    @pytest.mark.asyncio
    async def test_memory_logs_trimmed(self):
        """최대 로그 수 초과 시 오래된 로그 삭제"""
        manager = AuditLogManager(max_memory_logs=5)

        for i in range(10):
            await manager.log_trade_open(
                bot_name=f"bot-{i}",
                side="LONG",
                quantity=0.001,
                entry_price=50000.0 + i,
            )

        # 최대 5개만 유지
        assert len(manager._memory_logs) == 5
        # 마지막 5개가 유지됨
        assert manager._memory_logs[0].bot_name == "bot-5"
        assert manager._memory_logs[4].bot_name == "bot-9"


class TestAuditLogManagerGetLogsByDateRange:
    """날짜 범위 로그 조회 테스트"""

    @pytest.mark.asyncio
    async def test_get_logs_by_date_range(self):
        """날짜 범위로 로그 조회"""
        manager = AuditLogManager()

        # 수동으로 로그 추가 (시간 제어)
        now = datetime.now(timezone.utc)
        log1 = AuditLog(
            event_type=AuditEventType.TRADE_OPEN,
            bot_name="btc-bot",
            details={"side": "LONG"},
            timestamp=now - timedelta(hours=2),
        )
        log2 = AuditLog(
            event_type=AuditEventType.TRADE_CLOSE,
            bot_name="btc-bot",
            details={"side": "LONG"},
            timestamp=now - timedelta(hours=1),
        )
        log3 = AuditLog(
            event_type=AuditEventType.BOT_PAUSE,
            bot_name="eth-bot",
            details={},
            timestamp=now,
        )

        manager._memory_logs = [log1, log2, log3]

        # 1.5시간 전부터 현재까지 조회
        start = now - timedelta(hours=1, minutes=30)
        end = now + timedelta(minutes=1)

        logs = await manager.get_logs_by_date_range(start, end)
        assert len(logs) == 2  # log2, log3

    @pytest.mark.asyncio
    async def test_get_logs_by_date_range_with_bot_name(self):
        """날짜 범위 + 봇 이름으로 로그 조회"""
        manager = AuditLogManager()

        now = datetime.now(timezone.utc)
        log1 = AuditLog(
            event_type=AuditEventType.TRADE_OPEN,
            bot_name="btc-bot",
            details={},
            timestamp=now - timedelta(hours=1),
        )
        log2 = AuditLog(
            event_type=AuditEventType.TRADE_OPEN,
            bot_name="eth-bot",
            details={},
            timestamp=now,
        )

        manager._memory_logs = [log1, log2]

        start = now - timedelta(hours=2)
        end = now + timedelta(minutes=1)

        logs = await manager.get_logs_by_date_range(start, end, bot_name="btc-bot")
        assert len(logs) == 1
        assert logs[0].bot_name == "btc-bot"


class TestAuditLogManagerGetStats:
    """감사 로그 통계 테스트"""

    @pytest.mark.asyncio
    async def test_get_stats_empty(self):
        """빈 로그에서 통계"""
        manager = AuditLogManager()
        stats = manager.get_stats()

        assert stats["total_logs"] == 0
        assert stats["event_counts"] == {}
        assert stats["db_connected"] is False

    @pytest.mark.asyncio
    async def test_get_stats_with_logs(self):
        """로그가 있을 때 통계"""
        manager = AuditLogManager()

        await manager.log_trade_open("bot1", "LONG", 0.001, 50000.0)
        await manager.log_trade_open("bot2", "SHORT", 0.01, 3000.0)
        await manager.log_trade_close("bot1", "LONG", "TP", 100.0, 1.0)
        await manager.log_bot_pause("bot1", reason="manual")

        stats = manager.get_stats()

        assert stats["total_logs"] == 4
        assert stats["event_counts"]["TRADE_OPEN"] == 2
        assert stats["event_counts"]["TRADE_CLOSE"] == 1
        assert stats["event_counts"]["BOT_PAUSE"] == 1
        assert stats["db_connected"] is False

    @pytest.mark.asyncio
    async def test_get_stats_with_db_pool(self):
        """DB 풀이 있을 때 db_connected=True"""
        manager = AuditLogManager(db_pool=MagicMock())
        stats = manager.get_stats()
        assert stats["db_connected"] is True


class TestAuditLogSessionId:
    """AuditLog의 session_id 필드 테스트"""

    def test_audit_log_with_session_id(self):
        """session_id가 있는 AuditLog"""
        log = AuditLog(
            event_type=AuditEventType.TRADE_OPEN,
            bot_name="btc-bot",
            details={},
            session_id="session-123",
        )
        assert log.session_id == "session-123"

        data = log.to_dict()
        assert data["session_id"] == "session-123"

    def test_audit_log_without_session_id(self):
        """session_id가 없는 AuditLog"""
        log = AuditLog(
            event_type=AuditEventType.TRADE_OPEN,
            bot_name="btc-bot",
            details={},
        )
        assert log.session_id is None


class TestAuditLogTradeOpenWithKwargs:
    """log_trade_open의 추가 kwargs 테스트"""

    @pytest.mark.asyncio
    async def test_log_trade_open_with_extra_fields(self):
        """추가 필드가 details에 포함되는지 확인"""
        manager = AuditLogManager()

        await manager.log_trade_open(
            bot_name="btc-bot",
            side="LONG",
            quantity=0.001,
            entry_price=50000.0,
            leverage=15,
            signal_source="gemini",
        )

        logs = await manager.get_recent_logs(bot_name="btc-bot", limit=1)
        assert len(logs) == 1
        assert logs[0].details["leverage"] == 15
        assert logs[0].details["signal_source"] == "gemini"


class TestAuditLogTradeCloseWithKwargs:
    """log_trade_close의 추가 kwargs 테스트"""

    @pytest.mark.asyncio
    async def test_log_trade_close_with_extra_fields(self):
        """추가 필드가 details에 포함되는지 확인"""
        manager = AuditLogManager()

        await manager.log_trade_close(
            bot_name="btc-bot",
            side="LONG",
            exit_reason="TP",
            pnl=100.0,
            pnl_pct=1.5,
            exit_price=51000.0,
        )

        logs = await manager.get_recent_logs(bot_name="btc-bot", limit=1)
        assert len(logs) == 1
        assert logs[0].details["exit_price"] == 51000.0
