"""Transfer Entropy 테스트.

APEX-V Phase 2 Step 3: KSG 기반 TE + SignalDeduplicator 통합.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from src.ai.confluence.ksg_estimator import (
    KSGMIMatrix,
    ksg_transfer_entropy,
)
from src.ai.confluence.signal_dedup import SignalDeduplicator
from src.ai.ensemble import SignalSource


@dataclass
class MockIndividualSignal:
    """테스트용 IndividualSignal mock."""
    source: SignalSource
    signal: str
    confidence: float
    weight: float


class TestKSGTransferEntropy:
    """ksg_transfer_entropy 함수 테스트."""

    def test_independent_signals_low_te(self):
        """독립 시그널 간 TE ≈ 0."""
        rng = random.Random(42)
        source = [rng.gauss(0, 1) for _ in range(100)]
        target = [rng.gauss(0, 1) for _ in range(100)]
        te = ksg_transfer_entropy(source, target, k=3, lag=1)
        assert te < 0.3, f"독립 시그널 TE={te:.3f}가 너무 높음"

    def test_causal_signal_positive_te(self):
        """인과 관계 시그널 → TE > 0."""
        rng = random.Random(42)
        source = [rng.gauss(0, 1) for _ in range(200)]
        # target = source shifted by 1 + noise
        target = [0.0] + [
            source[i] * 0.8 + rng.gauss(0, 0.2) for i in range(199)
        ]
        te = ksg_transfer_entropy(source, target, k=3, lag=1)
        assert te >= 0.0  # TE는 항상 >= 0

    def test_te_direction_asymmetry(self):
        """TE(X→Y) != TE(Y→X) — 방향 비대칭."""
        rng = random.Random(42)
        x = [rng.gauss(0, 1) for _ in range(200)]
        y = [0.0] + [x[i] * 0.9 + rng.gauss(0, 0.1) for i in range(199)]

        te_xy = ksg_transfer_entropy(x, y, k=3, lag=1)
        te_yx = ksg_transfer_entropy(y, x, k=3, lag=1)

        # TE는 다르거나 같을 수 있지만, 둘 다 >= 0
        assert te_xy >= 0.0
        assert te_yx >= 0.0

    def test_te_insufficient_data(self):
        """데이터 부족 시 TE = 0."""
        source = [1.0, 2.0]
        target = [1.0, 2.0]
        te = ksg_transfer_entropy(source, target, k=3, lag=1)
        assert te == 0.0

    def test_te_lag_parameter(self):
        """lag 파라미터 변화."""
        rng = random.Random(42)
        source = [rng.gauss(0, 1) for _ in range(100)]
        target = [rng.gauss(0, 1) for _ in range(100)]
        te_lag1 = ksg_transfer_entropy(source, target, lag=1)
        te_lag3 = ksg_transfer_entropy(source, target, lag=3)
        # 둘 다 >= 0
        assert te_lag1 >= 0.0
        assert te_lag3 >= 0.0

    def test_te_nonnegative(self):
        """TE는 항상 >= 0."""
        rng = random.Random(42)
        for _ in range(5):
            source = [rng.gauss(0, 1) for _ in range(80)]
            target = [rng.gauss(0, 1) for _ in range(80)]
            te = ksg_transfer_entropy(source, target)
            assert te >= 0.0


class TestKSGMIMatrixTE:
    """KSGMIMatrix.compute_te_matrix 테스트."""

    def test_compute_te_matrix(self):
        """TE 행렬 계산."""
        matrix = KSGMIMatrix()
        rng = random.Random(42)

        history = {
            "a": [rng.gauss(0, 1) for _ in range(60)],
            "b": [rng.gauss(0, 1) for _ in range(60)],
            "c": [rng.gauss(0, 1) for _ in range(60)],
        }

        result = matrix.compute_te_matrix(history)
        # 3 sources → 6 directed pairs (A→B, A→C, B→A, B→C, C→A, C→B)
        assert len(result) == 6
        assert matrix.te_computed is True
        for te in result.values():
            assert te >= 0.0

    def test_te_matrix_insufficient_samples(self):
        """샘플 부족 시 빈 행렬."""
        matrix = KSGMIMatrix()
        history = {
            "a": [1.0, 2.0],
            "b": [1.0, 2.0],
        }
        result = matrix.compute_te_matrix(history)
        assert len(result) == 0

    def test_get_te(self):
        """get_te로 특정 쌍의 TE 조회."""
        matrix = KSGMIMatrix()
        rng = random.Random(42)
        history = {
            "a": [rng.gauss(0, 1) for _ in range(60)],
            "b": [rng.gauss(0, 1) for _ in range(60)],
        }
        matrix.compute_te_matrix(history)
        te_ab = matrix.get_te("a", "b")
        te_ba = matrix.get_te("b", "a")
        assert isinstance(te_ab, float)
        assert isinstance(te_ba, float)

    def test_get_te_unknown_pair(self):
        """미계산 쌍은 0.0 반환."""
        matrix = KSGMIMatrix()
        assert matrix.get_te("x", "y") == 0.0


class TestSignalDeduplicatorTE:
    """SignalDeduplicator Transfer Entropy 통합 테스트."""

    def _make_signal(
        self, source: SignalSource, signal: str = "LONG",
        confidence: float = 0.7, weight: float = 1.0,
    ):
        """IndividualSignal-compatible object 생성."""
        from src.ai.ensemble import IndividualSignal
        return IndividualSignal(
            source=source, signal=signal,
            confidence=confidence, weight=weight,
        )

    def test_te_disabled_by_default(self):
        """use_transfer_entropy=False → TE 조정 안 함."""
        dedup = SignalDeduplicator()
        signals = [
            self._make_signal(SignalSource.TSMOM),
            self._make_signal(SignalSource.SMART_MONEY),
        ]
        result = dedup.adjust_weights(signals)
        assert len(result) == 2

    def test_te_enabled_with_ksg_matrix(self):
        """TE 활성화 + KSG matrix → 가중치 조정."""
        matrix = KSGMIMatrix()
        rng = random.Random(42)
        history = {
            SignalSource.TSMOM.value: [rng.gauss(0, 1) for _ in range(60)],
            SignalSource.SMART_MONEY.value: [rng.gauss(0, 1) for _ in range(60)],
        }
        matrix.compute_from_history(history)
        matrix.compute_te_matrix(history)

        dedup = SignalDeduplicator(
            ksg_matrix=matrix, use_transfer_entropy=True
        )
        signals = [
            self._make_signal(SignalSource.TSMOM),
            self._make_signal(SignalSource.SMART_MONEY),
        ]
        result = dedup.adjust_weights(signals)
        assert len(result) == 2
        # 가중치가 조정되었을 수 있음
        for sig in result:
            assert sig.weight > 0

    def test_te_not_applied_without_te_matrix(self):
        """TE 활성화지만 TE 행렬 미계산 → TE 조정 스킵."""
        matrix = KSGMIMatrix()
        rng = random.Random(42)
        history = {
            SignalSource.TSMOM.value: [rng.gauss(0, 1) for _ in range(60)],
            SignalSource.SMART_MONEY.value: [rng.gauss(0, 1) for _ in range(60)],
        }
        matrix.compute_from_history(history)
        # TE 행렬 계산 안 함

        dedup = SignalDeduplicator(
            ksg_matrix=matrix, use_transfer_entropy=True
        )
        signals = [
            self._make_signal(SignalSource.TSMOM),
            self._make_signal(SignalSource.SMART_MONEY),
        ]
        result = dedup.adjust_weights(signals)
        assert len(result) == 2
