"""
Tests for RuleBasedSignalGenerator
"""
import pytest
from src.ai.rule_based import RuleBasedSignalGenerator


class TestRuleBasedSignalGeneratorInit:
    """RuleBasedSignalGenerator 초기화 테스트"""

    def test_init_default_params(self):
        """기본 파라미터로 초기화"""
        generator = RuleBasedSignalGenerator()

        assert generator.rsi_oversold == 35.0
        assert generator.rsi_overbought == 65.0
        assert generator.volume_threshold == 1.2

    def test_init_custom_params(self):
        """커스텀 파라미터로 초기화"""
        generator = RuleBasedSignalGenerator(
            rsi_oversold=30.0,
            rsi_overbought=70.0,
            volume_threshold=1.5
        )

        assert generator.rsi_oversold == 30.0
        assert generator.rsi_overbought == 70.0
        assert generator.volume_threshold == 1.5


class TestGetSignalLong:
    """LONG 신호 테스트"""

    @pytest.fixture
    def generator(self):
        return RuleBasedSignalGenerator()

    def test_long_signal_all_conditions_met(self, generator):
        """모든 LONG 조건 충족"""
        market_data = {
            "current_price": 105000.0,
            "rsi": 30.0,           # < 35 (oversold)
            "ma_7": 104000.0,      # price > ma_7 (uptrend)
            "volume_ratio": 1.5,   # > 1.2 (high volume)
        }

        signal = generator.get_signal(market_data)

        assert signal == "LONG"

    def test_long_signal_rsi_exactly_at_threshold(self, generator):
        """RSI가 정확히 임계값일 때"""
        market_data = {
            "current_price": 105000.0,
            "rsi": 35.0,           # == 35 (not oversold)
            "ma_7": 104000.0,
            "volume_ratio": 1.5,
        }

        signal = generator.get_signal(market_data)

        # RSI가 35.0이면 oversold 조건 불충족
        assert signal == "WAIT"

    def test_long_signal_price_below_ma(self, generator):
        """가격이 MA 아래일 때 (LONG 불충족)"""
        market_data = {
            "current_price": 103000.0,  # < ma_7 (downtrend)
            "rsi": 30.0,
            "ma_7": 104000.0,
            "volume_ratio": 1.5,
        }

        signal = generator.get_signal(market_data)

        assert signal == "WAIT"

    def test_long_signal_low_volume(self, generator):
        """거래량이 낮을 때 (LONG 불충족)"""
        market_data = {
            "current_price": 105000.0,
            "rsi": 30.0,
            "ma_7": 104000.0,
            "volume_ratio": 1.0,   # < 1.2 (low volume)
        }

        signal = generator.get_signal(market_data)

        assert signal == "WAIT"


class TestGetSignalShort:
    """SHORT 신호 테스트"""

    @pytest.fixture
    def generator(self):
        return RuleBasedSignalGenerator()

    def test_short_signal_all_conditions_met(self, generator):
        """모든 SHORT 조건 충족"""
        market_data = {
            "current_price": 103000.0,
            "rsi": 70.0,           # > 65 (overbought)
            "ma_7": 104000.0,      # price < ma_7 (downtrend)
            "volume_ratio": 1.5,   # > 1.2 (high volume)
        }

        signal = generator.get_signal(market_data)

        assert signal == "SHORT"

    def test_short_signal_rsi_exactly_at_threshold(self, generator):
        """RSI가 정확히 임계값일 때"""
        market_data = {
            "current_price": 103000.0,
            "rsi": 65.0,           # == 65 (not overbought)
            "ma_7": 104000.0,
            "volume_ratio": 1.5,
        }

        signal = generator.get_signal(market_data)

        # RSI가 65.0이면 overbought 조건 불충족
        assert signal == "WAIT"

    def test_short_signal_price_above_ma(self, generator):
        """가격이 MA 위일 때 (SHORT 불충족)"""
        market_data = {
            "current_price": 105000.0,  # > ma_7 (uptrend)
            "rsi": 70.0,
            "ma_7": 104000.0,
            "volume_ratio": 1.5,
        }

        signal = generator.get_signal(market_data)

        assert signal == "WAIT"

    def test_short_signal_low_volume(self, generator):
        """거래량이 낮을 때 (SHORT 불충족)"""
        market_data = {
            "current_price": 103000.0,
            "rsi": 70.0,
            "ma_7": 104000.0,
            "volume_ratio": 1.0,   # < 1.2 (low volume)
        }

        signal = generator.get_signal(market_data)

        assert signal == "WAIT"


class TestGetSignalWait:
    """WAIT 신호 테스트"""

    @pytest.fixture
    def generator(self):
        return RuleBasedSignalGenerator()

    def test_wait_signal_neutral_rsi(self, generator):
        """중립적인 RSI"""
        market_data = {
            "current_price": 105000.0,
            "rsi": 50.0,           # 35-65 사이 (neutral)
            "ma_7": 104000.0,
            "volume_ratio": 1.5,
        }

        signal = generator.get_signal(market_data)

        assert signal == "WAIT"

    def test_wait_signal_conflicting_conditions(self, generator):
        """상충하는 조건 (oversold + downtrend)"""
        market_data = {
            "current_price": 103000.0,  # < ma_7
            "rsi": 30.0,                # oversold (LONG 조건)
            "ma_7": 104000.0,
            "volume_ratio": 1.5,
        }

        signal = generator.get_signal(market_data)

        # RSI는 LONG이지만 가격이 MA 아래라 WAIT
        assert signal == "WAIT"


class TestGetSignalDefaultValues:
    """기본값 테스트"""

    @pytest.fixture
    def generator(self):
        return RuleBasedSignalGenerator()

    def test_missing_current_price(self, generator):
        """current_price 누락"""
        market_data = {
            "rsi": 30.0,
            "ma_7": 104000.0,
            "volume_ratio": 1.5,
        }

        signal = generator.get_signal(market_data)

        # current_price=0 이므로 조건 불충족
        assert signal == "WAIT"

    def test_missing_rsi(self, generator):
        """RSI 누락"""
        market_data = {
            "current_price": 105000.0,
            "ma_7": 104000.0,
            "volume_ratio": 1.5,
        }

        signal = generator.get_signal(market_data)

        # rsi=50 (기본값)이므로 neutral
        assert signal == "WAIT"

    def test_missing_ma_7(self, generator):
        """MA_7 누락"""
        market_data = {
            "current_price": 105000.0,
            "rsi": 30.0,
            "volume_ratio": 1.5,
        }

        signal = generator.get_signal(market_data)

        # ma_7가 current_price로 기본값 설정
        # price (105000) == ma_7 (105000)이면 조건 불충족
        assert signal == "WAIT"

    def test_missing_volume_ratio(self, generator):
        """volume_ratio 누락"""
        market_data = {
            "current_price": 105000.0,
            "rsi": 30.0,
            "ma_7": 104000.0,
        }

        signal = generator.get_signal(market_data)

        # volume_ratio=1.0 (기본값) < 1.2
        assert signal == "WAIT"


class TestGetSignalEdgeCases:
    """경계값 테스트"""

    @pytest.fixture
    def generator(self):
        return RuleBasedSignalGenerator()

    def test_extreme_rsi_low(self, generator):
        """극도로 낮은 RSI"""
        market_data = {
            "current_price": 105000.0,
            "rsi": 10.0,
            "ma_7": 104000.0,
            "volume_ratio": 2.0,
        }

        signal = generator.get_signal(market_data)

        assert signal == "LONG"

    def test_extreme_rsi_high(self, generator):
        """극도로 높은 RSI"""
        market_data = {
            "current_price": 103000.0,
            "rsi": 90.0,
            "ma_7": 104000.0,
            "volume_ratio": 2.0,
        }

        signal = generator.get_signal(market_data)

        assert signal == "SHORT"

    def test_zero_volume_ratio(self, generator):
        """거래량 비율 0"""
        market_data = {
            "current_price": 105000.0,
            "rsi": 30.0,
            "ma_7": 104000.0,
            "volume_ratio": 0.0,
        }

        signal = generator.get_signal(market_data)

        assert signal == "WAIT"


class TestGetSignalCustomThresholds:
    """커스텀 임계값 테스트"""

    def test_custom_rsi_thresholds(self):
        """커스텀 RSI 임계값"""
        generator = RuleBasedSignalGenerator(
            rsi_oversold=25.0,
            rsi_overbought=75.0
        )

        # RSI 30은 기본 임계값에서는 oversold지만
        # 커스텀 임계값(25)에서는 아님
        market_data = {
            "current_price": 105000.0,
            "rsi": 30.0,
            "ma_7": 104000.0,
            "volume_ratio": 1.5,
        }

        signal = generator.get_signal(market_data)

        assert signal == "WAIT"

    def test_custom_volume_threshold(self):
        """커스텀 거래량 임계값"""
        generator = RuleBasedSignalGenerator(volume_threshold=2.0)

        market_data = {
            "current_price": 105000.0,
            "rsi": 30.0,
            "ma_7": 104000.0,
            "volume_ratio": 1.5,  # < 2.0
        }

        signal = generator.get_signal(market_data)

        assert signal == "WAIT"


class TestGetSignalErrorHandling:
    """에러 처리 테스트"""

    @pytest.fixture
    def generator(self):
        return RuleBasedSignalGenerator()

    def test_empty_market_data(self, generator):
        """빈 시장 데이터"""
        signal = generator.get_signal({})

        assert signal == "WAIT"

    def test_none_values(self, generator):
        """None 값"""
        market_data = {
            "current_price": None,
            "rsi": None,
            "ma_7": None,
            "volume_ratio": None,
        }

        # None은 get()의 기본값으로 대체됨
        signal = generator.get_signal(market_data)

        assert signal == "WAIT"

    def test_invalid_types(self, generator):
        """잘못된 타입"""
        market_data = {
            "current_price": "invalid",
            "rsi": "invalid",
            "ma_7": "invalid",
            "volume_ratio": "invalid",
        }

        # 예외 발생 시 WAIT 반환
        signal = generator.get_signal(market_data)

        assert signal == "WAIT"
