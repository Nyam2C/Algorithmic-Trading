"""
Data 모듈 커버리지 개선 테스트

multi_timeframe.py의 미커버 라인을 대상으로 합니다.
Lines: 97, 112, 131, 155, 179-193, 209-213
"""

from src.data.multi_timeframe import (
    MultiTimeframeAnalyzer,
    TimeframeAlignment,
)


class TestMultiTimeframeStrictModeEdgeCases:
    """엄격 모드 엣지 케이스 (lines 93-97)"""

    def test_strict_mode_short_not_bearish_aligned(self):
        """엄격 모드: SHORT + MA 비하락 정렬 → CONFLICTING (lines 96-97)"""
        analyzer = MultiTimeframeAnalyzer(strict_mode=True)

        higher_tf_data = {
            "ma_7": 52000.0,
            "ma_25": 51000.0,
            "ma_99": 53000.0,  # MA7 < MA99 → 비하락 정렬
            "current_price": 49000.0,  # 가격은 MA25 아래
        }

        result = analyzer.check_alignment("SHORT", higher_tf_data)
        assert result == TimeframeAlignment.CONFLICTING


class TestMultiTimeframeNeutralReturn:
    """마지막 NEUTRAL 반환 (line 112)"""

    def test_alignment_returns_neutral_for_unknown_signal(self):
        """알 수 없는 시그널 → NEUTRAL (line 112)"""
        analyzer = MultiTimeframeAnalyzer()

        higher_tf_data = {
            "ma_25": 50000.0,
            "current_price": 51000.0,
        }

        # 일반적으로 도달하지 않지만, 커버를 위해 직접 확인
        # "WAIT"가 아닌 다른 값이면서 "LONG"도 "SHORT"도 아닌 경우
        # 실제로는 "LONG" / "SHORT" / "WAIT" 외 다른 값을 전달할 수 없지만,
        # check_alignment에서 WAIT 체크 → LONG 체크 → SHORT 체크 후 NEUTRAL
        # 이를 위해 빈 문자열 전달
        result = analyzer.check_alignment("", higher_tf_data)
        assert result == TimeframeAlignment.NEUTRAL


class TestMultiTimeframeCheckMAMissing:
    """MA 데이터 누락 테스트 (lines 130-131)"""

    def test_check_ma_alignment_missing_ma7(self):
        """MA7 없음 (line 131)"""
        analyzer = MultiTimeframeAnalyzer()
        result = analyzer.check_ma_alignment({"ma_25": 50000, "ma_99": 49000})
        assert result == (False, False)

    def test_check_ma_alignment_missing_ma25(self):
        """MA25 없음 (line 131)"""
        analyzer = MultiTimeframeAnalyzer()
        result = analyzer.check_ma_alignment({"ma_7": 51000, "ma_99": 49000})
        assert result == (False, False)

    def test_check_ma_alignment_missing_ma99(self):
        """MA99 없음 (line 131)"""
        analyzer = MultiTimeframeAnalyzer()
        result = analyzer.check_ma_alignment({"ma_7": 51000, "ma_25": 50000})
        assert result == (False, False)


class TestMultiTimeframeFilterWait:
    """filter_signal WAIT 통과 테스트 (line 155)"""

    def test_filter_signal_wait_passthrough(self):
        """WAIT 시그널은 바로 반환 (lines 154-155)"""
        analyzer = MultiTimeframeAnalyzer()
        result = analyzer.filter_signal("WAIT", {"ma_25": 50000, "current_price": 51000})
        assert result == "WAIT"


class TestMultiTimeframeGetHigherTFTrend:
    """get_higher_tf_trend 테스트 (lines 179-193)"""

    def test_trend_bullish(self):
        """상승 추세 (lines 190-191)"""
        analyzer = MultiTimeframeAnalyzer()
        result = analyzer.get_higher_tf_trend({
            "ma_25": 50000.0,
            "current_price": 51000.0,
        })
        assert result == "BULLISH"

    def test_trend_bearish(self):
        """하락 추세 (lines 192-193)"""
        analyzer = MultiTimeframeAnalyzer()
        result = analyzer.get_higher_tf_trend({
            "ma_25": 50000.0,
            "current_price": 49000.0,
        })
        assert result == "BEARISH"

    def test_trend_neutral_within_tolerance(self):
        """허용 범위 내 → NEUTRAL (lines 187-188)"""
        analyzer = MultiTimeframeAnalyzer(tolerance_pct=0.5)
        result = analyzer.get_higher_tf_trend({
            "ma_25": 50000.0,
            "current_price": 50200.0,  # 0.4% → 허용 범위 내
        })
        assert result == "NEUTRAL"

    def test_trend_missing_data(self):
        """데이터 부족 → NEUTRAL (lines 182-183)"""
        analyzer = MultiTimeframeAnalyzer()
        result = analyzer.get_higher_tf_trend({})
        assert result == "NEUTRAL"

    def test_trend_with_price_key(self):
        """'price' 키 사용 (current_price 대신)"""
        analyzer = MultiTimeframeAnalyzer()
        result = analyzer.get_higher_tf_trend({
            "ma_25": 50000.0,
            "price": 49000.0,
        })
        assert result == "BEARISH"


class TestMultiTimeframeGetAnalysisInfo:
    """get_analysis_info 테스트 (lines 209-213)"""

    def test_analysis_info_full(self):
        """전체 분석 정보 반환 (lines 209-220)"""
        analyzer = MultiTimeframeAnalyzer()
        higher_tf_data = {
            "ma_7": 52000.0,
            "ma_25": 50000.0,
            "ma_99": 49000.0,
            "current_price": 51000.0,
        }

        info = analyzer.get_analysis_info("LONG", higher_tf_data)

        assert info["signal"] == "LONG"
        assert info["alignment"] == "aligned"
        assert info["higher_tf_trend"] == "BULLISH"
        assert info["ma_bullish_aligned"] is True
        assert info["ma_bearish_aligned"] is False
        assert info["filtered_signal"] == "LONG"

    def test_analysis_info_conflicting(self):
        """충돌 상황 분석 정보"""
        analyzer = MultiTimeframeAnalyzer()
        higher_tf_data = {
            "ma_7": 48000.0,
            "ma_25": 50000.0,
            "ma_99": 51000.0,
            "current_price": 49000.0,
        }

        info = analyzer.get_analysis_info("LONG", higher_tf_data)

        assert info["alignment"] == "conflicting"
        assert info["higher_tf_trend"] == "BEARISH"
        assert info["filtered_signal"] == "WAIT"

    def test_analysis_info_with_wait(self):
        """WAIT 시그널 분석 정보"""
        analyzer = MultiTimeframeAnalyzer()
        higher_tf_data = {
            "ma_7": 52000.0,
            "ma_25": 50000.0,
            "ma_99": 49000.0,
            "current_price": 51000.0,
        }

        info = analyzer.get_analysis_info("WAIT", higher_tf_data)

        assert info["signal"] == "WAIT"
        assert info["alignment"] == "neutral"
        assert info["filtered_signal"] == "WAIT"
