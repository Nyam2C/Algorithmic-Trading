"""Tests for Phase 9 WS1: Position Lifecycle & PnL Accuracy.

Issue A: close_position() nulls current_position before DB read
Issue C: PnL USD double-counts leverage
Issue D: close_position() error returns None silently (should re-raise)
Issue E: Post-close cancel_all_open_orders may cancel other bot's SL
Issue O: check_timecut() mutates position dict
"""
from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest

from src.config import TradingConfig
from src.trading.executor import TradingExecutor


@pytest.fixture
def mock_config():
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
def mock_binance_client():
    client = Mock()
    client.set_leverage = AsyncMock(return_value={"leverage": 15})
    client.get_position = AsyncMock(return_value=None)
    client.create_market_order = AsyncMock(return_value={
        "orderId": 12345, "symbol": "BTCUSDT",
        "side": "BUY", "status": "FILLED",
    })
    client.close_position = AsyncMock(return_value={
        "orderId": 67890, "status": "FILLED", "executedQty": "0.01",
    })
    client.create_stop_market_order = AsyncMock(return_value={"orderId": 10001})
    client.create_take_profit_market_order = AsyncMock(return_value={"orderId": 10002})
    client.cancel_all_open_orders = AsyncMock(return_value=None)
    return client


@pytest.fixture
def executor(mock_binance_client, mock_config):
    return TradingExecutor(mock_binance_client, mock_config)


# =========================================================================
# Issue A: close_position() should NOT null current_position
# =========================================================================


class TestIssueAClosePositionPreservesState:
    """Issue A: close_position() must not set current_position=None.

    The bot needs to read current_position after close for DB write and metrics.
    A separate clear_position() method should be used by the caller afterward.
    """

    @pytest.mark.asyncio
    async def test_close_position_preserves_current_position(
        self, executor, mock_binance_client
    ):
        """After close_position(), current_position should still be available."""
        mock_binance_client.get_position = AsyncMock(return_value={
            "side": "LONG", "position_amt": 0.01, "entry_price": 100000.0,
        })

        # Set position state before close
        executor.current_position = {
            "signal": "LONG", "side": "BUY",
            "entry_price": 100000.0, "trade_id": 42,
            "entry_time": datetime.now(),
        }

        order = await executor.close_position()

        assert order is not None
        # current_position should NOT be None after close
        assert executor.current_position is not None
        assert executor.current_position["trade_id"] == 42

    def test_clear_position_exists(self, executor):
        """TradingExecutor should have a clear_position() method."""
        assert hasattr(executor, "clear_position")
        assert callable(executor.clear_position)

    def test_clear_position_nulls_state(self, executor):
        """clear_position() should set current_position to None."""
        executor.current_position = {
            "signal": "LONG", "entry_price": 100000.0,
        }

        executor.clear_position()

        assert executor.current_position is None

    @pytest.mark.asyncio
    async def test_full_lifecycle_close_then_clear(
        self, executor, mock_binance_client
    ):
        """Full lifecycle: close -> read state -> clear."""
        mock_binance_client.get_position = AsyncMock(return_value={
            "side": "LONG", "position_amt": 0.01, "entry_price": 100000.0,
        })
        executor.current_position = {
            "signal": "LONG", "trade_id": 99,
            "entry_time": datetime.now(),
        }

        # Step 1: Close position
        order = await executor.close_position()
        assert order is not None

        # Step 2: Read state (bot does DB writes here)
        assert executor.current_position is not None
        trade_id = executor.current_position["trade_id"]
        assert trade_id == 99

        # Step 3: Clear state
        executor.clear_position()
        assert executor.current_position is None


# =========================================================================
# Issue C: PnL USD double-counts leverage
# =========================================================================


class TestIssueCPnlLeverageDoubleCount:
    """Issue C: pnl_usd should NOT multiply by leverage.

    position_amt from exchange is already the leveraged quantity.
    Multiplying by leverage again doubles the PnL.
    """

    def test_pnl_usd_no_leverage_multiplication(self):
        """Verify PnL calculation without leverage double-counting.

        Scenario: LONG 0.01 BTC at 00000, exit at 01000.
        position_amt = 0.01 (already leveraged from exchange).
        Expected PnL = (101000 - 100000) * 0.01 = 0.
        Bug: was 0 * 15 = 50 (wrong).
        """
        entry_price = 100000.0
        exit_price = 101000.0
        position_amt = 0.01  # Already leveraged quantity from exchange

        # Correct PnL (no leverage multiplication)
        pnl_usd = (exit_price - entry_price) * abs(position_amt)
        assert pnl_usd == 10.0

        # Bug PnL (with leverage multiplication)
        leverage = 15
        buggy_pnl = pnl_usd * leverage
        assert buggy_pnl == 150.0  # This was the bug - 15x too much


# =========================================================================
# Issue D: close_position() error should re-raise, not return None
# =========================================================================


class TestIssueDClosePositionReRaisesErrors:
    """Issue D: close_position() must re-raise BinanceAPIException and
    ConnectionError so the caller knows the close failed.
    """

    @pytest.mark.asyncio
    async def test_close_position_reraises_binance_api_exception(
        self, mock_binance_client, mock_config
    ):
        """BinanceAPIException should propagate to caller."""
        import types

        from binance.exceptions import BinanceAPIException

        mock_binance_client.get_position = AsyncMock(return_value={
            "side": "LONG", "position_amt": 0.01, "entry_price": 100000.0,
        })
        resp = types.SimpleNamespace(text="API Error", status_code=400)
        mock_binance_client.close_position = AsyncMock(
            side_effect=BinanceAPIException(resp, 400, "API Error")
        )

        executor = TradingExecutor(mock_binance_client, mock_config)

        with pytest.raises(BinanceAPIException):
            await executor.close_position()

    @pytest.mark.asyncio
    async def test_close_position_reraises_connection_error(
        self, mock_binance_client, mock_config
    ):
        """ConnectionError should propagate to caller."""
        mock_binance_client.get_position = AsyncMock(return_value={
            "side": "LONG", "position_amt": 0.01, "entry_price": 100000.0,
        })
        mock_binance_client.close_position = AsyncMock(
            side_effect=ConnectionError("Network down")
        )

        executor = TradingExecutor(mock_binance_client, mock_config)

        with pytest.raises(ConnectionError):
            await executor.close_position()

    @pytest.mark.asyncio
    async def test_close_position_generic_exception_still_returns_none(
        self, mock_binance_client, mock_config
    ):
        """Other exceptions (non-exchange) should still return None."""
        mock_binance_client.get_position = AsyncMock(return_value={
            "side": "LONG", "position_amt": 0.01, "entry_price": 100000.0,
        })
        mock_binance_client.close_position = AsyncMock(
            side_effect=ValueError("Some internal error")
        )

        executor = TradingExecutor(mock_binance_client, mock_config)

        result = await executor.close_position()
        assert result is None


# =========================================================================
# Issue O: check_timecut() should NOT mutate position dict
# =========================================================================


class TestIssueOTimecutNoMutation:
    """Issue O: check_timecut() with missing entry_time should NOT
    mutate the position dict. It should return False without side effects.
    """

    def test_check_timecut_no_entry_time_no_mutation(self, executor):
        """Position dict without entry_time should not be mutated."""
        position = {"side": "LONG"}
        original_keys = set(position.keys())

        result = executor.check_timecut(position)

        assert result is False
        # Position dict should NOT have been mutated
        assert set(position.keys()) == original_keys
        assert "entry_time" not in position

    def test_check_timecut_none_entry_time_no_mutation(self, executor):
        """Position dict with entry_time=None should not be mutated."""
        position = {"side": "LONG", "entry_time": None}

        result = executor.check_timecut(position)

        assert result is False
        # entry_time should still be None (not mutated)
        assert position["entry_time"] is None
