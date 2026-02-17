"""Tests for ExecutionTracker.

실행 품질 추적기의 record, quality, size modifier, slippage, pause, serialization 테스트.
"""

import pytest

from src.trading.execution_tracker import ExecutionTracker


@pytest.fixture
def tracker() -> ExecutionTracker:
    """기본 ExecutionTracker 인스턴스 (window_size=50)."""
    return ExecutionTracker(window_size=50)


@pytest.fixture
def small_tracker() -> ExecutionTracker:
    """소형 window ExecutionTracker (window_size=5)."""
    return ExecutionTracker(window_size=5)


def _fill_tracker_with_quality(
    tracker: ExecutionTracker, quality: float, count: int = 10
) -> None:
    """Helper: tracker에 지정 품질 비율로 실행 기록을 채운다.

    actual = theoretical * quality 로 설정하여 get_exec_quality() ~= quality.
    주의: count가 클수록 FP 누적 오차가 생길 수 있음.
    """
    for _ in range(count):
        tracker.record_execution(
            entry_price=100.0,
            exit_price=101.0,
            side="LONG",
            pnl_actual=10.0 * quality,
            pnl_theoretical=10.0,
            slippage_pct=0.05,
        )


class TestExecutionTracker:
    """ExecutionTracker 핵심 기능 테스트."""

    def test_empty_tracker_quality(self, tracker: ExecutionTracker) -> None:
        """빈 트래커: quality = 1.0."""
        assert tracker.get_exec_quality() == 1.0

    def test_empty_tracker_modifier(self, tracker: ExecutionTracker) -> None:
        """빈 트래커: quality=1.0 > 0.95 이므로 modifier = 1.05."""
        assert tracker.get_size_modifier() == 1.05

    def test_empty_tracker_slippage(self, tracker: ExecutionTracker) -> None:
        """빈 트래커: slippage factor = 0.1 (기본값)."""
        assert tracker.get_calibrated_slippage_factor() == 0.1

    def test_empty_tracker_pause(self, tracker: ExecutionTracker) -> None:
        """빈 트래커: pause = False."""
        assert tracker.should_pause_strategy() is False

    def test_single_execution_record(self, tracker: ExecutionTracker) -> None:
        """단일 실행 기록 후 quality 확인."""
        tracker.record_execution(
            entry_price=50000.0,
            exit_price=50500.0,
            side="LONG",
            pnl_actual=8.0,
            pnl_theoretical=10.0,
            slippage_pct=0.02,
        )
        assert tracker.get_exec_quality() == pytest.approx(0.8, rel=1e-6)

    def test_record_and_quality_multiple(self, tracker: ExecutionTracker) -> None:
        """여러 실행 기록 후 품질 = mean(actual/theoretical)."""
        # Record 1: ratio = 9/10 = 0.9
        tracker.record_execution(
            entry_price=100.0, exit_price=101.0, side="LONG",
            pnl_actual=9.0, pnl_theoretical=10.0, slippage_pct=0.01,
        )
        # Record 2: ratio = 7/10 = 0.7
        tracker.record_execution(
            entry_price=100.0, exit_price=99.0, side="SHORT",
            pnl_actual=7.0, pnl_theoretical=10.0, slippage_pct=0.03,
        )
        # mean(0.9, 0.7) = 0.8
        assert tracker.get_exec_quality() == pytest.approx(0.8, rel=1e-6)

    def test_rolling_window_keeps_only_last_n(self) -> None:
        """window_size=50일 때 55건 추가하면 마지막 50건만 유지."""
        t = ExecutionTracker(window_size=50)
        for i in range(55):
            t.record_execution(
                entry_price=100.0, exit_price=101.0, side="LONG",
                pnl_actual=float(i), pnl_theoretical=10.0, slippage_pct=0.01,
            )
        # deque maxlen=50 이므로 55건 중 인덱스 5~54만 남음
        data = t.to_dict()
        assert len(data["executions"]) == 50
        # 첫 번째 남은 기록은 i=5
        assert data["executions"][0]["pnl_actual"] == 5.0
        # 마지막 기록은 i=54
        assert data["executions"][-1]["pnl_actual"] == 54.0

    def test_mixed_positive_negative_results(self, tracker: ExecutionTracker) -> None:
        """양수/음수 결과 혼합 시 quality 계산."""
        # ratio = 8/10 = 0.8
        tracker.record_execution(
            entry_price=100.0, exit_price=101.0, side="LONG",
            pnl_actual=8.0, pnl_theoretical=10.0, slippage_pct=0.02,
        )
        # ratio = -4/-5 = 0.8  (both negative -> positive ratio)
        tracker.record_execution(
            entry_price=100.0, exit_price=99.0, side="LONG",
            pnl_actual=-4.0, pnl_theoretical=-5.0, slippage_pct=0.02,
        )
        # mean(0.8, 0.8) = 0.8
        assert tracker.get_exec_quality() == pytest.approx(0.8, rel=1e-6)

    def test_zero_theoretical_pnl_excluded(self, tracker: ExecutionTracker) -> None:
        """theoretical PnL이 0인 거래는 quality 계산에서 제외."""
        # 유효 기록: ratio = 9/10 = 0.9
        tracker.record_execution(
            entry_price=100.0, exit_price=101.0, side="LONG",
            pnl_actual=9.0, pnl_theoretical=10.0, slippage_pct=0.01,
        )
        # theoretical = 0 -> 제외
        tracker.record_execution(
            entry_price=100.0, exit_price=100.0, side="LONG",
            pnl_actual=0.0, pnl_theoretical=0.0, slippage_pct=0.0,
        )
        # 유효한 기록만 사용: quality = 0.9
        assert tracker.get_exec_quality() == pytest.approx(0.9, rel=1e-6)

    def test_all_zero_theoretical_returns_one(self, tracker: ExecutionTracker) -> None:
        """모든 theoretical PnL이 0이면 quality = 1.0 (기본값)."""
        tracker.record_execution(
            entry_price=100.0, exit_price=100.0, side="LONG",
            pnl_actual=0.0, pnl_theoretical=0.0, slippage_pct=0.0,
        )
        tracker.record_execution(
            entry_price=100.0, exit_price=100.0, side="SHORT",
            pnl_actual=0.5, pnl_theoretical=0.0, slippage_pct=0.0,
        )
        assert tracker.get_exec_quality() == 1.0

    def test_calibrated_slippage_factor(self, tracker: ExecutionTracker) -> None:
        """기록된 슬리피지의 평균 반환."""
        tracker.record_execution(
            entry_price=100.0, exit_price=101.0, side="LONG",
            pnl_actual=10.0, pnl_theoretical=10.0, slippage_pct=0.02,
        )
        tracker.record_execution(
            entry_price=100.0, exit_price=101.0, side="LONG",
            pnl_actual=10.0, pnl_theoretical=10.0, slippage_pct=0.06,
        )
        # mean(0.02, 0.06) = 0.04
        assert tracker.get_calibrated_slippage_factor() == pytest.approx(0.04, rel=1e-6)


class TestExecutionSizeModifier:
    """get_size_modifier() 임계값 테스트."""

    def test_quality_050_returns_0(self, tracker: ExecutionTracker) -> None:
        """quality=0.50 (<0.60) -> size modifier = 0.0."""
        _fill_tracker_with_quality(tracker, 0.50)
        assert tracker.get_exec_quality() == pytest.approx(0.50, rel=1e-6)
        assert tracker.get_size_modifier() == 0.0

    def test_quality_059_returns_0(self, tracker: ExecutionTracker) -> None:
        """quality=0.59 (<0.60 경계) -> size modifier = 0.0."""
        _fill_tracker_with_quality(tracker, 0.59)
        assert tracker.get_size_modifier() == 0.0

    def test_quality_060_returns_09(self, tracker: ExecutionTracker) -> None:
        """quality=0.60 (>=0.60 but <0.80) -> size modifier = 0.9."""
        # count=1 로 FP 누적 오차 방지 (sum([0.6]*10)/10 != 0.6)
        _fill_tracker_with_quality(tracker, 0.60, count=1)
        assert tracker.get_exec_quality() == pytest.approx(0.60, rel=1e-6)
        assert tracker.get_size_modifier() == 0.9

    def test_quality_070_returns_09(self, tracker: ExecutionTracker) -> None:
        """quality=0.70 (<0.80) -> size modifier = 0.9."""
        _fill_tracker_with_quality(tracker, 0.70)
        assert tracker.get_exec_quality() == pytest.approx(0.70, rel=1e-6)
        assert tracker.get_size_modifier() == 0.9

    def test_quality_080_returns_10(self, tracker: ExecutionTracker) -> None:
        """quality=0.80 (>=0.80, <=0.95) -> size modifier = 1.0."""
        # count=1 로 FP 누적 오차 방지
        _fill_tracker_with_quality(tracker, 0.80, count=1)
        assert tracker.get_exec_quality() == pytest.approx(0.80, rel=1e-6)
        assert tracker.get_size_modifier() == 1.0

    def test_quality_085_returns_10(self, tracker: ExecutionTracker) -> None:
        """quality=0.85 -> size modifier = 1.0."""
        _fill_tracker_with_quality(tracker, 0.85)
        assert tracker.get_exec_quality() == pytest.approx(0.85, rel=1e-6)
        assert tracker.get_size_modifier() == 1.0

    def test_quality_095_returns_10(self, tracker: ExecutionTracker) -> None:
        """quality=0.95 (경계값, <=0.95) -> size modifier = 1.0."""
        _fill_tracker_with_quality(tracker, 0.95)
        assert tracker.get_exec_quality() == pytest.approx(0.95, rel=1e-6)
        assert tracker.get_size_modifier() == 1.0

    def test_quality_098_returns_105(self, tracker: ExecutionTracker) -> None:
        """quality=0.98 (>0.95) -> size modifier = 1.05."""
        _fill_tracker_with_quality(tracker, 0.98)
        assert tracker.get_exec_quality() == pytest.approx(0.98, rel=1e-6)
        assert tracker.get_size_modifier() == 1.05


class TestExecutionPause:
    """should_pause_strategy() 테스트."""

    def test_pause_when_quality_below_060(self, tracker: ExecutionTracker) -> None:
        """quality < 0.60 -> 일시정지."""
        _fill_tracker_with_quality(tracker, 0.50)
        assert tracker.should_pause_strategy() is True

    def test_no_pause_at_060(self, tracker: ExecutionTracker) -> None:
        """quality = 0.60 -> 일시정지 아님."""
        # count=1 로 FP 누적 오차 방지
        _fill_tracker_with_quality(tracker, 0.60, count=1)
        assert tracker.should_pause_strategy() is False

    def test_no_pause_at_high_quality(self, tracker: ExecutionTracker) -> None:
        """quality = 0.90 -> 일시정지 아님."""
        _fill_tracker_with_quality(tracker, 0.90)
        assert tracker.should_pause_strategy() is False


class TestExecutionSerialization:
    """to_dict() / from_dict() 직렬화 테스트."""

    def test_round_trip_empty(self, tracker: ExecutionTracker) -> None:
        """빈 트래커 직렬화 -> 복원 라운드트립."""
        data = tracker.to_dict()
        new_tracker = ExecutionTracker(window_size=10)  # 다른 window_size로 생성
        new_tracker.from_dict(data)

        assert new_tracker.get_exec_quality() == 1.0
        assert new_tracker._window_size == 50  # 원본 window_size 복원

    def test_round_trip_with_data(self, tracker: ExecutionTracker) -> None:
        """기록이 있는 트래커 직렬화 -> 복원 라운드트립."""
        tracker.record_execution(
            entry_price=100.0, exit_price=101.0, side="LONG",
            pnl_actual=9.0, pnl_theoretical=10.0, slippage_pct=0.03,
        )
        tracker.record_execution(
            entry_price=100.0, exit_price=99.0, side="SHORT",
            pnl_actual=7.0, pnl_theoretical=10.0, slippage_pct=0.05,
        )

        data = tracker.to_dict()
        new_tracker = ExecutionTracker()
        new_tracker.from_dict(data)

        assert new_tracker.get_exec_quality() == pytest.approx(
            tracker.get_exec_quality(), rel=1e-6
        )
        assert new_tracker.get_calibrated_slippage_factor() == pytest.approx(
            tracker.get_calibrated_slippage_factor(), rel=1e-6
        )
        assert new_tracker.get_size_modifier() == tracker.get_size_modifier()
        assert new_tracker.should_pause_strategy() == tracker.should_pause_strategy()

    def test_to_dict_structure(self, tracker: ExecutionTracker) -> None:
        """to_dict 반환값 구조 확인."""
        tracker.record_execution(
            entry_price=100.0, exit_price=101.0, side="LONG",
            pnl_actual=10.0, pnl_theoretical=10.0, slippage_pct=0.01,
        )
        data = tracker.to_dict()

        assert "window_size" in data
        assert "executions" in data
        assert data["window_size"] == 50
        assert len(data["executions"]) == 1
        assert data["executions"][0]["side"] == "LONG"
        assert data["executions"][0]["pnl_actual"] == 10.0

    def test_from_dict_restores_maxlen(self) -> None:
        """from_dict로 복원 후 maxlen 제한이 유지되는지 확인."""
        t = ExecutionTracker(window_size=3)
        for i in range(3):
            t.record_execution(
                entry_price=100.0, exit_price=101.0, side="LONG",
                pnl_actual=float(i), pnl_theoretical=10.0, slippage_pct=0.01,
            )
        data = t.to_dict()

        restored = ExecutionTracker()
        restored.from_dict(data)

        # maxlen=3으로 복원되었으므로 추가 기록 시 오래된 것 제거
        restored.record_execution(
            entry_price=100.0, exit_price=101.0, side="LONG",
            pnl_actual=99.0, pnl_theoretical=10.0, slippage_pct=0.01,
        )
        assert len(restored.to_dict()["executions"]) == 3
        # 가장 오래된 i=0 제거, i=1, i=2, 99.0 남음
        assert restored.to_dict()["executions"][0]["pnl_actual"] == 1.0
        assert restored.to_dict()["executions"][-1]["pnl_actual"] == 99.0
