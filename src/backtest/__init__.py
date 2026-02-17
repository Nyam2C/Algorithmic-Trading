"""백테스트 모듈.

Phase 6.5: 백테스트 프레임워크
Phase 6.2: 슬리피지 모델 추가
Phase E: Monte Carlo, Session Analysis, Walk-Forward
"""
from src.backtest.engine import (
    BacktestConfig,
    BacktestEngine,
    BacktestResult,
    Trade,
)
from src.backtest.monte_carlo import (
    MonteCarloConfig,
    MonteCarloResult,
    MonteCarloSimulator,
)
from src.backtest.session_analysis import (
    SessionAnalysisResult,
    SessionAnalyzer,
    SessionStats,
)
from src.backtest.slippage import (
    SlippageModel,
    calculate_realistic_entry_price,
    calculate_realistic_exit_price,
)
from src.backtest.walk_forward import (
    FoldResult,
    WalkForwardConfig,
    WalkForwardResult,
    WalkForwardValidator,
)

__all__ = [
    "BacktestConfig",
    "BacktestEngine",
    "BacktestResult",
    "FoldResult",
    "MonteCarloConfig",
    "MonteCarloResult",
    "MonteCarloSimulator",
    "SessionAnalysisResult",
    "SessionAnalyzer",
    "SessionStats",
    "SlippageModel",
    "Trade",
    "WalkForwardConfig",
    "WalkForwardResult",
    "WalkForwardValidator",
    "calculate_realistic_entry_price",
    "calculate_realistic_exit_price",
]
