"""Tests for position reconciliation on bot startup."""
from unittest.mock import AsyncMock, Mock

import pytest

from src.bot_config import BotConfig
from src.bot_instance import BotInstance


def _make_bot_instance(
    binance_client=None,
    redis_state_manager=None,
) -> BotInstance:
    """BotInstance 생성 헬퍼."""
    config = BotConfig(bot_name="test-bot", symbol="BTCUSDT")
    client = binance_client or Mock()
    return BotInstance(
        config=config,
        binance_api_key="test",
        binance_secret_key="test",
        gemini_api_key="test",
        discord_webhook_url="https://test.com",
        binance_client=client,
        redis_state_manager=redis_state_manager,
    )


class TestReconcilePosition:
    """_reconcile_position 테스트"""

    @pytest.mark.asyncio
    async def test_orphan_position_adopted(self):
        """거래소에만 포지션이 있으면 Redis에 저장하고 내부 상태 갱신."""
        binance = Mock()
        binance.get_position = AsyncMock(return_value={
            "symbol": "BTCUSDT",
            "position_amt": 0.01,
            "entry_price": 98000.0,
            "unrealized_pnl": 50.0,
            "leverage": 10,
            "side": "LONG",
        })

        redis_mgr = Mock()
        redis_mgr.load_position = AsyncMock(return_value=None)
        redis_mgr.save_position = AsyncMock(return_value=True)

        bot = _make_bot_instance(binance_client=binance, redis_state_manager=redis_mgr)

        await bot._reconcile_position()

        # 내부 포지션 상태가 거래소 값으로 설정됨
        assert bot._current_position is not None
        assert bot._current_position["side"] == "LONG"
        assert bot._current_position["entry_price"] == 98000.0

        # Redis에 저장됨
        redis_mgr.save_position.assert_called_once()

    @pytest.mark.asyncio
    async def test_ghost_position_removed(self):
        """Redis에만 포지션이 있고 거래소에 없으면 Redis에서 삭제."""
        binance = Mock()
        binance.get_position = AsyncMock(return_value=None)

        redis_mgr = Mock()
        redis_mgr.load_position = AsyncMock(return_value={
            "side": "SHORT",
            "entry_price": 99000.0,
            "quantity": 0.01,
        })
        redis_mgr.delete_position = AsyncMock(return_value=True)

        bot = _make_bot_instance(binance_client=binance, redis_state_manager=redis_mgr)

        await bot._reconcile_position()

        # 내부 포지션 없어야 함
        assert bot._current_position is None

        # Redis에서 삭제됨
        redis_mgr.delete_position.assert_called_once()

    @pytest.mark.asyncio
    async def test_both_exist_sync_to_exchange(self):
        """양쪽 다 포지션이 있으면 거래소 값으로 동기화."""
        binance = Mock()
        binance.get_position = AsyncMock(return_value={
            "symbol": "BTCUSDT",
            "position_amt": 0.02,
            "entry_price": 97000.0,
            "unrealized_pnl": 100.0,
            "leverage": 10,
            "side": "LONG",
        })

        redis_mgr = Mock()
        redis_mgr.load_position = AsyncMock(return_value={
            "side": "LONG",
            "entry_price": 96000.0,  # 다른 값
            "quantity": 0.01,
        })
        redis_mgr.save_position = AsyncMock(return_value=True)

        bot = _make_bot_instance(binance_client=binance, redis_state_manager=redis_mgr)

        await bot._reconcile_position()

        # 거래소 값으로 동기화됨
        assert bot._current_position is not None
        assert bot._current_position["entry_price"] == 97000.0
        assert bot._current_position["side"] == "LONG"

        # Redis에 거래소 값 저장됨
        redis_mgr.save_position.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_position_anywhere(self):
        """양쪽 다 포지션이 없으면 아무 동작 없음."""
        binance = Mock()
        binance.get_position = AsyncMock(return_value=None)

        redis_mgr = Mock()
        redis_mgr.load_position = AsyncMock(return_value=None)
        redis_mgr.save_position = AsyncMock()
        redis_mgr.delete_position = AsyncMock()

        bot = _make_bot_instance(binance_client=binance, redis_state_manager=redis_mgr)

        await bot._reconcile_position()

        assert bot._current_position is None
        redis_mgr.save_position.assert_not_called()
        redis_mgr.delete_position.assert_not_called()
