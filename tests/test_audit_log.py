"""
Tests for Audit Log

Phase 7.3: 거래 감사 로그
"""
import pytest
from unittest.mock import MagicMock

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
