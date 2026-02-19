"""KSG MI Estimator 테스트."""

import numpy as np

from src.ai.confluence.ksg_estimator import (
    KSGMIMatrix,
    digamma,
    ksg_mutual_information,
)
from src.ai.confluence.signal_dedup import SignalDeduplicator
from src.ai.ensemble import IndividualSignal, SignalSource


class TestDigamma:
    def test_known_value_1(self):
        """digamma(1) approx -euler_gamma approx -0.5772."""
        result = digamma(1.0)
        assert abs(result - (-0.5772)) < 0.01

    def test_known_value_2(self):
        """digamma(2) approx 1 - euler_gamma approx 0.4228."""
        result = digamma(2.0)
        assert abs(result - 0.4228) < 0.01

    def test_known_value_10(self):
        """digamma(10) ≈ 2.2517."""
        result = digamma(10.0)
        assert abs(result - 2.2517) < 0.01

    def test_zero_returns_large_negative(self):
        result = digamma(0.0)
        assert result < -1e9

    def test_monotonically_increasing(self):
        values = [digamma(x) for x in [1.0, 2.0, 5.0, 10.0]]
        for i in range(len(values) - 1):
            assert values[i] < values[i + 1]


class TestKSGMutualInformation:
    def test_independent_low_mi(self):
        """독립 변수 → MI ≈ 0."""
        rng = np.random.RandomState(42)
        x = rng.randn(200)
        y = rng.randn(200)
        mi = ksg_mutual_information(x, y, k=3)
        assert mi < 0.2  # 추정 오차 허용

    def test_identical_high_mi(self):
        """동일 변수 → 높은 MI."""
        rng = np.random.RandomState(42)
        x = rng.randn(200)
        mi = ksg_mutual_information(x, x, k=3)
        assert mi > 0.5

    def test_correlated_moderate_mi(self):
        """상관 변수 → 중간 MI."""
        rng = np.random.RandomState(42)
        x = rng.randn(200)
        y = x * 0.8 + rng.randn(200) * 0.2
        mi = ksg_mutual_information(x, y, k=3)
        assert mi > 0.1

    def test_too_few_samples(self):
        x = np.array([1.0, 2.0])
        y = np.array([3.0, 4.0])
        mi = ksg_mutual_information(x, y, k=3)
        assert mi == 0.0

    def test_zero_variance(self):
        x = np.ones(100)
        y = np.random.randn(100)
        mi = ksg_mutual_information(x, y, k=3)
        assert mi == 0.0

    def test_non_negative(self):
        """MI는 항상 >= 0 (clamped)."""
        rng = np.random.RandomState(123)
        x = rng.randn(50)
        y = rng.randn(50)
        mi = ksg_mutual_information(x, y, k=3)
        assert mi >= 0.0


class TestKSGMIMatrix:
    def test_compute_from_history(self):
        rng = np.random.RandomState(42)
        history = {
            "tsmom": list(rng.randn(100)),
            "funding_basis": list(rng.randn(100)),
        }
        matrix = KSGMIMatrix()
        result = matrix.compute_from_history(history)
        assert len(result) == 1
        assert matrix.is_computed

    def test_insufficient_samples(self):
        history = {
            "a": [1.0, 2.0, 3.0],  # < MIN_SAMPLES
            "b": [4.0, 5.0, 6.0],
        }
        matrix = KSGMIMatrix()
        result = matrix.compute_from_history(history)
        assert len(result) == 0

    def test_penalty_below_threshold(self):
        matrix = KSGMIMatrix()
        matrix._mi_matrix = {("a", "b"): 0.2}  # below 0.3
        assert matrix.get_penalty("a", "b") == 0.0

    def test_penalty_above_threshold(self):
        matrix = KSGMIMatrix()
        matrix._mi_matrix = {("a", "b"): 0.5}
        penalty = matrix.get_penalty("a", "b")
        assert penalty == 0.5

    def test_penalty_reverse_order(self):
        """pair 순서 무관하게 조회."""
        matrix = KSGMIMatrix()
        matrix._mi_matrix = {("a", "b"): 0.5}
        assert matrix.get_penalty("b", "a") == 0.5

    def test_is_computed_false_initially(self):
        matrix = KSGMIMatrix()
        assert not matrix.is_computed


class TestDedupKSGIntegration:
    def test_dedup_with_ksg(self):
        """KSG matrix가 있으면 동적 MI 사용."""
        matrix = KSGMIMatrix()
        matrix._mi_matrix = {
            ("funding_basis", "tsmom"): 0.5,
        }
        dedup = SignalDeduplicator(ksg_matrix=matrix)

        signals = [
            IndividualSignal(
                source=SignalSource.TSMOM, signal="LONG",
                confidence=0.8, weight=0.15,
            ),
            IndividualSignal(
                source=SignalSource.FUNDING_BASIS, signal="LONG",
                confidence=0.7, weight=0.15,
            ),
        ]
        adjusted = dedup.adjust_weights(signals)
        # MI=0.5 > 0.3 → penalty=0.5 → weight = 0.15 * 0.5 = 0.075
        assert adjusted[0].weight < 0.15
        assert adjusted[1].weight < 0.15

    def test_dedup_without_ksg_uses_static(self):
        """KSG 없으면 정적 MI."""
        dedup = SignalDeduplicator()

        signals = [
            IndividualSignal(
                source=SignalSource.TSMOM, signal="LONG",
                confidence=0.8, weight=0.15,
            ),
            IndividualSignal(
                source=SignalSource.SMART_MONEY, signal="LONG",
                confidence=0.7, weight=0.15,
            ),
        ]
        adjusted = dedup.adjust_weights(signals)
        # SAME_LAYER_MI=0.3 → weight = 0.15 * 0.7 = 0.105
        assert abs(adjusted[0].weight - 0.105) < 0.001

    def test_dedup_single_signal_passthrough(self):
        dedup = SignalDeduplicator()
        signals = [
            IndividualSignal(
                source=SignalSource.TSMOM, signal="LONG",
                confidence=0.8, weight=0.15,
            ),
        ]
        adjusted = dedup.adjust_weights(signals)
        assert adjusted[0].weight == 0.15
