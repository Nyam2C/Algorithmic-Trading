"""Monte Carlo 시뮬레이션 — APEX-V Phase E.

과거 거래 PnL을 무작위로 재배열하여
VaR, 최대 낙폭, 파산 리스크를 추정한다.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from src.backtest.engine import Trade

# 시뮬레이션 상수
DEFAULT_N_SIMULATIONS = 1000
DEFAULT_CONFIDENCE_LEVEL = 0.95
DEFAULT_RUIN_THRESHOLD = 0.50
DEFAULT_INITIAL_CAPITAL = 10000.0
MAX_ACCEPTABLE_RUIN = 0.01


@dataclass
class MonteCarloConfig:
    """Monte Carlo 설정."""

    n_simulations: int = DEFAULT_N_SIMULATIONS
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL
    ruin_threshold: float = DEFAULT_RUIN_THRESHOLD
    initial_capital: float = DEFAULT_INITIAL_CAPITAL
    seed: int | None = None


@dataclass
class MonteCarloResult:
    """Monte Carlo 결과."""

    var_95: float
    max_drawdown_95: float
    max_drawdown_median: float
    risk_of_ruin: float
    is_valid: bool
    n_simulations: int
    final_capital_median: float


class MonteCarloSimulator:
    """Monte Carlo 시뮬레이션.

    거래 PnL 순서를 N회 셔플하여 통계적 위험 지표를 산출한다.
    """

    def __init__(self, config: MonteCarloConfig | None = None) -> None:
        self.config = config or MonteCarloConfig()

    def run(self, trades: list[Trade]) -> MonteCarloResult:
        """시뮬레이션 실행.

        Args:
            trades: 과거 거래 목록 (pnl 필드 사용).

        Returns:
            MonteCarloResult
        """
        pnls = [t.pnl for t in trades if t.pnl is not None]

        if not pnls:
            return MonteCarloResult(
                var_95=0.0,
                max_drawdown_95=0.0,
                max_drawdown_median=0.0,
                risk_of_ruin=0.0,
                is_valid=True,
                n_simulations=self.config.n_simulations,
                final_capital_median=self.config.initial_capital,
            )

        rng = random.Random(self.config.seed)
        initial = self.config.initial_capital
        ruin_line = initial * (1.0 - self.config.ruin_threshold)

        max_drawdowns: list[float] = []
        final_capitals: list[float] = []
        ruin_count = 0

        for _ in range(self.config.n_simulations):
            shuffled = pnls[:]
            rng.shuffle(shuffled)
            mdd, final_cap = self._simulate_one(
                shuffled, initial, ruin_line,
            )
            max_drawdowns.append(mdd)
            final_capitals.append(final_cap)
            if final_cap <= ruin_line:
                ruin_count += 1

        max_drawdowns.sort()
        final_capitals.sort()

        n = self.config.n_simulations
        idx_95 = int(n * self.config.confidence_level) - 1
        idx_50 = n // 2

        # VaR: initial_capital - 95th percentile worst final capital
        worst_finals = sorted(final_capitals)
        var_95 = initial - worst_finals[max(0, n - idx_95 - 1)]

        risk_of_ruin = ruin_count / n

        return MonteCarloResult(
            var_95=var_95,
            max_drawdown_95=max_drawdowns[min(idx_95, n - 1)],
            max_drawdown_median=max_drawdowns[idx_50],
            risk_of_ruin=risk_of_ruin,
            is_valid=risk_of_ruin < MAX_ACCEPTABLE_RUIN,
            n_simulations=n,
            final_capital_median=final_capitals[idx_50],
        )

    def _simulate_one(
        self,
        pnls: list[float],
        initial_capital: float,
        ruin_line: float,
    ) -> tuple[float, float]:
        """단일 경로 시뮬레이션.

        Returns:
            (max_drawdown, final_capital)
        """
        equity = initial_capital
        peak = equity
        max_dd = 0.0

        for pnl in pnls:
            equity += pnl
            peak = max(peak, equity)
            dd = (peak - equity) / peak if peak > 0 else 0.0
            max_dd = max(max_dd, dd)
            if equity <= ruin_line:
                return max_dd, equity

        return max_dd, equity
