"""Phase 3: 오케스트레이션 서비스 테스트."""
from unittest.mock import AsyncMock

import pytest

from src.api.services.orchestration_service import OrchestrationService


@pytest.fixture
def mock_redis():
    """Mock Redis 상태 관리자."""
    redis = AsyncMock()
    redis.get_registered_bots = AsyncMock(return_value=["btc-bot", "eth-bot"])
    redis.read_heartbeat = AsyncMock(return_value=None)
    redis.load_bot_state = AsyncMock(return_value=None)
    redis.load_risk_state = AsyncMock(return_value=None)
    redis.load_position = AsyncMock(return_value=None)
    redis.push_command = AsyncMock(return_value=True)
    redis.get_total_exposure = AsyncMock(return_value={})
    return redis


@pytest.fixture
def service(mock_redis):
    """오케스트레이션 서비스."""
    return OrchestrationService(mock_redis)


class TestListBots:
    """봇 목록 조회 테스트."""

    @pytest.mark.asyncio
    async def test_list_bots_all_dead(self, service, mock_redis):
        """하트비트 없으면 dead."""
        bots = await service.list_bots()

        assert len(bots) == 2
        assert bots[0]["bot_name"] == "btc-bot"
        assert bots[0]["alive"] is False
        assert bots[1]["bot_name"] == "eth-bot"
        assert bots[1]["alive"] is False

    @pytest.mark.asyncio
    async def test_list_bots_with_heartbeat(self, service, mock_redis):
        """하트비트 있으면 alive."""
        mock_redis.read_heartbeat.side_effect = [
            {"timestamp": "2026-02-15T10:00:00", "status": "running"},
            None,
        ]

        bots = await service.list_bots()

        assert bots[0]["alive"] is True
        assert bots[1]["alive"] is False

    @pytest.mark.asyncio
    async def test_list_bots_empty(self, service, mock_redis):
        """등록된 봇 없으면 빈 리스트."""
        mock_redis.get_registered_bots.return_value = []

        bots = await service.list_bots()
        assert bots == []


class TestGetBotState:
    """개별 봇 상태 조회 테스트."""

    @pytest.mark.asyncio
    async def test_get_existing_bot(self, service, mock_redis):
        """존재하는 봇 상태 조회."""
        mock_redis.read_heartbeat.return_value = {
            "timestamp": "2026-02-15T10:00:00",
            "status": "running",
        }
        mock_redis.load_bot_state.return_value = {
            "is_running": True,
            "current_price": 98000.0,
        }

        state = await service.get_bot_state("btc-bot")

        assert state is not None
        assert state["alive"] is True
        assert state["state"]["is_running"] is True

    @pytest.mark.asyncio
    async def test_get_nonexistent_bot(self, service, mock_redis):
        """존재하지 않는 봇 → None."""
        state = await service.get_bot_state("unknown-bot")
        assert state is None


class TestBotCommands:
    """봇 명령 전송 테스트."""

    @pytest.mark.asyncio
    async def test_pause_bot(self, service, mock_redis):
        """PAUSE 명령 전송."""
        result = await service.pause_bot("btc-bot")

        assert result is True
        mock_redis.push_command.assert_called_once_with(
            "btc-bot", {"action": "PAUSE"}
        )

    @pytest.mark.asyncio
    async def test_resume_bot(self, service, mock_redis):
        """RESUME 명령 전송."""
        result = await service.resume_bot("btc-bot")

        assert result is True
        mock_redis.push_command.assert_called_once_with(
            "btc-bot", {"action": "RESUME"}
        )

    @pytest.mark.asyncio
    async def test_emergency_close(self, service, mock_redis):
        """EMERGENCY_CLOSE 명령 전송."""
        result = await service.emergency_close("btc-bot")

        assert result is True
        mock_redis.push_command.assert_called_once_with(
            "btc-bot", {"action": "EMERGENCY_CLOSE"}
        )

    @pytest.mark.asyncio
    async def test_stop_bot(self, service, mock_redis):
        """STOP 명령 전송."""
        result = await service.stop_bot("btc-bot")

        assert result is True
        mock_redis.push_command.assert_called_once_with(
            "btc-bot", {"action": "STOP"}
        )


class TestExposureSummary:
    """노출도 요약 테스트."""

    @pytest.mark.asyncio
    async def test_exposure_summary(self, service, mock_redis):
        """노출도 요약 조회."""
        mock_redis.get_total_exposure.return_value = {
            "btc-bot": 500.0,
            "eth-bot": 300.0,
        }

        summary = await service.get_exposure_summary()

        assert summary["total_exposure"] == 800.0
        assert summary["by_bot"]["btc-bot"] == 500.0

    @pytest.mark.asyncio
    async def test_exposure_summary_empty(self, service, mock_redis):
        """노출도 없으면 0."""
        summary = await service.get_exposure_summary()

        assert summary["total_exposure"] == 0.0
        assert summary["by_bot"] == {}


class TestIsOrchestratorMode:
    """오케스트레이터 모드 헬퍼 테스트."""

    def test_default_false(self):
        """기본값 False."""
        import os

        from src.api.dependencies import is_orchestrator_mode

        old_val = os.environ.pop("ORCHESTRATOR_MODE", None)
        try:
            assert is_orchestrator_mode() is False
        finally:
            if old_val:
                os.environ["ORCHESTRATOR_MODE"] = old_val

    def test_true(self):
        """ORCHESTRATOR_MODE=true → True."""
        import os

        from src.api.dependencies import is_orchestrator_mode

        old_val = os.environ.get("ORCHESTRATOR_MODE")
        os.environ["ORCHESTRATOR_MODE"] = "true"
        try:
            assert is_orchestrator_mode() is True
        finally:
            if old_val:
                os.environ["ORCHESTRATOR_MODE"] = old_val
            else:
                os.environ.pop("ORCHESTRATOR_MODE", None)

    def test_false_explicit(self):
        """ORCHESTRATOR_MODE=false → False."""
        import os

        from src.api.dependencies import is_orchestrator_mode

        old_val = os.environ.get("ORCHESTRATOR_MODE")
        os.environ["ORCHESTRATOR_MODE"] = "false"
        try:
            assert is_orchestrator_mode() is False
        finally:
            if old_val:
                os.environ["ORCHESTRATOR_MODE"] = old_val
            else:
                os.environ.pop("ORCHESTRATOR_MODE", None)
