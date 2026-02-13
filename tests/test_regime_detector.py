"""
Tests for RegimeDetector

Phase 6.2: 마켓 레짐 감지 테스트
"""
import pytest

from src.data.regime_detector import MarketRegime, RegimeDetector


@pytest.fixture
def detector():
    """기본 RegimeDetector 인스턴스 (부분 추세 모드 비활성화)"""
    return RegimeDetector(
        atr_strong_threshold=1.0,
        atr_weak_threshold=0.5,
        partial_trend_mode=False,
    )


class TestRegimeDetection:
    """레짐 감지 테스트"""

    def test_detect_strong_uptrend(self, detector):
        """강한 상승 추세 감지"""
        market_data = {
            "ma_7": 100500.0,
            "ma_25": 100000.0,
            "ma_99": 99000.0,
            "atr": 1500.0,  # 1.5%
            "price": 100500.0,
        }

        regime = detector.detect(market_data)

        assert regime == MarketRegime.STRONG_UPTREND

    def test_detect_weak_uptrend(self, detector):
        """약한 상승 추세 감지"""
        market_data = {
            "ma_7": 100500.0,
            "ma_25": 100000.0,
            "ma_99": 99000.0,
            "atr": 400.0,  # 0.4%
            "price": 100500.0,
        }

        regime = detector.detect(market_data)

        assert regime == MarketRegime.WEAK_UPTREND

    def test_detect_strong_downtrend(self, detector):
        """강한 하락 추세 감지"""
        market_data = {
            "ma_7": 98500.0,
            "ma_25": 99000.0,
            "ma_99": 100000.0,
            "atr": 1500.0,  # 1.5%
            "price": 98500.0,
        }

        regime = detector.detect(market_data)

        assert regime == MarketRegime.STRONG_DOWNTREND

    def test_detect_weak_downtrend(self, detector):
        """약한 하락 추세 감지"""
        market_data = {
            "ma_7": 98500.0,
            "ma_25": 99000.0,
            "ma_99": 100000.0,
            "atr": 400.0,  # 0.4%
            "price": 98500.0,
        }

        regime = detector.detect(market_data)

        assert regime == MarketRegime.WEAK_DOWNTREND

    def test_detect_ranging_mixed_ma(self, detector):
        """횡보장 감지 (MA 혼재)"""
        market_data = {
            "ma_7": 100000.0,
            "ma_25": 100500.0,  # MA25 > MA7 (정렬 안 됨)
            "ma_99": 99500.0,
            "atr": 500.0,
            "price": 100000.0,
        }

        regime = detector.detect(market_data)

        assert regime == MarketRegime.RANGING

    def test_detect_ranging_all_same(self, detector):
        """횡보장 감지 (MA 비슷)"""
        market_data = {
            "ma_7": 100000.0,
            "ma_25": 100100.0,  # 정렬 안 됨
            "ma_99": 99900.0,
            "atr": 300.0,
            "price": 100000.0,
        }

        regime = detector.detect(market_data)

        assert regime == MarketRegime.RANGING

    def test_detect_unknown_missing_data(self, detector):
        """데이터 부족 시 UNKNOWN"""
        market_data = {
            "ma_7": 100000.0,
            # ma_25, ma_99 없음
        }

        regime = detector.detect(market_data)

        assert regime == MarketRegime.UNKNOWN

    def test_detect_with_atr_pct(self, detector):
        """atr_pct로 ATR 비율 직접 제공"""
        market_data = {
            "ma_7": 100500.0,
            "ma_25": 100000.0,
            "ma_99": 99000.0,
            "atr_pct": 1.5,  # 직접 비율 제공
        }

        regime = detector.detect(market_data)

        assert regime == MarketRegime.STRONG_UPTREND


class TestSignalFiltering:
    """시그널 필터링 테스트"""

    def test_filter_signal_ranging_long(self, detector):
        """횡보장에서 LONG 필터링"""
        signal = detector.filter_signal("LONG", MarketRegime.RANGING)

        assert signal == "WAIT"

    def test_filter_signal_ranging_short(self, detector):
        """횡보장에서 SHORT 필터링"""
        signal = detector.filter_signal("SHORT", MarketRegime.RANGING)

        assert signal == "WAIT"

    def test_filter_signal_unknown(self, detector):
        """UNKNOWN 레짐에서 필터링 - 데이터 부족 시 시그널 허용"""
        signal = detector.filter_signal("LONG", MarketRegime.UNKNOWN)

        assert signal == "LONG"

    def test_filter_signal_strong_uptrend_long(self, detector):
        """강한 상승 추세에서 LONG 허용"""
        signal = detector.filter_signal("LONG", MarketRegime.STRONG_UPTREND)

        assert signal == "LONG"

    def test_filter_signal_strong_uptrend_short(self, detector):
        """강한 상승 추세에서 SHORT 차단"""
        signal = detector.filter_signal("SHORT", MarketRegime.STRONG_UPTREND)

        assert signal == "WAIT"

    def test_filter_signal_strong_downtrend_short(self, detector):
        """강한 하락 추세에서 SHORT 허용"""
        signal = detector.filter_signal("SHORT", MarketRegime.STRONG_DOWNTREND)

        assert signal == "SHORT"

    def test_filter_signal_strong_downtrend_long(self, detector):
        """강한 하락 추세에서 LONG 차단"""
        signal = detector.filter_signal("LONG", MarketRegime.STRONG_DOWNTREND)

        assert signal == "WAIT"

    def test_filter_signal_weak_trend_allow(self, detector):
        """약한 추세에서 시그널 허용 (allow_weak_trend=True)"""
        signal = detector.filter_signal(
            "LONG", MarketRegime.WEAK_UPTREND, allow_weak_trend=True
        )

        assert signal == "LONG"

    def test_filter_signal_weak_trend_block(self, detector):
        """약한 추세에서 시그널 차단 (allow_weak_trend=False)"""
        signal = detector.filter_signal(
            "LONG", MarketRegime.WEAK_UPTREND, allow_weak_trend=False
        )

        assert signal == "WAIT"

    def test_filter_signal_wait_passthrough(self, detector):
        """WAIT 시그널은 그대로 통과"""
        signal = detector.filter_signal("WAIT", MarketRegime.RANGING)

        assert signal == "WAIT"


class TestGetRegimeInfo:
    """레짐 정보 조회 테스트"""

    def test_get_regime_info_strong_uptrend(self, detector):
        """강한 상승 추세 정보"""
        info = detector.get_regime_info(MarketRegime.STRONG_UPTREND)

        assert info["name"] == "강한 상승 추세"
        assert "LONG" in info["recommended_action"]

    def test_get_regime_info_ranging(self, detector):
        """횡보장 정보"""
        info = detector.get_regime_info(MarketRegime.RANGING)

        assert info["name"] == "횡보장"
        assert "회피" in info["recommended_action"]
        assert info["risk_level"] == "high"

    def test_get_regime_info_unknown(self, detector):
        """UNKNOWN 레짐 정보"""
        info = detector.get_regime_info(MarketRegime.UNKNOWN)

        assert info["name"] == "알 수 없음"
        assert info["risk_level"] == "high"

class TestPartialTrendMode:
    """부분 추세 모드 테스트"""

    def test_partial_trend_bullish(self):
        """MA7>MA25 but MA99 not aligned -> WEAK_UPTREND with partial mode (sufficient volatility)"""
        detector = RegimeDetector(partial_trend_mode=True)
        market_data = {
            "ma_7": 100500.0,
            "ma_25": 100000.0,
            "ma_99": 100200.0,  # MA99 between MA7 and MA25 -> not fully aligned
            "atr": 600.0,       # Phase 9: ATR > weak_threshold (0.5%) required for partial trend
            "price": 100500.0,
        }
        regime = detector.detect(market_data)
        assert regime == MarketRegime.WEAK_UPTREND

    def test_partial_trend_bearish(self):
        """MA7<MA25 but MA99 not aligned -> WEAK_DOWNTREND with partial mode (sufficient volatility)"""
        detector = RegimeDetector(partial_trend_mode=True)
        market_data = {
            "ma_7": 99500.0,
            "ma_25": 100000.0,
            "ma_99": 99800.0,  # MA99 not aligned for full bearish
            "atr": 600.0,       # Phase 9: ATR > weak_threshold (0.5%) required for partial trend
            "price": 99500.0,
        }
        regime = detector.detect(market_data)
        assert regime == MarketRegime.WEAK_DOWNTREND

    def test_partial_trend_disabled(self):
        """Same data but partial_trend_mode=False -> RANGING"""
        detector = RegimeDetector(partial_trend_mode=False)
        market_data = {
            "ma_7": 100500.0,
            "ma_25": 100000.0,
            "ma_99": 100200.0,
            "atr": 500.0,
            "price": 100500.0,
        }
        regime = detector.detect(market_data)
        assert regime == MarketRegime.RANGING

    def test_full_alignment_still_works(self):
        """Full alignment still produces STRONG/WEAK trends"""
        detector = RegimeDetector(partial_trend_mode=True)
        market_data = {
            "ma_7": 100500.0,
            "ma_25": 100000.0,
            "ma_99": 99000.0,  # Fully aligned
            "atr": 1500.0,
            "price": 100500.0,
        }
        regime = detector.detect(market_data)
        assert regime == MarketRegime.STRONG_UPTREND


class TestNanMaReturnsUnknown:
    """Issue 13: NaN MA -> UNKNOWN (not RANGING)"""

    def test_nan_ma_returns_unknown_not_ranging(self):
        """NaN MA values should return UNKNOWN, not RANGING"""
        detector = RegimeDetector()
        market_data = {
            "ma_7": 100000.0,
            "ma_25": float("nan"),
            "ma_99": float("nan"),
            "atr": 500.0,
            "price": 100000.0,
        }
        regime = detector.detect(market_data)
        assert regime == MarketRegime.UNKNOWN

    def test_nan_single_ma_returns_unknown(self):
        """Single NaN MA should return UNKNOWN"""
        detector = RegimeDetector()
        market_data = {
            "ma_7": 100000.0,
            "ma_25": 99000.0,
            "ma_99": float("nan"),
            "atr": 500.0,
            "price": 100000.0,
        }
        regime = detector.detect(market_data)
        assert regime == MarketRegime.UNKNOWN

    def test_unknown_regime_allows_signal_with_warning(self):
        """UNKNOWN regime should allow signal (not block like RANGING)"""
        detector = RegimeDetector()
        signal = detector.filter_signal("LONG", MarketRegime.UNKNOWN)
        assert signal == "LONG"

    def test_unknown_regime_allows_short_signal(self):
        """UNKNOWN regime should allow SHORT signal too"""
        detector = RegimeDetector()
        signal = detector.filter_signal("SHORT", MarketRegime.UNKNOWN)
        assert signal == "SHORT"

    def test_ranging_still_blocks_signal(self):
        """RANGING should still block signals (existing behavior)"""
        detector = RegimeDetector()
        signal = detector.filter_signal("LONG", MarketRegime.RANGING)
        assert signal == "WAIT"
