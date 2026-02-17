"""Tests for MonteCarloSimulator — APEX-V Phase E."""

from src.backtest.engine import Trade
from src.backtest.monte_carlo import (
    MonteCarloConfig,
    MonteCarloSimulator,
)


def _make_trade(pnl: float) -> Trade:
    """PnL이 설정된 Trade 생성."""
    return Trade(
        entry_time=0,
        entry_price=100.0,
        side="LONG",
        quantity=1.0,
        exit_price=100.0 + pnl,
        pnl=pnl,
    )


class TestMonteCarloConfig:
    """MonteCarloConfig 기본값 테스트."""

    def test_defaults(self) -> None:
        cfg = MonteCarloConfig()
        assert cfg.n_simulations == 1000
        assert cfg.confidence_level == 0.95
        assert cfg.ruin_threshold == 0.50
        assert cfg.initial_capital == 10000.0
        assert cfg.seed is None

    def test_custom_values(self) -> None:
        cfg = MonteCarloConfig(
            n_simulations=500,
            seed=42,
        )
        assert cfg.n_simulations == 500
        assert cfg.seed == 42


class TestMonteCarloSimulator:
    """MonteCarloSimulator 핵심 테스트."""

    def test_empty_trades_zero_risk(self) -> None:
        """빈 거래 목록 -> 리스크 0."""
        sim = MonteCarloSimulator()
        result = sim.run([])
        assert result.risk_of_ruin == 0.0
        assert result.is_valid is True
        assert result.var_95 == 0.0
        assert result.final_capital_median == 10000.0

    def test_deterministic_with_seed(self) -> None:
        """동일 seed -> 동일 결과."""
        trades = [_make_trade(10.0) for _ in range(20)]
        trades += [_make_trade(-5.0) for _ in range(10)]

        cfg = MonteCarloConfig(n_simulations=100, seed=42)
        sim = MonteCarloSimulator(cfg)

        r1 = sim.run(trades)
        r2 = sim.run(trades)

        assert r1.var_95 == r2.var_95
        assert r1.max_drawdown_95 == r2.max_drawdown_95
        assert r1.risk_of_ruin == r2.risk_of_ruin

    def test_all_winners_zero_ruin(self) -> None:
        """전승 -> 파산 리스크 0."""
        trades = [_make_trade(50.0) for _ in range(30)]
        cfg = MonteCarloConfig(n_simulations=200, seed=1)
        sim = MonteCarloSimulator(cfg)
        result = sim.run(trades)

        assert result.risk_of_ruin == 0.0
        assert result.is_valid is True
        assert result.final_capital_median > 10000.0

    def test_all_losers_high_ruin(self) -> None:
        """전패 (큰 손실) -> 높은 파산 리스크."""
        # 30 trades x -500 = -15000 > initial 10000
        trades = [_make_trade(-500.0) for _ in range(30)]
        cfg = MonteCarloConfig(n_simulations=100, seed=1)
        sim = MonteCarloSimulator(cfg)
        result = sim.run(trades)

        assert result.risk_of_ruin == 1.0
        assert result.is_valid is False

    def test_mixed_trades_reasonable_range(self) -> None:
        """혼합 거래 -> VaR/MDD가 합리적 범위."""
        trades = [_make_trade(20.0) for _ in range(60)]
        trades += [_make_trade(-15.0) for _ in range(40)]
        cfg = MonteCarloConfig(n_simulations=500, seed=7)
        sim = MonteCarloSimulator(cfg)
        result = sim.run(trades)

        # 순 PnL = 60*20 - 40*15 = 600 (양수)
        assert result.final_capital_median > 10000.0
        assert result.max_drawdown_95 > 0.0
        assert result.max_drawdown_95 < 1.0
        # VaR < 0 means net profit at confidence level
        assert isinstance(result.var_95, float)

    def test_is_valid_flag(self) -> None:
        """risk_of_ruin < 0.01 이면 is_valid = True."""
        # 대부분 이기는 거래
        trades = [_make_trade(10.0) for _ in range(50)]
        trades += [_make_trade(-2.0) for _ in range(10)]
        cfg = MonteCarloConfig(n_simulations=200, seed=3)
        sim = MonteCarloSimulator(cfg)
        result = sim.run(trades)

        assert result.is_valid is True
        assert result.risk_of_ruin < 0.01

    def test_n_simulations_in_result(self) -> None:
        """결과에 n_simulations 반영."""
        cfg = MonteCarloConfig(n_simulations=77, seed=1)
        sim = MonteCarloSimulator(cfg)
        result = sim.run([_make_trade(1.0)])
        assert result.n_simulations == 77

    def test_trades_with_none_pnl_skipped(self) -> None:
        """pnl=None인 거래는 무시."""
        trades = [_make_trade(10.0) for _ in range(5)]
        no_pnl = Trade(
            entry_time=0,
            entry_price=100.0,
            side="LONG",
            quantity=1.0,
        )
        trades.append(no_pnl)

        cfg = MonteCarloConfig(n_simulations=50, seed=1)
        sim = MonteCarloSimulator(cfg)
        result = sim.run(trades)
        # 5 trades x 10 = 50 profit
        assert result.final_capital_median > 10000.0

    def test_mdd_median_leq_mdd_95(self) -> None:
        """MDD median <= MDD 95th percentile."""
        trades = [_make_trade(5.0) for _ in range(40)]
        trades += [_make_trade(-8.0) for _ in range(20)]
        cfg = MonteCarloConfig(n_simulations=300, seed=5)
        sim = MonteCarloSimulator(cfg)
        result = sim.run(trades)

        assert result.max_drawdown_median <= result.max_drawdown_95
