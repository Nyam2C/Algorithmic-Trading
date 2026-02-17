"""E2E Tests — Walk-Forward + Monte Carlo + Session Analysis.

APEX-V Phase E: 검증 파이프라인 통합 테스트.
"""
from datetime import datetime, timezone

from src.backtest.engine import BacktestConfig, Trade
from src.backtest.monte_carlo import MonteCarloConfig, MonteCarloSimulator
from src.backtest.session_analysis import SessionAnalyzer
from src.backtest.walk_forward import WalkForwardConfig, WalkForwardValidator


def _make_candles(n: int, base_price: float = 50000.0) -> list[dict]:
    """테스트용 캔들 데이터."""
    candles = []
    price = base_price
    for i in range(n):
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
    """간단한 MA 기반 전략."""
    ma = market_data.get("ma_7")
    if ma is None:
        return "WAIT"
    if candle["close"] > ma:
        return "LONG"
    if candle["close"] < ma:
        return "SHORT"
    return "WAIT"


class TestValidationE2E:
    """검증 파이프라인 E2E 테스트."""

    def test_walk_forward_to_monte_carlo(self) -> None:
        """WF OOS 거래 -> MC 시뮬레이션."""
        candles = _make_candles(500)
        wf_cfg = WalkForwardConfig(
            train_bars=100,
            embargo_bars=10,
            test_bars=50,
            n_folds=3,
        )
        bt_cfg = BacktestConfig(
            use_slippage=False, use_realistic_exits=False,
        )

        # Walk-Forward
        wf = WalkForwardValidator(wf_cfg)
        wf_result = wf.run(candles, _simple_strategy, bt_cfg)
        assert len(wf_result.folds) > 0

        # OOS 거래 추출
        oos_trades: list[Trade] = []
        for fold in wf_result.folds:
            oos_trades.extend(fold.oos_result.trades)

        # Monte Carlo
        mc_cfg = MonteCarloConfig(n_simulations=100, seed=42)
        mc = MonteCarloSimulator(mc_cfg)
        mc_result = mc.run(oos_trades)

        assert mc_result.n_simulations == 100
        assert mc_result.risk_of_ruin >= 0.0
        assert mc_result.max_drawdown_95 >= 0.0

    def test_walk_forward_to_session_analysis(self) -> None:
        """WF OOS 거래 -> 세션 분석.

        WF 거래의 entry_time이 int일 경우 UNKNOWN 분류.
        """
        candles = _make_candles(500)
        wf_cfg = WalkForwardConfig(
            train_bars=100,
            embargo_bars=10,
            test_bars=50,
            n_folds=3,
        )
        bt_cfg = BacktestConfig(
            use_slippage=False, use_realistic_exits=False,
        )

        wf = WalkForwardValidator(wf_cfg)
        wf_result = wf.run(candles, _simple_strategy, bt_cfg)

        oos_trades: list[Trade] = []
        for fold in wf_result.folds:
            oos_trades.extend(fold.oos_result.trades)

        # Session Analysis
        sa = SessionAnalyzer()
        sa_result = sa.analyze(oos_trades)

        # int timestamps -> UNKNOWN
        if oos_trades:
            assert "UNKNOWN" in sa_result.sessions
            d = sa_result.to_dict()
            assert "sessions" in d

    def test_full_pipeline(self) -> None:
        """WF + MC + Session 전체 파이프라인."""
        candles = _make_candles(600)
        wf_cfg = WalkForwardConfig(
            train_bars=120,
            embargo_bars=10,
            test_bars=60,
            n_folds=3,
        )
        bt_cfg = BacktestConfig(
            use_slippage=False, use_realistic_exits=False,
        )

        # 1. Walk-Forward
        wf = WalkForwardValidator(wf_cfg)
        wf_result = wf.run(candles, _simple_strategy, bt_cfg)

        # 2. OOS 거래 추출
        oos_trades: list[Trade] = []
        for fold in wf_result.folds:
            oos_trades.extend(fold.oos_result.trades)

        # 3. Monte Carlo
        mc = MonteCarloSimulator(
            MonteCarloConfig(n_simulations=50, seed=7),
        )
        mc_result = mc.run(oos_trades)

        # 4. Session Analysis
        sa = SessionAnalyzer()
        sa_result = sa.analyze(oos_trades)

        # 결과 검증
        assert isinstance(wf_result.avg_wfe, float)
        assert isinstance(mc_result.risk_of_ruin, float)
        assert isinstance(sa_result.to_dict(), dict)

    def test_session_analysis_with_datetime_trades(self) -> None:
        """datetime entry_time 거래 -> 세션 분류."""
        trades = [
            Trade(
                entry_time=datetime(2025, 6, 15, 3, 0, tzinfo=timezone.utc),
                entry_price=100.0, side="LONG", quantity=1.0,
                exit_price=110.0, pnl=10.0,
            ),
            Trade(
                entry_time=datetime(2025, 6, 15, 10, 0, tzinfo=timezone.utc),
                entry_price=100.0, side="LONG", quantity=1.0,
                exit_price=95.0, pnl=-5.0,
            ),
            Trade(
                entry_time=datetime(2025, 6, 15, 15, 0, tzinfo=timezone.utc),
                entry_price=100.0, side="SHORT", quantity=1.0,
                exit_price=90.0, pnl=10.0,
            ),
        ]

        sa = SessionAnalyzer()
        result = sa.analyze(trades)
        assert "ASIA" in result.sessions
        assert "EU" in result.sessions
        assert "US" in result.sessions

        # MC on same trades
        mc = MonteCarloSimulator(
            MonteCarloConfig(n_simulations=50, seed=1),
        )
        mc_result = mc.run(trades)
        assert mc_result.final_capital_median > 0
