"""KSG Mutual Information Estimator.

KSG Algorithm 1 (Kraskov et al. 2004)로 시그널 간 MI 추정.
scipy 의존성 없이 digamma 근사 사용.
"""
from __future__ import annotations

import math

import numpy as np
from loguru import logger


def digamma(x: float) -> float:
    """Digamma 함수 근사 (Bernardo 1976).

    scipy.special.digamma 대체.
    """
    if x <= 0:
        return -50.0  # 하한 클리핑 (overflow 방지)
    result = 0.0
    # x가 충분히 클 때까지 recurrence: psi(x) = psi(x+1) - 1/x
    _asymptotic_threshold = 6.0
    while x < _asymptotic_threshold:
        result -= 1.0 / x
        x += 1.0
    # Stirling 근사: psi(x) ≈ ln(x) - 1/(2x) - 1/(12x^2) + 1/(120x^4) - ...
    result += math.log(x) - 0.5 / x
    x2 = x * x
    result -= 1.0 / (12.0 * x2)
    result += 1.0 / (120.0 * x2 * x2)
    result -= 1.0 / (252.0 * x2 * x2 * x2)
    return max(-50.0, result)  # P2-6: 극소값 underflow 방지


def ksg_mutual_information(
    x: np.ndarray,
    y: np.ndarray,
    k: int = 3,
) -> float:
    """KSG Algorithm 1 MI 추정.

    Chebyshev norm 기반 k-NN.
    MI = digamma(k) - <digamma(n_x+1) + digamma(n_y+1)> + digamma(N)

    Args:
        x: 1D array (N,)
        y: 1D array (N,)
        k: k-nearest neighbors (기본 3)

    Returns:
        MI 추정치 (bits, 음수 가능 — 추정 오차)
    """
    n = len(x)
    if n < k + 1:
        return 0.0

    # 정규화 (unit variance)
    x_std = np.std(x)
    y_std = np.std(y)
    if x_std == 0 or y_std == 0:
        return 0.0
    x_norm = (x - np.mean(x)) / x_std
    y_norm = (y - np.mean(y)) / y_std

    # 각 포인트별 k-th nearest neighbor의 Chebyshev distance
    psi_nx_sum = 0.0
    psi_ny_sum = 0.0

    for i in range(n):
        # Chebyshev distance to all other points
        dx = np.abs(x_norm - x_norm[i])
        dy = np.abs(y_norm - y_norm[i])
        d_cheb = np.maximum(dx, dy)

        # 자기 자신 제외 (distance=0)
        d_cheb[i] = np.inf

        # k-th smallest distance
        # partition은 O(n), sort는 O(n log n)
        if n - 1 < k:
            continue
        kth_idx = np.argpartition(d_cheb, k)[:k]
        eps_i = np.max(d_cheb[kth_idx])

        # Count points within eps_i in marginals
        n_x = int(np.sum(dx < eps_i)) - 1  # exclude self
        n_y = int(np.sum(dy < eps_i)) - 1

        psi_nx_sum += digamma(max(1, n_x + 1))
        psi_ny_sum += digamma(max(1, n_y + 1))

    mi = digamma(k) - (psi_nx_sum + psi_ny_sum) / n + digamma(n)
    return max(0.0, mi)  # MI는 이론적으로 >= 0


class KSGMIMatrix:
    """KSG MI 행렬 관리자.

    소스 쌍 간의 MI를 계산하고, 중복 페널티 제공.
    """

    MIN_SAMPLES = 50
    MI_THRESHOLD = 0.3
    DEFAULT_K = 3

    def __init__(self) -> None:
        self._mi_matrix: dict[tuple[str, str], float] = {}
        self._log = logger.bind(module="ksg_mi")

    @property
    def is_computed(self) -> bool:
        """MI 행렬이 계산되었는지."""
        return len(self._mi_matrix) > 0

    def compute_from_history(
        self,
        signal_history: dict[str, list[float]],
    ) -> dict[tuple[str, str], float]:
        """시그널 히스토리에서 MI 행렬 계산.

        Args:
            signal_history: {source_name: [score_1, score_2, ...]}

        Returns:
            {(source_a, source_b): mi_value}
        """
        sources = list(signal_history.keys())
        result: dict[tuple[str, str], float] = {}

        for i in range(len(sources)):
            for j in range(i + 1, len(sources)):
                a, b = sources[i], sources[j]
                values_a = signal_history[a]
                values_b = signal_history[b]

                # 길이 맞추기
                min_len = min(len(values_a), len(values_b))
                if min_len < self.MIN_SAMPLES:
                    continue

                x = np.array(values_a[:min_len], dtype=np.float64)
                y = np.array(values_b[:min_len], dtype=np.float64)

                mi = ksg_mutual_information(x, y, k=self.DEFAULT_K)
                pair = (a, b) if a <= b else (b, a)
                result[pair] = mi

        self._mi_matrix = result
        self._log.info(
            f"KSG MI 행렬 계산 완료: {len(result)} pairs"
        )
        return result

    def get_penalty(self, source_a: str, source_b: str) -> float:
        """MI 기반 페널티 반환.

        MI > MI_THRESHOLD → penalty = MI / 1.0 (최대 1.0)
        MI <= MI_THRESHOLD → penalty = 0.0

        Returns:
            0.0 ~ 1.0 페널티
        """
        pair = (source_a, source_b) if source_a <= source_b else (source_b, source_a)
        mi = self._mi_matrix.get(pair, 0.0)
        if mi <= self.MI_THRESHOLD:
            return 0.0
        return min(1.0, mi)
