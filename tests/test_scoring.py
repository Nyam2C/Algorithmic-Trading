"""
Scoring 모듈 테스트

IndicatorScorer의 경계값 및 엣지 케이스 테스트
(test_ai_coverage.py에서 분리)
"""
import pytest

from src.ai.scoring import IndicatorScorer

# =============================================================================
# Scoring: RSI 경계값 테스트
# =============================================================================


class TestScoringRSIEdgeCases:
    """RSI 스코어링 경계값 테스트"""

    @pytest.fixture
    def scorer(self):
        return IndicatorScorer()

    def test_rsi_extreme_oversold(self, scorer):
        """RSI < 20: 극단적 과매도 (lines 197-198)"""
        score = scorer._score_rsi(15.0)
        assert score.score == 1.0
        assert "극단적 과매도" in score.reason

    def test_rsi_low_zone(self, scorer):
        """RSI 30-40: 저점 근접 (lines 203-204)"""
        score = scorer._score_rsi(35.0)
        assert score.score > 0.3
        assert "저점 근접" in score.reason

    def test_rsi_high_zone(self, scorer):
        """RSI 60-70: 고점 근접 (lines 209-210)"""
        score = scorer._score_rsi(65.0)
        assert score.score < -0.3
        assert "고점 근접" in score.reason

    def test_rsi_extreme_overbought(self, scorer):
        """RSI > 80: 극단적 과매수 (lines 215-216)"""
        score = scorer._score_rsi(85.0)
        assert score.score == -1.0
        assert "극단적 과매수" in score.reason


# =============================================================================
# Scoring: MA 추세 경계값 테스트
# =============================================================================


class TestScoringMATrendEdgeCases:
    """MA 추세 스코어링 경계값 테스트"""

    @pytest.fixture
    def scorer(self):
        return IndicatorScorer()

    def test_ma_trend_zero_values(self, scorer):
        """MA 값 0인 경우 (line 239)"""
        data = {"ma_7": 0, "ma_25": 0}
        score = scorer._score_ma_trend(data)
        assert score.score == 0
        assert "데이터 부족" in score.reason

    def test_ma_trend_ma7_above_ma25_with_ma99_but_not_all_aligned(self, scorer):
        """MA99가 있고 MA7>MA25이지만 완전 정렬이 아닌 경우 (lines 255-257)"""
        data = {
            "ma_7": 52000.0,
            "ma_25": 50000.0,
            "ma_99": 51000.0,  # MA25 < MA99 < MA7 → 완전 정렬 아님
        }
        score = scorer._score_ma_trend(data)
        assert score.score == 0.5
        assert "상승 추세" in score.reason

    def test_ma_trend_ma7_below_ma25_with_ma99_not_all_aligned(self, scorer):
        """MA99가 있고 MA7<MA25이지만 완전 하락 정렬이 아닌 경우 (lines 258-260)"""
        data = {
            "ma_7": 49000.0,
            "ma_25": 50000.0,
            "ma_99": 49500.0,  # MA7 < MA99 < MA25 → 완전 정렬 아님
        }
        score = scorer._score_ma_trend(data)
        assert score.score == -0.5
        assert "하락 추세" in score.reason

    def test_ma_trend_equal_with_ma99(self, scorer):
        """MA7 == MA25이고 MA99가 있는 경우 (lines 261-263)"""
        data = {
            "ma_7": 50000.0,
            "ma_25": 50000.0,
            "ma_99": 49000.0,
        }
        score = scorer._score_ma_trend(data)
        assert score.score == 0.0
        assert "혼재" in score.reason

    def test_ma_trend_no_ma99_uptrend(self, scorer):
        """MA99 없이 MA7 > MA25 (lines 265-267)"""
        data = {"ma_7": 51000.0, "ma_25": 50000.0}
        score = scorer._score_ma_trend(data)
        assert score.score == 0.5
        assert "상승 추세" in score.reason

    def test_ma_trend_no_ma99_downtrend(self, scorer):
        """MA99 없이 MA7 < MA25 (lines 268-270)"""
        data = {"ma_7": 49000.0, "ma_25": 50000.0}
        score = scorer._score_ma_trend(data)
        assert score.score == -0.5
        assert "하락 추세" in score.reason


# =============================================================================
# Scoring: 볼륨, ATR 경계값 테스트
# =============================================================================


class TestScoringVolumeATREdgeCases:
    """볼륨, ATR 스코어링 경계값 테스트"""

    @pytest.fixture
    def scorer(self):
        return IndicatorScorer()

    def test_volume_high(self, scorer):
        """볼륨 > 2.0 (lines 289-290)"""
        score = scorer._score_volume(2.5)
        assert score.score == 0.5
        assert "높은 거래량" in score.reason

    def test_volume_low(self, scorer):
        """볼륨 < 0.8 (lines 298-299)"""
        score = scorer._score_volume(0.5)
        assert score.score == -0.2
        assert "낮은 거래량" in score.reason

    def test_atr_high_volatility(self, scorer):
        """ATR > 3.0: 높은 변동성 (lines 315-316)"""
        score = scorer._score_atr(3.5)
        assert score.score == -0.3
        assert "높은 변동성" in score.reason

    def test_atr_moderate_volatility(self, scorer):
        """ATR 1.5-3.0: 적정 변동성 (lines 318-319)"""
        score = scorer._score_atr(2.0)
        assert score.score == 0.2
        assert "적정 변동성" in score.reason

    def test_atr_very_low_volatility(self, scorer):
        """ATR < 0.5: 매우 낮은 변동성 (lines 324-325)"""
        score = scorer._score_atr(0.3)
        assert score.score == -0.2
        assert "매우 낮은 변동성" in score.reason


# =============================================================================
# Scoring: MACD 경계값 테스트
# =============================================================================


class TestScoringMACDEdgeCases:
    """MACD 스코어링 경계값 테스트"""

    @pytest.fixture
    def scorer(self):
        return IndicatorScorer()

    def test_macd_strong_bullish(self, scorer):
        """MACD histogram > 50: 강한 상승 (lines 349-350)"""
        data = {"macd": 100, "macd_signal": 30, "macd_histogram": 70}
        score = scorer._score_macd(data)
        assert score.score == 0.8
        assert "강한 상승" in score.reason

    def test_macd_strong_bearish(self, scorer):
        """MACD histogram < -50: 강한 하락 (lines 357-358)"""
        data = {"macd": -100, "macd_signal": -30, "macd_histogram": -70}
        score = scorer._score_macd(data)
        assert score.score == -0.8
        assert "강한 하락" in score.reason


# =============================================================================
# Scoring: 가격 위치 경계값 테스트
# =============================================================================


class TestScoringPricePositionEdgeCases:
    """가격 위치 스코어링 경계값 테스트"""

    @pytest.fixture
    def scorer(self):
        return IndicatorScorer()

    def test_price_overheated(self, scorer):
        """가격 MA25 위 3% 이상: 과열 (lines 383-384)"""
        data = {"price_vs_ma25_pct": 4.0}
        score = scorer._score_price_position(data)
        assert score.score == -0.3
        assert "과열" in score.reason

    def test_price_oversold(self, scorer):
        """가격 MA25 아래 3% 이상: 과매도 (lines 389-390)"""
        data = {"price_vs_ma25_pct": -4.0}
        score = scorer._score_price_position(data)
        assert score.score == 0.3
        assert "과매도" in score.reason


# =============================================================================
# Scoring: 빈 데이터 테스트
# =============================================================================


class TestScoringEmptyData:
    """빈 데이터 스코어링 테스트"""

    def test_calculate_score_no_indicators(self):
        """지표가 없는 경우 total_score == 0 (line 171)"""
        scorer = IndicatorScorer()
        result = scorer.calculate_score({})
        assert result.total_score == 0.0
        assert result.signal == "WAIT"
