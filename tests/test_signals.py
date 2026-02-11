"""
Tests for trading signal parsing and validation
"""

from src.ai.signals import (
    get_signal_color,
    get_signal_emoji,
    parse_signal,
    should_enter_trade,
    validate_signal,
)


class TestParseSignal:
    """신호 파싱 테스트"""

    def test_parse_simple_signal(self):
        """단순한 신호 파싱"""
        assert parse_signal("LONG") == "LONG"
        assert parse_signal("SHORT") == "SHORT"
        assert parse_signal("WAIT") == "WAIT"

    def test_parse_lowercase(self):
        """소문자를 대문자로 변환"""
        assert parse_signal("long") == "LONG"
        assert parse_signal("short") == "SHORT"
        assert parse_signal("wait") == "WAIT"

    def test_parse_with_whitespace(self):
        """공백 제거"""
        assert parse_signal("  LONG  ") == "LONG"
        assert parse_signal("\nSHORT\n") == "SHORT"

    def test_parse_with_prefix(self):
        """프리픽스 제거"""
        assert parse_signal("SIGNAL: LONG") == "LONG"
        assert parse_signal("OUTPUT: SHORT") == "SHORT"
        assert parse_signal("RESULT: WAIT") == "WAIT"

    def test_parse_multiple_words(self):
        """여러 단어 중 첫 단어만 추출"""
        assert parse_signal("LONG position recommended") == "LONG"
        assert parse_signal("SHORT trade signal") == "SHORT"


class TestValidateSignal:
    """신호 검증 테스트"""

    def test_validate_valid_signals(self):
        """유효한 신호 검증"""
        assert validate_signal("LONG") is True
        assert validate_signal("SHORT") is True
        assert validate_signal("WAIT") is True

    def test_validate_invalid_signals(self):
        """유효하지 않은 신호 검증"""
        assert validate_signal("BUY") is False
        assert validate_signal("SELL") is False
        assert validate_signal("HOLD") is False
        assert validate_signal("INVALID") is False
        assert validate_signal("") is False


class TestGetSignalEmoji:
    """신호 이모지 테스트"""

    def test_get_emoji_for_signals(self):
        """각 신호에 대한 이모지 반환"""
        assert get_signal_emoji("LONG") == "🟢"
        assert get_signal_emoji("SHORT") == "🔴"
        assert get_signal_emoji("WAIT") == "⏸️"

    def test_get_emoji_for_invalid(self):
        """유효하지 않은 신호는 물음표"""
        assert get_signal_emoji("INVALID") == "❓"


class TestGetSignalColor:
    """신호 색상 코드 테스트"""

    def test_get_color_for_signals(self):
        """각 신호에 대한 Discord 색상 코드"""
        assert get_signal_color("LONG") == 0x00FF00  # 녹색
        assert get_signal_color("SHORT") == 0xFF0000  # 빨간색
        assert get_signal_color("WAIT") == 0xFFFF00  # 노란색

    def test_get_color_for_invalid(self):
        """유효하지 않은 신호는 회색"""
        assert get_signal_color("INVALID") == 0x808080


class TestShouldEnterTrade:
    """거래 진입 여부 판단 테스트"""

    def test_should_enter_with_no_position(self):
        """포지션 없을 때 LONG/SHORT 신호면 진입"""
        assert should_enter_trade("LONG", has_position=False) is True
        assert should_enter_trade("SHORT", has_position=False) is True

    def test_should_not_enter_with_wait(self):
        """WAIT 신호면 진입하지 않음"""
        assert should_enter_trade("WAIT", has_position=False) is False

    def test_should_not_enter_with_existing_position(self):
        """이미 포지션이 있으면 진입하지 않음"""
        assert should_enter_trade("LONG", has_position=True) is False
        assert should_enter_trade("SHORT", has_position=True) is False
        assert should_enter_trade("WAIT", has_position=True) is False

    def test_signal_and_position_combinations(self):
        """다양한 신호와 포지션 조합 테스트"""
        # 포지션 없음 + 진입 신호 = True
        assert should_enter_trade("LONG", False) is True
        assert should_enter_trade("SHORT", False) is True

        # 포지션 없음 + WAIT = False
        assert should_enter_trade("WAIT", False) is False

        # 포지션 있음 + 모든 신호 = False
        assert should_enter_trade("LONG", True) is False
        assert should_enter_trade("SHORT", True) is False
        assert should_enter_trade("WAIT", True) is False
