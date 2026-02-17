"""Tests for WalkForwardValidator — APEX-V Phase E."""
import pytest

from src.backtest.engine import BacktestConfig
from src.backtest.walk_forward import (
    WalkForwardConfig,
    WalkForwardValidator,
)


def _make_candles(n: int, base_price: float = 50000.0) -> list[dict]:
    """테스트용 캔들 데이터 생성.

    약간의 변동이 있는 시뮬레이션 데이터.
    """
    candles = []
    price = base_price
    for i in range(n):
        # 작은 변동 (sine-like)
        delta = 50.0 * (1 if i % 7 < 4 else -1)
        high = price + abs(delta) + 10
        low = price - abs(delta) - 10
        close = price + delta
        candles.append({
            "timestamp": i,
            "open": price,
            "high": high,
            "low": low,
            "close": close,
            "volume": 1000.0,
        })
        price = close
    return candles


def _simple_strategy(candle: dict, market_data: dict) -> str:
    """간단한 테스트 전략: MA 기반."""
    ma = market_data.get("ma_7")
    if ma is None:
        return "WAIT"
    if candle["close"] > ma:
        return "LONG"
    if candle["close"] < ma:
        return "SHORT"
    return "WAIT"


class TestWalkForwardConfig:
    """WalkForwardConfig 기본값 테스트."""

    def test_defaults(self) -> None:
        cfg = WalkForwardConfig()
        assert cfg.train_bars == 17280
        assert cfg.embargo_bars == 72
        assert cfg.test_bars == 2880
        assert cfg.step_bars is None
        assert cfg.n_folds == 20

    def test_custom(self) -> None:
        cfg = WalkForwardConfig(
            train_bars=100, test_bars=50, n_folds=5,
        )
        assert cfg.train_bars == 100
        assert cfg.test_bars == 50


class TestWalkForwardValidator:
    """WalkForwardValidator 핵심 테스트."""

    def test_insufficient_data_no_crash(self) -> None:
        """데이터 부족 -> 빈 결과 (크래시 없음)."""
        candles = _make_candles(50)
        cfg = WalkForwardConfig(
            train_bars=100, test_bars=50,
        )
        validator = WalkForwardValidator(cfg)
        bt_cfg = BacktestConfig(
            use_slippage=False, use_realistic_exits=False,
        )
        result = validator.run(candles, _simple_strategy, bt_cfg)
        assert result.folds == []
        assert result.is_valid is False

    def test_basic_run_produces_folds(self) -> None:
        """충분한 데이터 -> fold 생성."""
        candles = _make_candles(500)
        cfg = WalkForwardConfig(
            train_bars=100,
            embargo_bars=10,
            test_bars=50,
            n_folds=3,
        )
        validator = WalkForwardValidator(cfg)
        bt_cfg = BacktestConfig(
            use_slippage=False, use_realistic_exits=False,
        )
        result = validator.run(candles, _simple_strategy, bt_cfg)

        assert len(result.folds) > 0
        assert len(result.folds) <= 3

    def test_folds_respect_embargo(self) -> None:
        """Fold 분할이 embargo gap을 존중."""
        cfg = WalkForwardConfig(
            train_bars=100,
            embargo_bars=20,
            test_bars=50,
            n_folds=5,
        )
        validator = WalkForwardValidator(cfg)
        splits = validator._split_folds(500)

        for train_start, train_end, test_start, test_end in splits:
            assert test_start == train_end + 20
            assert test_end - test_start == 50
            assert train_end - train_start == 100

    def test_wfe_positive_is_sharpe(self) -> None:
        """IS Sharpe > 0 -> WFE = OOS/IS."""
        from src.backtest.engine import BacktestResult

        is_result = BacktestResult(
            trades=[], initial_capital=10000, final_capital=10000,
        )
        is_result.sharpe_ratio = 2.0

        oos_result = BacktestResult(
            trades=[], initial_capital=10000, final_capital=10000,
        )
        oos_result.sharpe_ratio = 1.0

        validator = WalkForwardValidator()
        wfe = validator._calculate_wfe(is_result, oos_result)
        assert wfe == pytest.approx(0.5)

    def test_wfe_negative_is_sharpe(self) -> None:
        """IS Sharpe <= 0 -> WFE = 0.0."""
        from src.backtest.engine import BacktestResult

        is_result = BacktestResult(
            trades=[], initial_capital=10000, final_capital=10000,
        )
        is_result.sharpe_ratio = -1.0

        oos_result = BacktestResult(
            trades=[], initial_capital=10000, final_capital=10000,
        )
        oos_result.sharpe_ratio = 1.5

        validator = WalkForwardValidator()
        wfe = validator._calculate_wfe(is_result, oos_result)
        assert wfe == 0.0

    def test_is_valid_reflects_avg_wfe(self) -> None:
        """is_valid = (avg_wfe > 0.5) 관계 검증."""
        candles = _make_candles(1000)
        cfg = WalkForwardConfig(
            train_bars=200,
            embargo_bars=10,
            test_bars=80,
            n_folds=3,
        )
        validator = WalkForwardValidator(cfg)
        bt_cfg = BacktestConfig(
            use_slippage=False, use_realistic_exits=False,
        )
        result = validator.run(candles, _simple_strategy, bt_cfg)

        # is_valid must match avg_wfe threshold
        assert result.is_valid == (result.avg_wfe > 0.5)
        assert isinstance(result.avg_wfe, float)

    def test_deterministic_same_data(self) -> None:
        """동일 데이터 + 동일 전략 -> 동일 결과."""
        candles = _make_candles(500)
        cfg = WalkForwardConfig(
            train_bars=100,
            embargo_bars=10,
            test_bars=50,
            n_folds=3,
        )
        validator = WalkForwardValidator(cfg)
        bt_cfg = BacktestConfig(
            use_slippage=False, use_realistic_exits=False,
        )

        r1 = validator.run(candles, _simple_strategy, bt_cfg)
        r2 = validator.run(candles, _simple_strategy, bt_cfg)

        assert r1.avg_wfe == r2.avg_wfe
        assert r1.oos_total_trades == r2.oos_total_trades
        assert r1.oos_total_pnl == r2.oos_total_pnl

    def test_custom_step_bars(self) -> None:
        """step_bars 지정 시 해당 간격으로 fold 생성."""
        cfg = WalkForwardConfig(
            train_bars=100,
            embargo_bars=10,
            test_bars=50,
            step_bars=80,
            n_folds=5,
        )
        validator = WalkForwardValidator(cfg)
        splits = validator._split_folds(500)

        if len(splits) >= 2:
            assert splits[1][0] - splits[0][0] == 80

    def test_oos_metrics_aggregated(self) -> None:
        """OOS 지표가 전체 fold에서 집계."""
        candles = _make_candles(500)
        cfg = WalkForwardConfig(
            train_bars=100,
            embargo_bars=10,
            test_bars=50,
            n_folds=3,
        )
        validator = WalkForwardValidator(cfg)
        bt_cfg = BacktestConfig(
            use_slippage=False, use_realistic_exits=False,
        )
        result = validator.run(candles, _simple_strategy, bt_cfg)

        # 집계 검증
        expected_trades = sum(
            f.oos_result.total_trades for f in result.folds
        )
        assert result.oos_total_trades == expected_trades
