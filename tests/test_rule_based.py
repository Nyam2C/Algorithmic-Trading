"""
Tests for RuleBasedSignalGenerator
"""
import pytest

from src.ai.rule_based import RuleBasedSignalGenerator


class TestRuleBasedSignalGeneratorInit:
    """RuleBasedSignalGenerator 초기화 테스트"""

    def test_init_default_params(self):
        """기본 파라미터로 초기화 (테스트용 완화된 조건)"""
        generator = RuleBasedSignalGenerator()

        assert generator.rsi_oversold == 30.0
        assert generator.rsi_overbought == 70.0
        assert generator.volume_threshold == 0.5
        assert generator.strategy == "trend_pullback"

    def test_init_custom_params(self):
        """커스텀 파라미터로 초기화"""
        generator = RuleBasedSignalGenerator(
            rsi_oversold=30.0,
            rsi_overbought=70.0,
            volume_threshold=1.5,
            strategy="classic",
        )

        assert generator.rsi_oversold == 30.0
        assert generator.rsi_overbought == 70.0
        assert generator.volume_threshold == 1.5
        assert generator.strategy == "classic"


class TestTrendPullbackSignal:
    """trend_pullback 전략 테스트"""

    @pytest.fixture
    def generator(self):
        return RuleBasedSignalGenerator(strategy="trend_pullback")

    def test_long_signal_uptrend_pullback(self, generator):
        """상승추세에서 풀백 시 LONG"""
        market_data = {
            "rsi": 25.0,             # < 30 (oversold pullback)
            "ma_7": 105000.0,        # > ma_25 (uptrend)
            "ma_25": 104000.0,
            "volume_ratio": 1.5,     # > 0.5
            "current_price": 105000.0,  # > prev_close (bullish candle)
            "prev_close": 104500.0,
        }
        assert generator.get_signal(market_data) == "LONG"

    def test_long_signal_boundary_rsi(self, generator):
        """RSI가 정확히 oversold 경계에서는 WAIT"""
        market_data = {
            "rsi": 30.0,             # == 30, not < 30
            "ma_7": 105000.0,
            "ma_25": 104000.0,
            "volume_ratio": 1.5,
        }
        assert generator.get_signal(market_data) == "WAIT"

    def test_long_signal_no_uptrend(self, generator):
        """MA7 < MA25이면 LONG 불가"""
        market_data = {
            "rsi": 25.0,
            "ma_7": 103000.0,        # < ma_25 (downtrend)
            "ma_25": 104000.0,
            "volume_ratio": 1.5,
        }
        # MA7 < MA25이므로 uptrend 아님 -> WAIT (SHORT 조건은 rsi > overbought 필요)
        assert generator.get_signal(market_data) == "WAIT"

    def test_long_signal_low_volume(self, generator):
        """거래량 부족 시 WAIT"""
        market_data = {
            "rsi": 25.0,
            "ma_7": 105000.0,
            "ma_25": 104000.0,
            "volume_ratio": 0.3,     # < 0.5
        }
        assert generator.get_signal(market_data) == "WAIT"

    def test_short_signal_downtrend_overbought(self, generator):
        """하락추세에서 과매수 시 SHORT"""
        market_data = {
            "rsi": 75.0,             # > 70 (overbought)
            "ma_7": 103000.0,        # < ma_25 (downtrend)
            "ma_25": 104000.0,
            "volume_ratio": 1.5,
            "current_price": 103000.0,  # < prev_close (bearish candle)
            "prev_close": 103500.0,
        }
        assert generator.get_signal(market_data) == "SHORT"

    def test_short_signal_boundary_rsi(self, generator):
        """RSI가 정확히 overbought 경계에서는 WAIT"""
        market_data = {
            "rsi": 70.0,             # == 70, not > 70
            "ma_7": 103000.0,
            "ma_25": 104000.0,
            "volume_ratio": 1.5,
        }
        assert generator.get_signal(market_data) == "WAIT"

    def test_short_signal_no_downtrend(self, generator):
        """MA7 > MA25이면 SHORT 불가"""
        market_data = {
            "rsi": 75.0,
            "ma_7": 105000.0,        # > ma_25 (uptrend)
            "ma_25": 104000.0,
            "volume_ratio": 1.5,
        }
        assert generator.get_signal(market_data) == "WAIT"

    def test_short_signal_low_volume(self, generator):
        """SHORT 조건에서 거래량 부족 시 WAIT"""
        market_data = {
            "rsi": 75.0,
            "ma_7": 103000.0,
            "ma_25": 104000.0,
            "volume_ratio": 0.3,
        }
        assert generator.get_signal(market_data) == "WAIT"

    def test_wait_neutral_rsi(self, generator):
        """중립 RSI에서 WAIT"""
        market_data = {
            "rsi": 50.0,
            "ma_7": 105000.0,
            "ma_25": 104000.0,
            "volume_ratio": 1.5,
        }
        assert generator.get_signal(market_data) == "WAIT"

    def test_wait_ma25_zero(self, generator):
        """MA25가 0이면 추세 판단 불가 -> WAIT"""
        market_data = {
            "rsi": 25.0,
            "ma_7": 105000.0,
            "ma_25": 0,
            "volume_ratio": 1.5,
        }
        assert generator.get_signal(market_data) == "WAIT"

    def test_missing_ma_25_defaults_zero(self, generator):
        """MA25가 없으면 기본값 0 -> WAIT"""
        market_data = {
            "rsi": 25.0,
            "ma_7": 105000.0,
            "volume_ratio": 1.5,
        }
        assert generator.get_signal(market_data) == "WAIT"

    def test_error_handling_returns_wait(self, generator):
        """예외 발생 시 WAIT"""
        market_data = {
            "rsi": "invalid",
            "ma_7": "invalid",
            "ma_25": "invalid",
            "volume_ratio": "invalid",
        }
        assert generator.get_signal(market_data) == "WAIT"



class TestTrendPullbackCandleConfirmation:
    """trend_pullback 전략 캔들 방향 확인 테스트"""

    @pytest.fixture
    def generator(self):
        return RuleBasedSignalGenerator(strategy="trend_pullback")

    def test_long_with_bullish_candle_confirmation(self, generator):
        """상승 추세 + 풀백 + 양봉 확인 -> LONG"""
        market_data = {
            "rsi": 25.0,
            "ma_7": 105000.0,
            "ma_25": 104000.0,
            "volume_ratio": 1.5,
            "current_price": 105000.0,
            "prev_close": 104500.0,  # current > prev = bullish
        }
        assert generator.get_signal(market_data) == "LONG"

    def test_long_rejected_without_bullish_candle(self, generator):
        """상승 추세 + 풀백이지만 음봉이면 WAIT"""
        market_data = {
            "rsi": 25.0,
            "ma_7": 105000.0,
            "ma_25": 104000.0,
            "volume_ratio": 1.5,
            "current_price": 104000.0,  # current < prev = bearish
            "prev_close": 104500.0,
        }
        assert generator.get_signal(market_data) == "WAIT"

    def test_short_with_bearish_candle_confirmation(self, generator):
        """하락 추세 + 과매수 + 음봉 확인 -> SHORT"""
        market_data = {
            "rsi": 75.0,
            "ma_7": 103000.0,
            "ma_25": 104000.0,
            "volume_ratio": 1.5,
            "current_price": 103000.0,
            "prev_close": 103500.0,  # current < prev = bearish
        }
        assert generator.get_signal(market_data) == "SHORT"

    def test_short_rejected_without_bearish_candle(self, generator):
        """하락 추세 + 과매수이지만 양봉이면 WAIT"""
        market_data = {
            "rsi": 75.0,
            "ma_7": 103000.0,
            "ma_25": 104000.0,
            "volume_ratio": 1.5,
            "current_price": 104000.0,  # current > prev = bullish
            "prev_close": 103500.0,
        }
        assert generator.get_signal(market_data) == "WAIT"

    def test_backward_compat_no_prev_close(self, generator):
        """prev_close 없으면 current_price를 기본값으로 사용 (동일 -> WAIT)"""
        market_data = {
            "rsi": 25.0,
            "ma_7": 105000.0,
            "ma_25": 104000.0,
            "volume_ratio": 1.5,
            "current_price": 105000.0,
            # prev_close 없음 -> defaults to current_price -> not > -> WAIT
        }
        # current_close == prev_close -> not strictly greater -> WAIT
        assert generator.get_signal(market_data) == "WAIT"


class TestClassicSignalCompat:
    """classic 전략 호환성 테스트 (기존 RSI + price vs MA7 로직)"""

    @pytest.fixture
    def generator(self):
        return RuleBasedSignalGenerator(strategy="classic")

    def test_long_signal_all_conditions_met(self, generator):
        """모든 LONG 조건 충족"""
        market_data = {
            "current_price": 105000.0,
            "rsi": 25.0,           # < 30 (oversold)
            "ma_7": 104000.0,      # price > ma_7 (uptrend)
            "volume_ratio": 1.5,   # > 0.5
        }
        assert generator.get_signal(market_data) == "LONG"

    def test_long_signal_rsi_exactly_at_threshold(self, generator):
        """RSI가 정확히 임계값일 때"""
        market_data = {
            "current_price": 105000.0,
            "rsi": 30.0,           # == 30 (not oversold)
            "ma_7": 104000.0,
            "volume_ratio": 1.5,
        }
        assert generator.get_signal(market_data) == "WAIT"

    def test_long_signal_price_below_ma(self, generator):
        """가격이 MA 아래일 때 (LONG 불충족)"""
        market_data = {
            "current_price": 103000.0,  # < ma_7
            "rsi": 25.0,
            "ma_7": 104000.0,
            "volume_ratio": 1.5,
        }
        assert generator.get_signal(market_data) == "WAIT"

    def test_long_signal_low_volume(self, generator):
        """거래량이 낮을 때 (LONG 불충족)"""
        market_data = {
            "current_price": 105000.0,
            "rsi": 25.0,
            "ma_7": 104000.0,
            "volume_ratio": 0.3,
        }
        assert generator.get_signal(market_data) == "WAIT"

    def test_short_signal_all_conditions_met(self, generator):
        """모든 SHORT 조건 충족"""
        market_data = {
            "current_price": 103000.0,
            "rsi": 75.0,           # > 70 (overbought)
            "ma_7": 104000.0,      # price < ma_7
            "volume_ratio": 1.5,
        }
        assert generator.get_signal(market_data) == "SHORT"

    def test_short_signal_rsi_exactly_at_threshold(self, generator):
        """RSI가 정확히 임계값일 때"""
        market_data = {
            "current_price": 103000.0,
            "rsi": 70.0,           # == 70 (not overbought)
            "ma_7": 104000.0,
            "volume_ratio": 1.5,
        }
        assert generator.get_signal(market_data) == "WAIT"

    def test_short_signal_price_above_ma(self, generator):
        """가격이 MA 위일 때 (SHORT 불충족)"""
        market_data = {
            "current_price": 105000.0,
            "rsi": 75.0,
            "ma_7": 104000.0,
            "volume_ratio": 1.5,
        }
        assert generator.get_signal(market_data) == "WAIT"

    def test_short_signal_low_volume(self, generator):
        """거래량이 낮을 때 (SHORT 불충족)"""
        market_data = {
            "current_price": 103000.0,
            "rsi": 75.0,
            "ma_7": 104000.0,
            "volume_ratio": 0.3,
        }
        assert generator.get_signal(market_data) == "WAIT"

    def test_wait_signal_neutral_rsi(self, generator):
        """중립적인 RSI"""
        market_data = {
            "current_price": 105000.0,
            "rsi": 50.0,
            "ma_7": 104000.0,
            "volume_ratio": 1.5,
        }
        assert generator.get_signal(market_data) == "WAIT"

    def test_wait_signal_conflicting_conditions(self, generator):
        """상충하는 조건 (oversold + downtrend)"""
        market_data = {
            "current_price": 103000.0,  # < ma_7
            "rsi": 25.0,
            "ma_7": 104000.0,
            "volume_ratio": 1.5,
        }
        assert generator.get_signal(market_data) == "WAIT"


class TestGetSignalDefaultValues:
    """classic 전략 기본값 테스트"""

    @pytest.fixture
    def generator(self):
        return RuleBasedSignalGenerator(strategy="classic")

    def test_missing_current_price(self, generator):
        """current_price 누락"""
        market_data = {
            "rsi": 25.0,
            "ma_7": 104000.0,
            "volume_ratio": 1.5,
        }
        assert generator.get_signal(market_data) == "WAIT"

    def test_missing_rsi(self, generator):
        """RSI 누락"""
        market_data = {
            "current_price": 105000.0,
            "ma_7": 104000.0,
            "volume_ratio": 1.5,
        }
        assert generator.get_signal(market_data) == "WAIT"

    def test_missing_ma_7(self, generator):
        """MA_7 누락"""
        market_data = {
            "current_price": 105000.0,
            "rsi": 25.0,
            "volume_ratio": 1.5,
        }
        assert generator.get_signal(market_data) == "WAIT"

    def test_missing_volume_ratio(self, generator):
        """volume_ratio 누락"""
        market_data = {
            "current_price": 105000.0,
            "rsi": 25.0,
            "ma_7": 104000.0,
        }
        # volume_ratio=1.0 (기본값) > 0.5이므로 LONG 조건 충족
        assert generator.get_signal(market_data) == "LONG"


class TestGetSignalEdgeCases:
    """경계값 테스트 (classic 전략)"""

    @pytest.fixture
    def generator(self):
        return RuleBasedSignalGenerator(strategy="classic")

    def test_extreme_rsi_low(self, generator):
        """극도로 낮은 RSI"""
        market_data = {
            "current_price": 105000.0,
            "rsi": 10.0,
            "ma_7": 104000.0,
            "volume_ratio": 2.0,
        }
        assert generator.get_signal(market_data) == "LONG"

    def test_extreme_rsi_high(self, generator):
        """극도로 높은 RSI"""
        market_data = {
            "current_price": 103000.0,
            "rsi": 90.0,
            "ma_7": 104000.0,
            "volume_ratio": 2.0,
        }
        assert generator.get_signal(market_data) == "SHORT"

    def test_zero_volume_ratio(self, generator):
        """거래량 비율 0"""
        market_data = {
            "current_price": 105000.0,
            "rsi": 25.0,
            "ma_7": 104000.0,
            "volume_ratio": 0.0,
        }
        assert generator.get_signal(market_data) == "WAIT"


class TestGetSignalCustomThresholds:
    """커스텀 임계값 테스트"""

    def test_custom_rsi_thresholds(self):
        """커스텀 RSI 임계값"""
        generator = RuleBasedSignalGenerator(
            rsi_oversold=25.0,
            rsi_overbought=75.0,
            strategy="classic",
        )

        market_data = {
            "current_price": 105000.0,
            "rsi": 30.0,
            "ma_7": 104000.0,
            "volume_ratio": 1.5,
        }
        assert generator.get_signal(market_data) == "WAIT"

    def test_custom_volume_threshold(self):
        """커스텀 거래량 임계값"""
        generator = RuleBasedSignalGenerator(
            volume_threshold=2.0,
            strategy="classic",
        )

        market_data = {
            "current_price": 105000.0,
            "rsi": 25.0,
            "ma_7": 104000.0,
            "volume_ratio": 1.5,
        }
        assert generator.get_signal(market_data) == "WAIT"


class TestGetSignalErrorHandling:
    """에러 처리 테스트"""

    @pytest.fixture
    def generator(self):
        return RuleBasedSignalGenerator(strategy="classic")

    def test_empty_market_data(self, generator):
        """빈 시장 데이터"""
        assert generator.get_signal({}) == "WAIT"

    def test_none_values(self, generator):
        """None 값"""
        market_data = {
            "current_price": None,
            "rsi": None,
            "ma_7": None,
            "volume_ratio": None,
        }
        assert generator.get_signal(market_data) == "WAIT"

    def test_invalid_types(self, generator):
        """잘못된 타입"""
        market_data = {
            "current_price": "invalid",
            "rsi": "invalid",
            "ma_7": "invalid",
            "volume_ratio": "invalid",
        }
        assert generator.get_signal(market_data) == "WAIT"


class TestTrendFollowingSignal:
    """trend_following 전략 테스트"""

    @pytest.fixture
    def generator(self):
        return RuleBasedSignalGenerator(strategy="trend_following")

    def test_long_signal_uptrend(self, generator):
        """MA7 > MA25 → LONG"""
        market_data = {
            "ma_7": 105000.0,
            "ma_25": 104000.0,
        }
        assert generator.get_signal(market_data) == "LONG"

    def test_short_signal_downtrend(self, generator):
        """MA7 < MA25 → SHORT"""
        market_data = {
            "ma_7": 103000.0,
            "ma_25": 104000.0,
        }
        assert generator.get_signal(market_data) == "SHORT"

    def test_wait_signal_converged_mas(self, generator):
        """MA 수렴 시 WAIT (|MA7 - MA25| / MA25 < 0.05%)"""
        market_data = {
            "ma_7": 104000.0,
            "ma_25": 104000.0,  # 동일 → divergence = 0
        }
        assert generator.get_signal(market_data) == "WAIT"

    def test_wait_signal_near_convergence(self, generator):
        """MA 거의 수렴 (0.04% divergence) → WAIT"""
        # 0.04% of 104000 = 41.6 → MA7 = 104041.6
        market_data = {
            "ma_7": 104041.0,
            "ma_25": 104000.0,
        }
        assert generator.get_signal(market_data) == "WAIT"

    def test_long_signal_just_above_convergence(self, generator):
        """MA divergence가 0.05% 이상이면 LONG"""
        # 0.06% of 104000 = 62.4 → MA7 = 104062.4
        market_data = {
            "ma_7": 104063.0,
            "ma_25": 104000.0,
        }
        assert generator.get_signal(market_data) == "LONG"

    def test_short_signal_just_above_convergence(self, generator):
        """MA divergence가 0.05% 이상이면 SHORT"""
        market_data = {
            "ma_7": 103937.0,  # 104000 - 63
            "ma_25": 104000.0,
        }
        assert generator.get_signal(market_data) == "SHORT"

    def test_wait_ma25_zero(self, generator):
        """MA25가 0이면 WAIT"""
        market_data = {
            "ma_7": 105000.0,
            "ma_25": 0,
        }
        assert generator.get_signal(market_data) == "WAIT"

    def test_wait_ma25_missing(self, generator):
        """MA25 누락 → 기본값 0 → WAIT"""
        market_data = {
            "ma_7": 105000.0,
        }
        assert generator.get_signal(market_data) == "WAIT"

    def test_rsi_not_required(self, generator):
        """RSI 없이도 시그널 생성 가능"""
        market_data = {
            "ma_7": 105000.0,
            "ma_25": 104000.0,
        }
        # RSI가 없어도 MA만으로 판단
        assert generator.get_signal(market_data) == "LONG"

    def test_volume_not_required(self, generator):
        """Volume 없이도 시그널 생성 가능"""
        market_data = {
            "ma_7": 103000.0,
            "ma_25": 104000.0,
            "volume_ratio": 0.0,  # 볼륨 0이어도 무관
        }
        assert generator.get_signal(market_data) == "SHORT"

    def test_error_handling(self, generator):
        """잘못된 데이터 → WAIT"""
        market_data = {
            "ma_7": "invalid",
            "ma_25": "invalid",
        }
        assert generator.get_signal(market_data) == "WAIT"

    def test_empty_data(self, generator):
        """빈 데이터 → WAIT"""
        assert generator.get_signal({}) == "WAIT"

    def test_diagnostic(self, generator):
        """trend_following 진단 정보"""
        market_data = {
            "rsi": 55.0,
            "ma_7": 105000.0,
            "ma_25": 104000.0,
            "volume_ratio": 1.0,
            "current_price": 105000.0,
        }
        diag = generator.get_signal_diagnostic(market_data)
        assert diag["strategy"] == "trend_following"
        assert diag["signal"] == "LONG"
        assert "trend" in diag
        assert diag["trend"]["is_uptrend"] is True
        assert "ma_divergence" in diag["trend"]


class TestSignalDiagnostic:
    """get_signal_diagnostic 테스트"""

    def test_trend_pullback_diagnostic(self):
        """trend_pullback 전략 진단 정보"""
        generator = RuleBasedSignalGenerator(strategy="trend_pullback")
        market_data = {
            "rsi": 25.0,
            "ma_7": 105000.0,
            "ma_25": 104000.0,
            "volume_ratio": 1.5,
            "current_price": 105000.0,
            "prev_close": 104500.0,
        }
        diag = generator.get_signal_diagnostic(market_data)

        assert diag["strategy"] == "trend_pullback"
        assert diag["signal"] == "LONG"
        assert diag["rsi"]["value"] == 25.0
        assert diag["rsi"]["is_oversold"] is True
        assert diag["rsi"]["is_overbought"] is False
        assert diag["volume"]["passes"] is True
        assert "trend" in diag
        assert diag["trend"]["is_uptrend"] is True
        assert diag["trend"]["is_downtrend"] is False

    def test_classic_diagnostic(self):
        """classic 전략 진단 정보"""
        generator = RuleBasedSignalGenerator(strategy="classic")
        market_data = {
            "current_price": 105000.0,
            "rsi": 25.0,
            "ma_7": 104000.0,
            "volume_ratio": 1.5,
        }
        diag = generator.get_signal_diagnostic(market_data)

        assert diag["strategy"] == "classic"
        assert diag["signal"] == "LONG"
        assert "price" in diag
        assert diag["price"]["above_ma7"] is True

    def test_diagnostic_wait_signal(self):
        """WAIT 시그널 진단"""
        generator = RuleBasedSignalGenerator(strategy="trend_pullback")
        market_data = {
            "rsi": 50.0,
            "ma_7": 105000.0,
            "ma_25": 104000.0,
            "volume_ratio": 1.5,
        }
        diag = generator.get_signal_diagnostic(market_data)

        assert diag["signal"] == "WAIT"
        assert diag["rsi"]["is_oversold"] is False
        assert diag["rsi"]["is_overbought"] is False

    def test_diagnostic_contains_thresholds(self):
        """진단 정보에 임계값 포함"""
        generator = RuleBasedSignalGenerator(
            rsi_oversold=30.0,
            rsi_overbought=70.0,
            volume_threshold=1.2,
            strategy="trend_pullback",
        )
        market_data = {"rsi": 50.0, "ma_7": 100.0, "ma_25": 100.0, "volume_ratio": 1.0}
        diag = generator.get_signal_diagnostic(market_data)

        assert diag["rsi"]["oversold_threshold"] == 30.0
        assert diag["rsi"]["overbought_threshold"] == 70.0
        assert diag["volume"]["threshold"] == 1.2
