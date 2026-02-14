"""
n8n 콜백 서비스 연결(wiring) 테스트

main.py에서 N8NCallbackService가 MultiBotManager 콜백에 올바르게 연결되는지 테스트합니다.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.services.n8n_callback import CallbackResult, N8NCallbackService
from src.bot_manager import MultiBotManager


class TestN8NCallbackWiring:
    """N8NCallbackService와 MultiBotManager 연결 테스트"""

    def test_signal_callback_registered(self):
        """시그널 콜백이 MultiBotManager에 등록되는지 확인"""
        manager = MagicMock(spec=MultiBotManager)
        callback_service = N8NCallbackService(webhook_url="https://n8n.example.com/webhook")

        async def _signal_cb(bot_name: str, signal: str, price: float) -> None:
            await callback_service.send_signal(bot_name, signal, price)

        manager.set_on_signal_callback(_signal_cb)
        manager.set_on_signal_callback.assert_called_once_with(_signal_cb)

    def test_trade_callback_registered(self):
        """거래 콜백이 MultiBotManager에 등록되는지 확인"""
        manager = MagicMock(spec=MultiBotManager)
        callback_service = N8NCallbackService(webhook_url="https://n8n.example.com/webhook")

        async def _trade_cb(
            bot_name: str, action: str, side: str, price: float, pnl: float | None
        ) -> None:
            await callback_service.send_trade(bot_name, action, side, price, pnl=pnl)

        manager.set_on_trade_callback(_trade_cb)
        manager.set_on_trade_callback.assert_called_once_with(_trade_cb)

    def test_error_callback_registered(self):
        """에러 콜백이 MultiBotManager에 등록되는지 확인"""
        manager = MagicMock(spec=MultiBotManager)
        callback_service = N8NCallbackService(webhook_url="https://n8n.example.com/webhook")

        async def _error_cb(bot_name: str, error: Exception) -> None:
            await callback_service.send_error(bot_name, error)

        manager.set_on_error_callback(_error_cb)
        manager.set_on_error_callback.assert_called_once_with(_error_cb)

    @pytest.mark.asyncio
    async def test_signal_callback_invokes_service(self):
        """시그널 콜백이 N8NCallbackService.send_signal을 호출하는지 확인"""
        callback_service = N8NCallbackService(webhook_url="https://n8n.example.com/webhook")

        with patch.object(
            callback_service, "send_signal", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = CallbackResult.SUCCESS

            async def _signal_cb(bot_name: str, signal: str, price: float) -> None:
                await callback_service.send_signal(bot_name, signal, price)

            await _signal_cb("btc-bot", "LONG", 50000.0)

            mock_send.assert_called_once_with("btc-bot", "LONG", 50000.0)

    @pytest.mark.asyncio
    async def test_trade_callback_invokes_service(self):
        """거래 콜백이 N8NCallbackService.send_trade를 호출하는지 확인"""
        callback_service = N8NCallbackService(webhook_url="https://n8n.example.com/webhook")

        with patch.object(
            callback_service, "send_trade", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = CallbackResult.SUCCESS

            async def _trade_cb(
                bot_name: str, action: str, side: str, price: float, pnl: float | None
            ) -> None:
                await callback_service.send_trade(bot_name, action, side, price, pnl=pnl)

            await _trade_cb("btc-bot", "OPEN", "LONG", 50000.0, None)

            mock_send.assert_called_once_with(
                "btc-bot", "OPEN", "LONG", 50000.0, pnl=None
            )

    @pytest.mark.asyncio
    async def test_error_callback_invokes_service(self):
        """에러 콜백이 N8NCallbackService.send_error를 호출하는지 확인"""
        callback_service = N8NCallbackService(webhook_url="https://n8n.example.com/webhook")

        with patch.object(
            callback_service, "send_error", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = CallbackResult.SUCCESS

            async def _error_cb(bot_name: str, error: Exception) -> None:
                await callback_service.send_error(bot_name, error)

            test_error = ValueError("test error")
            await _error_cb("btc-bot", test_error)

            mock_send.assert_called_once_with("btc-bot", test_error)

    @pytest.mark.asyncio
    async def test_disabled_callback_returns_disabled(self):
        """URL 없으면 DISABLED 반환"""
        callback_service = N8NCallbackService(webhook_url=None)

        result = await callback_service.send_signal("btc-bot", "LONG", 50000.0)
        assert result == CallbackResult.DISABLED

    @pytest.mark.asyncio
    async def test_callback_error_does_not_propagate(self):
        """콜백 에러가 전파되지 않는지 확인"""
        callback_service = N8NCallbackService(webhook_url="https://n8n.example.com/webhook")

        with patch.object(
            callback_service, "send_signal", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = CallbackResult.FAILED

            async def _signal_cb(bot_name: str, signal: str, price: float) -> None:
                await callback_service.send_signal(bot_name, signal, price)

            # 에러가 발생하지 않아야 함
            await _signal_cb("btc-bot", "LONG", 50000.0)

    @pytest.mark.asyncio
    async def test_close_session_cleanup(self):
        """종료 시 세션이 정리되는지 확인"""
        callback_service = N8NCallbackService(webhook_url="https://n8n.example.com/webhook")

        # 세션 생성
        session = await callback_service._get_session()
        assert session is not None

        # 종료
        await callback_service.close()
        assert callback_service._session is None

    @pytest.mark.asyncio
    async def test_trade_callback_with_pnl(self):
        """PnL이 포함된 거래 콜백"""
        callback_service = N8NCallbackService(webhook_url="https://n8n.example.com/webhook")

        with patch.object(
            callback_service, "send_trade", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = CallbackResult.SUCCESS

            async def _trade_cb(
                bot_name: str, action: str, side: str, price: float, pnl: float | None
            ) -> None:
                await callback_service.send_trade(bot_name, action, side, price, pnl=pnl)

            await _trade_cb("btc-bot", "CLOSE", "LONG", 51000.0, 100.50)

            mock_send.assert_called_once_with(
                "btc-bot", "CLOSE", "LONG", 51000.0, pnl=100.50
            )
