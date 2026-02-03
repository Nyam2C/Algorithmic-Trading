"""
백테스트 모듈

Phase 6.5: 백테스트 프레임워크
Phase 6.2: 슬리피지 모델 추가
"""
from src.backtest.engine import (
    BacktestEngine,
    BacktestConfig,
    BacktestResult,
    Trade,
)
from src.backtest.slippage import (
    SlippageModel,
    MarketImpactModel,
    calculate_realistic_entry_price,
    calculate_realistic_exit_price,
)

__all__ = [
    "BacktestEngine",
    "BacktestConfig",
    "BacktestResult",
    "Trade",
    "SlippageModel",
    "MarketImpactModel",
    "calculate_realistic_entry_price",
    "calculate_realistic_exit_price",
]
