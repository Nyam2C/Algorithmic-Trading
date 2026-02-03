"""
n8n 콜백 서비스 테스트

n8n 웹훅 콜백 발송 테스트입니다.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from src.api.services.n8n_callback import N8NCallbackService
from src.api.schemas.n8n import N8NCallbackPayload


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
        """콜백 비활성화 시 전송 안 함"""
        payload = N8NCallbackPayload(
            event_type="signal",
            bot_name="test-bot",
            data={"signal": "LONG"},
        )

        result = await callback_service_no_url.send_callback(payload)

        assert result is False

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

            assert result is True
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
