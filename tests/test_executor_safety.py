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
        """부분 체결 -> 재시도 실패 -> critical 로그"""
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

        import loguru
        messages = []
        def sink(message):
            messages.append(str(message))
        handler_id = loguru.logger.add(sink, level="CRITICAL")

        try:
            executor = TradingExecutor(mock_binance_client, mock_config)
            order = await executor.close_position()

            assert order is not None
            # The executedQty stays at partial amount since retry failed
            assert order["executedQty"] == "0.01"
            # Retry was attempted with BUY (closing SHORT)
            mock_binance_client.create_market_order.assert_called_once_with(
                symbol="BTCUSDT",
                side="BUY",  # Closing SHORT -> BUY
                quantity=0.01,
            )
            # Critical log for manual intervention
            assert any("잔여 수량 청산 실패" in m for m in messages)
        finally:
            loguru.logger.remove(handler_id)

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
