"""
n8n 콜백 서비스 테스트

n8n 웹훅 콜백 발송 테스트입니다.
"""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from src.api.schemas.n8n import N8NCallbackPayload
from src.api.services.n8n_callback import CallbackResult, N8NCallbackService


@pytest.fixture
def callback_service():
    """N8NCallbackService fixture"""
    return N8NCallbackService(webhook_url="https://n8n.example.com/webhook/test")


@pytest.fixture
def callback_service_no_url():
    """URL이 없는 N8NCallbackService fixture"""
    return N8NCallbackService(webhook_url=None)


class TestN8NCallbackService:
    """N8NCallbackService 테스트"""

    def test_init_with_url(self, callback_service):
        """URL로 초기화"""
        assert callback_service.webhook_url == "https://n8n.example.com/webhook/test"
        assert callback_service.is_enabled is True

    def test_init_without_url(self, callback_service_no_url):
        """URL 없이 초기화"""
        assert callback_service_no_url.webhook_url is None
        assert callback_service_no_url.is_enabled is False

    @pytest.mark.asyncio
    async def test_send_callback_disabled(self, callback_service_no_url):
        """콜백 비활성화 시 DISABLED 반환"""
        payload = N8NCallbackPayload(
            event_type="signal",
            bot_name="test-bot",
            data={"signal": "LONG"},
        )

        result = await callback_service_no_url.send_callback(payload)

        assert result == CallbackResult.DISABLED

    @pytest.mark.asyncio
    async def test_send_callback_success(self, callback_service):
        """콜백 전송 성공"""
        payload = N8NCallbackPayload(
            event_type="signal",
            bot_name="test-bot",
            data={"signal": "LONG", "price": 50000.0},
        )

        # mock response context manager
        mock_response = MagicMock()
        mock_response.status = 200

        # mock post context manager
        mock_post_cm = MagicMock()
        mock_post_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post_cm.__aexit__ = AsyncMock(return_value=None)

        # mock session (_get_session에서 반환되는 세션)
        mock_session = MagicMock()
        mock_session.post.return_value = mock_post_cm

        # _get_session을 mock하여 세션 반환
        with patch.object(
            callback_service, "_get_session", new_callable=AsyncMock
        ) as mock_get_session:
            mock_get_session.return_value = mock_session

            result = await callback_service.send_callback(payload)

            assert result == CallbackResult.SUCCESS
            mock_get_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_signal_callback(self, callback_service):
        """시그널 콜백 전송"""
        with patch.object(callback_service, "send_callback", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            result = await callback_service.send_signal(
                bot_name="test-bot",
                signal="LONG",
                price=50000.0,
            )

            assert result is True
            mock_send.assert_called_once()
            call_args = mock_send.call_args[0][0]
            assert call_args.event_type == "signal"
            assert call_args.bot_name == "test-bot"
            assert call_args.data["signal"] == "LONG"
            assert call_args.data["price"] == 50000.0

    @pytest.mark.asyncio
    async def test_send_trade_callback(self, callback_service):
        """거래 콜백 전송"""
        with patch.object(callback_service, "send_callback", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            result = await callback_service.send_trade(
                bot_name="test-bot",
                action="OPEN",
                side="LONG",
                price=50000.0,
                pnl=None,
            )

            assert result is True
            mock_send.assert_called_once()
            call_args = mock_send.call_args[0][0]
            assert call_args.event_type == "trade"
            assert call_args.data["action"] == "OPEN"
            assert call_args.data["side"] == "LONG"

    @pytest.mark.asyncio
    async def test_send_error_callback(self, callback_service):
        """에러 콜백 전송"""
        with patch.object(callback_service, "send_callback", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            result = await callback_service.send_error(
                bot_name="test-bot",
                error=ValueError("Test error"),
            )

            assert result is True
            mock_send.assert_called_once()
            call_args = mock_send.call_args[0][0]
            assert call_args.event_type == "error"
            assert "Test error" in call_args.data["error"]

    @pytest.mark.asyncio
    async def test_send_status_callback(self, callback_service):
        """상태 콜백 전송"""
        with patch.object(callback_service, "send_callback", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            status_data = {
                "is_running": True,
                "is_paused": False,
                "current_price": 50000.0,
            }

            result = await callback_service.send_status(
                bot_name="test-bot",
                status=status_data,
            )

            assert result is True
            mock_send.assert_called_once()
            call_args = mock_send.call_args[0][0]
            assert call_args.event_type == "status"
            assert call_args.data["is_running"] is True


class TestN8NCallbackPayload:
    """N8NCallbackPayload 테스트"""

    def test_payload_creation(self):
        """페이로드 생성"""
        payload = N8NCallbackPayload(
            event_type="signal",
            bot_name="test-bot",
            data={"signal": "LONG"},
        )

        assert payload.event_type == "signal"
        assert payload.bot_name == "test-bot"
        assert payload.data["signal"] == "LONG"
        assert isinstance(payload.timestamp, datetime)

    def test_payload_json_serialization(self):
        """페이로드 JSON 직렬화"""
        payload = N8NCallbackPayload(
            event_type="trade",
            bot_name="test-bot",
            data={"action": "OPEN"},
        )

        json_data = payload.model_dump_json()
        assert "trade" in json_data
        assert "test-bot" in json_data


# =============================================================================
# src/api/services/n8n_callback.py 커버리지 테스트 (from test_api_coverage.py)
# =============================================================================


class TestN8NCallbackServiceSession:
    """N8NCallbackService 세션 관리 테스트 (lines 54-58, 65-68)"""

    @pytest.mark.asyncio
    async def test_get_session_creates_new(self):
        """세션이 없을 때 새로 생성 (lines 54-58)"""
        service = N8NCallbackService(webhook_url="https://example.com/webhook")
        assert service._session is None

        session = await service._get_session()
        assert isinstance(session, aiohttp.ClientSession)
        # 정리
        await session.close()

    @pytest.mark.asyncio
    async def test_get_session_reuses_existing(self):
        """기존 세션 재사용"""
        service = N8NCallbackService(webhook_url="https://example.com/webhook")

        session1 = await service._get_session()
        session2 = await service._get_session()
        assert session1 is session2
        await session1.close()

    @pytest.mark.asyncio
    async def test_close_session(self):
        """세션 종료 (lines 65-68)"""
        service = N8NCallbackService(webhook_url="https://example.com/webhook")

        # 세션 생성
        session = await service._get_session()
        assert service._session is not None

        # 세션 종료
        await service.close()
        assert service._session is None

    @pytest.mark.asyncio
    async def test_close_no_session(self):
        """세션 없을 때 close 호출"""
        service = N8NCallbackService(webhook_url="https://example.com/webhook")
        # 세션 없는 상태에서 close - 에러 없어야 함
        await service.close()
        assert service._session is None


class TestN8NCallbackSendErrors:
    """send_callback 에러 케이스 (lines 97-107)"""

    @pytest.mark.asyncio
    async def test_send_callback_http_error_status(self):
        """HTTP 에러 응답 (lines 97-100)"""
        service = N8NCallbackService(webhook_url="https://example.com/webhook")

        mock_response = MagicMock()
        mock_response.status = 500

        mock_post_cm = MagicMock()
        mock_post_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.post.return_value = mock_post_cm

        with patch.object(service, "_get_session", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_session

            payload = N8NCallbackPayload(
                event_type="signal",
                bot_name="test-bot",
                data={"signal": "LONG"},
            )
            result = await service.send_callback(payload)
            assert result == CallbackResult.FAILED

    @pytest.mark.asyncio
    async def test_send_callback_client_error(self):
        """네트워크 에러 (lines 102-104)"""
        service = N8NCallbackService(webhook_url="https://example.com/webhook")

        with patch.object(service, "_get_session", new_callable=AsyncMock) as mock_get:
            mock_session = MagicMock()
            mock_session.post.side_effect = aiohttp.ClientError("Connection refused")
            mock_get.return_value = mock_session

            payload = N8NCallbackPayload(
                event_type="signal",
                bot_name="test-bot",
                data={"signal": "LONG"},
            )
            result = await service.send_callback(payload)
            assert result == CallbackResult.FAILED

    @pytest.mark.asyncio
    async def test_send_callback_general_exception(self):
        """일반 예외 (lines 105-107)"""
        service = N8NCallbackService(webhook_url="https://example.com/webhook")

        with patch.object(service, "_get_session", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = Exception("Unexpected error")

            payload = N8NCallbackPayload(
                event_type="signal",
                bot_name="test-bot",
                data={"signal": "LONG"},
            )
            result = await service.send_callback(payload)
            assert result == CallbackResult.FAILED


class TestN8NCallbackSendTradeWithOptionals:
    """send_trade 옵셔널 파라미터 테스트 (lines 172, 174, 176)"""

    @pytest.mark.asyncio
    async def test_send_trade_with_pnl_and_quantity(self):
        """pnl과 quantity가 포함된 거래 콜백"""
        service = N8NCallbackService(webhook_url="https://example.com/webhook")

        with patch.object(service, "send_callback", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            result = await service.send_trade(
                bot_name="test-bot",
                action="CLOSE",
                side="LONG",
                price=50000.0,
                pnl=100.0,
                quantity=0.01,
                metadata={"reason": "TP"},
            )

            assert result is True
            call_payload = mock_send.call_args[0][0]
            assert call_payload.data["pnl"] == 100.0
            assert call_payload.data["quantity"] == 0.01
            assert call_payload.data["reason"] == "TP"

    @pytest.mark.asyncio
    async def test_send_trade_without_optionals(self):
        """옵셔널 파라미터 없는 거래 콜백"""
        service = N8NCallbackService(webhook_url="https://example.com/webhook")

        with patch.object(service, "send_callback", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            result = await service.send_trade(
                bot_name="test-bot",
                action="OPEN",
                side="SHORT",
                price=3000.0,
            )

            assert result is True
            call_payload = mock_send.call_args[0][0]
            assert "pnl" not in call_payload.data
            assert "quantity" not in call_payload.data


class TestN8NCallbackInitMasking:
    """URL 마스킹 테스트"""

    def test_init_short_url(self):
        """짧은 URL 마스킹"""
        service = N8NCallbackService(webhook_url="http://short")
        assert service.is_enabled is True

    def test_init_long_url(self):
        """긴 URL 마스킹"""
        long_url = "https://n8n.example.com/webhook/very-long-path-here"
        service = N8NCallbackService(webhook_url=long_url)
        assert service.is_enabled is True


# =============================================================================
# Fix #6: n8n ClientError Log Level = WARNING (not ERROR)
# =============================================================================


class TestN8NClientErrorLogLevel:
    """aiohttp.ClientError는 WARNING으로 로그"""

    @pytest.mark.asyncio
    async def test_client_error_logs_warning_not_error(self):
        """ClientError 발생 시 logger.warning 사용 확인"""
        service = N8NCallbackService(webhook_url="https://example.com/webhook")

        with patch.object(service, "_get_session", new_callable=AsyncMock) as mock_get:
            mock_session = MagicMock()
            mock_session.post.side_effect = aiohttp.ClientError("Connection refused")
            mock_get.return_value = mock_session

            payload = N8NCallbackPayload(
                event_type="signal",
                bot_name="test-bot",
                data={"signal": "LONG"},
            )

            # Capture loguru output
            import loguru
            messages = []
            def sink(message):
                messages.append(message)
            handler_id = loguru.logger.add(sink, level="DEBUG")

            try:
                result = await service.send_callback(payload)
                assert result == CallbackResult.FAILED

                # WARNING 레벨 메시지가 있어야 함
                warning_msgs = [m for m in messages if "WARNING" in str(m)]
                assert any("n8n 콜백 발송 실패 (네트워크)" in str(m) for m in warning_msgs)

                # ERROR 레벨의 "n8n 콜백 발송" 메시지는 없어야 함
                error_n8n = [
                    m for m in messages
                    if "ERROR" in str(m) and "n8n 콜백 발송" in str(m)
                ]
                assert len(error_n8n) == 0
            finally:
                loguru.logger.remove(handler_id)
