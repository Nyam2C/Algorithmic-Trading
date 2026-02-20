"""Tests for API Weight Tracker (WS-6)."""
import time

from src.exchange.api_weight_tracker import APIWeightTracker


class TestAPIWeightTracker:
    """APIWeightTracker 테스트."""

    def test_initial_weight_zero(self):
        tracker = APIWeightTracker()
        assert tracker.current_weight == 0

    def test_record_increases_weight(self):
        tracker = APIWeightTracker()
        tracker.record("get_klines")
        assert tracker.current_weight == 5  # get_klines weight = 5

    def test_record_unknown_endpoint_weight_1(self):
        tracker = APIWeightTracker()
        tracker.record("unknown_endpoint")
        assert tracker.current_weight == 1

    def test_can_proceed_under_target(self):
        tracker = APIWeightTracker()
        assert tracker.can_proceed("get_klines") is True

    def test_can_proceed_at_target(self):
        """TARGET에 도달하면 추가 호출 불가."""
        tracker = APIWeightTracker()
        # TARGET=800, get_klines=5 → 160회로 800
        for _ in range(160):
            tracker.record("get_klines")
        assert tracker.current_weight == 800
        assert tracker.can_proceed("get_klines") is False

    def test_should_delay_zero_under_target(self):
        tracker = APIWeightTracker()
        assert tracker.should_delay() == 0.0

    def test_should_delay_positive_over_target(self):
        tracker = APIWeightTracker()
        for _ in range(170):
            tracker.record("get_klines")
        delay = tracker.should_delay()
        assert delay > 0.0

    def test_should_delay_max_at_limit(self):
        tracker = APIWeightTracker()
        for _ in range(240):
            tracker.record("get_klines")
        delay = tracker.should_delay()
        assert delay == APIWeightTracker.MAX_DELAY_SEC

    def test_window_purge_after_60s(self):
        """60초 이후 가중치 자동 제거."""
        tracker = APIWeightTracker()
        # 수동으로 과거 기록 추가
        tracker._window.append((time.monotonic() - 61, 100))
        assert tracker.current_weight == 0  # purge됨

    def test_get_status(self):
        tracker = APIWeightTracker()
        tracker.record("get_klines")
        status = tracker.get_status()
        assert status["current_weight"] == 5
        assert status["target_weight"] == 800
        assert status["max_weight"] == 1200
        assert "utilization_pct" in status
        assert "can_proceed" in status

    def test_endpoint_weights_defined(self):
        """주요 엔드포인트 가중치 정의 확인."""
        assert APIWeightTracker.ENDPOINT_WEIGHTS["get_klines"] == 5
        assert APIWeightTracker.ENDPOINT_WEIGHTS["get_funding_rate"] == 1
        assert APIWeightTracker.ENDPOINT_WEIGHTS["create_market_order"] == 1

    def test_multiple_records(self):
        tracker = APIWeightTracker()
        tracker.record("get_klines")       # 5
        tracker.record("get_position")     # 5
        tracker.record("get_funding_rate") # 1
        assert tracker.current_weight == 11
