"""Phase 2: 독립 봇 실행기 테스트."""
from unittest.mock import patch

import pytest

from src.bot_runner import find_bot_config


class TestFindBotConfig:
    """봇 설정 로드 테스트."""

    def test_find_existing_bot(self):
        """YAML에서 존재하는 봇 설정 로드."""
        from src.bot_config import BotConfig

        mock_configs = [
            BotConfig(bot_name="btc-conservative", symbol="BTCUSDT", risk_level="low"),
            BotConfig(bot_name="eth-balanced", symbol="ETHUSDT", risk_level="medium"),
        ]

        with patch(
            "src.bot_runner.load_bots_from_yaml_optional",
            return_value=(mock_configs, None),
        ):
            config = find_bot_config("btc-conservative")
            assert config.bot_name == "btc-conservative"
            assert config.symbol == "BTCUSDT"

    def test_find_nonexistent_bot(self):
        """존재하지 않는 봇 설정 시 ValueError."""
        from src.bot_config import BotConfig

        mock_configs = [
            BotConfig(bot_name="btc-conservative", symbol="BTCUSDT", risk_level="low"),
        ]

        with patch(
            "src.bot_runner.load_bots_from_yaml_optional",
            return_value=(mock_configs, None),
        ):
            with pytest.raises(ValueError, match="봇 'unknown-bot' 설정을 찾을 수 없습니다"):
                find_bot_config("unknown-bot")

    def test_find_bot_no_yaml(self):
        """YAML 파일 없을 때 ValueError."""
        with patch(
            "src.bot_runner.load_bots_from_yaml_optional",
            return_value=([], None),
        ):
            with pytest.raises(ValueError, match="설정을 찾을 수 없습니다"):
                find_bot_config("any-bot")

    def test_find_bot_error_message_includes_available(self):
        """에러 메시지에 사용 가능한 봇 목록 포함."""
        from src.bot_config import BotConfig

        mock_configs = [
            BotConfig(bot_name="bot-a", symbol="BTCUSDT", risk_level="low"),
            BotConfig(bot_name="bot-b", symbol="ETHUSDT", risk_level="medium"),
        ]

        with patch(
            "src.bot_runner.load_bots_from_yaml_optional",
            return_value=(mock_configs, None),
        ):
            with pytest.raises(ValueError, match=r"bot-a.*bot-b"):
                find_bot_config("nonexistent")
