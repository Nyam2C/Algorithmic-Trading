"""Tests for exchange-side STOP_MARKET and TAKE_PROFIT_MARKET orders."""
from unittest.mock import AsyncMock, Mock

import pytest

from src.config import TradingConfig
from src.exchange.binance import BinanceTestnetClient
from src.trading.executor import TradingExecutor


@pytest.fixture
def mock_async_client():
    """Mock AsyncClient (inner binance client)."""
    client = Mock()
    client.futures_create_order = AsyncMock(return_value={
        "orderId": 55555,
        "symbol": "BTCUSDT",
        "type": "STOP_MARKET",
        "status": "NEW",
    })
    client.futures_cancel_all_open_orders = AsyncMock(return_value={
        "code": 200,
        "msg": "The operation of cancel all open order is done.",
    })
    return client


@pytest.fixture
def binance_client(mock_async_client):
    """BinanceTestnetClient with mocked inner client."""
    bc = BinanceTestnetClient(api_key="test", secret_key="test", testnet=True)
    bc._client = mock_async_client
    return bc


@pytest.fixture
def mock_config():
    """TradingConfig for tests."""
    return TradingConfig(
        bot_name="test-bot",
        binance_api_key="test_key",
        binance_secret_key="test_secret",
        gemini_api_key="test_gemini",
        discord_webhook_url="https://test.com",
        symbol="BTCUSDT",
        leverage=10,
        position_size_pct=0.05,
        take_profit_pct=0.008,
        stop_loss_pct=0.004,
        use_atr_tp_sl=True,
        atr_tp_multiplier=2.0,
        atr_sl_multiplier=1.0,
    )


class TestCreateStopMarketOrder:
    """create_stop_market_order 테스트"""

    @pytest.mark.asyncio
    async def test_stop_market_long_position(self, binance_client, mock_async_client):
        """LONG 포지션 스톱마켓 주문 생성"""
        result = await binance_client.create_stop_market_order(
            symbol="BTCUSDT",
            side="SELL",
            quantity=0.01,
            stop_price=99000.0,
        )

        assert result["orderId"] == 55555
        mock_async_client.futures_create_order.assert_called_once()
        call_kwargs = mock_async_client.futures_create_order.call_args[1]
        assert call_kwargs["symbol"] == "BTCUSDT"
        assert call_kwargs["side"] == "SELL"
        assert call_kwargs["type"] == "STOP_MARKET"
        assert call_kwargs["stopPrice"] == 99000.0
        assert call_kwargs["quantity"] == 0.01
        assert call_kwargs["closePosition"] == "true"

    @pytest.mark.asyncio
    async def test_stop_market_short_position(self, binance_client, mock_async_client):
        """SHORT 포지션 스톱마켓 주문 생성"""
        result = await binance_client.create_stop_market_order(
            symbol="BTCUSDT",
            side="BUY",
            quantity=0.01,
            stop_price=101000.0,
        )

        assert result is not None
        call_kwargs = mock_async_client.futures_create_order.call_args[1]
        assert call_kwargs["side"] == "BUY"
        assert call_kwargs["stopPrice"] == 101000.0

    @pytest.mark.asyncio
    async def test_stop_market_api_error(self, binance_client, mock_async_client):
        """API 에러 시 예외 전파"""
        mock_async_client.futures_create_order = AsyncMock(
            side_effect=Exception("API Error")
        )

        with pytest.raises(Exception, match="API Error"):
            await binance_client.create_stop_market_order(
                symbol="BTCUSDT",
                side="SELL",
                quantity=0.01,
                stop_price=99000.0,
            )


class TestCreateTakeProfitMarketOrder:
    """create_take_profit_market_order 테스트"""

    @pytest.mark.asyncio
    async def test_tp_market_long_position(self, binance_client, mock_async_client):
        """LONG 포지션 TP 마켓 주문 생성"""
        mock_async_client.futures_create_order = AsyncMock(return_value={
            "orderId": 66666,
            "symbol": "BTCUSDT",
            "type": "TAKE_PROFIT_MARKET",
            "status": "NEW",
        })

        result = await binance_client.create_take_profit_market_order(
            symbol="BTCUSDT",
            side="SELL",
            quantity=0.01,
            stop_price=101000.0,
        )

        assert result["orderId"] == 66666
        call_kwargs = mock_async_client.futures_create_order.call_args[1]
        assert call_kwargs["type"] == "TAKE_PROFIT_MARKET"
        assert call_kwargs["stopPrice"] == 101000.0
        assert call_kwargs["closePosition"] == "true"


class TestCancelAllOpenOrders:
    """cancel_all_open_orders 테스트"""

    @pytest.mark.asyncio
    async def test_cancel_all_orders(self, binance_client, mock_async_client):
        """모든 주문 취소"""
        result = await binance_client.cancel_all_open_orders(symbol="BTCUSDT")

        assert result is not None
        mock_async_client.futures_cancel_all_open_orders.assert_called_once_with(
            symbol="BTCUSDT"
        )

    @pytest.mark.asyncio
    async def test_cancel_all_orders_api_error(self, binance_client, mock_async_client):
        """API 에러 시 예외 전파"""
        mock_async_client.futures_cancel_all_open_orders = AsyncMock(
            side_effect=Exception("API Error")
        )

        with pytest.raises(Exception, match="API Error"):
            await binance_client.cancel_all_open_orders(symbol="BTCUSDT")


class TestPlaceExchangeTpSl:
    """executor._place_exchange_tp_sl 테스트"""

    @pytest.fixture
    def mock_binance_client(self):
        """Mock binance client for executor tests."""
        client = Mock()
        client.set_leverage = AsyncMock(return_value={"leverage": 10})
        client.get_position = AsyncMock(return_value=None)
        client.create_market_order = AsyncMock(return_value={
            "orderId": 12345,
            "symbol": "BTCUSDT",
            "side": "BUY",
            "status": "FILLED",
        })
        client.create_stop_market_order = AsyncMock(return_value={
            "orderId": 77777,
            "type": "STOP_MARKET",
            "status": "NEW",
        })
        client.create_take_profit_market_order = AsyncMock(return_value={
            "orderId": 88888,
            "type": "TAKE_PROFIT_MARKET",
            "status": "NEW",
        })
        client.cancel_all_open_orders = AsyncMock(return_value={"code": 200})
        return client

    @pytest.mark.asyncio
    async def test_place_exchange_tp_sl_long_atr(self, mock_binance_client, mock_config):
        """LONG 포지션 ATR 기반 TP/SL 주문"""
        executor = TradingExecutor(mock_binance_client, mock_config)

        await executor._place_exchange_tp_sl(
            symbol="BTCUSDT",
            side="LONG",
            quantity=0.01,
            entry_price=100000.0,
            entry_atr=500.0,
        )

        # SL: SELL, stop_price = 100000 - 500*1.0 = 99500
        sl_call = mock_binance_client.create_stop_market_order.call_args[1]
        assert sl_call["side"] == "SELL"
        assert sl_call["stop_price"] == 99500.0

        # TP: SELL, stop_price = 100000 + 500*2.0 = 101000
        tp_call = mock_binance_client.create_take_profit_market_order.call_args[1]
        assert tp_call["side"] == "SELL"
        assert tp_call["stop_price"] == 101000.0

    @pytest.mark.asyncio
    async def test_place_exchange_tp_sl_short_atr(self, mock_binance_client, mock_config):
        """SHORT 포지션 ATR 기반 TP/SL 주문"""
        executor = TradingExecutor(mock_binance_client, mock_config)

        await executor._place_exchange_tp_sl(
            symbol="BTCUSDT",
            side="SHORT",
            quantity=0.01,
            entry_price=100000.0,
            entry_atr=500.0,
        )

        # SL: BUY, stop_price = 100000 + 500*1.0 = 100500
        sl_call = mock_binance_client.create_stop_market_order.call_args[1]
        assert sl_call["side"] == "BUY"
        assert sl_call["stop_price"] == 100500.0

        # TP: BUY, stop_price = 100000 - 500*2.0 = 99000
        tp_call = mock_binance_client.create_take_profit_market_order.call_args[1]
        assert tp_call["side"] == "BUY"
        assert tp_call["stop_price"] == 99000.0

    @pytest.mark.asyncio
    async def test_place_exchange_tp_sl_fixed_pct(self, mock_binance_client):
        """ATR 없을 때 고정 퍼센트 기반 TP/SL"""
        config = TradingConfig(
            bot_name="test-bot",
            binance_api_key="test_key",
            binance_secret_key="test_secret",
            gemini_api_key="test_gemini",
            discord_webhook_url="https://test.com",
            symbol="BTCUSDT",
            leverage=10,
            take_profit_pct=0.008,
            stop_loss_pct=0.004,
            use_atr_tp_sl=False,
        )
        executor = TradingExecutor(mock_binance_client, config)

        await executor._place_exchange_tp_sl(
            symbol="BTCUSDT",
            side="LONG",
            quantity=0.01,
            entry_price=100000.0,
            entry_atr=None,
        )

        # SL: 100000 * (1 - 0.004) = 99600
        sl_call = mock_binance_client.create_stop_market_order.call_args[1]
        assert sl_call["stop_price"] == 99600.0

        # TP: 100000 * (1 + 0.008) = 100800
        tp_call = mock_binance_client.create_take_profit_market_order.call_args[1]
        assert tp_call["stop_price"] == 100800.0


