"""Walk-Forward 검증 — APEX-V Phase E.

Rolling window로 In-Sample/Out-of-Sample 분할 후
BacktestEngine으로 각 구간을 시뮬레이션하고,
Walk-Forward Efficiency(WFE)를 계산한다.
"""
from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field

from loguru import logger

from src.backtest.engine import BacktestConfig, BacktestEngine, BacktestResult

# WFE 상수
MIN_WFE_THRESHOLD = 0.5


@dataclass
class WalkForwardConfig:
    """Walk-Forward 설정."""

    train_bars: int = 17280
    embargo_bars: int = 72
    test_bars: int = 2880
    step_bars: int | None = None
    n_folds: int = 20


@dataclass
class FoldResult:
    """단일 Fold 결과."""

    fold_index: int
    is_result: BacktestResult
    oos_result: BacktestResult
    wfe: float


@dataclass
class WalkForwardResult:
    """Walk-Forward 전체 결과."""

    folds: list[FoldResult] = field(default_factory=list)
    avg_wfe: float = 0.0
    is_valid: bool = False
    oos_total_trades: int = 0
    oos_win_rate: float = 0.0
    oos_total_pnl: float = 0.0


class WalkForwardValidator:
    """Walk-Forward 검증기."""

    def __init__(self, config: WalkForwardConfig | None = None) -> None:
        self.config = config or WalkForwardConfig()

    def run(
        self,
        candles: list[dict],
        strategy: Callable[[dict, dict], str],
        backtest_config: BacktestConfig | None = None,
    ) -> WalkForwardResult:
        """Walk-Forward 검증 실행.

        Args:
            candles: 전체 캔들 데이터.
            strategy: 전략 함수.
            backtest_config: 백테스트 설정 (기본값 사용 가능).

        Returns:
            WalkForwardResult
        """
        bt_config = backtest_config or BacktestConfig()
        splits = self._split_folds(len(candles))

        if not splits:
            logger.warning("Walk-Forward: 데이터 부족으로 fold 생성 불가")
            return WalkForwardResult()

        folds: list[FoldResult] = []

        for fold_idx, (
            train_start, train_end, test_start, test_end,
        ) in enumerate(splits):
            # In-Sample
            is_data = candles[train_start:train_end]
            is_engine = BacktestEngine(bt_config, is_data)
            is_result = is_engine.run(strategy)

            # Out-of-Sample
            oos_data = candles[test_start:test_end]
            oos_engine = BacktestEngine(bt_config, oos_data)
            oos_result = oos_engine.run(strategy)

            wfe = self._calculate_wfe(is_result, oos_result)
            folds.append(FoldResult(
                fold_index=fold_idx,
                is_result=is_result,
                oos_result=oos_result,
                wfe=wfe,
            ))

            logger.debug(
                f"Fold {fold_idx}: IS trades={is_result.total_trades}, "
                f"OOS trades={oos_result.total_trades}, WFE={wfe:.3f}"
            )

        # 집계
        avg_wfe = (
            sum(f.wfe for f in folds) / len(folds) if folds else 0.0
        )

        oos_trades_total = sum(f.oos_result.total_trades for f in folds)
        oos_winners = sum(f.oos_result.winning_trades for f in folds)
        oos_pnl = sum(f.oos_result.total_pnl for f in folds)
        oos_wr = (
            (oos_winners / oos_trades_total * 100)
            if oos_trades_total > 0
            else 0.0
        )

        return WalkForwardResult(
            folds=folds,
            avg_wfe=avg_wfe,
            is_valid=avg_wfe > MIN_WFE_THRESHOLD,
            oos_total_trades=oos_trades_total,
            oos_win_rate=oos_wr,
            oos_total_pnl=oos_pnl,
        )

    def _split_folds(
        self, n_candles: int,
    ) -> list[tuple[int, int, int, int]]:
        """Fold 분할 인덱스 생성.

        Returns:
            (train_start, train_end, test_start, test_end) 리스트.
        """
        cfg = self.config
        min_required = cfg.train_bars + cfg.embargo_bars + cfg.test_bars

        if n_candles < min_required:
            return []

        step = cfg.step_bars
        if step is None:
            remaining = n_candles - cfg.train_bars - cfg.test_bars
            step = max(
                1,
                remaining // max(1, cfg.n_folds - 1),
            )

        folds: list[tuple[int, int, int, int]] = []
        start = 0

        for _ in range(cfg.n_folds):
            train_end = start + cfg.train_bars
            test_start = train_end + cfg.embargo_bars
            test_end = test_start + cfg.test_bars

            if test_end > n_candles:
                break

            folds.append((start, train_end, test_start, test_end))
            start += step

        return folds

    def _calculate_wfe(
        self,
        is_result: BacktestResult,
        oos_result: BacktestResult,
    ) -> float:
        """Walk-Forward Efficiency 계산.

        WFE = OOS Sharpe / IS Sharpe.
        IS Sharpe <= 0 → WFE = 0.0.
        """
        is_sharpe = is_result.sharpe_ratio
        if is_sharpe <= 0 or math.isnan(is_sharpe):
            return 0.0

        oos_sharpe = oos_result.sharpe_ratio
        if math.isnan(oos_sharpe):
            return 0.0

        return oos_sharpe / is_sharpe
