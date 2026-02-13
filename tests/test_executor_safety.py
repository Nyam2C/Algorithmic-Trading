"""Tests for executor P1 safety fixes.

Issue 1.1: Balance fallback safety
Issue 1.4: Minimum order quantity validation
Issue 1.3: Slippage protection
Issue 2.3: Partial fill handling
"""
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest

from src.config import TradingConfig
from src.trading.executor import TradingExecutor


@pytest.fixture
def mock_config():
    """Mock 설정 생성"""
    return TradingConfig(
        bot_name="test-bot",
        binance_api_key="test_key",
        binance_secret_key="test_secret",
        gemini_api_key="test_gemini",
        discord_webhook_url="https://test.com",
        symbol="BTCUSDT",
        leverage=15,
        position_size_pct=0.05,
        take_profit_pct=0.004,
        stop_loss_pct=0.004,
    )


@pytest.fixture
def mock_config_real_balance():
    """use_real_balance=True 설정"""
    return TradingConfig(
        bot_name="test-bot",
        binance_api_key="test_key",
        binance_secret_key="test_secret",
        gemini_api_key="test_gemini",
        discord_webhook_url="https://test.com",
        symbol="BTCUSDT",
        leverage=15,
        position_size_pct=0.05,
        use_real_balance=True,
    )


@pytest.fixture
def mock_binance_client():
    """Mock Binance 클라이언트"""
    client = Mock()
    client.set_leverage = AsyncMock(return_value={"leverage": 15})
    client.get_position = AsyncMock(return_value=None)
    client.create_market_order = AsyncMock(return_value={
        "orderId": 12345,
        "symbol": "BTCUSDT",
        "side": "BUY",
        "status": "FILLED",
    })
    client.close_position = AsyncMock(return_value={
        "orderId": 67890,
        "status": "FILLED",
        "executedQty": "0.01",
    })
    client.get_account_balance = AsyncMock(return_value={
        "asset": "USDT",
        "balance": 5000.0,
        "available": 4500.0,
        "unrealized_pnl": 100.0,
    })
    client.create_stop_market_order = AsyncMock(return_value={
        "orderId": 77777, "type": "STOP_MARKET", "status": "NEW",
    })
    client.create_take_profit_market_order = AsyncMock(return_value={
        "orderId": 88888, "type": "TAKE_PROFIT_MARKET", "status": "NEW",
    })
    client.cancel_all_open_orders = AsyncMock(return_value={
        "code": 200, "msg": "success",
    })
    return client


# =============================================================================
# Issue 1.1: Balance Fallback Safety Tests
# =============================================================================


class TestBalanceFallbackSafety:
    """Issue 1.1: API 실패 시 잔고 fallback 안전성 테스트"""

    @pytest.mark.asyncio
    async def test_balance_fallback_api_fail_no_cache(
        self, mock_binance_client, mock_config_real_balance
    ):
        """API 실패 + 캐시 없음 -> RuntimeError"""
        mock_binance_client.get_account_balance = AsyncMock(
            side_effect=Exception("API Error")
        )
        executor = TradingExecutor(mock_binance_client, mock_config_real_balance)

        with pytest.raises(RuntimeError, match="잔고 조회 실패"):
            await executor._calculate_position_size_with_balance(100000.0)

    @pytest.mark.asyncio
    async def test_balance_fallback_api_fail_fresh_cache(
        self, mock_binance_client, mock_config_real_balance
    ):
        """API 실패 + 캐시 5분 이내 -> 캐시 사용"""
        mock_binance_client.get_account_balance = AsyncMock(
            side_effect=Exception("API Error")
        )
        executor = TradingExecutor(mock_binance_client, mock_config_real_balance)

        # Set fresh cache (2 minutes ago)
        executor._cached_balance = 5000.0
        executor._balance_cache_time = datetime.now() - timedelta(minutes=2)

        quantity = await executor._calculate_position_size_with_balance(100000.0)

        # Should use cached balance of 5000
        # 5000 * 0.05 * 15 / 100000 = 0.0375 -> round(0.0375, 3) = 0.038
        expected = round(5000 * 0.05 * 15 / 100000, 3)
        assert quantity == expected

    @pytest.mark.asyncio
    async def test_balance_fallback_api_fail_stale_cache(
        self, mock_binance_client, mock_config_real_balance
    ):
        """API 실패 + 캐시 5분 초과 -> RuntimeError"""
        mock_binance_client.get_account_balance = AsyncMock(
            side_effect=Exception("API Error")
        )
        executor = TradingExecutor(mock_binance_client, mock_config_real_balance)

        # Set stale cache (10 minutes ago)
        executor._cached_balance = 5000.0
        executor._balance_cache_time = datetime.now() - timedelta(minutes=10)

        with pytest.raises(RuntimeError, match="잔고 조회 실패"):
            await executor._calculate_position_size_with_balance(100000.0)

    @pytest.mark.asyncio
    async def test_cache_ttl_changed_to_300(
        self, mock_binance_client, mock_config_real_balance
    ):
        """캐시 TTL이 300초(5분)로 설정됨"""
        executor = TradingExecutor(mock_binance_client, mock_config_real_balance)
        assert executor._balance_cache_ttl_seconds == 300


# =============================================================================
# Issue 1.4: Minimum Order Quantity Validation Tests
# =============================================================================


class TestMinimumQuantityValidation:
    """Issue 1.4: 최소 주문 수량 검증 테스트"""

    def test_min_quantity_too_small(self, mock_binance_client, mock_config):
        """자본 부족으로 최소 수량 미만 -> ValueError"""
        executor = TradingExecutor(mock_binance_client, mock_config)

        # Very small capital leads to quantity < 0.001
        # capital=1, size_pct=0.05, leverage=15, price=100000
        # 1 * 0.05 * 15 / 100000 = 0.0000075 -> round = 0.0
        with pytest.raises(ValueError, match="최소 주문 수량"):
            executor._calculate_position_size(100000.0, capital=1.0)

    def test_min_quantity_normal(self, mock_binance_client, mock_config):
        """정상 자본금 -> 통과"""
        executor = TradingExecutor(mock_binance_client, mock_config)

        # Default capital 1000, price 100000
        # 1000 * 0.05 * 15 / 100000 = 0.0075 -> round = 0.008
        quantity = executor._calculate_position_size(100000.0)
        assert quantity >= 0.001

    def test_min_quantity_edge_case(self, mock_binance_client, mock_config):
        """경계값: 정확히 0.001 -> 통과"""
        executor = TradingExecutor(mock_binance_client, mock_config)

        # Find capital that gives exactly 0.001
        # capital * 0.05 * 15 / price = 0.001
        # capital = 0.001 * price / (0.05 * 15) = 0.001 * 100000 / 0.75 = 133.33
        quantity = executor._calculate_position_size(100000.0, capital=133.34)
        assert quantity == 0.001

    @pytest.mark.asyncio
    async def test_min_quantity_caught_by_open_position(
        self, mock_binance_client, mock_config
    ):
        """open_position에서 ValueError를 잡아 None 반환"""
        executor = TradingExecutor(mock_binance_client, mock_config)

        # Very high price with low capital -> quantity < 0.001
        result = await executor.open_position("LONG", 999999999.0)
        assert result is None


# =============================================================================
# Issue 1.3: Slippage Protection Tests
# =============================================================================


class TestSlippageProtection:
    """Issue 1.3: 슬리피지 보호 테스트"""

    @pytest.mark.asyncio
    async def test_slippage_within_limit(self, mock_binance_client, mock_config):
        """슬리피지 허용 범위 내 -> critical 로그 없음"""
        mock_binance_client.create_market_order = AsyncMock(return_value={
            "orderId": 12345,
            "symbol": "BTCUSDT",
            "side": "BUY",
            "status": "FILLED",
            "avgPrice": "100100.0",  # 0.1% slippage (within 0.5% limit)
        })
        executor = TradingExecutor(mock_binance_client, mock_config)

        order = await executor.open_position("LONG", 100000.0)

        assert order is not None
        # Entry price should be updated to actual fill price
        assert executor.current_position["entry_price"] == 100100.0

    @pytest.mark.asyncio
    async def test_slippage_exceeds_limit(self, mock_binance_client, mock_config, caplog):
        """슬리피지 초과 -> critical 로그"""
        mock_binance_client.create_market_order = AsyncMock(return_value={
            "orderId": 12345,
            "symbol": "BTCUSDT",
            "side": "BUY",
            "status": "FILLED",
            "avgPrice": "101000.0",  # 1.0% slippage (exceeds 0.5% limit)
        })
        executor = TradingExecutor(mock_binance_client, mock_config)


        import loguru

        # Capture loguru output
        messages = []
        def sink(message):
            messages.append(str(message))
        handler_id = loguru.logger.add(sink, level="CRITICAL")

        try:
            order = await executor.open_position("LONG", 100000.0)

            assert order is not None
            # Entry price should still be updated to fill price
            assert executor.current_position["entry_price"] == 101000.0
            # Critical slippage warning should be logged
            assert any("슬리피지 경고" in m for m in messages)
        finally:
            loguru.logger.remove(handler_id)

    @pytest.mark.asyncio
    async def test_slippage_no_avg_price(self, mock_binance_client, mock_config):
        """avgPrice 없음 -> 원래 가격 사용"""
        mock_binance_client.create_market_order = AsyncMock(return_value={
            "orderId": 12345,
            "symbol": "BTCUSDT",
            "side": "BUY",
            "status": "FILLED",
            # No avgPrice field
        })
        executor = TradingExecutor(mock_binance_client, mock_config)

        order = await executor.open_position("LONG", 100000.0)

        assert order is not None
        # Entry price should remain the original price
        assert executor.current_position["entry_price"] == 100000.0

    @pytest.mark.asyncio
    async def test_slippage_not_checked_for_maker(self, mock_binance_client, mock_config):
        """Maker 주문에서는 슬리피지 체크 안 함"""
        mock_binance_client.create_limit_order = AsyncMock(return_value={
            "orderId": 11111,
            "symbol": "BTCUSDT",
            "side": "BUY",
            "status": "NEW",
            "avgPrice": "101000.0",  # Even with high slippage
        })
        mock_binance_client.get_order_status = AsyncMock(return_value={
            "orderId": 11111,
            "status": "FILLED",
        })
        executor = TradingExecutor(mock_binance_client, mock_config)

        order = await executor.open_position_maker("LONG", 100000.0, use_maker=True)

        assert order is not None
        # For maker orders, entry price stays at current_price (no slippage check)
        assert executor.current_position["entry_price"] == 100000.0


# =============================================================================
# Issue 2.3: Partial Fill Handling Tests
# =============================================================================


class TestPartialFillHandling:
    """Issue 2.3: 부분 체결 처리 테스트"""

    @pytest.mark.asyncio
    async def test_partial_fill_complete(self, mock_binance_client, mock_config):
        """전량 체결 -> 재시도 없음"""
        mock_binance_client.get_position = AsyncMock(return_value={
            "side": "LONG",
            "position_amt": 0.01,
        })
        mock_binance_client.close_position = AsyncMock(return_value={
            "orderId": 67890,
            "status": "FILLED",
            "executedQty": "0.01",  # 100% filled
        })

        executor = TradingExecutor(mock_binance_client, mock_config)
        order = await executor.close_position()

        assert order is not None
        assert order["executedQty"] == "0.01"
        # No retry market order should be called
        mock_binance_client.create_market_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_partial_fill_retry_success(self, mock_binance_client, mock_config):
        """부분 체결 -> 재시도 성공"""
        mock_binance_client.get_position = AsyncMock(return_value={
            "side": "LONG",
            "position_amt": 0.01,
        })
        mock_binance_client.close_position = AsyncMock(return_value={
            "orderId": 67890,
            "status": "PARTIALLY_FILLED",
            "executedQty": "0.005",  # 50% filled
        })
        mock_binance_client.create_market_order = AsyncMock(return_value={
            "orderId": 67891,
            "status": "FILLED",
            "executedQty": "0.005",
        })

        executor = TradingExecutor(mock_binance_client, mock_config)
        order = await executor.close_position()

        assert order is not None
        # executedQty should be merged to full amount
        assert order["executedQty"] == str(0.01)
        # Retry order should be called with remaining quantity
        mock_binance_client.create_market_order.assert_called_once_with(
            symbol="BTCUSDT",
            side="SELL",  # Closing LONG -> SELL
            quantity=0.005,
        )

    @pytest.mark.asyncio
    async def test_partial_fill_retry_failure(self, mock_binance_client, mock_config):
        """부분 체결 -> 재시도 실패 -> RuntimeError 발생"""
        mock_binance_client.get_position = AsyncMock(return_value={
            "side": "SHORT",
            "position_amt": -0.02,
        })
        mock_binance_client.close_position = AsyncMock(return_value={
            "orderId": 67890,
            "status": "PARTIALLY_FILLED",
            "executedQty": "0.01",  # 50% filled
        })
        mock_binance_client.create_market_order = AsyncMock(
            side_effect=Exception("Retry failed")
        )

        executor = TradingExecutor(mock_binance_client, mock_config)

        with pytest.raises(RuntimeError, match="Partial fill retry failed"):
            await executor.close_position()

        # Retry was attempted with BUY (closing SHORT)
        mock_binance_client.create_market_order.assert_called_once_with(
            symbol="BTCUSDT",
            side="BUY",  # Closing SHORT -> BUY
            quantity=0.01,
        )

    @pytest.mark.asyncio
    async def test_partial_fill_no_order(self, mock_binance_client, mock_config):
        """청산 주문 결과 None -> 정상 처리"""
        mock_binance_client.get_position = AsyncMock(return_value={
            "side": "LONG",
            "position_amt": 0.01,
        })
        mock_binance_client.close_position = AsyncMock(return_value=None)

        executor = TradingExecutor(mock_binance_client, mock_config)
        order = await executor.close_position()

        # None order -> no partial fill check
        assert order is None
        assert executor.current_position is None


# =============================================================================
# Issue #1: Exchange TP/SL Placement After Position Open
# =============================================================================


class TestExchangeTpSlPlacement:
    """Issue #1: 포지션 오픈 후 거래소 TP/SL 배치 확인"""

    @pytest.mark.asyncio
    async def test_open_position_calls_place_exchange_tp_sl(
        self, mock_binance_client, mock_config
    ):
        """open_position() 후 _place_exchange_tp_sl() 호출 확인"""
        mock_binance_client.create_stop_market_order = AsyncMock(return_value={
            "orderId": 77777, "type": "STOP_MARKET", "status": "NEW",
        })
        mock_binance_client.create_take_profit_market_order = AsyncMock(return_value={
            "orderId": 88888, "type": "TAKE_PROFIT_MARKET", "status": "NEW",
        })

        executor = TradingExecutor(mock_binance_client, mock_config)
        order = await executor.open_position("LONG", 100000.0, entry_atr=500.0)

        assert order is not None
        # TP/SL 주문이 배치되어야 함
        mock_binance_client.create_stop_market_order.assert_called_once()
        mock_binance_client.create_take_profit_market_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_open_position_tp_sl_correct_args(
        self, mock_binance_client, mock_config
    ):
        """TP/SL 주문 인자 검증 (LONG 포지션, 고정 퍼센트)"""
        mock_binance_client.create_stop_market_order = AsyncMock(return_value={
            "orderId": 77777, "type": "STOP_MARKET", "status": "NEW",
        })
        mock_binance_client.create_take_profit_market_order = AsyncMock(return_value={
            "orderId": 88888, "type": "TAKE_PROFIT_MARKET", "status": "NEW",
        })

        executor = TradingExecutor(mock_binance_client, mock_config)
        await executor.open_position("LONG", 100000.0)

        # SL: SELL, price = 100000 * (1 - 0.004) = 99600
        sl_call = mock_binance_client.create_stop_market_order.call_args[1]
        assert sl_call["side"] == "SELL"
        assert sl_call["stop_price"] == 99600.0

        # TP: SELL, price = 100000 * (1 + 0.004) = 100400
        tp_call = mock_binance_client.create_take_profit_market_order.call_args[1]
        assert tp_call["side"] == "SELL"
        assert tp_call["stop_price"] == 100400.0

    @pytest.mark.asyncio
    async def test_open_position_short_tp_sl_args(
        self, mock_binance_client, mock_config
    ):
        """SHORT 포지션 TP/SL 주문 인자 검증"""
        mock_binance_client.create_market_order = AsyncMock(return_value={
            "orderId": 12345, "symbol": "BTCUSDT", "side": "SELL", "status": "FILLED",
        })
        mock_binance_client.create_stop_market_order = AsyncMock(return_value={
            "orderId": 77777, "type": "STOP_MARKET", "status": "NEW",
        })
        mock_binance_client.create_take_profit_market_order = AsyncMock(return_value={
            "orderId": 88888, "type": "TAKE_PROFIT_MARKET", "status": "NEW",
        })

        executor = TradingExecutor(mock_binance_client, mock_config)
        await executor.open_position("SHORT", 100000.0)

        # SL: BUY, price = 100000 * (1 + 0.004) = 100400
        sl_call = mock_binance_client.create_stop_market_order.call_args[1]
        assert sl_call["side"] == "BUY"
        assert sl_call["stop_price"] == 100400.0

        # TP: BUY, price = 100000 * (1 - 0.004) = 99600
        tp_call = mock_binance_client.create_take_profit_market_order.call_args[1]
        assert tp_call["side"] == "BUY"
        assert tp_call["stop_price"] == 99600.0


# =============================================================================
# Issue #1 (part 2): Cancel Exchange TP/SL on Close
# =============================================================================


class TestClosePositionCancelsOrders:
    """Issue #1: 포지션 청산 시 거래소 TP/SL 주문 취소 확인"""

    @pytest.mark.asyncio
    async def test_close_position_cancels_all_orders(
        self, mock_binance_client, mock_config
    ):
        """close_position() 후 cancel_all_open_orders() 호출 확인"""
        mock_binance_client.get_position = AsyncMock(return_value={
            "side": "LONG", "position_amt": 0.01, "entry_price": 100000.0,
        })
        mock_binance_client.cancel_all_open_orders = AsyncMock(return_value={
            "code": 200, "msg": "success",
        })

        executor = TradingExecutor(mock_binance_client, mock_config)
        order = await executor.close_position()

        assert order is not None
        mock_binance_client.cancel_all_open_orders.assert_called_once_with("BTCUSDT")

    @pytest.mark.asyncio
    async def test_close_position_cancel_failure_ignored(
        self, mock_binance_client, mock_config
    ):
        """TP/SL 취소 실패해도 청산은 성공"""
        mock_binance_client.get_position = AsyncMock(return_value={
            "side": "LONG", "position_amt": 0.01, "entry_price": 100000.0,
        })
        mock_binance_client.cancel_all_open_orders = AsyncMock(
            side_effect=Exception("Cancel failed")
        )

        executor = TradingExecutor(mock_binance_client, mock_config)
        order = await executor.close_position()

        # 청산은 성공해야 함
        assert order is not None
        assert executor.current_position is None

    @pytest.mark.asyncio
    async def test_close_position_no_position_no_cancel(
        self, mock_binance_client, mock_config
    ):
        """포지션 없으면 cancel 호출 안 함"""
        mock_binance_client.get_position = AsyncMock(return_value=None)
        mock_binance_client.cancel_all_open_orders = AsyncMock()

        executor = TradingExecutor(mock_binance_client, mock_config)
        order = await executor.close_position()

        assert order is None
        mock_binance_client.cancel_all_open_orders.assert_not_called()


# =============================================================================
# Issue #12: Slippage Detection with Close Action
# =============================================================================


class TestSlippageCloseAction:
    """Issue #12: 과도한 슬리피지 시 포지션 즉시 청산"""

    @pytest.mark.asyncio
    async def test_excessive_slippage_closes_position(self, mock_binance_client):
        """close_on_excessive_slippage=True + 과도한 슬리피지 -> 포지션 청산, None 반환"""
        mock_binance_client.create_market_order = AsyncMock(return_value={
            "orderId": 12345,
            "symbol": "BTCUSDT",
            "side": "BUY",
            "status": "FILLED",
            "avgPrice": "101000.0",  # 1.0% slippage (exceeds 0.5%)
        })
        mock_binance_client.close_position = AsyncMock(return_value={
            "orderId": 67890, "status": "FILLED",
        })

        config = TradingConfig(
            bot_name="test-bot",
            binance_api_key="test_key",
            binance_secret_key="test_secret",
            gemini_api_key="test_gemini",
            discord_webhook_url="https://test.com",
            symbol="BTCUSDT",
            leverage=15,
            position_size_pct=0.05,
            close_on_excessive_slippage=True,
        )

        executor = TradingExecutor(mock_binance_client, config)
        result = await executor.open_position("LONG", 100000.0)

        assert result is None
        mock_binance_client.close_position.assert_called_once_with("BTCUSDT")

    @pytest.mark.asyncio
    async def test_excessive_slippage_default_no_close(self, mock_binance_client, mock_config):
        """close_on_excessive_slippage 미설정 (기본=False) -> 포지션 유지"""
        mock_binance_client.create_market_order = AsyncMock(return_value={
            "orderId": 12345,
            "symbol": "BTCUSDT",
            "side": "BUY",
            "status": "FILLED",
            "avgPrice": "101000.0",  # 1.0% slippage
        })
        # Need TP/SL mock since position opens
        mock_binance_client.create_stop_market_order = AsyncMock(return_value={
            "orderId": 77777, "type": "STOP_MARKET", "status": "NEW",
        })
        mock_binance_client.create_take_profit_market_order = AsyncMock(return_value={
            "orderId": 88888, "type": "TAKE_PROFIT_MARKET", "status": "NEW",
        })

        executor = TradingExecutor(mock_binance_client, mock_config)
        result = await executor.open_position("LONG", 100000.0)

        # 포지션이 유지되어야 함 (기존 동작)
        assert result is not None
        assert executor.current_position["entry_price"] == 101000.0

    @pytest.mark.asyncio
    async def test_excessive_slippage_close_failure(self, mock_binance_client):
        """슬리피지 청산 실패 시에도 None 반환"""
        mock_binance_client.create_market_order = AsyncMock(return_value={
            "orderId": 12345,
            "symbol": "BTCUSDT",
            "side": "BUY",
            "status": "FILLED",
            "avgPrice": "102000.0",  # 2.0% slippage
        })
        mock_binance_client.close_position = AsyncMock(
            side_effect=Exception("Close failed")
        )

        config = TradingConfig(
            bot_name="test-bot",
            binance_api_key="test_key",
            binance_secret_key="test_secret",
            gemini_api_key="test_gemini",
            discord_webhook_url="https://test.com",
            symbol="BTCUSDT",
            leverage=15,
            position_size_pct=0.05,
            close_on_excessive_slippage=True,
        )

        executor = TradingExecutor(mock_binance_client, config)
        result = await executor.open_position("LONG", 100000.0)

        # 청산 실패해도 None 반환 (포지션 저장 안 됨)
        assert result is None

    @pytest.mark.asyncio
    async def test_normal_slippage_not_closed(self, mock_binance_client):
        """슬리피지가 허용 범위 내 -> close 안 함"""
        mock_binance_client.create_market_order = AsyncMock(return_value={
            "orderId": 12345,
            "symbol": "BTCUSDT",
            "side": "BUY",
            "status": "FILLED",
            "avgPrice": "100100.0",  # 0.1% slippage (within 0.5%)
        })
        mock_binance_client.create_stop_market_order = AsyncMock(return_value={
            "orderId": 77777, "type": "STOP_MARKET", "status": "NEW",
        })
        mock_binance_client.create_take_profit_market_order = AsyncMock(return_value={
            "orderId": 88888, "type": "TAKE_PROFIT_MARKET", "status": "NEW",
        })

        config = TradingConfig(
            bot_name="test-bot",
            binance_api_key="test_key",
            binance_secret_key="test_secret",
            gemini_api_key="test_gemini",
            discord_webhook_url="https://test.com",
            symbol="BTCUSDT",
            leverage=15,
            position_size_pct=0.05,
            close_on_excessive_slippage=True,
        )

        executor = TradingExecutor(mock_binance_client, config)
        result = await executor.open_position("LONG", 100000.0)

        # 정상 슬리피지 -> 포지션 유지
        assert result is not None
        assert executor.current_position["entry_price"] == 100100.0


# =============================================================================
# Issue 6: Deduct Unrealized Losses from Cached Balance
# =============================================================================


class TestDeductUnrealizedLossesFromCachedBalance:
    """Issue 6: 캐시된 잔고에서 미실현 손실 차감 테스트"""

    @pytest.mark.asyncio
    async def test_cached_balance_deducts_unrealized_loss(
        self, mock_binance_client, mock_config_real_balance
    ):
        """캐시된 잔고 사용 시 미실현 손실 차감"""
        executor = TradingExecutor(mock_binance_client, mock_config_real_balance)

        # Set fresh cache
        executor._cached_balance = 5000.0
        executor._balance_cache_time = datetime.now() - timedelta(minutes=1)

        # Set current position with unrealized loss
        executor.current_position = {
            "signal": "LONG",
            "entry_price": 100000.0,
            "unrealized_pnl": -200.0,
        }

        balance = await executor._get_available_balance()
        # Should deduct unrealized loss: 5000 - 200 = 4800
        assert balance == 4800.0

    @pytest.mark.asyncio
    async def test_cached_balance_no_deduction_for_profit(
        self, mock_binance_client, mock_config_real_balance
    ):
        """미실현 이익일 때는 차감 없음"""
        executor = TradingExecutor(mock_binance_client, mock_config_real_balance)

        # Set fresh cache
        executor._cached_balance = 5000.0
        executor._balance_cache_time = datetime.now() - timedelta(minutes=1)

        # Set current position with unrealized profit
        executor.current_position = {
            "signal": "LONG",
            "entry_price": 100000.0,
            "unrealized_pnl": 300.0,
        }

        balance = await executor._get_available_balance()
        # Profit should not affect balance
        assert balance == 5000.0

    @pytest.mark.asyncio
    async def test_cached_balance_no_position_no_deduction(
        self, mock_binance_client, mock_config_real_balance
    ):
        """포지션 없을 때는 차감 없음"""
        executor = TradingExecutor(mock_binance_client, mock_config_real_balance)

        # Set fresh cache
        executor._cached_balance = 5000.0
        executor._balance_cache_time = datetime.now() - timedelta(minutes=1)

        # No position
        executor.current_position = None

        balance = await executor._get_available_balance()
        assert balance == 5000.0

    @pytest.mark.asyncio
    async def test_cached_balance_floor_at_zero(
        self, mock_binance_client, mock_config_real_balance
    ):
        """잔고가 0 미만으로 내려가지 않음"""
        executor = TradingExecutor(mock_binance_client, mock_config_real_balance)

        # Set fresh cache
        executor._cached_balance = 100.0
        executor._balance_cache_time = datetime.now() - timedelta(minutes=1)

        # Unrealized loss exceeds balance
        executor.current_position = {
            "signal": "LONG",
            "entry_price": 100000.0,
            "unrealized_pnl": -500.0,
        }

        balance = await executor._get_available_balance()
        assert balance == 0.0

    @pytest.mark.asyncio
    async def test_fresh_api_balance_also_deducts_unrealized_loss(
        self, mock_binance_client, mock_config_real_balance
    ):
        """API에서 직접 조회한 잔고에서도 미실현 손실 차감"""
        mock_binance_client.get_account_balance = AsyncMock(return_value={
            "asset": "USDT",
            "balance": 5000.0,
            "available": 5000.0,
        })
        executor = TradingExecutor(mock_binance_client, mock_config_real_balance)

        # Set current position with unrealized loss
        executor.current_position = {
            "signal": "LONG",
            "entry_price": 100000.0,
            "unrealized_pnl": -150.0,
        }

        balance = await executor._get_available_balance()
        assert balance == 4850.0


# =============================================================================
# Issue #1 (Phase 8): SL Placement Failure -> Immediate Position Close
# =============================================================================


class TestSLPlacementFailure:
    """Issue #1: SL 배치 실패 시 즉시 포지션 청산"""

    @pytest.mark.asyncio
    async def test_place_exchange_tp_sl_returns_true_on_success(
        self, mock_binance_client, mock_config
    ):
        """SL+TP 배치 성공 시 True 반환"""
        mock_binance_client.create_stop_market_order = AsyncMock(return_value={
            'orderId': 77777, 'type': 'STOP_MARKET', 'status': 'NEW',
        })
        mock_binance_client.create_take_profit_market_order = AsyncMock(return_value={
            'orderId': 88888, 'type': 'TAKE_PROFIT_MARKET', 'status': 'NEW',
        })

        executor = TradingExecutor(mock_binance_client, mock_config)
        result = await executor._place_exchange_tp_sl(
            symbol='BTCUSDT', side='LONG', quantity=0.01,
            entry_price=100000.0, entry_atr=None,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_place_exchange_tp_sl_returns_false_on_sl_failure(
        self, mock_binance_client, mock_config
    ):
        """SL 배치 실패 시 False 반환"""
        mock_binance_client.create_stop_market_order = AsyncMock(
            side_effect=Exception('SL order failed')
        )
        mock_binance_client.create_take_profit_market_order = AsyncMock(return_value={
            'orderId': 88888, 'type': 'TAKE_PROFIT_MARKET', 'status': 'NEW',
        })

        executor = TradingExecutor(mock_binance_client, mock_config)
        result = await executor._place_exchange_tp_sl(
            symbol='BTCUSDT', side='LONG', quantity=0.01,
            entry_price=100000.0, entry_atr=None,
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_tp_failure_returns_true(
        self, mock_binance_client, mock_config
    ):
        """TP 배치 실패해도 SL 성공이면 True 반환 (TP는 비필수)"""
        mock_binance_client.create_stop_market_order = AsyncMock(return_value={
            'orderId': 77777, 'type': 'STOP_MARKET', 'status': 'NEW',
        })
        mock_binance_client.create_take_profit_market_order = AsyncMock(
            side_effect=Exception('TP order failed')
        )

        executor = TradingExecutor(mock_binance_client, mock_config)
        result = await executor._place_exchange_tp_sl(
            symbol='BTCUSDT', side='LONG', quantity=0.01,
            entry_price=100000.0, entry_atr=None,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_sl_failure_closes_position_in_open(
        self, mock_binance_client, mock_config
    ):
        """SL 배치 실패 시 _prepare_and_open_position에서 포지션 즉시 청산"""
        # SL placement fails
        mock_binance_client.create_stop_market_order = AsyncMock(
            side_effect=Exception('SL order failed')
        )
        mock_binance_client.close_position = AsyncMock(return_value={
            'orderId': 99999, 'status': 'FILLED',
        })

        executor = TradingExecutor(mock_binance_client, mock_config)
        result = await executor.open_position('LONG', 100000.0)

        # Position should be closed and None returned
        assert result is None
        mock_binance_client.close_position.assert_called_once_with('BTCUSDT')

    @pytest.mark.asyncio
    async def test_tp_failure_keeps_position_open(
        self, mock_binance_client, mock_config
    ):
        """TP 배치 실패 시 포지션은 유지됨 (SL만 필수)"""
        mock_binance_client.create_stop_market_order = AsyncMock(return_value={
            'orderId': 77777, 'type': 'STOP_MARKET', 'status': 'NEW',
        })
        mock_binance_client.create_take_profit_market_order = AsyncMock(
            side_effect=Exception('TP order failed')
        )

        executor = TradingExecutor(mock_binance_client, mock_config)
        result = await executor.open_position('LONG', 100000.0)

        # Position should still be open
        assert result is not None
        assert executor.current_position is not None


# =============================================================================
# Issue #2 (Phase 8): Cancel Orders Before Force Close
# =============================================================================


class TestCancelOrdersBeforeClose:
    """Issue #2: 강제 청산 전 주문 취소"""

    @pytest.mark.asyncio
    async def test_close_position_cancel_orders_first(
        self, mock_binance_client, mock_config
    ):
        """cancel_orders_first=True 시 주문 먼저 취소"""
        mock_binance_client.get_position = AsyncMock(return_value={
            'side': 'LONG', 'position_amt': 0.01,
        })
        mock_binance_client.cancel_all_open_orders = AsyncMock(return_value={
            'code': 200, 'msg': 'success',
        })

        executor = TradingExecutor(mock_binance_client, mock_config)
        order = await executor.close_position(cancel_orders_first=True)

        assert order is not None
        # cancel_all_open_orders should be called BEFORE close
        mock_binance_client.cancel_all_open_orders.assert_called()

    @pytest.mark.asyncio
    async def test_close_position_default_no_pre_cancel(
        self, mock_binance_client, mock_config
    ):
        """기본값(cancel_orders_first=False) 시 사전 취소 안 함"""
        mock_binance_client.get_position = AsyncMock(return_value={
            'side': 'LONG', 'position_amt': 0.01,
        })
        mock_binance_client.cancel_all_open_orders = AsyncMock(return_value={
            'code': 200, 'msg': 'success',
        })

        executor = TradingExecutor(mock_binance_client, mock_config)
        order = await executor.close_position()

        assert order is not None
        # cancel_all_open_orders is called once (post-close cleanup only)
        assert mock_binance_client.cancel_all_open_orders.call_count == 1

    @pytest.mark.asyncio
    async def test_cancel_orders_first_position_gone(
        self, mock_binance_client, mock_config
    ):
        """주문 취소 후 포지션이 이미 없으면 (SL 체결됨) 바로 반환"""
        call_count = 0
        async def get_position_side_effect(symbol):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {'side': 'LONG', 'position_amt': 0.01}
            return None  # Position gone after cancel (SL already filled)

        mock_binance_client.get_position = AsyncMock(side_effect=get_position_side_effect)
        mock_binance_client.cancel_all_open_orders = AsyncMock()

        executor = TradingExecutor(mock_binance_client, mock_config)
        order = await executor.close_position(cancel_orders_first=True)

        # Should return None because position is already gone
        assert order is None
        mock_binance_client.cancel_all_open_orders.assert_called_once()


# =============================================================================
# Issue #3 (Phase 8): Partial Fill Retry Failure -> RuntimeError
# =============================================================================


class TestPartialFillRuntimeError:
    """Issue #3: 부분 체결 재시도 실패 시 RuntimeError"""

    @pytest.mark.asyncio
    async def test_partial_fill_retry_failure_raises_runtime_error(
        self, mock_binance_client, mock_config
    ):
        """재시도 실패 시 RuntimeError 발생"""
        mock_binance_client.get_position = AsyncMock(return_value={
            'side': 'LONG', 'position_amt': 0.01,
        })
        mock_binance_client.close_position = AsyncMock(return_value={
            'orderId': 67890,
            'status': 'PARTIALLY_FILLED',
            'executedQty': '0.005',  # 50% filled
        })
        mock_binance_client.create_market_order = AsyncMock(
            side_effect=Exception('Retry failed')
        )

        executor = TradingExecutor(mock_binance_client, mock_config)

        with pytest.raises(RuntimeError, match='Partial fill retry failed'):
            await executor.close_position()

    @pytest.mark.asyncio
    async def test_partial_fill_retry_failure_preserves_position(
        self, mock_binance_client, mock_config
    ):
        """재시도 실패 시 current_position이 None이 되지 않음"""
        mock_binance_client.get_position = AsyncMock(return_value={
            'side': 'LONG', 'position_amt': 0.01,
        })
        mock_binance_client.close_position = AsyncMock(return_value={
            'orderId': 67890,
            'status': 'PARTIALLY_FILLED',
            'executedQty': '0.005',
        })
        mock_binance_client.create_market_order = AsyncMock(
            side_effect=Exception('Retry failed')
        )

        executor = TradingExecutor(mock_binance_client, mock_config)
        executor.current_position = {'signal': 'LONG', 'entry_price': 100000}

        with pytest.raises(RuntimeError):
            await executor.close_position()

        # Position should NOT be cleared on partial fill failure
        assert executor.current_position is not None
