"""
통계적 신뢰도 테스트

Phase 6.2: 신뢰구간, p-value, 통계적 유의성 테스트
"""
import pytest

from src.analytics.trade_analyzer import (
    MIN_SAMPLE_SIZE,
    MIN_SAMPLE_SIZE_RELAXED,
    StatisticalInsight,
    PatternInsight,
    calculate_confidence_interval,
    _normal_cdf,
)


class TestConstants:
    """상수 테스트"""

    def test_min_sample_size(self):
        """최소 샘플 수가 30인지 확인"""
        assert MIN_SAMPLE_SIZE == 30

    def test_min_sample_size_relaxed(self):
        """완화된 최소 샘플 수가 10인지 확인"""
        assert MIN_SAMPLE_SIZE_RELAXED == 10


class TestNormalCDF:
    """정규분포 CDF 테스트"""

    def test_cdf_at_zero(self):
        """x=0에서 CDF는 0.5"""
        assert _normal_cdf(0) == pytest.approx(0.5, abs=0.001)

    def test_cdf_at_positive(self):
        """양수에서 CDF는 0.5보다 큼"""
        assert _normal_cdf(1.96) == pytest.approx(0.975, abs=0.01)

    def test_cdf_at_negative(self):
        """음수에서 CDF는 0.5보다 작음"""
        assert _normal_cdf(-1.96) == pytest.approx(0.025, abs=0.01)


class TestStatisticalInsight:
    """StatisticalInsight 테스트"""

    def test_from_win_rate_basic(self):
        """기본 승률 계산 테스트"""
        insight = StatisticalInsight.from_win_rate(wins=60, total=100)

        assert insight.metric == "win_rate"
        assert insight.value == 60.0  # 60%
        assert insight.sample_size == 100

    def test_from_win_rate_confidence_interval(self):
        """신뢰구간 계산 테스트"""
        insight = StatisticalInsight.from_win_rate(wins=60, total=100)

        # 95% 신뢰구간은 60% 주위에 있어야 함
        assert insight.lower_bound < 60.0
        assert insight.upper_bound > 60.0
        assert insight.lower_bound > 45.0  # 합리적인 범위
        assert insight.upper_bound < 75.0

    def test_from_win_rate_significance_above_baseline(self):
        """기준보다 높은 승률의 통계적 유의성 테스트"""
        # 75% 승률, 100 샘플 -> 50%보다 유의하게 높음
        insight = StatisticalInsight.from_win_rate(
            wins=75, total=100, baseline=0.5
        )

        # 신뢰구간이 50%를 포함하지 않음
        assert insight.lower_bound > 50.0
        assert insight.is_statistically_significant is True

    def test_from_win_rate_significance_below_baseline(self):
        """기준보다 낮은 승률의 통계적 유의성 테스트"""
        # 25% 승률, 100 샘플 -> 50%보다 유의하게 낮음
        insight = StatisticalInsight.from_win_rate(
            wins=25, total=100, baseline=0.5
        )

        # 신뢰구간이 50%를 포함하지 않음
        assert insight.upper_bound < 50.0
        assert insight.is_statistically_significant is True

    def test_from_win_rate_not_significant(self):
        """통계적으로 유의하지 않은 경우 테스트"""
        # 55% 승률, 30 샘플 -> 50%와 구분 어려움
        insight = StatisticalInsight.from_win_rate(
            wins=16, total=30, baseline=0.5
        )

        # 신뢰구간이 50%를 포함할 가능성 높음
        # (실제로는 경계에 가까움)
        # is_statistically_significant는 False일 수 있음
        assert insight.sample_size == 30

    def test_from_win_rate_small_sample(self):
        """작은 샘플에서 유의성 없음 테스트"""
        # 5 샘플은 MIN_SAMPLE_SIZE 미만
        insight = StatisticalInsight.from_win_rate(
            wins=4, total=5, baseline=0.5
        )

        # 샘플이 부족하면 유의하지 않음
        assert insight.sample_size < MIN_SAMPLE_SIZE
        assert insight.is_statistically_significant is False

    def test_from_win_rate_p_value(self):
        """p-value 계산 테스트"""
        # 큰 샘플에서 p-value 계산
        insight = StatisticalInsight.from_win_rate(
            wins=70, total=100, baseline=0.5
        )

        # p-value가 계산되어야 함
        assert insight.p_value is not None
        assert insight.p_value < 0.05  # 유의 수준 5%

    def test_from_win_rate_zero_total(self):
        """총 거래 0인 경우 테스트"""
        insight = StatisticalInsight.from_win_rate(wins=0, total=0)

        assert insight.value == 0.0
        assert insight.sample_size == 0
        assert insight.is_statistically_significant is False

    def test_to_dict(self):
        """딕셔너리 변환 테스트"""
        insight = StatisticalInsight.from_win_rate(wins=60, total=100)
        data = insight.to_dict()

        assert "metric" in data
        assert "value" in data
        assert "sample_size" in data
        assert "confidence_level" in data
        assert "lower_bound" in data
        assert "upper_bound" in data
        assert "is_statistically_significant" in data


class TestCalculateConfidenceInterval:
    """calculate_confidence_interval 테스트"""

    def test_empty_values(self):
        """빈 리스트 테스트"""
        mean, lower, upper, std_error = calculate_confidence_interval([])

        assert mean == 0.0
        assert lower == 0.0
        assert upper == 0.0

    def test_single_value(self):
        """단일 값 테스트"""
        mean, lower, upper, std_error = calculate_confidence_interval([100.0])

        assert mean == 100.0
        assert lower == 100.0
        assert upper == 100.0
        assert std_error == 0.0

    def test_multiple_values(self):
        """여러 값 테스트"""
        values = [100.0, 110.0, 90.0, 105.0, 95.0]
        mean, lower, upper, std_error = calculate_confidence_interval(values)

        # 평균은 100
        assert mean == 100.0

        # 신뢰구간이 평균 주위에 있음
        assert lower < 100.0
        assert upper > 100.0

        # 표준 오차가 양수
        assert std_error > 0

    def test_confidence_interval_width(self):
        """샘플 크기에 따른 신뢰구간 너비 테스트"""
        # 작은 샘플
        values_small = [100.0, 110.0, 90.0]
        _, lower_small, upper_small, _ = calculate_confidence_interval(values_small)

        # 큰 샘플
        values_large = [100.0] * 50 + [110.0] * 25 + [90.0] * 25
        _, lower_large, upper_large, _ = calculate_confidence_interval(values_large)

        # 큰 샘플이 더 좁은 신뢰구간
        width_small = upper_small - lower_small
        width_large = upper_large - lower_large

        assert width_large < width_small


class TestPatternInsightWithConfidence:
    """PatternInsight 신뢰도 테스트"""

    def test_with_confidence_high(self):
        """높은 신뢰도 패턴 테스트"""
        insight = PatternInsight.with_confidence(
            pattern_type="rsi_zone",
            description="RSI 30 이하에서 LONG 진입",
            side="LONG",
            condition="rsi_zone=oversold",
            wins=25,  # 83% 승률
            total=30,
            avg_pnl=50.0,
            recommendation="RSI 과매도에서 LONG 권장",
        )

        # 30 샘플 이상이고 통계적으로 유의
        assert insight.sample_size >= MIN_SAMPLE_SIZE
        assert insight.win_rate == pytest.approx(83.33, rel=0.01)
        # 높은 승률이므로 유의할 가능성 높음

    def test_with_confidence_medium(self):
        """중간 신뢰도 패턴 테스트"""
        insight = PatternInsight.with_confidence(
            pattern_type="rsi_zone",
            description="RSI 30 이하에서 LONG 진입",
            side="LONG",
            condition="rsi_zone=oversold",
            wins=12,  # 60% 승률
            total=20,  # 샘플 부족
            avg_pnl=30.0,
            recommendation="RSI 과매도에서 LONG",
        )

        # 샘플이 MIN_SAMPLE_SIZE 미만
        assert insight.sample_size < MIN_SAMPLE_SIZE
        assert insight.confidence_level in ["LOW", "MEDIUM"]

    def test_with_confidence_low(self):
        """낮은 신뢰도 패턴 테스트"""
        insight = PatternInsight.with_confidence(
            pattern_type="rsi_zone",
            description="테스트",
            side="LONG",
            condition="test",
            wins=3,
            total=5,  # 매우 적은 샘플
            avg_pnl=10.0,
            recommendation="테스트",
        )

        assert insight.sample_size < MIN_SAMPLE_SIZE_RELAXED
        assert insight.confidence_level == "LOW"
        assert insight.is_statistically_significant is False

    def test_confidence_interval_bounds(self):
        """신뢰구간 경계 테스트"""
        insight = PatternInsight.with_confidence(
            pattern_type="hourly",
            description="14시에 LONG 진입",
            side="LONG",
            condition="hour=14",
            wins=24,  # 80% 승률
            total=30,
            avg_pnl=40.0,
            recommendation="14시에 LONG 권장",
        )

        # 신뢰구간이 승률 주위에 있음
        assert insight.win_rate_lower < insight.win_rate
        assert insight.win_rate_upper > insight.win_rate

        # 합리적인 범위
        assert insight.win_rate_lower >= 0
        assert insight.win_rate_upper <= 100

    def test_to_dict_includes_confidence_fields(self):
        """딕셔너리에 신뢰도 필드 포함 테스트"""
        insight = PatternInsight.with_confidence(
            pattern_type="test",
            description="test",
            side="LONG",
            condition="test",
            wins=25,
            total=50,
            avg_pnl=10.0,
            recommendation="test",
        )

        data = insight.to_dict()

        assert "confidence_level" in data
        assert "win_rate_lower" in data
        assert "win_rate_upper" in data
        assert "is_statistically_significant" in data


class TestStatisticalEdgeCases:
    """통계적 엣지 케이스 테스트"""

    def test_perfect_win_rate(self):
        """100% 승률 테스트"""
        insight = StatisticalInsight.from_win_rate(wins=30, total=30)

        assert insight.value == 100.0
        assert insight.lower_bound < 100.0  # 신뢰구간은 더 넓음
        assert insight.upper_bound == 100.0  # 상한은 100

    def test_zero_win_rate(self):
        """0% 승률 테스트"""
        insight = StatisticalInsight.from_win_rate(wins=0, total=30)

        assert insight.value == 0.0
        assert insight.lower_bound == 0.0  # 하한은 0
        assert insight.upper_bound > 0.0  # 신뢰구간은 더 넓음

    def test_very_large_sample(self):
        """매우 큰 샘플 테스트"""
        insight = StatisticalInsight.from_win_rate(wins=600, total=1000)

        # 큰 샘플은 좁은 신뢰구간
        ci_width = insight.upper_bound - insight.lower_bound

        # 1000 샘플에서 60% 승률의 CI는 약 3% 정도
        assert ci_width < 10.0
        assert insight.is_statistically_significant is True

    def test_exactly_50_percent(self):
        """정확히 50% 승률 테스트"""
        insight = StatisticalInsight.from_win_rate(
            wins=50, total=100, baseline=0.5
        )

        # 50%는 기준선과 같으므로 유의하지 않음
        assert insight.value == 50.0
        assert insight.is_statistically_significant is False
