"""
Tests for technical indicators calculation
"""
import numpy as np
import pandas as pd
import pytest

from src.data.indicators import (
    analyze_candle_pattern,
    analyze_market,
    analyze_rsi_trend,
    calculate_adx,
    calculate_adx_components,
    calculate_atr,
    calculate_bollinger_bandwidth,
    calculate_ema,
    calculate_ma,
    calculate_price_vs_ma,
    calculate_returns,
    calculate_rsi,
    calculate_volume_ratio,
)


@pytest.fixture
def sample_candle_data():
    """샘플 캔들 데이터 생성"""
    return pd.DataFrame({
        'timestamp': pd.date_range('2024-01-01', periods=100, freq='5min'),
        'open': np.random.uniform(100, 110, 100),
        'high': np.random.uniform(110, 115, 100),
        'low': np.random.uniform(95, 100, 100),
        'close': np.random.uniform(100, 110, 100),
        'volume': np.random.uniform(1000, 2000, 100),
    })


@pytest.fixture
def uptrend_data():
    """상승 추세 데이터"""
    closes = np.linspace(100, 120, 50)  # 100에서 120으로 상승
    return pd.DataFrame({
        'timestamp': pd.date_range('2024-01-01', periods=50, freq='5min'),
        'open': closes - 0.5,
        'high': closes + 1,
        'low': closes - 1,
        'close': closes,
        'volume': np.random.uniform(1000, 2000, 50),
    })


@pytest.fixture
def downtrend_data():
    """하락 추세 데이터"""
    closes = np.linspace(120, 100, 50)  # 120에서 100으로 하락
    return pd.DataFrame({
        'timestamp': pd.date_range('2024-01-01', periods=50, freq='5min'),
        'open': closes + 0.5,
        'high': closes + 1,
        'low': closes - 1,
        'close': closes,
        'volume': np.random.uniform(1000, 2000, 50),
    })


class TestCalculateRSI:
    """RSI 계산 테스트"""

    def test_rsi_calculation(self, sample_candle_data):
        """RSI가 정상적으로 계산되는지 테스트"""
        rsi = calculate_rsi(sample_candle_data, period=14)

        assert len(rsi) == len(sample_candle_data)
        assert not rsi.isna().all()  # 일부 값은 있어야 함

        # RSI는 0-100 사이여야 함
        valid_rsi = rsi[~rsi.isna()]
        assert (valid_rsi >= 0).all()
        assert (valid_rsi <= 100).all()

    def test_rsi_uptrend(self, uptrend_data):
        """상승 추세에서 RSI가 높게 나오는지 테스트"""
        rsi = calculate_rsi(uptrend_data, period=14)

        # 상승 추세의 마지막 RSI는 높아야 함 (>50)
        last_rsi = rsi.iloc[-1]
        assert last_rsi > 50

    def test_rsi_downtrend(self, downtrend_data):
        """하락 추세에서 RSI가 낮게 나오는지 테스트"""
        rsi = calculate_rsi(downtrend_data, period=14)

        # 하락 추세의 마지막 RSI는 낮아야 함 (<50)
        last_rsi = rsi.iloc[-1]
        assert last_rsi < 50


class TestCalculateMA:
    """이동평균 계산 테스트"""

    def test_ma_calculation(self, sample_candle_data):
        """MA가 정상적으로 계산되는지 테스트"""
        mas = calculate_ma(sample_candle_data, periods=[7, 25, 99])

        assert 'ma_7' in mas
        assert 'ma_25' in mas
        assert 'ma_99' in mas

        # 모든 MA는 같은 길이
        assert len(mas['ma_7']) == len(sample_candle_data)
        assert len(mas['ma_25']) == len(sample_candle_data)
        assert len(mas['ma_99']) == len(sample_candle_data)

    def test_ma_ordering(self, uptrend_data):
        """상승 추세에서 단기 MA > 장기 MA 테스트"""
        mas = calculate_ma(uptrend_data, periods=[7, 25])

        ma7_last = mas['ma_7'].iloc[-1]
        ma25_last = mas['ma_25'].iloc[-1]

        # 상승 추세에서는 단기 MA가 장기 MA보다 높음
        assert ma7_last > ma25_last


class TestCalculateATR:
    """ATR 계산 테스트"""

    def test_atr_calculation(self, sample_candle_data):
        """ATR이 정상적으로 계산되는지 테스트"""
        atr = calculate_atr(sample_candle_data, period=14)

        assert len(atr) == len(sample_candle_data)

        # ATR은 항상 양수
        valid_atr = atr[~atr.isna()]
        assert (valid_atr >= 0).all()

    def test_atr_positive_values(self, sample_candle_data):
        """ATR 값이 0보다 큰지 테스트"""
        atr = calculate_atr(sample_candle_data)

        last_atr = atr.iloc[-1]
        assert last_atr > 0


class TestCalculateVolumeRatio:
    """볼륨 비율 계산 테스트"""

    def test_volume_ratio_normal(self, sample_candle_data):
        """정상적인 볼륨 비율 계산"""
        ratio = calculate_volume_ratio(sample_candle_data)

        assert isinstance(ratio, float)
        assert ratio > 0

    def test_volume_ratio_high_volume(self):
        """높은 볼륨일 때 비율이 높은지 테스트 (미완성 캔들 제외)"""
        # 마지막 캔들(미완성)은 제외하고 완성된 캔들들로 계산
        df = pd.DataFrame({
            'volume': [1000] * 19 + [5000, 100],  # 마지막 100은 미완성 캔들
        })

        ratio = calculate_volume_ratio(df)

        # 완성된 캔들 중 마지막(5000) / 완성된 캔들 평균
        # 평균 = (1000*19 + 5000) / 20 = 1200
        # 비율 = 5000 / 1200 ≈ 4.17
        assert ratio > 1

    def test_volume_ratio_excludes_incomplete_candle(self):
        """미완성 캔들이 제외되는지 테스트"""
        # 마지막 캔들의 거래량이 극단적으로 낮음 (진행 중)
        df = pd.DataFrame({
            'volume': [1000] * 20 + [10],  # 마지막 10은 미완성 캔들
        })

        ratio = calculate_volume_ratio(df)

        # 미완성 캔들(10) 제외 → 완성된 마지막 캔들(1000) / 평균(1000) = 1.0
        assert ratio == pytest.approx(1.0, rel=0.01)

    def test_volume_ratio_single_candle(self):
        """캔들이 1개만 있을 때 (제외 불가)"""
        df = pd.DataFrame({
            'volume': [1000],
        })

        ratio = calculate_volume_ratio(df)
        assert ratio == pytest.approx(1.0, rel=0.01)


class TestAnalyzeRSITrend:
    """RSI 추세 분석 테스트"""

    def test_rsi_rising(self):
        """RSI 상승 추세 감지"""
        rsi = pd.Series([30, 35, 40, 45, 50])
        trend = analyze_rsi_trend(rsi, window=5)

        assert trend == "rising"

    def test_rsi_falling(self):
        """RSI 하락 추세 감지"""
        rsi = pd.Series([70, 65, 60, 55, 50])
        trend = analyze_rsi_trend(rsi, window=5)

        assert trend == "falling"

    def test_rsi_flat(self):
        """RSI 횡보 감지"""
        rsi = pd.Series([50, 50.5, 50, 49.5, 50])
        trend = analyze_rsi_trend(rsi, window=5)

        assert trend == "flat"


class TestCalculatePriceVsMA:
    """가격과 MA 비교 테스트"""

    def test_price_above_ma(self):
        """가격이 MA 위에 있을 때"""
        pct_diff, position = calculate_price_vs_ma(110, 100)

        assert pct_diff == pytest.approx(10.0, rel=0.01)
        assert position == "above"

    def test_price_below_ma(self):
        """가격이 MA 아래에 있을 때"""
        pct_diff, position = calculate_price_vs_ma(90, 100)

        assert pct_diff == pytest.approx(-10.0, rel=0.01)
        assert position == "below"

    def test_price_vs_ma_nan(self):
        """MA가 NaN일 때 안전하게 처리"""
        import math
        pct_diff, position = calculate_price_vs_ma(100, float("nan"))

        assert math.isnan(pct_diff)
        assert position == "N/A"

    def test_price_vs_ma_zero(self):
        """MA가 0일 때 안전하게 처리"""
        import math
        pct_diff, position = calculate_price_vs_ma(100, 0.0)

        assert math.isnan(pct_diff)
        assert position == "N/A"


class TestAnalyzeCandlePattern:
    """캔들 패턴 분석 테스트"""

    def test_bullish_candles(self, uptrend_data):
        """상승 캔들이 더 많은지 테스트"""
        pattern = analyze_candle_pattern(uptrend_data)

        assert pattern['bullish_candles'] > pattern['bearish_candles']
        assert pattern['trend_2h_pct'] > 0  # 상승 추세

    def test_bearish_candles(self, downtrend_data):
        """하락 캔들이 더 많은지 테스트"""
        pattern = analyze_candle_pattern(downtrend_data)

        assert pattern['bearish_candles'] > pattern['bullish_candles']
        assert pattern['trend_2h_pct'] < 0  # 하락 추세


class TestAnalyzeMarket:
    """전체 시장 분석 통합 테스트"""

    def test_analyze_market_complete(self, sample_candle_data):
        """전체 시장 분석이 모든 지표를 반환하는지 테스트"""
        ticker_24h = {
            'high_24h': 115.0,
            'low_24h': 95.0,
            'change_24h': 2.5,
            'volume_24h': 50000.0,
            'quote_volume_24h': 5000000.0,
        }
        current_price = 105.0

        analysis = analyze_market(sample_candle_data, ticker_24h, current_price)

        # 필수 키 확인
        required_keys = [
            'current_price', 'rsi', 'ma_7', 'ma_25', 'ma_99',
            'atr', 'volume_ratio', 'trend_2h_pct',
            'resistance', 'support'
        ]

        for key in required_keys:
            assert key in analysis, f"Missing key: {key}"

    def test_analyze_market_values_valid(self, sample_candle_data):
        """분석 결과 값들이 유효한 범위인지 테스트"""
        ticker_24h = {
            'high_24h': 115.0,
            'low_24h': 95.0,
            'change_24h': 2.5,
            'volume_24h': 50000.0,
            'quote_volume_24h': 5000000.0,
        }
        current_price = 105.0

        analysis = analyze_market(sample_candle_data, ticker_24h, current_price)

        # RSI는 0-100
        assert 0 <= analysis['rsi'] <= 100

        # ATR은 양수
        assert analysis['atr'] > 0

        # 볼륨 비율은 양수
        assert analysis['volume_ratio'] > 0

        # 저항/지지는 현재가 근처
        assert analysis['resistance'] >= current_price
        assert analysis['support'] <= current_price



class TestCalculateADX:
    """ADX 계산 테스트"""

    def test_adx_calculation(self, sample_candle_data):
        """ADX가 정상적으로 계산되는지"""
        adx = calculate_adx(sample_candle_data)
        assert len(adx) == len(sample_candle_data)
        valid = adx[~adx.isna()]
        assert len(valid) > 0
        assert (valid >= 0).all()
        assert (valid <= 100).all()

    def test_adx_strong_trend(self, uptrend_data):
        """상승 추세에서 ADX가 높게 나오는지"""
        adx = calculate_adx(uptrend_data)
        last_adx = adx.iloc[-1]
        assert last_adx > 20  # 추세 존재

    def test_adx_components(self, sample_candle_data):
        """ADX 컴포넌트(DI+, DI-) 정상 반환"""
        components = calculate_adx_components(sample_candle_data)
        assert "adx" in components
        assert "di_plus" in components
        assert "di_minus" in components
        for key in components:
            valid = components[key][~components[key].isna()]
            assert len(valid) > 0

    def test_adx_uptrend_di_plus_dominates(self, uptrend_data):
        """상승 추세에서 DI+ > DI-"""
        components = calculate_adx_components(uptrend_data)
        last_di_plus = components["di_plus"].iloc[-1]
        last_di_minus = components["di_minus"].iloc[-1]
        assert last_di_plus > last_di_minus


class TestCalculateEMA:
    """EMA 계산 테스트"""

    def test_ema_calculation(self, sample_candle_data):
        """EMA가 정상적으로 계산되는지"""
        ema = calculate_ema(sample_candle_data, period=20)
        assert len(ema) == len(sample_candle_data)
        valid = ema[~ema.isna()]
        assert len(valid) > 0
        assert (valid > 0).all()

    def test_ema_follows_uptrend(self, uptrend_data):
        """상승 추세에서 EMA가 가격 아래에 있는지"""
        ema = calculate_ema(uptrend_data, period=10)
        last_ema = ema.iloc[-1]
        last_close = uptrend_data["close"].iloc[-1]
        assert last_close > last_ema

    def test_ema_different_periods(self, sample_candle_data):
        """다른 주기의 EMA가 정상 계산되는지"""
        ema_10 = calculate_ema(sample_candle_data, period=10)
        ema_20 = calculate_ema(sample_candle_data, period=20)
        # 짧은 주기 EMA가 더 빨리 유효값을 가짐
        valid_10 = ema_10[~ema_10.isna()]
        valid_20 = ema_20[~ema_20.isna()]
        assert len(valid_10) >= len(valid_20)


class TestCalculateBollingerBandwidth:
    """Bollinger Bandwidth 테스트"""

    def test_bb_bandwidth_calculation(self, sample_candle_data):
        """BB 대역폭이 정상 계산되는지"""
        bw = calculate_bollinger_bandwidth(sample_candle_data)
        assert len(bw) == len(sample_candle_data)
        valid = bw[~bw.isna()]
        assert len(valid) > 0
        assert (valid >= 0).all()

    def test_bb_bandwidth_narrow_range(self):
        """좁은 범위 데이터에서 대역폭이 좁은지"""
        closes = [100.0] * 30 + [100.1, 99.9] * 5
        df = pd.DataFrame({
            "close": closes,
            "high": [c + 0.1 for c in closes],
            "low": [c - 0.1 for c in closes],
        })
        bw = calculate_bollinger_bandwidth(df)
        last_bw = bw.iloc[-1]
        assert last_bw < 0.01  # 매우 좁은 범위

    def test_bb_bandwidth_wide_range(self):
        """넓은 변동성 데이터에서 대역폭이 넓은지"""
        import numpy as np
        closes = list(np.linspace(100, 130, 20)) + list(np.linspace(130, 100, 20))
        df = pd.DataFrame({
            "close": closes,
            "high": [c + 5 for c in closes],
            "low": [c - 5 for c in closes],
        })
        bw = calculate_bollinger_bandwidth(df)
        valid = bw[~bw.isna()]
        if len(valid) > 0:
            assert valid.iloc[-1] > 0.01


class TestCalculateReturns:
    """Returns 계산 테스트"""

    def test_returns_default_periods(self, sample_candle_data):
        """기본 주기 리턴 계산"""
        returns = calculate_returns(sample_candle_data)
        assert "returns_5" in returns
        assert "returns_10" in returns
        assert "returns_20" in returns
        for key in returns:
            assert len(returns[key]) == len(sample_candle_data)

    def test_returns_custom_periods(self, sample_candle_data):
        """커스텀 주기 리턴 계산"""
        returns = calculate_returns(sample_candle_data, periods=[3, 7])
        assert "returns_3" in returns
        assert "returns_7" in returns
        assert "returns_5" not in returns

    def test_returns_uptrend_positive(self, uptrend_data):
        """상승 추세에서 리턴이 양수"""
        returns = calculate_returns(uptrend_data, periods=[10])
        valid = returns["returns_10"].dropna()
        if len(valid) > 0:
            assert valid.iloc[-1] > 0

    def test_returns_downtrend_negative(self, downtrend_data):
        """하락 추세에서 리턴이 음수"""
        returns = calculate_returns(downtrend_data, periods=[10])
        valid = returns["returns_10"].dropna()
        if len(valid) > 0:
            assert valid.iloc[-1] < 0


class TestAnalyzeMarketExpanded:
    """analyze_market 확장 필드 테스트"""

    def test_analyze_market_has_adx(self, sample_candle_data):
        """analyze_market 결과에 adx 필드 존재"""
        ticker = {"high_24h": 115.0, "low_24h": 95.0, "change_24h": 1.5}
        result = analyze_market(sample_candle_data, ticker, 105.0)
        assert "adx" in result
        assert isinstance(result["adx"], float)

    def test_analyze_market_has_ema_20(self, sample_candle_data):
        """analyze_market 결과에 ema_20 필드 존재"""
        ticker = {"high_24h": 115.0, "low_24h": 95.0, "change_24h": 1.5}
        result = analyze_market(sample_candle_data, ticker, 105.0)
        assert "ema_20" in result
        assert isinstance(result["ema_20"], float)

    def test_analyze_market_has_bb_width(self, sample_candle_data):
        """analyze_market 결과에 bb_width 필드 존재"""
        ticker = {"high_24h": 115.0, "low_24h": 95.0, "change_24h": 1.5}
        result = analyze_market(sample_candle_data, ticker, 105.0)
        assert "bb_width" in result
        assert isinstance(result["bb_width"], float)
