"""
Tests for APEX-V backtest engine additions.

Phase A-5: ADX and returns in backtest market data
"""

from src.backtest.engine import BacktestConfig, BacktestEngine


def _make_candles(n=100, base_price=50000.0, trend=0.0):
    """Generate test candle data."""
    candles = []
    price = base_price
    for i in range(n):
        price = price + trend + (i % 3 - 1) * 10  # small noise
        candles.append({
            "timestamp": f"2024-01-01T{i:04d}",
            "open": price - 5,
            "high": price + 20,
            "low": price - 20,
            "close": price,
            "volume": 1000 + i * 10,
        })
    return candles


class TestBacktestADX:
    """백테스트 ADX 계산 테스트"""

    def test_prepare_market_data_has_adx(self):
        """market_data에 adx 필드 존재"""
        candles = _make_candles(100)
        config = BacktestConfig()
        engine = BacktestEngine(config, candles)
        market_data = engine._prepare_market_data(50)
        assert "adx" in market_data
        assert isinstance(market_data["adx"], float)
        assert market_data["adx"] >= 0

    def test_prepare_market_data_has_di(self):
        """market_data에 di_plus, di_minus 필드 존재"""
        candles = _make_candles(100)
        config = BacktestConfig()
        engine = BacktestEngine(config, candles)
        market_data = engine._prepare_market_data(50)
        assert "di_plus" in market_data
        assert "di_minus" in market_data

    def test_prepare_market_data_has_returns(self):
        """market_data에 returns 필드 존재"""
        candles = _make_candles(100)
        config = BacktestConfig()
        engine = BacktestEngine(config, candles)
        market_data = engine._prepare_market_data(50)
        assert "returns_5" in market_data
        assert "returns_10" in market_data
        assert "returns_20" in market_data

    def test_adx_not_in_early_bars(self):
        """초기 봉에서는 ADX 없음"""
        candles = _make_candles(100)
        config = BacktestConfig()
        engine = BacktestEngine(config, candles)
        market_data = engine._prepare_market_data(5)
        assert "adx" not in market_data

    def test_calculate_adx_uptrend(self):
        """상승 추세 ADX 계산"""
        candles = _make_candles(50, trend=50)
        config = BacktestConfig()
        engine = BacktestEngine(config, candles)
        result = engine._calculate_adx(candles)
        assert "adx" in result
        assert result["adx"] > 0
        assert result["di_plus"] > result["di_minus"]

    def test_calculate_adx_insufficient_data(self):
        """데이터 부족 시 빈 dict"""
        candles = _make_candles(5)
        config = BacktestConfig()
        engine = BacktestEngine(config, candles)
        result = engine._calculate_adx(candles)
        assert result == {}

    def test_calculate_returns_uptrend(self):
        """상승 추세 returns 양수"""
        candles = _make_candles(50, trend=50)
        config = BacktestConfig()
        engine = BacktestEngine(config, candles)
        result = engine._calculate_returns([float(x) for x in range(100, 150)])
        assert result.get("returns_5", 0) > 0

    def test_calculate_returns_insufficient_data(self):
        """데이터 부족 시 빈 dict"""
        candles = _make_candles(3)
        config = BacktestConfig()
        engine = BacktestEngine(config, candles)
        result = engine._calculate_returns([100.0, 101.0, 102.0])
        assert "returns_20" not in result

    def test_backtest_runs_with_new_data(self):
        """새 데이터 필드 포함해도 백테스트 정상 실행"""
        candles = _make_candles(200)
        config = BacktestConfig(initial_capital=10000)
        engine = BacktestEngine(config, candles)

        def simple_strategy(candle, market_data):
            rsi = market_data.get("rsi", 50)
            if rsi < 30:
                return "LONG"
            if rsi > 70:
                return "SHORT"
            return "WAIT"

        result = engine.run(simple_strategy)
        assert result.total_trades >= 0
        assert result.final_capital > 0

    def test_existing_fields_unchanged(self):
        """기존 필드(ma, rsi, atr, macd, bb)가 여전히 존재"""
        candles = _make_candles(100)
        config = BacktestConfig()
        engine = BacktestEngine(config, candles)
        market_data = engine._prepare_market_data(50)
        # Existing fields
        assert "current_price" in market_data
        assert "rsi" in market_data
        assert "atr" in market_data
        assert "bb_width" in market_data
