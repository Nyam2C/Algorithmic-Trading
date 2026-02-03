"""
Tests for Multi-Timeframe Confirmation

Phase 6.4: 다중 타임프레임 확인
- 상위 TF(15분봉) 추세와 시그널 방향 확인
"""
import pytest

from src.data.multi_timeframe import (
    MultiTimeframeAnalyzer,
    TimeframeAlignment,
)


class TestTimeframeAlignment:
    """TimeframeAlignment Enum 테스트"""

    def test_aligned(self):
        """정렬된 상태"""
        assert TimeframeAlignment.ALIGNED.value == "aligned"

    def test_conflicting(self):
        """충돌 상태"""
        assert TimeframeAlignment.CONFLICTING.value == "conflicting"

    def test_neutral(self):
        """중립 상태"""
        assert TimeframeAlignment.NEUTRAL.value == "neutral"


class TestMultiTimeframeAnalyzer:
    """MultiTimeframeAnalyzer 테스트"""

    @pytest.fixture
    def analyzer(self):
        """기본 Analyzer"""
        return MultiTimeframeAnalyzer()

    def test_check_alignment_long_bullish(self, analyzer):
        """LONG + 상위 TF 상승 → ALIGNED"""
        higher_tf_data = {
            "ma_25": 50000.0,
            "current_price": 51000.0,  # 가격 > MA25
        }

        result = analyzer.check_alignment("LONG", higher_tf_data)
        assert result == TimeframeAlignment.ALIGNED

    def test_check_alignment_long_bearish(self, analyzer):
        """LONG + 상위 TF 하락 → CONFLICTING"""
        higher_tf_data = {
            "ma_25": 50000.0,
            "current_price": 49000.0,  # 가격 < MA25
        }

        result = analyzer.check_alignment("LONG", higher_tf_data)
        assert result == TimeframeAlignment.CONFLICTING

    def test_check_alignment_short_bearish(self, analyzer):
        """SHORT + 상위 TF 하락 → ALIGNED"""
        higher_tf_data = {
            "ma_25": 50000.0,
            "current_price": 49000.0,  # 가격 < MA25
        }

        result = analyzer.check_alignment("SHORT", higher_tf_data)
        assert result == TimeframeAlignment.ALIGNED

    def test_check_alignment_short_bullish(self, analyzer):
        """SHORT + 상위 TF 상승 → CONFLICTING"""
        higher_tf_data = {
            "ma_25": 50000.0,
            "current_price": 51000.0,  # 가격 > MA25
        }

        result = analyzer.check_alignment("SHORT", higher_tf_data)
        assert result == TimeframeAlignment.CONFLICTING

    def test_check_alignment_wait_signal(self, analyzer):
        """WAIT 시그널 → NEUTRAL"""
        higher_tf_data = {
            "ma_25": 50000.0,
            "current_price": 50000.0,
        }

        result = analyzer.check_alignment("WAIT", higher_tf_data)
        assert result == TimeframeAlignment.NEUTRAL

    def test_check_alignment_missing_data(self, analyzer):
        """데이터 부족 → NEUTRAL"""
        result = analyzer.check_alignment("LONG", {})
        assert result == TimeframeAlignment.NEUTRAL

    def test_filter_signal_aligned(self, analyzer):
        """정렬된 시그널 → 통과"""
        higher_tf_data = {
            "ma_25": 50000.0,
            "current_price": 51000.0,
        }

        result = analyzer.filter_signal("LONG", higher_tf_data)
        assert result == "LONG"

    def test_filter_signal_conflicting(self, analyzer):
        """충돌 시그널 → WAIT"""
        higher_tf_data = {
            "ma_25": 50000.0,
            "current_price": 49000.0,  # 하락 추세
        }

        result = analyzer.filter_signal("LONG", higher_tf_data)
        assert result == "WAIT"

    def test_filter_signal_with_tolerance(self):
        """허용 범위 내 → ALIGNED"""
        analyzer = MultiTimeframeAnalyzer(tolerance_pct=0.5)

        higher_tf_data = {
            "ma_25": 50000.0,
            "current_price": 49800.0,  # MA25의 0.4% 아래 (허용 범위 내)
        }

        result = analyzer.filter_signal("LONG", higher_tf_data)
        assert result == "LONG"

    def test_check_ma_alignment(self, analyzer):
        """MA 정렬 확인"""
        higher_tf_data = {
            "ma_7": 51000.0,
            "ma_25": 50000.0,
            "ma_99": 49000.0,  # MA7 > MA25 > MA99 → 상승
        }

        is_bullish, is_bearish = analyzer.check_ma_alignment(higher_tf_data)
        assert is_bullish is True
        assert is_bearish is False

    def test_check_ma_alignment_bearish(self, analyzer):
        """하락 MA 정렬"""
        higher_tf_data = {
            "ma_7": 49000.0,
            "ma_25": 50000.0,
            "ma_99": 51000.0,  # MA7 < MA25 < MA99 → 하락
        }

        is_bullish, is_bearish = analyzer.check_ma_alignment(higher_tf_data)
        assert is_bullish is False
        assert is_bearish is True


class TestMultiTimeframeWithStrict:
    """엄격 모드 테스트"""

    def test_strict_mode_requires_ma_alignment(self):
        """엄격 모드: MA 정렬 필요"""
        analyzer = MultiTimeframeAnalyzer(strict_mode=True)

        # 가격은 MA25 위지만 MA가 정렬되지 않음
        higher_tf_data = {
            "ma_7": 50500.0,
            "ma_25": 51000.0,  # MA7 < MA25 → 정렬 안됨
            "ma_99": 49000.0,
            "current_price": 52000.0,
        }

        result = analyzer.filter_signal("LONG", higher_tf_data)
        assert result == "WAIT"

    def test_strict_mode_aligned(self):
        """엄격 모드: 완전 정렬"""
        analyzer = MultiTimeframeAnalyzer(strict_mode=True)

        higher_tf_data = {
            "ma_7": 52000.0,
            "ma_25": 51000.0,
            "ma_99": 50000.0,  # MA7 > MA25 > MA99
            "current_price": 53000.0,
        }

        result = analyzer.filter_signal("LONG", higher_tf_data)
        assert result == "LONG"
