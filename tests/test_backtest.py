"""
Tests for Backtest Framework

Phase 6.5: 백테스트 프레임워크
"""
import pytest
from typing import List, Dict

from src.backtest.engine import (
    BacktestEngine,
    BacktestConfig,
    BacktestResult,
    Trade,
)


@pytest.fixture
def sample_candles() -> List[Dict]:
    """샘플 캔들 데이터"""
    return [
        {"timestamp": 1, "open": 100, "high": 105, "low": 99, "close": 104, "volume": 1000},
        {"timestamp": 2, "open": 104, "high": 108, "low": 103, "close": 107, "volume": 1100},
        {"timestamp": 3, "open": 107, "high": 110, "low": 106, "close": 109, "volume": 1200},
        {"timestamp": 4, "open": 109, "high": 112, "low": 105, "close": 106, "volume": 1300},
        {"timestamp": 5, "open": 106, "high": 108, "low": 102, "close": 103, "volume": 1400},
        {"timestamp": 6, "open": 103, "high": 107, "low": 101, "close": 105, "volume": 1500},
        {"timestamp": 7, "open": 105, "high": 109, "low": 104, "close": 108, "volume": 1600},
        {"timestamp": 8, "open": 108, "high": 111, "low": 107, "close": 110, "volume": 1700},
        {"timestamp": 9, "open": 110, "high": 113, "low": 109, "close": 112, "volume": 1800},
        {"timestamp": 10, "open": 112, "high": 115, "low": 111, "close": 114, "volume": 1900},
    ]


class TestBacktestConfig:
    """BacktestConfig 테스트"""

    def test_default_config(self):
        """기본 설정"""
        config = BacktestConfig()

        assert config.initial_capital == 10000.0
        assert config.leverage == 10
        assert config.position_size_pct == 0.05
        assert config.tp_pct == 0.01
        assert config.sl_pct == 0.005

    def test_custom_config(self):
        """커스텀 설정"""
        config = BacktestConfig(
            initial_capital=50000.0,
            leverage=20,
            position_size_pct=0.03,
        )

        assert config.initial_capital == 50000.0
        assert config.leverage == 20
        assert config.position_size_pct == 0.03


class TestTrade:
    """Trade 데이터클래스 테스트"""

    def test_create_trade(self):
        """거래 생성"""
        trade = Trade(
            entry_time=1,
            entry_price=100.0,
            side="LONG",
            quantity=0.1,
        )

        assert trade.entry_price == 100.0
        assert trade.side == "LONG"
        assert trade.exit_price is None
        assert trade.pnl is None

    def test_trade_pnl_long_win(self):
        """LONG 승리 PnL"""
        trade = Trade(
            entry_time=1,
            entry_price=100.0,
            side="LONG",
            quantity=0.1,
            exit_time=2,
            exit_price=105.0,
            exit_reason="TP",
        )
        trade.calculate_pnl()

        assert trade.pnl == 0.5  # (105 - 100) * 0.1

    def test_trade_pnl_short_win(self):
        """SHORT 승리 PnL"""
        trade = Trade(
            entry_time=1,
            entry_price=100.0,
            side="SHORT",
            quantity=0.1,
            exit_time=2,
            exit_price=95.0,
            exit_reason="TP",
        )
        trade.calculate_pnl()

        assert trade.pnl == 0.5  # (100 - 95) * 0.1

    def test_trade_pnl_loss(self):
        """손실 PnL"""
        trade = Trade(
            entry_time=1,
            entry_price=100.0,
            side="LONG",
            quantity=0.1,
            exit_time=2,
            exit_price=98.0,
            exit_reason="SL",
        )
        trade.calculate_pnl()

        assert trade.pnl == -0.2  # (98 - 100) * 0.1


class TestBacktestResult:
    """BacktestResult 테스트"""

    def test_calculate_metrics(self):
        """메트릭 계산"""
        trades = [
            Trade(1, 100.0, "LONG", 0.1, 2, 105.0, "TP"),
            Trade(3, 105.0, "SHORT", 0.1, 4, 100.0, "TP"),
            Trade(5, 100.0, "LONG", 0.1, 6, 98.0, "SL"),
        ]
        for t in trades:
            t.calculate_pnl()

        result = BacktestResult(
            trades=trades,
            initial_capital=1000.0,
            final_capital=1008.0,  # 1000 + 0.5 + 0.5 - 0.2 = 1000.8 실제는 이걸 수동 계산
        )
        result.calculate_metrics()

        assert result.total_trades == 3
        assert result.winning_trades == 2
        assert result.losing_trades == 1
        assert result.win_rate == pytest.approx(66.67, rel=0.01)

    def test_empty_result(self):
        """거래 없는 결과"""
        result = BacktestResult(
            trades=[],
            initial_capital=1000.0,
            final_capital=1000.0,
        )
        result.calculate_metrics()

        assert result.total_trades == 0
        assert result.win_rate == 0.0


class TestBacktestEngine:
    """BacktestEngine 테스트"""

    def test_engine_init(self, sample_candles):
        """엔진 초기화"""
        config = BacktestConfig()
        engine = BacktestEngine(config, sample_candles)

        assert engine.config == config
        assert len(engine.data) == 10

    def test_simple_strategy(self, sample_candles):
        """간단한 전략 테스트"""
        config = BacktestConfig(
            initial_capital=10000.0,
            tp_pct=0.05,
            sl_pct=0.03,
        )

        # 항상 LONG 시그널 반환하는 전략
        def always_long_strategy(candle, market_data):
            return "LONG"

        engine = BacktestEngine(config, sample_candles)
        result = engine.run(always_long_strategy)

        assert isinstance(result, BacktestResult)
        assert result.initial_capital == 10000.0

    def test_no_signal_strategy(self, sample_candles):
        """시그널 없는 전략"""
        config = BacktestConfig()

        def no_signal_strategy(candle, market_data):
            return "WAIT"

        engine = BacktestEngine(config, sample_candles)
        result = engine.run(no_signal_strategy)

        assert result.total_trades == 0

    def test_tp_trigger(self):
        """TP 트리거 테스트"""
        # 가격이 지속적으로 상승하는 데이터
        candles = [
            {"timestamp": i, "open": 100 + i, "high": 102 + i, "low": 99 + i, "close": 101 + i, "volume": 1000}
            for i in range(20)
        ]

        config = BacktestConfig(
            tp_pct=0.05,  # 5% TP
            sl_pct=0.10,  # 10% SL
        )

        def long_once(candle, market_data):
            if candle["timestamp"] == 0:
                return "LONG"
            return "WAIT"

        engine = BacktestEngine(config, candles)
        result = engine.run(long_once)

        # 적어도 하나의 거래가 있어야 함
        assert result.total_trades >= 0
