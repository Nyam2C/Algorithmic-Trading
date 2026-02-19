"""Microprice Smart Limit executor 통합 테스트."""
from unittest.mock import AsyncMock

import pytest

from src.config import TradingConfig
from src.trading.executor import TradingExecutor


@pytest.fixture
def _microprice_config():
    return TradingConfig(
        bot_name="mp-test",
        binance_api_key="k",
        binance_secret_key="s",
        gemini_api_key="g",
        discord_webhook_url="https://x.com",
        symbol="BTCUSDT",
        leverage=10,
        position_size_pct=0.05,
        take_profit_pct=0.008,
        stop_loss_pct=0.004,
    )


@pytest.fixture
def _mp_client():
    """Binance mock client with limit/cancel/market/status support."""
    from unittest.mock import Mock

    client = Mock()
    client.set_leverage = AsyncMock(return_value={"leverage": 10})
    client.get_position = AsyncMock(return_value=None)
    client.create_market_order = AsyncMock(return_value={
        "orderId": 99999, "symbol": "BTCUSDT", "status": "FILLED",
    })
    client.create_limit_order = AsyncMock(return_value={
        "orderId": 55555, "symbol": "BTCUSDT", "status": "NEW",
    })
    client.get_order_status = AsyncMock(return_value={
        "orderId": 55555, "status": "FILLED",
    })
    client.cancel_order = AsyncMock(return_value={"orderId": 55555})
    client.create_stop_market_order = AsyncMock(return_value={
        "orderId": 77777, "type": "STOP_MARKET", "status": "NEW",
    })
    client.create_take_profit_market_order = AsyncMock(return_value={
        "orderId": 88888, "type": "TAKE_PROFIT_MARKET", "status": "NEW",
    })
    client.cancel_all_open_orders = AsyncMock(return_value={"code": 200})
    client.close_position = AsyncMock(return_value={
        "orderId": 67890, "status": "FILLED", "executedQty": "0.01",
    })
    return client


def _make_microprice_data(**overrides):
    """기본 microprice_data dict 생성."""
    data = {
        "best_bid": 99_990.0,
        "best_ask": 100_010.0,
        "bid_vol": 15.0,
        "ask_vol": 10.0,
        "atr_1m": 50.0,
        "liquidity_tier": "high",
        "offset_factor": 0.1,
        "slide_factor": 0.5,
    }
    data.update(overrides)
    return data


class TestMicropriceLimit:
    """Microprice Smart Limit 실행 테스트."""

    @pytest.mark.asyncio
    async def test_microprice_first_fill(self, _mp_client, _microprice_config):
        """1차 지정가 즉시 체결."""
        executor = TradingExecutor(_mp_client, _microprice_config)

        order = await executor.open_position(
            "LONG", 100_000.0, entry_atr=250.0,
            microprice_data=_make_microprice_data(),
        )

        assert order is not None
        assert order["orderId"] == 55555
        _mp_client.create_limit_order.assert_called_once()
        # Market order는 호출되지 않아야 함
        _mp_client.create_market_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_microprice_slide_fill(self, _mp_client, _microprice_config):
        """1차 미체결 → slide → 2차 체결."""
        # 2차 limit order는 다른 orderId
        _mp_client.create_limit_order = AsyncMock(
            side_effect=[
                {"orderId": 55555, "status": "NEW"},
                {"orderId": 55556, "status": "NEW"},
            ]
        )

        executor = TradingExecutor(_mp_client, _microprice_config)

        # _wait_for_fill: 1차 False, 2차 True
        original_wait = executor._wait_for_fill
        call_count = 0

        async def mock_wait(order_id, timeout=30, check_interval=2):
            nonlocal call_count
            call_count += 1
            return call_count >= 2  # 1차 False, 2차 True

        executor._wait_for_fill = mock_wait  # type: ignore[assignment]

        order = await executor.open_position(
            "LONG", 100_000.0, entry_atr=250.0,
            microprice_data=_make_microprice_data(liquidity_tier="medium"),
        )

        assert order is not None
        assert order["orderId"] == 55556
        assert _mp_client.cancel_order.call_count >= 1
        executor._wait_for_fill = original_wait

    @pytest.mark.asyncio
    async def test_microprice_market_fallback(self, _mp_client, _microprice_config):
        """1차+slide 미체결 → Market fallback (high tier)."""
        executor = TradingExecutor(_mp_client, _microprice_config)
        # 모든 _wait_for_fill → False (미체결)
        executor._wait_for_fill = AsyncMock(return_value=False)  # type: ignore[assignment]

        order = await executor.open_position(
            "LONG", 100_000.0, entry_atr=250.0,
            microprice_data=_make_microprice_data(liquidity_tier="high"),
        )

        assert order is not None
        # Market fallback으로 체결
        _mp_client.create_market_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_microprice_low_liquidity_no_market(
        self, _mp_client, _microprice_config
    ):
        """Low liquidity: 미체결 시 Market 금지 → None 반환."""
        executor = TradingExecutor(_mp_client, _microprice_config)
        # 모든 _wait_for_fill → False (미체결)
        executor._wait_for_fill = AsyncMock(return_value=False)  # type: ignore[assignment]

        order = await executor.open_position(
            "SHORT", 100_000.0, entry_atr=250.0,
            microprice_data=_make_microprice_data(liquidity_tier="low"),
        )

        # RuntimeError → open_position try/except → None
        assert order is None
        _mp_client.create_market_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_microprice_crossed_book_fallback(
        self, _mp_client, _microprice_config
    ):
        """Crossed book → microprice None → Market fallback."""
        executor = TradingExecutor(_mp_client, _microprice_config)
        order = await executor.open_position(
            "LONG", 100_000.0, entry_atr=250.0,
            microprice_data=_make_microprice_data(
                best_bid=100_010.0, best_ask=99_990.0  # crossed
            ),
        )

        assert order is not None
        _mp_client.create_market_order.assert_called()

    @pytest.mark.asyncio
    async def test_microprice_short_limit_price(self, _mp_client, _microprice_config):
        """SHORT: 지정가가 microprice보다 높아야 함."""
        executor = TradingExecutor(_mp_client, _microprice_config)

        await executor.open_position(
            "SHORT", 100_000.0, entry_atr=250.0,
            microprice_data=_make_microprice_data(),
        )

        call_args = _mp_client.create_limit_order.call_args
        limit_price = call_args[1]["price"]
        # SHORT: microprice + ATR*0.1
        # microprice ≈ 99_990*10 + 100_010*15 / 25 ≈ 100_002
        # limit = 100_002 + 50*0.1 = 100_007
        assert limit_price > 100_000.0

    @pytest.mark.asyncio
    async def test_microprice_none_uses_market(self, _mp_client, _microprice_config):
        """microprice_data=None → 기존 Market 주문 경로."""
        executor = TradingExecutor(_mp_client, _microprice_config)
        order = await executor.open_position(
            "LONG", 100_000.0, entry_atr=250.0,
            microprice_data=None,
        )

        assert order is not None
        _mp_client.create_market_order.assert_called_once()
        _mp_client.create_limit_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_microprice_no_slippage_detection(
        self, _mp_client, _microprice_config
    ):
        """Microprice limit은 slippage detection 건너뜀."""
        _mp_client.create_limit_order = AsyncMock(return_value={
            "orderId": 55555, "status": "FILLED",
            "avgPrice": "99950.00",  # 큰 차이가 있어도
        })
        _mp_client.get_order_status = AsyncMock(return_value={
            "orderId": 55555, "status": "FILLED",
        })

        executor = TradingExecutor(_mp_client, _microprice_config)
        order = await executor.open_position(
            "LONG", 100_000.0, entry_atr=250.0,
            microprice_data=_make_microprice_data(),
        )

        # 슬리피지로 인한 포지션 청산이 발생하지 않아야 함
        assert order is not None
        _mp_client.close_position.assert_not_called()

    @pytest.mark.asyncio
    async def test_microprice_custom_offset_factor(
        self, _mp_client, _microprice_config
    ):
        """커스텀 offset_factor가 적용되는지 확인."""
        executor = TradingExecutor(_mp_client, _microprice_config)

        await executor.open_position(
            "LONG", 100_000.0, entry_atr=250.0,
            microprice_data=_make_microprice_data(offset_factor=0.2),
        )

        call_args = _mp_client.create_limit_order.call_args
        limit_price = call_args[1]["price"]
        # offset=0.2 이면 더 큰 오프셋 → 더 낮은 가격
        from src.trading.microprice import calculate_microprice
        mp = calculate_microprice(99_990.0, 100_010.0, 15.0, 10.0)
        expected = round(mp - 50.0 * 0.2, 2)  # type: ignore[operator]
        assert limit_price == expected
