"""
Tests for technical indicators calculation
"""
import pytest
import pandas as pd
import numpy as np

from src.data.indicators import (
    calculate_rsi,
    calculate_ma,
    calculate_atr,
    calculate_volume_ratio,
    analyze_rsi_trend,
    calculate_price_vs_ma,
    analyze_candle_pattern,
    analyze_market,
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
        """높은 볼륨일 때 비율이 높은지 테스트"""
        df = pd.DataFrame({
            'volume': [1000] * 20 + [5000],  # 마지막 볼륨이 5배
        })

        ratio = calculate_volume_ratio(df)

        # 마지막 볼륨이 평균보다 높으므로 비율 > 1
        assert ratio > 1


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
