"""WebSocket Manager 테스트."""
import asyncio
import time

import pytest

from src.exchange.ws_manager import (
    BinanceWSManager,
    OrderBookAggregator,
    TradeAggregator,
)

# =========================================================================
# OrderBookAggregator 테스트
# =========================================================================

class TestOrderBookAggregator:
    """OrderBookAggregator 테스트."""

    def test_initial_snapshot_returns_none(self):
        agg = OrderBookAggregator()
        assert agg.snapshot() is None

    def test_update_and_snapshot(self):
        agg = OrderBookAggregator()
        # 5개 이상의 메시지를 넣어야 snapshot이 반환됨
        for i in range(10):
            agg.update({
                "bids": [["100.0", str(10 + i)]],
                "asks": [["101.0", str(5 + i)]],
            })
        snap = agg.snapshot()
        assert snap is not None
        assert "ofi_5" in snap
        assert "ofi_20" in snap
        assert "ofi_50" in snap
        assert "cvd" in snap
        assert "sample_count" in snap
        assert snap["sample_count"] >= 5

    def test_delta_calculation(self):
        agg = OrderBookAggregator()
        # First update: sets baseline
        agg.update({"bids": [["100.0", "10"]], "asks": [["101.0", "5"]]})
        # Second: bid +5, ask +3
        agg.update({"bids": [["100.0", "15"]], "asks": [["101.0", "8"]]})
        # Buffer should have entries
        assert len(agg._buffer) >= 1

    def test_insufficient_data_returns_none(self):
        agg = OrderBookAggregator()
        # Only 3 updates (< 5 required)
        for _ in range(3):
            agg.update({"bids": [["100.0", "10"]], "asks": [["101.0", "5"]]})
        assert agg.snapshot() is None

    def test_stale_data_returns_none(self):
        agg = OrderBookAggregator()
        for i in range(10):
            agg.update({"bids": [["100.0", str(i)]], "asks": [["101.0", str(i)]]})
        # Manually set last update to past
        agg._last_update_time = time.monotonic() - 10.0
        assert agg.snapshot() is None

    def test_maxlen_respected(self):
        agg = OrderBookAggregator()
        for i in range(4000):
            agg.update({"bids": [["100.0", str(i % 100)]], "asks": [["101.0", str(i % 50)]]})
        assert len(agg._buffer) <= agg.MAX_BUFFER_SIZE

    def test_ofi_values_positive_for_bid_increase(self):
        agg = OrderBookAggregator()
        # Start with baseline
        agg.update({"bids": [["100.0", "10"]], "asks": [["101.0", "10"]]})
        # Increase bids only
        for i in range(10):
            agg.update({"bids": [["100.0", str(15 + i)]], "asks": [["101.0", "10"]]})
        snap = agg.snapshot()
        assert snap is not None
        # OFI should be positive (bid increases > ask increases)
        assert snap["ofi_5"] > 0

    def test_multiple_price_levels(self):
        agg = OrderBookAggregator()
        agg.update({
            "bids": [["100.0", "10"], ["99.0", "20"]],
            "asks": [["101.0", "5"], ["102.0", "15"]],
        })
        for i in range(6):
            agg.update({
                "bids": [["100.0", str(10 + i)], ["99.0", str(20 + i)]],
                "asks": [["101.0", str(5 + i)], ["102.0", str(15 + i)]],
            })
        snap = agg.snapshot()
        assert snap is not None

    def test_uses_b_a_keys(self):
        """Alternative key format (b/a instead of bids/asks)."""
        agg = OrderBookAggregator()
        for i in range(10):
            agg.update({
                "b": [["100.0", str(10 + i)]],
                "a": [["101.0", str(5 + i)]],
            })
        snap = agg.snapshot()
        assert snap is not None


# =========================================================================
# TradeAggregator 테스트
# =========================================================================

class TestTradeAggregator:
    """TradeAggregator 테스트."""

    def test_initial_snapshot_returns_none(self):
        agg = TradeAggregator()
        assert agg.snapshot() is None

    def test_update_and_snapshot(self):
        agg = TradeAggregator()
        # Add enough trades for percentile calculation
        for i in range(100):
            qty = 0.1 * (i + 1)
            agg.update({"q": str(qty), "m": i % 2 == 0})
        snap = agg.snapshot()
        assert snap is not None
        assert "whale_buy_vol" in snap
        assert "whale_sell_vol" in snap
        assert "retail_buy_vol" in snap
        assert "retail_sell_vol" in snap
        assert "total_trades" in snap
        assert snap["total_trades"] == 100

    def test_whale_classification(self):
        agg = TradeAggregator()
        # 90 small trades + 10 large trades
        for _ in range(90):
            agg.update({"q": "0.1", "m": False})  # buyer taker (buy)
        for _ in range(10):
            agg.update({"q": "100.0", "m": False})  # buyer taker, large (whale buy)
        # Force percentile recalculation
        agg._last_percentile_time = 0
        snap = agg.snapshot()
        assert snap is not None
        assert snap["whale_buy_vol"] > 0

    def test_retail_classification(self):
        agg = TradeAggregator()
        # Wide range of sizes to ensure clear percentile boundaries
        for _ in range(25):
            agg.update({"q": "0.001", "m": True})  # tiny sell (retail)
        for _ in range(50):
            agg.update({"q": "1.0", "m": True})  # medium sell (algo)
        for _ in range(25):
            agg.update({"q": "100.0", "m": True})  # large sell (whale)
        # Force full recalculation with all data
        agg._recalculate_percentiles()
        snap = agg.snapshot()
        assert snap is not None
        # 25th percentile = 1.0, so trades with qty < 1.0 (the 0.001 ones) are retail
        assert snap["retail_sell_vol"] > 0

    def test_stale_data_returns_none(self):
        agg = TradeAggregator()
        for _ in range(50):
            agg.update({"q": "1.0", "m": False})
        agg._last_update_time = time.monotonic() - 15.0
        assert agg.snapshot() is None

    def test_maxlen_respected(self):
        agg = TradeAggregator()
        for _ in range(7000):
            agg.update({"q": "1.0", "m": False})
        assert len(agg._buffer) <= agg.MAX_BUFFER_SIZE

    def test_is_buyer_maker_true_means_sell(self):
        """is_buyer_maker=True → seller is taker → sell."""
        agg = TradeAggregator()
        for _ in range(100):
            agg.update({"q": "1.0", "m": True})
        agg._last_percentile_time = 0
        snap = agg.snapshot()
        assert snap is not None
        # All trades are sells, no buys
        assert snap["whale_buy_vol"] == 0.0
        assert snap["retail_buy_vol"] == 0.0

    def test_is_buyer_maker_false_means_buy(self):
        """is_buyer_maker=False → buyer is taker → buy."""
        agg = TradeAggregator()
        for _ in range(100):
            agg.update({"q": "1.0", "m": False})
        agg._last_percentile_time = 0
        snap = agg.snapshot()
        assert snap is not None
        # All trades are buys, no sells
        assert snap["whale_sell_vol"] == 0.0
        assert snap["retail_sell_vol"] == 0.0

    def test_percentile_recalculation_interval(self):
        agg = TradeAggregator()
        for i in range(50):
            agg.update({"q": str(i + 1), "m": False})
        # First snap triggers recalc
        agg.snapshot()
        old_whale = agg._whale_threshold
        assert old_whale > 0

    def test_alternative_keys(self):
        """Alternative key format (quantity/is_buyer_maker)."""
        agg = TradeAggregator()
        for i in range(50):
            agg.update({"quantity": str(i + 1), "is_buyer_maker": i % 2 == 0})
        snap = agg.snapshot()
        assert snap is not None
        assert snap["total_trades"] == 50


# =========================================================================
# BinanceWSManager 테스트
# =========================================================================

class TestBinanceWSManager:
    """BinanceWSManager 테스트."""

    def test_init_defaults(self):
        mgr = BinanceWSManager(symbol="btcusdt", testnet=True)
        assert mgr._symbol == "btcusdt"
        assert mgr._testnet is True
        assert mgr.orderbook_aggregator is not None
        assert mgr.trade_aggregator is not None
        assert mgr._running is False

    def test_is_connected_false_when_not_running(self):
        mgr = BinanceWSManager(symbol="btcusdt")
        assert mgr.is_connected is False

    def test_is_connected_false_when_no_messages(self):
        mgr = BinanceWSManager(symbol="btcusdt")
        mgr._running = True
        # last_message_time = 0 → False
        assert mgr.is_connected is False

    def test_is_connected_true_with_recent_message(self):
        mgr = BinanceWSManager(symbol="btcusdt")
        mgr._running = True
        mgr._last_message_time = time.monotonic()
        assert mgr.is_connected is True

    def test_is_connected_false_when_stale(self):
        mgr = BinanceWSManager(symbol="btcusdt")
        mgr._running = True
        mgr._last_message_time = time.monotonic() - 35.0  # > 30s
        assert mgr.is_connected is False

    @pytest.mark.asyncio
    async def test_start_sets_running(self):
        mgr = BinanceWSManager(symbol="btcusdt")
        # Mock _run_streams to avoid actual WS connection
        stop_event = asyncio.Event()
        async def mock_run():
            await stop_event.wait()

        original = mgr._run_streams
        mgr._run_streams = mock_run
        try:
            await mgr.start()
            assert mgr._running is True
            assert len(mgr._tasks) == 1
        finally:
            await mgr.stop()

    @pytest.mark.asyncio
    async def test_stop_clears_state(self):
        mgr = BinanceWSManager(symbol="btcusdt")

        stop_event = asyncio.Event()
        async def mock_run():
            await stop_event.wait()

        mgr._run_streams = mock_run
        await mgr.start()
        stop_event.set()
        await mgr.stop()
        assert mgr._running is False
        assert len(mgr._tasks) == 0

    @pytest.mark.asyncio
    async def test_start_idempotent(self):
        mgr = BinanceWSManager(symbol="btcusdt")

        stop_event = asyncio.Event()
        async def mock_run():
            await stop_event.wait()

        mgr._run_streams = mock_run
        try:
            await mgr.start()
            await mgr.start()  # Second call should be no-op
            assert len(mgr._tasks) == 1
        finally:
            await mgr.stop()

    def test_reconnect_constants(self):
        mgr = BinanceWSManager(symbol="btcusdt")
        assert mgr.RECONNECT_BASE_DELAY == 1.0
        assert mgr.RECONNECT_MAX_DELAY == 30.0
        assert mgr.MAX_RECONNECT_FAILURES == 5
        assert mgr.HEALTH_TIMEOUT_SEC == 30.0

    @pytest.mark.asyncio
    async def test_reconnect_failure_stops_running(self):
        mgr = BinanceWSManager(symbol="btcusdt")
        mgr._running = True
        mgr.RECONNECT_BASE_DELAY = 0.01  # Speed up test
        mgr.RECONNECT_MAX_DELAY = 0.02

        async def mock_connect():
            raise ConnectionError("Test error")

        mgr._connect_and_listen = mock_connect
        # Run _run_streams directly to test reconnect logic
        await mgr._run_streams()
        assert mgr._running is False
        assert mgr._reconnect_failures >= mgr.MAX_RECONNECT_FAILURES
