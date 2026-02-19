"""LiquidationAggregator 테스트."""
import time

from src.exchange.ws_manager import LiquidationAggregator


class TestLiquidationAggregatorUpdate:
    """update() 메서드 테스트."""

    def test_valid_force_order_message(self):
        agg = LiquidationAggregator()
        msg = {"o": {"S": "SELL", "q": "1.5", "p": "50000"}}
        agg.update(msg)
        assert len(agg._buffer) == 1

    def test_buy_side_message(self):
        agg = LiquidationAggregator()
        msg = {"o": {"S": "BUY", "q": "0.5", "p": "48000"}}
        agg.update(msg)
        assert agg._buffer[0][1] == "BUY"

    def test_invalid_side_skipped(self):
        agg = LiquidationAggregator()
        msg = {"o": {"S": "INVALID", "q": "1.0", "p": "50000"}}
        agg.update(msg)
        assert len(agg._buffer) == 0

    def test_zero_qty_skipped(self):
        agg = LiquidationAggregator()
        msg = {"o": {"S": "SELL", "q": "0", "p": "50000"}}
        agg.update(msg)
        assert len(agg._buffer) == 0

    def test_zero_price_skipped(self):
        agg = LiquidationAggregator()
        msg = {"o": {"S": "SELL", "q": "1.0", "p": "0"}}
        agg.update(msg)
        assert len(agg._buffer) == 0

    def test_flat_message_format(self):
        """msg 자체가 o 필드 없이 flat인 경우."""
        agg = LiquidationAggregator()
        msg = {"S": "SELL", "q": "2.0", "p": "45000"}
        agg.update(msg)
        assert len(agg._buffer) == 1

    def test_invalid_qty_type_skipped(self):
        agg = LiquidationAggregator()
        msg = {"o": {"S": "SELL", "q": "abc", "p": "50000"}}
        agg.update(msg)
        assert len(agg._buffer) == 0

    def test_maxlen_enforced(self):
        agg = LiquidationAggregator()
        for _i in range(LiquidationAggregator.MAX_BUFFER_SIZE + 100):
            agg.update({"o": {"S": "SELL", "q": "0.1", "p": "50000"}})
        assert len(agg._buffer) == LiquidationAggregator.MAX_BUFFER_SIZE

    def test_updates_last_update_time(self):
        agg = LiquidationAggregator()
        assert agg._last_update_time == 0.0
        agg.update({"o": {"S": "SELL", "q": "1.0", "p": "50000"}})
        assert agg._last_update_time > 0


class TestLiquidationAggregatorSnapshot:
    """snapshot() 메서드 테스트."""

    def test_empty_returns_none(self):
        agg = LiquidationAggregator()
        assert agg.snapshot() is None

    def test_stale_returns_none(self):
        agg = LiquidationAggregator()
        agg.update({"o": {"S": "SELL", "q": "1.0", "p": "50000"}})
        # Force stale
        agg._last_update_time = time.monotonic() - 120.0
        assert agg.snapshot() is None

    def test_snapshot_with_events(self):
        agg = LiquidationAggregator()
        agg.update({"o": {"S": "SELL", "q": "1.5", "p": "50000"}})
        agg.update({"o": {"S": "BUY", "q": "0.5", "p": "48000"}})

        snap = agg.snapshot(window=60.0)
        assert snap is not None
        assert snap["count"] == 2
        assert snap["sell_vol"] == 1.5
        assert snap["buy_vol"] == 0.5
        assert snap["total_vol"] == 2.0

    def test_snapshot_window_filter(self):
        agg = LiquidationAggregator()
        now = time.monotonic()

        # Old event (outside window)
        agg._buffer.append((now - 100.0, "SELL", 1.0, 50000.0))
        # Recent event
        agg._buffer.append((now - 5.0, "SELL", 2.0, 49000.0))
        agg._last_update_time = now - 5.0

        snap = agg.snapshot(window=30.0)
        assert snap is not None
        assert snap["count"] == 1
        assert snap["sell_vol"] == 2.0


class TestLiquidationAggregatorHelpers:
    """count_in_window(), daily_average() 테스트."""

    def test_count_in_window(self):
        agg = LiquidationAggregator()
        agg.update({"o": {"S": "SELL", "q": "1.0", "p": "50000"}})
        agg.update({"o": {"S": "BUY", "q": "0.5", "p": "48000"}})
        assert agg.count_in_window(30.0) == 2

    def test_count_in_window_empty(self):
        agg = LiquidationAggregator()
        assert agg.count_in_window(30.0) == 0

    def test_daily_average_empty(self):
        agg = LiquidationAggregator()
        assert agg.daily_average() == 0.0

    def test_daily_average_single_event(self):
        agg = LiquidationAggregator()
        agg.update({"o": {"S": "SELL", "q": "1.0", "p": "50000"}})
        # single event → span=0 → 0.0
        assert agg.daily_average() == 0.0

    def test_daily_average_multiple_events(self):
        agg = LiquidationAggregator()
        now = time.monotonic()
        # 10 events over 100 seconds → 0.1/sec → 8640/day
        for i in range(10):
            agg._buffer.append((now - 100 + i * 10, "SELL", 1.0, 50000.0))
        avg = agg.daily_average()
        assert avg > 0
        # ~8640 events/day (10 events / 90s span * 86400)
        assert 5000 < avg < 15000
