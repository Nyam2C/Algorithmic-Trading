"""LiquidationCascadeHunter 테스트."""
import time

import pytest

from src.ai.channels.liquidation_cascade import (
    LiquidationCascadeHunter,
)
from src.ai.ensemble import SignalSource


@pytest.fixture
def hunter():
    return LiquidationCascadeHunter()


def _make_events(count: int, window: float = 30.0):
    """윈도우 내에 count개 이벤트 생성."""
    now = time.monotonic()
    events = []
    for i in range(count):
        ts = now - window + (i * window / max(count, 1))
        events.append((ts, "SELL", 1.0, 50000.0))
    return events


class TestDetectCascade:
    def test_no_daily_avg(self, hunter):
        snap = {"count": 10}
        is_cascade, ratio = hunter._detect_cascade(snap, 0.0)
        assert not is_cascade

    def test_below_threshold(self, hunter):
        # daily_avg=2880 → expected_30s = 2880/(86400/30) = 1.0
        snap = {"count": 2}
        is_cascade, ratio = hunter._detect_cascade(snap, 2880.0)
        assert not is_cascade
        assert ratio == 2.0

    def test_above_threshold(self, hunter):
        # expected_30s = 2880/(86400/30) = 1.0, count=4 → ratio=4.0 >= 3.0
        snap = {"count": 4}
        is_cascade, ratio = hunter._detect_cascade(snap, 2880.0)
        assert is_cascade
        assert ratio >= 3.0


class TestCheckDeceleration:
    def test_empty_events(self, hunter):
        assert not hunter._check_deceleration([])

    def test_single_event(self, hunter):
        now = time.monotonic()
        assert not hunter._check_deceleration([(now, "SELL", 1.0, 50000.0)])

    def test_decelerating(self, hunter):
        """30초 전체에 10건, 최근 10초에 1건 → 감속."""
        now = time.monotonic()
        events = []
        # 20~30초 전: 9건 (가속)
        for i in range(9):
            events.append((now - 30 + i * 2, "SELL", 1.0, 50000.0))
        # 최근 10초: 1건 (감속)
        events.append((now - 2, "SELL", 1.0, 50000.0))
        assert hunter._check_deceleration(events)

    def test_accelerating(self, hunter):
        """최근 10초에 더 많은 건수 → 가속."""
        now = time.monotonic()
        events = []
        # 20~30초 전: 1건
        events.append((now - 25, "SELL", 1.0, 50000.0))
        # 최근 10초: 9건
        for i in range(9):
            events.append((now - 8 + i, "SELL", 1.0, 50000.0))
        assert not hunter._check_deceleration(events)


class TestCheckRsiExtreme:
    def test_none_rsi(self, hunter):
        is_extreme, direction = hunter._check_rsi_extreme(None)
        assert not is_extreme

    def test_low_rsi(self, hunter):
        is_extreme, direction = hunter._check_rsi_extreme(10.0)
        assert is_extreme
        assert direction == "LONG"

    def test_high_rsi(self, hunter):
        is_extreme, direction = hunter._check_rsi_extreme(90.0)
        assert is_extreme
        assert direction == "SHORT"

    def test_normal_rsi(self, hunter):
        is_extreme, direction = hunter._check_rsi_extreme(50.0)
        assert not is_extreme


class TestCheckOppositeDepth:
    def test_none_depth(self, hunter):
        assert not hunter._check_opposite_depth(None, True)

    def test_sell_dominant_bid_strong(self, hunter):
        depth = {"bid_depth_total": 20.0, "ask_depth_total": 10.0}
        assert hunter._check_opposite_depth(depth, True)

    def test_sell_dominant_bid_weak(self, hunter):
        depth = {"bid_depth_total": 10.0, "ask_depth_total": 10.0}
        assert not hunter._check_opposite_depth(depth, True)

    def test_buy_dominant_ask_strong(self, hunter):
        depth = {"bid_depth_total": 10.0, "ask_depth_total": 20.0}
        assert hunter._check_opposite_depth(depth, False)


class TestModeASignal:
    @pytest.mark.asyncio
    async def test_no_data(self, hunter):
        sig = await hunter.generate_signal(None, 0.0)
        assert sig.signal == "WAIT"
        assert sig.source == SignalSource.LIQUIDATION_CASCADE

    @pytest.mark.asyncio
    async def test_no_cascade(self, hunter):
        snap = {"count": 1, "sell_vol": 0.5, "buy_vol": 0.5, "events": []}
        sig = await hunter.generate_signal(snap, 2880.0)
        assert sig.signal == "WAIT"

    @pytest.mark.asyncio
    async def test_cascade_with_deceleration(self, hunter):
        now = time.monotonic()
        events = []
        for i in range(9):
            events.append((now - 28 + i * 2, "SELL", 1.0, 50000.0))
        events.append((now - 1, "SELL", 1.0, 50000.0))

        snap = {
            "count": 10,
            "sell_vol": 8.0,
            "buy_vol": 2.0,
            "events": events,
        }
        # daily_avg=2880 → expected_30s=1.0 → ratio=10.0
        sig = await hunter.generate_signal(snap, 2880.0)
        assert sig.signal == "LONG"
        assert sig.confidence > 0

    @pytest.mark.asyncio
    async def test_cascade_without_deceleration(self, hunter):
        """가속 중이면 WAIT."""
        now = time.monotonic()
        events = []
        for i in range(10):
            events.append((now - 5 + i * 0.5, "SELL", 1.0, 50000.0))

        snap = {
            "count": 10,
            "sell_vol": 8.0,
            "buy_vol": 2.0,
            "events": events,
        }
        sig = await hunter.generate_signal(snap, 2880.0)
        assert sig.signal == "WAIT"


class TestModeBTrigger:
    @pytest.mark.asyncio
    async def test_no_data(self, hunter):
        trigger = await hunter.evaluate_cascade_trigger(None, 0.0)
        assert not trigger.should_enter

    @pytest.mark.asyncio
    async def test_all_conditions_met(self, hunter):
        now = time.monotonic()
        events = []
        for i in range(9):
            events.append((now - 28 + i * 2, "SELL", 1.0, 50000.0))
        events.append((now - 1, "SELL", 1.0, 50000.0))

        snap = {
            "count": 10,
            "sell_vol": 8.0,
            "buy_vol": 2.0,
            "events": events,
        }
        depth = {"bid_depth_total": 20.0, "ask_depth_total": 10.0}

        trigger = await hunter.evaluate_cascade_trigger(
            snap, 2880.0, rsi_1m=10.0, depth=depth
        )
        assert trigger.should_enter
        assert trigger.direction == "LONG"
        assert trigger.confidence > 0

    @pytest.mark.asyncio
    async def test_missing_rsi_condition(self, hunter):
        now = time.monotonic()
        events = []
        for i in range(9):
            events.append((now - 28 + i * 2, "SELL", 1.0, 50000.0))
        events.append((now - 1, "SELL", 1.0, 50000.0))

        snap = {
            "count": 10,
            "sell_vol": 8.0,
            "buy_vol": 2.0,
            "events": events,
        }
        depth = {"bid_depth_total": 20.0, "ask_depth_total": 10.0}

        # RSI=50 → not extreme
        trigger = await hunter.evaluate_cascade_trigger(
            snap, 2880.0, rsi_1m=50.0, depth=depth
        )
        assert not trigger.should_enter

    @pytest.mark.asyncio
    async def test_missing_depth_condition(self, hunter):
        now = time.monotonic()
        events = []
        for i in range(9):
            events.append((now - 28 + i * 2, "SELL", 1.0, 50000.0))
        events.append((now - 1, "SELL", 1.0, 50000.0))

        snap = {
            "count": 10,
            "sell_vol": 8.0,
            "buy_vol": 2.0,
            "events": events,
        }
        # No depth
        trigger = await hunter.evaluate_cascade_trigger(
            snap, 2880.0, rsi_1m=10.0, depth=None
        )
        assert not trigger.should_enter
