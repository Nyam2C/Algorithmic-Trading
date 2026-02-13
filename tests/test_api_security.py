"""Tests for API security fixes (Phase 7).

Issue 4.1: API_DEBUG production bypass prevention
Issue 4.2: Critical endpoint rate limiting
Issue 4.3: Discord command audit logging
"""
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from src.api.dependencies import (
    _rate_limit_store,
    check_critical_rate_limit,
    verify_api_key,
)
from src.discord_bot.client import TradingBotClient

# =============================================================================
# Issue 4.1: API_DEBUG Production Bypass
# =============================================================================


class TestApiDebugProductionBypass:
    """API_DEBUG=true가 프로덕션에서 차단되는지 테스트."""

    @pytest.fixture(autouse=True)
    def _clear_env(self, monkeypatch):
        """환경변수 초기화"""
        monkeypatch.delenv("API_KEY", raising=False)
        monkeypatch.delenv("API_DEBUG", raising=False)
        monkeypatch.delenv("ENV", raising=False)

    def _make_request(self):
        """Mock FastAPI Request 생성"""
        request = MagicMock()
        request.url.path = "/test"
        request.client.host = "127.0.0.1"
        return request

    @pytest.mark.asyncio
    async def test_api_debug_blocked_in_production(self, monkeypatch):
        """ENV=production + API_DEBUG=true -> 500 에러"""
        monkeypatch.setenv("API_DEBUG", "true")
        monkeypatch.setenv("ENV", "production")
        monkeypatch.delenv("API_KEY", raising=False)

        request = self._make_request()
        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key(request, x_api_key=None)

        assert exc_info.value.status_code == 500
        assert "API_DEBUG cannot be enabled in production" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_api_debug_allowed_in_development(self, monkeypatch):
        """ENV=development + API_DEBUG=true -> None 반환 (우회 허용)"""
        monkeypatch.setenv("API_DEBUG", "true")
        monkeypatch.setenv("ENV", "development")
        monkeypatch.delenv("API_KEY", raising=False)

        request = self._make_request()
        result = await verify_api_key(request, x_api_key=None)

        assert result is None

    @pytest.mark.asyncio
    async def test_api_debug_default_env(self, monkeypatch):
        """ENV 미설정 + API_DEBUG=true -> None 반환 (기본값=development)"""
        monkeypatch.setenv("API_DEBUG", "true")
        monkeypatch.delenv("ENV", raising=False)
        monkeypatch.delenv("API_KEY", raising=False)

        request = self._make_request()
        result = await verify_api_key(request, x_api_key=None)

        assert result is None

    @pytest.mark.asyncio
    async def test_normal_auth_no_debug(self, monkeypatch):
        """API_KEY 설정 + 유효한 키 -> 인증 통과"""
        monkeypatch.setenv("API_KEY", "my-secret-key")
        monkeypatch.delenv("API_DEBUG", raising=False)

        request = self._make_request()
        result = await verify_api_key(request, x_api_key="my-secret-key")

        assert result == "my-secret-key"

    @pytest.mark.asyncio
    async def test_api_debug_false_no_bypass(self, monkeypatch):
        """API_DEBUG=false -> 인증 우회 없음"""
        monkeypatch.setenv("API_DEBUG", "false")
        monkeypatch.delenv("API_KEY", raising=False)

        request = self._make_request()
        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key(request, x_api_key=None)

        assert exc_info.value.status_code == 500
        assert "API_KEY not configured" in exc_info.value.detail


# =============================================================================
# Issue 4.2: Critical Endpoint Rate Limiting
# =============================================================================


class TestCriticalRateLimiting:
    """크리티컬 엔드포인트 레이트 리밋 테스트."""

    @pytest.fixture(autouse=True)
    def _clear_rate_limit_store(self):
        """레이트 리밋 스토어 초기화"""
        _rate_limit_store.clear()

    def _make_request(self, client_ip: str = "192.168.1.1"):
        """Mock FastAPI Request 생성"""
        request = MagicMock()
        request.client.host = client_ip
        return request

    @pytest.mark.asyncio
    async def test_critical_rate_limit_under(self):
        """5회 이내 요청은 통과"""
        request = self._make_request()
        for _ in range(5):
            await check_critical_rate_limit(request)
        # 5번째까지 모두 통과

    @pytest.mark.asyncio
    async def test_critical_rate_limit_exceeded(self):
        """6번째 요청은 429"""
        request = self._make_request()
        for _ in range(5):
            await check_critical_rate_limit(request)

        with pytest.raises(HTTPException) as exc_info:
            await check_critical_rate_limit(request)

        assert exc_info.value.status_code == 429
        assert "Rate limit exceeded" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_critical_rate_limit_different_ips(self):
        """서로 다른 IP는 독립적 리밋"""
        request_a = self._make_request("10.0.0.1")
        request_b = self._make_request("10.0.0.2")

        # IP A: 5회 사용
        for _ in range(5):
            await check_critical_rate_limit(request_a)

        # IP B: 아직 0회 → 통과
        await check_critical_rate_limit(request_b)

        # IP A: 초과
        with pytest.raises(HTTPException) as exc_info:
            await check_critical_rate_limit(request_a)
        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_critical_rate_limit_window_expiry(self):
        """윈도우 만료 후 리밋 리셋"""
        request = self._make_request()

        # 5회 사용
        for _ in range(5):
            await check_critical_rate_limit(request)

        # 타임스탬프를 과거로 조작 (61초 전)
        key = "critical:192.168.1.1"
        _rate_limit_store[key] = [time.time() - 61 for _ in range(5)]

        # 이제 통과해야 함 (만료된 요청 제거)
        await check_critical_rate_limit(request)

    @pytest.mark.asyncio
    async def test_critical_rate_limit_no_client(self):
        """request.client가 None인 경우"""
        request = MagicMock()
        request.client = None

        # "unknown" IP로 처리되어 통과
        await check_critical_rate_limit(request)


# =============================================================================
# Issue 4.3: Discord Command Audit Logging
# =============================================================================


class TestDiscordAuditLogging:
    """Discord 명령어 감사 로그 테스트."""

    def _make_client(self, position=None, bot_manager=None):
        """TradingBotClient 생성 (테스트용)."""
        bot_state = {
            "is_running": True,
            "is_paused": False,
            "position": position,
        }
        with patch.object(TradingBotClient, "__init__", lambda self, **kw: None):
            client = TradingBotClient.__new__(TradingBotClient)
            client.bot_state = bot_state
            client.trade_db = None
            client.binance_client = None
            client.bot_manager = bot_manager
            client._api_url = "http://localhost:8000"
            client._audit_log = None
            return client

    def _make_interaction(self):
        """Mock Discord Interaction 생성."""
        interaction = AsyncMock()
        interaction.user = MagicMock()
        interaction.user.__str__ = lambda self: "TestUser#1234"
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()
        return interaction

    def _make_bot_manager(self, bot_name="test-bot"):
        """Mock BotManager 생성."""
        manager = MagicMock()
        manager.bot_count = 1
        mock_bot = MagicMock()
        mock_bot.bot_name = bot_name
        mock_bot.request_emergency_close = MagicMock()
        manager.bots = {bot_name: mock_bot}
        manager.get_bot = MagicMock(return_value=mock_bot)
        manager.pause_bot = MagicMock()
        manager.resume_bot = MagicMock()
        return manager

    @pytest.mark.asyncio
    async def test_audit_log_on_emergency_close(self):
        """긴급청산 시 감사 로그 기록"""
        bot_manager = self._make_bot_manager()
        client = self._make_client(
            position={"side": "LONG", "entry_price": 50000, "quantity": 0.1},
            bot_manager=bot_manager,
        )
        mock_audit = AsyncMock()
        mock_audit.log_event = AsyncMock()
        client.set_audit_log(mock_audit)

        interaction = self._make_interaction()
        await client._emergency_command(interaction)

        mock_audit.log_event.assert_called_once()
        call_kwargs = mock_audit.log_event.call_args
        assert call_kwargs.kwargs["event_type"] == "DISCORD_COMMAND"
        assert call_kwargs.kwargs["details"]["command"] == "긴급청산"
        assert "LONG" in call_kwargs.kwargs["details"]["details"]

    @pytest.mark.asyncio
    async def test_audit_log_on_pause(self):
        """일시정지 시 감사 로그 기록"""
        bot_manager = self._make_bot_manager()
        client = self._make_client(bot_manager=bot_manager)
        mock_audit = AsyncMock()
        mock_audit.log_event = AsyncMock()
        client.set_audit_log(mock_audit)

        interaction = self._make_interaction()
        await client._stop_command(interaction)

        mock_audit.log_event.assert_called_once()
        call_kwargs = mock_audit.log_event.call_args
        assert call_kwargs.kwargs["event_type"] == "DISCORD_COMMAND"
        assert call_kwargs.kwargs["details"]["command"] == "일시정지"

    @pytest.mark.asyncio
    async def test_audit_log_on_resume(self):
        """재시작 시 감사 로그 기록"""
        bot_manager = self._make_bot_manager()
        client = self._make_client(bot_manager=bot_manager)
        mock_audit = AsyncMock()
        mock_audit.log_event = AsyncMock()
        client.set_audit_log(mock_audit)

        interaction = self._make_interaction()
        await client._start_command(interaction)

        mock_audit.log_event.assert_called_once()
        call_kwargs = mock_audit.log_event.call_args
        assert call_kwargs.kwargs["event_type"] == "DISCORD_COMMAND"
        assert call_kwargs.kwargs["details"]["command"] == "재시작"

    @pytest.mark.asyncio
    async def test_no_audit_log_no_error(self):
        """_audit_log가 None이면 에러 없음"""
        bot_manager = self._make_bot_manager()
        client = self._make_client(
            position={"side": "LONG", "entry_price": 50000, "quantity": 0.1},
            bot_manager=bot_manager,
        )
        # _audit_log is None by default

        interaction = self._make_interaction()
        # Should not raise any error
        await client._emergency_command(interaction)

    @pytest.mark.asyncio
    async def test_audit_log_failure_does_not_propagate(self):
        """감사 로그 실패가 명령어 실행에 영향을 주지 않음"""
        bot_manager = self._make_bot_manager()
        client = self._make_client(bot_manager=bot_manager)
        mock_audit = AsyncMock()
        mock_audit.log_event = AsyncMock(side_effect=Exception("DB connection failed"))
        client.set_audit_log(mock_audit)

        interaction = self._make_interaction()
        # Should not raise even though audit log fails
        await client._stop_command(interaction)

    @pytest.mark.asyncio
    async def test_set_audit_log(self):
        """set_audit_log 메서드 테스트"""
        client = self._make_client()
        assert client._audit_log is None

        mock_audit = AsyncMock()
        client.set_audit_log(mock_audit)
        assert client._audit_log is mock_audit

    @pytest.mark.asyncio
    async def test_audit_command_without_bot_name(self):
        """봇 매니저 없을 때 감사 로그"""
        client = self._make_client(bot_manager=None)
        mock_audit = AsyncMock()
        mock_audit.log_event = AsyncMock()
        client.set_audit_log(mock_audit)

        await client._audit_command("테스트", "TestUser#1234")

        mock_audit.log_event.assert_called_once()
        call_kwargs = mock_audit.log_event.call_args
        assert call_kwargs.kwargs["bot_name"] == "global"
