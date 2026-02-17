"""VitalityTracker 테스트."""
import pytest

from src.ai.confluence.vitality_tracker import (
    VitalityLevel,
    VitalityTracker,
)


class TestVitalityLevel:
    """VitalityLevel enum 테스트."""

    def test_level_values(self):
        assert VitalityLevel.HEALTHY.value == "healthy"
        assert VitalityLevel.CAUTION.value == "caution"
        assert VitalityLevel.WARNING.value == "warning"
        assert VitalityLevel.CRITICAL.value == "critical"


class TestVitalityTracker:
    """VitalityTracker 테스트."""

    def setup_method(self):
        self.tracker = VitalityTracker(window_size=10)

    def test_empty_tracker(self):
        snapshot = self.tracker.get_vitality()
        assert snapshot.level == VitalityLevel.HEALTHY
        assert snapshot.trade_count == 0
        assert snapshot.sharpe_ratio == 0.0

    def test_single_trade(self):
        self.tracker.record_trade(0.02)
        snapshot = self.tracker.get_vitality()
        assert snapshot.trade_count == 1
        assert snapshot.avg_pnl_pct == 0.02

    def test_healthy_trades(self):
        """일관적으로 양의 PnL → HEALTHY."""
        for _ in range(5):
            self.tracker.record_trade(0.03)
        snapshot = self.tracker.get_vitality()
        assert snapshot.trade_count == 5
        # 동일 값 → std=0 → sharpe=0 (WARNING or HEALTHY)
        # 약간 분산 추가
        self.tracker = VitalityTracker(window_size=10)
        trades = [0.03, 0.02, 0.04, 0.025, 0.035]
        for t in trades:
            self.tracker.record_trade(t)
        snapshot = self.tracker.get_vitality()
        assert snapshot.sharpe_ratio > 1.0
        assert snapshot.level == VitalityLevel.HEALTHY

    def test_critical_trades(self):
        """일관적으로 음의 PnL → CRITICAL."""
        trades = [-0.03, -0.02, -0.04, -0.025, -0.035]
        for t in trades:
            self.tracker.record_trade(t)
        snapshot = self.tracker.get_vitality()
        assert snapshot.sharpe_ratio < 0
        assert snapshot.level == VitalityLevel.CRITICAL

    def test_mixed_trades_warning(self):
        """혼합 PnL → WARNING/CAUTION."""
        trades = [0.01, -0.01, 0.005, -0.005, 0.001]
        for t in trades:
            self.tracker.record_trade(t)
        snapshot = self.tracker.get_vitality()
        assert snapshot.level in (VitalityLevel.WARNING, VitalityLevel.CAUTION)

    def test_window_size_limit(self):
        """window_size 초과 시 오래된 데이터 제거."""
        tracker = VitalityTracker(window_size=3)
        tracker.record_trade(0.10)  # will be evicted
        tracker.record_trade(0.01)
        tracker.record_trade(0.01)
        tracker.record_trade(0.01)  # 4th trade, window=3
        snapshot = tracker.get_vitality()
        assert snapshot.trade_count == 3
        # avg should be ~0.01 (old 0.10 evicted)
        assert snapshot.avg_pnl_pct == pytest.approx(0.01)

    def test_classify_level_boundaries(self):
        assert VitalityTracker._classify_level(1.5) == VitalityLevel.HEALTHY
        assert VitalityTracker._classify_level(1.0) == VitalityLevel.HEALTHY
        assert VitalityTracker._classify_level(0.75) == VitalityLevel.CAUTION
        assert VitalityTracker._classify_level(0.5) == VitalityLevel.CAUTION
        assert VitalityTracker._classify_level(0.25) == VitalityLevel.WARNING
        assert VitalityTracker._classify_level(0.0) == VitalityLevel.WARNING
        assert VitalityTracker._classify_level(-0.1) == VitalityLevel.CRITICAL
