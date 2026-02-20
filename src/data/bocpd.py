"""Bayesian Online Changepoint Detection (BOCPD).

APEX-V Phase 2: 상수 위험률 + 가우시안 관측 모델로
run-length 분포를 온라인 업데이트하여 레짐 변화점 탐지.

참조: Adams & MacKay (2007), "Bayesian Online Changepoint Detection"
"""
from __future__ import annotations

import math
from collections import deque

from loguru import logger


class BOCPDDetector:
    """Bayesian Online Changepoint Detection.

    상수 위험률(constant hazard) + 가우시안 충분 통계량으로
    run-length 분포를 실시간 업데이트한다.

    Attributes:
        hazard_lambda: 평균 run-length (높을수록 변화점 덜 빈번)
        window_size: 롤링 윈도우 크기 (메모리 효율)
    """

    def __init__(
        self,
        hazard_lambda: float = 250.0,
        window_size: int = 100,
        *,
        mu_prior: float = 0.0,
        kappa_prior: float = 1.0,
        alpha_prior: float = 1.0,
        beta_prior: float = 1.0,
    ) -> None:
        """BOCPD 초기화.

        Args:
            hazard_lambda: 위험률 역수 (기본 250 — 평균 250 스텝마다 변화점)
            window_size: run-length 분포 최대 길이
            mu_prior: 가우시안 사전 평균
            kappa_prior: 관측 수 사전
            alpha_prior: 감마 분포 형태 모수
            beta_prior: 감마 분포 비율 모수
        """
        self._hazard_lambda = hazard_lambda
        self._window_size = window_size

        # 가우시안 충분 통계량 (Normal-Inverse-Gamma prior)
        self._mu0 = mu_prior
        self._kappa0 = kappa_prior
        self._alpha0 = alpha_prior
        self._beta0 = beta_prior

        # Run-length 분포 — run_lengths[i]는 P(r_t = i)
        self._run_lengths: list[float] = [1.0]  # 초기: r=0 확률 1.0

        # 각 run-length별 충분 통계량
        self._mus: list[float] = [mu_prior]
        self._kappas: list[float] = [kappa_prior]
        self._alphas: list[float] = [alpha_prior]
        self._betas: list[float] = [beta_prior]

        self._n_updates = 0
        self._observations: deque[float] = deque(maxlen=window_size)

        logger.debug(
            f"BOCPD 초기화: hazard_lambda={hazard_lambda}, "
            f"window={window_size}"
        )

    def update(self, observation: float) -> float:
        """새 관측값으로 run-length 분포 업데이트.

        Args:
            observation: 새 데이터 포인트 (예: ATR % 변화율)

        Returns:
            변화점 확률 (0~1)
        """
        self._observations.append(observation)
        self._n_updates += 1

        n = len(self._run_lengths)

        # Step 1: 예측 확률 계산 (Student-t)
        pred_probs = []
        for i in range(n):
            pp = self._student_t_pdf(
                observation,
                self._mus[i],
                self._kappas[i],
                self._alphas[i],
                self._betas[i],
            )
            pred_probs.append(pp)

        # Step 2: 위험률 (상수)
        h = 1.0 / self._hazard_lambda

        # Step 3: Growth probabilities
        # P(r_t = r+1, x_{1:t}) = P(r_{t-1}=r, x_{1:t-1}) * pred * (1-h)
        new_run_lengths = [0.0] * (n + 1)
        changepoint_mass = 0.0

        for i in range(n):
            grow = self._run_lengths[i] * pred_probs[i] * (1.0 - h)
            new_run_lengths[i + 1] = grow
            changepoint_mass += self._run_lengths[i] * pred_probs[i] * h

        # changepoint mass → r=0
        new_run_lengths[0] = changepoint_mass

        # Step 4: 정규화
        total = sum(new_run_lengths)
        if total > 0:
            new_run_lengths = [p / total for p in new_run_lengths]
        else:
            new_run_lengths = [1.0] + [0.0] * n

        # Step 5: 충분 통계량 업데이트
        new_mus = [self._mu0]
        new_kappas = [self._kappa0]
        new_alphas = [self._alpha0]
        new_betas = [self._beta0]

        for i in range(n):
            kappa_new = self._kappas[i] + 1.0
            mu_new = (
                self._kappas[i] * self._mus[i] + observation
            ) / kappa_new
            alpha_new = self._alphas[i] + 0.5
            beta_new = (
                self._betas[i]
                + 0.5
                * self._kappas[i]
                * (observation - self._mus[i]) ** 2
                / kappa_new
            )
            new_mus.append(mu_new)
            new_kappas.append(kappa_new)
            new_alphas.append(alpha_new)
            new_betas.append(beta_new)

        # Step 6: 윈도우 트리밍 (메모리 효율)
        if len(new_run_lengths) > self._window_size:
            new_run_lengths = new_run_lengths[: self._window_size]
            new_mus = new_mus[: self._window_size]
            new_kappas = new_kappas[: self._window_size]
            new_alphas = new_alphas[: self._window_size]
            new_betas = new_betas[: self._window_size]
            # 재정규화
            total = sum(new_run_lengths)
            if total > 0:
                new_run_lengths = [p / total for p in new_run_lengths]

        self._run_lengths = new_run_lengths
        self._mus = new_mus
        self._kappas = new_kappas
        self._alphas = new_alphas
        self._betas = new_betas

        return new_run_lengths[0]

    def get_confidence(self) -> float:
        """현재 레짐 안정도 (0~1).

        MAP run-length가 길수록 → 높은 confidence.
        confidence = 1.0 - changepoint_probability

        Returns:
            레짐 안정도 (0~1)
        """
        if self._n_updates < 2:  # noqa: PLR2004
            return 1.0
        return 1.0 - self._run_lengths[0]

    def get_changepoint_probability(self) -> float:
        """현재 변화점 확률.

        Returns:
            변화점 확률 (0~1)
        """
        if self._n_updates < 2:  # noqa: PLR2004
            return 0.0
        return self._run_lengths[0]

    def get_map_run_length(self) -> int:
        """MAP (Maximum A Posteriori) run-length.

        Returns:
            가장 확률이 높은 run-length
        """
        if not self._run_lengths:
            return 0
        return max(range(len(self._run_lengths)),
                   key=lambda i: self._run_lengths[i])

    @staticmethod
    def _student_t_pdf(
        x: float,
        mu: float,
        kappa: float,
        alpha: float,
        beta: float,
    ) -> float:
        """Student-t 예측 분포 PDF.

        Normal-Inverse-Gamma 사전 분포에서 유도.
        df = 2*alpha, scale = beta*(kappa+1)/(alpha*kappa)
        """
        df = 2.0 * alpha
        scale = beta * (kappa + 1.0) / (alpha * kappa)

        if scale <= 0 or df <= 0:
            return 1e-10

        # Student-t PDF via log-space computation
        z = (x - mu) ** 2 / (df * scale)
        log_pdf = (
            math.lgamma((df + 1.0) / 2.0)
            - math.lgamma(df / 2.0)
            - 0.5 * math.log(df * math.pi * scale)
            - ((df + 1.0) / 2.0) * math.log(1.0 + z)
        )
        return max(1e-300, math.exp(log_pdf))

    @property
    def n_updates(self) -> int:
        """업데이트 횟수."""
        return self._n_updates
