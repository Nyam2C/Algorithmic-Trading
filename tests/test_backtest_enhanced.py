"""
향상된 백테스트 엔진 테스트

Phase 6.2: 슬리피지, 지표 통합, 현실적 청산 테스트
"""
import pytest
from datetime import datetime, timedelta

from src.backtest.engine import BacktestEngine, BacktestConfig, Trade
from src.backtest.slippage import (
    SlippageModel,
    calculate_realistic_entry_price,
    calculate_realistic_exit_price,
)


class TestSlippageModel:
    """SlippageModel 테스트"""

    def test_base_slippage(self):
        """기본 슬리피지 테스트"""
        model = SlippageModel(base_slippage_pct=0.01)

        slippage = model.calculate_slippage(
            order_size=1000.0,
            avg_volume=100000.0,  # 큰 볼륨 (영향 적음)
            volatility=0.0,
        )

        # 기본 슬리피지 0.01% = 0.0001
        assert slippage == pytest.approx(0.0001, rel=0.1)

    def test_volume_impact(self):
        """볼륨 영향 테스트"""
        model = SlippageModel(
            base_slippage_pct=0.01,
            volume_impact_factor=0.001,
        )

        # 큰 주문 (볼륨의 10%)
        slippage_large = model.calculate_slippage(
            order_size=10000.0,
            avg_volume=100000.0,
        )

        # 작은 주문 (볼륨의 1%)
        slippage_small = model.calculate_slippage(
            order_size=1000.0,
            avg_volume=100000.0,
        )

        # 큰 주문이 더 많은 슬리피지
        assert slippage_large > slippage_small

    def test_volatility_impact(self):
        """변동성 영향 테스트"""
        # 볼륨 영향을 제거하고 변동성만 테스트
        model = SlippageModel(
            base_slippage_pct=0.0,  # 기본 슬리피지 제거
            volume_impact_factor=0.0,  # 볼륨 영향 제거
            volatility_impact_factor=0.5,
            max_slippage_pct=1.0,  # 높은 상한
        )

        # 높은 변동성
        slippage_high_vol = model.calculate_slippage(
            order_size=1000.0,
            avg_volume=100000.0,
            volatility=5.0,  # 5% ATR
        )

        # 낮은 변동성
        slippage_low_vol = model.calculate_slippage(
            order_size=1000.0,
            avg_volume=100000.0,
            volatility=1.0,  # 1% ATR
        )

        assert slippage_high_vol > slippage_low_vol

    def test_max_slippage_cap(self):
        """최대 슬리피지 제한 테스트"""
        model = SlippageModel(max_slippage_pct=0.1)  # 최대 0.1%

        # 극단적인 조건
        slippage = model.calculate_slippage(
            order_size=100000.0,  # 매우 큰 주문
            avg_volume=1000.0,  # 매우 작은 볼륨
            volatility=10.0,  # 높은 변동성
        )

        # 최대값 제한
        assert slippage <= 0.001  # 0.1%

    def test_apply_to_price_long(self):
        """LONG 포지션 가격 적용 테스트"""
        model = SlippageModel(base_slippage_pct=0.1)

        price = model.apply_to_price(
            price=50000.0,
            side="LONG",
            order_size=1000.0,
            avg_volume=100000.0,
        )

        # LONG은 더 높은 가격 (불리)
        assert price > 50000.0

    def test_apply_to_price_short(self):
        """SHORT 포지션 가격 적용 테스트"""
        model = SlippageModel(base_slippage_pct=0.1)

        price = model.apply_to_price(
            price=50000.0,
            side="SHORT",
            order_size=1000.0,
            avg_volume=100000.0,
        )

        # SHORT은 더 낮은 가격 (불리)
        assert price < 50000.0


class TestRealisticPricing:
    """현실적 가격 계산 테스트"""

    @pytest.fixture
    def sample_candle(self):
        """테스트용 캔들 데이터"""
        return {
            "timestamp": datetime.now(),
            "open": 49500.0,
            "high": 50500.0,
            "low": 49000.0,
            "close": 50000.0,
            "volume": 1000.0,
        }

    def test_realistic_entry_price_long(self, sample_candle):
        """LONG 현실적 진입 가격 테스트"""
        price = calculate_realistic_entry_price(
            candle=sample_candle,
            side="LONG",
            slippage_model=None,
        )

        # 종가와 고가 사이
        assert sample_candle["close"] <= price <= sample_candle["high"]

    def test_realistic_entry_price_short(self, sample_candle):
        """SHORT 현실적 진입 가격 테스트"""
        price = calculate_realistic_entry_price(
            candle=sample_candle,
            side="SHORT",
            slippage_model=None,
        )

        # 저가와 종가 사이
        assert sample_candle["low"] <= price <= sample_candle["close"]

    def test_realistic_exit_price_tp_long(self, sample_candle):
        """LONG TP 현실적 청산 가격 테스트"""
        entry_price = 49000.0
        tp_pct = 0.03  # 3% -> TP = 50470

        # 고가가 TP 가격 이상
        price = calculate_realistic_exit_price(
            candle=sample_candle,
            position_side="LONG",
            exit_reason="TP",
            entry_price=entry_price,
            tp_pct=tp_pct,
        )

        # TP 가격으로 청산
        expected_tp = entry_price * (1 + tp_pct)
        assert price == pytest.approx(expected_tp, rel=0.001)

    def test_realistic_exit_price_sl_long(self, sample_candle):
        """LONG SL 현실적 청산 가격 테스트"""
        entry_price = 50000.0
        sl_pct = 0.02  # 2% -> SL = 49000

        # 저가가 SL 가격 이하
        price = calculate_realistic_exit_price(
            candle=sample_candle,
            position_side="LONG",
            exit_reason="SL",
            entry_price=entry_price,
            sl_pct=sl_pct,
        )

        # SL 가격으로 청산
        expected_sl = entry_price * (1 - sl_pct)
        assert price == pytest.approx(expected_sl, rel=0.001)


class TestBacktestEngineTechnicalIndicators:
    """BacktestEngine 기술적 지표 테스트"""

    @pytest.fixture
    def candles(self):
        """테스트용 캔들 데이터 생성 (100개)"""
        candles = []
        base_price = 50000.0

        for i in range(100):
            # 사인파 가격 변동
            import math

            variation = math.sin(i * 0.1) * 500
            close = base_price + variation

            candles.append({
                "timestamp": datetime.now() + timedelta(minutes=5 * i),
                "open": close - 50,
                "high": close + 100,
                "low": close - 100,
                "close": close,
                "volume": 1000 + i * 10,
            })

        return candles

    @pytest.fixture
    def engine(self, candles):
        """테스트용 엔진 생성"""
        config = BacktestConfig(initial_capital=10000.0)
        return BacktestEngine(config, candles)

    def test_prepare_market_data_has_ma(self, engine):
        """MA 지표 포함 테스트"""
        market_data = engine._prepare_market_data(50)

        assert "ma_7" in market_data
        assert "ma_25" in market_data
        assert market_data["ma_7"] > 0
        assert market_data["ma_25"] > 0

    def test_prepare_market_data_has_rsi(self, engine):
        """RSI 지표 포함 테스트"""
        market_data = engine._prepare_market_data(50)

        assert "rsi" in market_data
        assert 0 <= market_data["rsi"] <= 100

    def test_prepare_market_data_has_atr(self, engine):
        """ATR 지표 포함 테스트"""
        market_data = engine._prepare_market_data(50)

        assert "atr" in market_data
        assert "atr_pct" in market_data
        assert market_data["atr"] > 0

    def test_prepare_market_data_has_macd(self, engine):
        """MACD 지표 포함 테스트"""
        market_data = engine._prepare_market_data(50)

        assert "macd" in market_data
        # macd_signal과 macd_histogram은 충분한 데이터가 있을 때만

    def test_prepare_market_data_has_bollinger(self, engine):
        """볼린저 밴드 지표 포함 테스트"""
        market_data = engine._prepare_market_data(50)

        assert "bb_upper" in market_data
        assert "bb_middle" in market_data
        assert "bb_lower" in market_data
        assert market_data["bb_upper"] > market_data["bb_middle"] > market_data["bb_lower"]

    def test_rsi_calculation(self, engine):
        """RSI 계산 정확성 테스트"""
        # 상승 추세 데이터
        rising_closes = [100 + i for i in range(20)]
        rsi = engine._calculate_rsi(rising_closes)
        assert rsi > 50  # 상승 추세 = 높은 RSI

        # 하락 추세 데이터
        falling_closes = [100 - i for i in range(20)]
        rsi = engine._calculate_rsi(falling_closes)
        assert rsi < 50  # 하락 추세 = 낮은 RSI

    def test_atr_calculation(self, engine, candles):
        """ATR 계산 정확성 테스트"""
        atr = engine._calculate_atr(candles[:20])

        # ATR은 양수
        assert atr > 0

        # ATR은 합리적인 범위 (high-low 평균 정도)
        avg_range = sum(c["high"] - c["low"] for c in candles[:20]) / 20
        assert atr <= avg_range * 1.5


class TestBacktestEngineSlippage:
    """BacktestEngine 슬리피지 통합 테스트"""

    @pytest.fixture
    def candles(self):
        """테스트용 캔들 데이터"""
        candles = []
        for i in range(50):
            candles.append({
                "timestamp": datetime.now() + timedelta(minutes=5 * i),
                "open": 50000.0,
                "high": 50200.0,
                "low": 49800.0,
                "close": 50100.0,
                "volume": 1000.0,
            })
        return candles

    def test_slippage_enabled_by_default(self, candles):
        """슬리피지 기본 활성화 테스트"""
        config = BacktestConfig()
        engine = BacktestEngine(config, candles)

        assert engine.slippage_model is not None

    def test_slippage_can_be_disabled(self, candles):
        """슬리피지 비활성화 테스트"""
        config = BacktestConfig(use_slippage=False)
        engine = BacktestEngine(config, candles)

        assert engine.slippage_model is None

    def test_slippage_affects_entry_price(self, candles):
        """슬리피지가 진입 가격에 영향 테스트"""
        # 슬리피지 ON
        config_with_slip = BacktestConfig(use_slippage=True)
        engine_with_slip = BacktestEngine(config_with_slip, candles)

        # 슬리피지 OFF
        config_no_slip = BacktestConfig(use_slippage=False, use_realistic_exits=False)
        engine_no_slip = BacktestEngine(config_no_slip, candles)

        # 동일 전략 실행
        def simple_strategy(candle, market_data):
            return "LONG" if len(engine_with_slip.trades) == 0 else "WAIT"

        result_with_slip = engine_with_slip.run(simple_strategy)
        result_no_slip = engine_no_slip.run(simple_strategy)

        # 슬리피지 있는 경우 더 불리한 진입
        if result_with_slip.trades and result_no_slip.trades:
            # LONG의 경우 슬리피지 있으면 더 높은 가격
            assert result_with_slip.trades[0].entry_price >= result_no_slip.trades[0].entry_price


class TestBacktestEngineRealisticExits:
    """현실적 청산 테스트"""

    @pytest.fixture
    def candles_with_tp_reached(self):
        """TP가 도달하는 캔들 데이터"""
        candles = []
        for i in range(10):
            candles.append({
                "timestamp": datetime.now() + timedelta(minutes=5 * i),
                "open": 50000.0,
                "high": 50600.0,  # 고가가 높음 (LONG TP 체결 가능)
                "low": 49500.0,
                "close": 50100.0,
                "volume": 1000.0,
            })
        return candles

    def test_realistic_exits_enabled_by_default(self, candles_with_tp_reached):
        """현실적 청산 기본 활성화 테스트"""
        config = BacktestConfig()
        _ = BacktestEngine(config, candles_with_tp_reached)  # engine 생성 확인

        assert config.use_realistic_exits is True

    def test_tp_uses_high_low_for_check(self, candles_with_tp_reached):
        """TP 체크가 high/low 사용 테스트"""
        config = BacktestConfig(
            tp_pct=0.01,  # 1% -> TP = 50500
            sl_pct=0.02,
            use_realistic_exits=True,
        )
        engine = BacktestEngine(config, candles_with_tp_reached)

        # LONG 포지션 설정 (진입가 50000)
        engine.position = Trade(
            entry_time=datetime.now(),
            entry_price=50000.0,
            side="LONG",
            quantity=0.1,
        )

        # 고가 50600 > TP 50500 이므로 TP 체결
        exit_reason = engine._check_exit(candles_with_tp_reached[0], bars=1)
        assert exit_reason == "TP"


class TestBacktestEngineIntegration:
    """통합 테스트"""

    @pytest.fixture
    def trending_candles(self):
        """상승 추세 캔들 데이터"""
        candles = []
        base_price = 50000.0

        for i in range(100):
            price = base_price + i * 10  # 상승 추세

            candles.append({
                "timestamp": datetime.now() + timedelta(minutes=5 * i),
                "open": price - 20,
                "high": price + 50,
                "low": price - 50,
                "close": price,
                "volume": 1000.0 + i,
            })

        return candles

    def test_full_backtest_with_enhancements(self, trending_candles):
        """전체 향상된 백테스트 실행 테스트"""
        config = BacktestConfig(
            initial_capital=10000.0,
            leverage=10,
            tp_pct=0.005,  # 0.5%
            sl_pct=0.003,  # 0.3%
            use_slippage=True,
            use_realistic_exits=True,
        )

        engine = BacktestEngine(config, trending_candles)

        # RSI 기반 전략
        def rsi_strategy(candle, market_data):
            rsi = market_data.get("rsi", 50)
            if rsi < 35:
                return "LONG"
            elif rsi > 65:
                return "SHORT"
            return "WAIT"

        result = engine.run(rsi_strategy)

        # 결과 검증
        assert result.total_trades >= 0
        assert result.initial_capital == 10000.0
        assert result.final_capital > 0
        assert len(result.equity_curve) > 0

    def test_backtest_result_metrics(self, trending_candles):
        """결과 메트릭 계산 테스트"""
        config = BacktestConfig(initial_capital=10000.0)
        engine = BacktestEngine(config, trending_candles)

        # 항상 LONG 전략 (상승 추세에서 유리)
        trade_count = 0

        def always_long(candle, market_data):
            nonlocal trade_count
            if trade_count < 3:
                trade_count += 1
                return "LONG"
            return "WAIT"

        result = engine.run(always_long)

        # 결과 딕셔너리 검증
        result_dict = result.to_dict()

        assert "total_trades" in result_dict
        assert "win_rate" in result_dict
        assert "total_pnl" in result_dict
        assert "max_drawdown" in result_dict
        assert "return_pct" in result_dict
