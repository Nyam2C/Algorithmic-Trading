"""Threshold Tuner 테스트."""
import pytest

from src.ai.confluence.session_classifier import TradingSession
from src.ai.confluence.threshold_tuner import (
    FLOOR_THRESHOLDS,
    ThresholdTuner,
    TradeRecord,
)


@pytest.fixture
def tuner():
    return ThresholdTuner()


@pytest.fixture
def default_thresholds():
    return {
        "strong_trend": {
            TradingSession.US: 0.25,
            TradingSession.EU: 0.28,
            TradingSession.ASIA: 0.30,
            TradingSession.DEEP_NIGHT: 0.35,
        },
        "weak_trend": {
            TradingSession.US: 0.30,
            TradingSession.EU: 0.33,
            TradingSession.ASIA: 0.35,
            TradingSession.DEEP_NIGHT: 0.40,
        },
    }


def _make_records(
    n: int,
    regime: str = "strong_trend",
    session: TradingSession = TradingSession.US,
    win_pct: float = 0.6,
    score_range: tuple[float, float] = (0.2, 0.8),
):
    """테스트용 거래 기록 생성."""
    records = []
    for i in range(n):
        score = score_range[0] + (score_range[1] - score_range[0]) * i / max(n - 1, 1)
        is_win = i < int(n * win_pct)
        records.append(TradeRecord(
            confluence_score=round(score, 3),
            regime=regime,
            session=session,
            is_win=is_win,
        ))
    return records


class TestFindMinThreshold:
    def test_all_wins(self, tuner):
        """모든 거래가 승 → 가장 낮은 score가 threshold."""
        records = _make_records(10, win_pct=1.0, score_range=(0.2, 0.8))
        threshold = tuner._find_min_threshold_for_wr(records, 0.57)
        assert threshold is not None
        assert threshold == 0.2  # 최저 score

    def test_all_losses(self, tuner):
        """모든 거래가 패 → None."""
        records = _make_records(10, win_pct=0.0, score_range=(0.2, 0.8))
        threshold = tuner._find_min_threshold_for_wr(records, 0.57)
        assert threshold is None

    def test_mixed_find_threshold(self, tuner):
        """혼합 거래에서 threshold 찾기."""
        # 0-5: 승(score 0.2~0.5), 6-9: 패(score 0.533~0.8)
        records = _make_records(10, win_pct=0.6, score_range=(0.2, 0.8))
        threshold = tuner._find_min_threshold_for_wr(records, 0.57)
        assert threshold is not None
        # 낮은 score 포함할수록 WR 높으므로 threshold는 낮은 값
        assert 0.2 <= threshold <= 0.8

    def test_empty_records(self, tuner):
        threshold = tuner._find_min_threshold_for_wr([], 0.57)
        assert threshold is None


class TestTune:
    def test_sufficient_samples(self, tuner, default_thresholds):
        records = _make_records(
            15, regime="strong_trend", session=TradingSession.US,
            win_pct=0.8, score_range=(0.2, 0.6),
        )
        results = tuner.tune(records, default_thresholds)
        assert len(results) == 1
        assert results[0].regime == "strong_trend"
        assert results[0].session == TradingSession.US
        assert results[0].sample_count == 15

    def test_insufficient_samples_skipped(self, tuner, default_thresholds):
        records = _make_records(
            5, regime="strong_trend", session=TradingSession.US,
        )
        results = tuner.tune(records, default_thresholds)
        assert len(results) == 0

    def test_smoothing_applied(self, tuner, default_thresholds):
        """old * 0.7 + new * 0.3 smoothing."""
        records = _make_records(
            20, regime="strong_trend", session=TradingSession.US,
            win_pct=1.0, score_range=(0.1, 0.5),
        )
        results = tuner.tune(records, default_thresholds)
        assert len(results) == 1
        result = results[0]
        # old=0.25, calc=0.1 → smoothed = 0.7*0.25 + 0.3*0.1 = 0.205
        # But floor for strong_trend/US = 0.15
        expected_smoothed = 0.7 * 0.25 + 0.3 * 0.1
        assert abs(result.new_threshold - round(expected_smoothed, 4)) < 0.01

    def test_floor_enforced(self, tuner, default_thresholds):
        """Floor 이하로 내려가지 않음."""
        records = _make_records(
            20, regime="strong_trend", session=TradingSession.US,
            win_pct=1.0, score_range=(0.01, 0.05),
        )
        results = tuner.tune(records, default_thresholds)
        assert len(results) == 1
        floor = FLOOR_THRESHOLDS["strong_trend"][TradingSession.US]
        assert results[0].new_threshold >= floor

    def test_multiple_buckets(self, tuner, default_thresholds):
        records = (
            _make_records(15, "strong_trend", TradingSession.US, 0.8)
            + _make_records(15, "weak_trend", TradingSession.EU, 0.7)
        )
        results = tuner.tune(records, default_thresholds)
        assert len(results) == 2


class TestApplyToEngine:
    def test_apply_updates(self, tuner, default_thresholds):
        from src.ai.confluence.threshold_tuner import TuningResult
        results = [
            TuningResult(
                regime="strong_trend",
                session=TradingSession.US,
                old_threshold=0.25,
                calc_threshold=0.20,
                new_threshold=0.22,
                sample_count=15,
                achieved_win_rate=0.60,
            ),
        ]
        new_table = tuner.apply_to_engine(default_thresholds, results)
        assert new_table["strong_trend"][TradingSession.US] == 0.22
        # Other values unchanged
        assert new_table["strong_trend"][TradingSession.EU] == 0.28

    def test_apply_preserves_original(self, tuner, default_thresholds):
        from src.ai.confluence.threshold_tuner import TuningResult
        results = [
            TuningResult(
                regime="strong_trend",
                session=TradingSession.US,
                old_threshold=0.25,
                calc_threshold=0.20,
                new_threshold=0.22,
                sample_count=15,
                achieved_win_rate=0.60,
            ),
        ]
        tuner.apply_to_engine(default_thresholds, results)
        # Original unchanged
        assert default_thresholds["strong_trend"][TradingSession.US] == 0.25
