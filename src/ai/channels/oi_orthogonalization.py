"""OI Orthogonalization.

Funding Rate에서 OI 기여분을 제거하여 순수 sentiment 예측력 향상.
Augustin(2024) 기반: FR_orthogonal = FR - beta * OI_change.
"""
from __future__ import annotations

from collections import deque

from loguru import logger


class OIOrthogonalizer:
    """OI Orthogonalizer.

    OLS 회귀로 FR-OI 관계의 beta를 추정하고,
    FR에서 OI 기여분을 제거하여 순수 FR 시그널 추출.
    """

    MIN_SAMPLES = 14
    ROLLING_WINDOW = 30
    BETA_SMOOTHING = 0.7  # new_beta = 0.7*old + 0.3*calc

    def __init__(self) -> None:
        self._beta: float = 0.0
        self._fr_history: deque[float] = deque(maxlen=self.ROLLING_WINDOW)
        self._oi_signal_history: deque[float] = deque(maxlen=self.ROLLING_WINDOW)
        self._log = logger.bind(module="oi_orthogonal")

    @property
    def beta(self) -> float:
        """현재 beta 값."""
        return self._beta

    def update(self, raw_fr: float, oi_change_pct: float) -> None:
        """히스토리에 새 데이터 추가.

        Args:
            raw_fr: 원본 펀딩레이트
            oi_change_pct: OI 변화율 (예: 0.02 = 2% 증가)
        """
        self._fr_history.append(raw_fr)
        self._oi_signal_history.append(oi_change_pct)

    def recompute_beta(self) -> float:
        """OLS beta 재계산: Cov(FR, OI) / Var(OI) + smoothing.

        Returns:
            새로운 beta 값
        """
        n = min(len(self._fr_history), len(self._oi_signal_history))
        if n < self.MIN_SAMPLES:
            return self._beta

        fr_list = list(self._fr_history)[-n:]
        oi_list = list(self._oi_signal_history)[-n:]

        # Mean
        fr_mean = sum(fr_list) / n
        oi_mean = sum(oi_list) / n

        # Covariance and variance for OLS
        cov = sum(
            (fr_list[i] - fr_mean) * (oi_list[i] - oi_mean) for i in range(n)
        ) / n
        var_oi = sum((oi_list[i] - oi_mean) ** 2 for i in range(n)) / n

        if var_oi == 0:
            return self._beta

        calc_beta = cov / var_oi

        # Smoothing
        if self._beta == 0:
            self._beta = calc_beta
        else:
            self._beta = (
                self.BETA_SMOOTHING * self._beta
                + (1 - self.BETA_SMOOTHING) * calc_beta
            )

        self._log.debug(
            f"OI beta 재계산: {self._beta:.6f} "
            f"(calc={calc_beta:.6f}, n={n})"
        )
        return self._beta

    def orthogonalize(self, raw_fr: float, oi_change_pct: float) -> float:
        """FR에서 OI 기여분 제거.

        Args:
            raw_fr: 원본 펀딩레이트
            oi_change_pct: OI 변화율

        Returns:
            직교화된 FR
        """
        return raw_fr - self._beta * oi_change_pct
