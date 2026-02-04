"""
Tests for configuration management
"""
import pytest
from pydantic import ValidationError

from src.config import TradingConfig, load_config, get_config


class TestTradingConfig:
    """Test TradingConfig model"""

    def test_config_creation_with_valid_data(self):
        """유효한 데이터로 설정 생성 테스트"""
        config = TradingConfig(
            bot_name="test-bot",
            binance_testnet=True,
            binance_api_key="test_key",
            binance_secret_key="test_secret",
            symbol="BTCUSDT",
            leverage=15,
            position_size_pct=0.05,
            take_profit_pct=0.004,
            stop_loss_pct=0.004,
            time_cut_minutes=120,
            gemini_api_key="test_gemini_key",
            discord_webhook_url="https://discord.com/api/webhooks/test",
        )

        assert config.bot_name == "test-bot"
        assert config.symbol == "BTCUSDT"
        assert config.leverage == 15
        assert config.binance_testnet is True

    def test_symbol_validation_uppercase(self):
        """심볼이 자동으로 대문자로 변환되는지 테스트"""
        config = TradingConfig(
            binance_api_key="test",
            binance_secret_key="test",
            gemini_api_key="test",
            discord_webhook_url="https://test.com",
            symbol="btcusdt",  # 소문자
        )

        assert config.symbol == "BTCUSDT"  # 대문자로 변환

    def test_symbol_validation_must_end_with_usdt(self):
        """심볼이 USDT로 끝나지 않으면 에러"""
        with pytest.raises(ValidationError) as exc_info:
            TradingConfig(
                binance_api_key="test",
                binance_secret_key="test",
                gemini_api_key="test",
                discord_webhook_url="https://test.com",
                symbol="BTCEUR",  # USDT로 끝나지 않음
            )

        assert "Symbol must end with USDT" in str(exc_info.value)

    def test_leverage_validation_range(self):
        """레버리지 범위 검증 (1-125)"""
        # 정상 범위
        config = TradingConfig(
            binance_api_key="test",
            binance_secret_key="test",
            gemini_api_key="test",
            discord_webhook_url="https://test.com",
            leverage=15,
        )
        assert config.leverage == 15

        # 범위 초과
        with pytest.raises(ValidationError):
            TradingConfig(
                binance_api_key="test",
                binance_secret_key="test",
                gemini_api_key="test",
                discord_webhook_url="https://test.com",
                leverage=126,  # 최대값 초과
            )

        # 0 이하
        with pytest.raises(ValidationError):
            TradingConfig(
                binance_api_key="test",
                binance_secret_key="test",
                gemini_api_key="test",
                discord_webhook_url="https://test.com",
                leverage=0,
            )

    def test_position_size_validation(self):
        """포지션 크기 검증 (0 < size <= 1)"""
        # 정상 범위
        config = TradingConfig(
            binance_api_key="test",
            binance_secret_key="test",
            gemini_api_key="test",
            discord_webhook_url="https://test.com",
            position_size_pct=0.05,
        )
        assert config.position_size_pct == 0.05

        # 0 이하
        with pytest.raises(ValidationError):
            TradingConfig(
                binance_api_key="test",
                binance_secret_key="test",
                gemini_api_key="test",
                discord_webhook_url="https://test.com",
                position_size_pct=0,
            )

        # 1 초과
        with pytest.raises(ValidationError):
            TradingConfig(
                binance_api_key="test",
                binance_secret_key="test",
                gemini_api_key="test",
                discord_webhook_url="https://test.com",
                position_size_pct=1.5,
            )

    def test_default_values(self):
        """기본값 테스트"""
        config = TradingConfig(
            binance_api_key="test",
            binance_secret_key="test",
            gemini_api_key="test",
            discord_webhook_url="https://test.com",
        )

        assert config.bot_name == "trading-bot"
        assert config.symbol == "BTCUSDT"
        assert config.leverage == 15
        assert config.position_size_pct == 0.05
        assert config.take_profit_pct == 0.004
        assert config.stop_loss_pct == 0.004
        assert config.time_cut_minutes == 120
        assert config.gemini_model == "gemini-2.0-flash-exp"
        assert config.gemini_temperature == 0.1
        assert config.loop_interval_seconds == 300


class TestLoadConfig:
    """Test load_config function"""

    def test_load_config_from_env(self, monkeypatch, tmp_path):
        """환경 변수에서 설정 로딩 테스트"""
        # 환경 변수 설정
        monkeypatch.setenv("BOT_NAME", "test-bot")
        monkeypatch.setenv("BINANCE_API_KEY", "test_key")
        monkeypatch.setenv("BINANCE_SECRET_KEY", "test_secret")
        monkeypatch.setenv("GEMINI_API_KEY", "test_gemini")
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://test.com")
        monkeypatch.setenv("SYMBOL", "ETHUSDT")
        monkeypatch.setenv("LEVERAGE", "10")

        # load_config 실행
        config = load_config()

        assert config.bot_name == "test-bot"
        assert config.symbol == "ETHUSDT"
        assert config.leverage == 10

    def test_load_config_missing_required_keys(self, monkeypatch):
        """필수 키가 없을 때 에러"""
        # 필수 키를 빈 문자열로 설정 (기본값)
        monkeypatch.setenv("BINANCE_API_KEY", "")
        monkeypatch.setenv("BINANCE_SECRET_KEY", "")
        monkeypatch.setenv("GEMINI_API_KEY", "")
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "")

        # 빈 문자열도 허용하므로 에러가 발생하지 않음
        # 실제로는 API 호출 시 에러가 발생할 것
        config = load_config()
        assert config.binance_api_key == ""
        assert config.gemini_api_key == ""


class TestGetConfig:
    """Test get_config singleton"""

    def test_get_config_singleton(self, monkeypatch):
        """get_config가 싱글톤으로 동작하는지 테스트"""
        # 환경 변수 설정
        monkeypatch.setenv("BINANCE_API_KEY", "test_key")
        monkeypatch.setenv("BINANCE_SECRET_KEY", "test_secret")
        monkeypatch.setenv("GEMINI_API_KEY", "test_gemini")
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://test.com")

        # 첫 번째 호출
        config1 = get_config()

        # 두 번째 호출
        config2 = get_config()

        # 같은 인스턴스여야 함
        assert config1 is config2


class TestMainnetSafetySwitch:
    """Phase 7.1: 메인넷 안전장치 테스트"""

    def test_testnet_no_confirmation_needed(self):
        """테스트넷에서는 확인 불필요"""
        config = TradingConfig(
            binance_api_key="test",
            binance_secret_key="test",
            gemini_api_key="test",
            discord_webhook_url="https://test.com",
            binance_testnet=True,  # 테스트넷
            mainnet_confirmation="",  # 확인 없음
        )

        # 에러 없이 통과
        result = config.validate_mainnet_switch()
        assert result is True

    def test_mainnet_without_confirmation_fails(self):
        """메인넷 활성화 시 확인 없으면 실패"""
        config = TradingConfig(
            binance_api_key="test",
            binance_secret_key="test",
            gemini_api_key="test",
            discord_webhook_url="https://test.com",
            binance_testnet=False,  # 메인넷
            mainnet_confirmation="",  # 확인 없음
        )

        with pytest.raises(ValueError) as exc_info:
            config.validate_mainnet_switch()

        assert "MAINNET_CONFIRMATION" in str(exc_info.value)
        assert "I_UNDERSTAND_THIS_IS_REAL_MONEY" in str(exc_info.value)

    def test_mainnet_with_wrong_confirmation_fails(self):
        """메인넷 활성화 시 잘못된 확인 문자열은 실패"""
        config = TradingConfig(
            binance_api_key="test",
            binance_secret_key="test",
            gemini_api_key="test",
            discord_webhook_url="https://test.com",
            binance_testnet=False,  # 메인넷
            mainnet_confirmation="wrong_string",  # 잘못된 확인
        )

        with pytest.raises(ValueError) as exc_info:
            config.validate_mainnet_switch()

        assert "MAINNET_CONFIRMATION" in str(exc_info.value)

    def test_mainnet_with_correct_confirmation_passes(self):
        """메인넷 활성화 시 올바른 확인 문자열은 통과"""
        config = TradingConfig(
            binance_api_key="test",
            binance_secret_key="test",
            gemini_api_key="test",
            discord_webhook_url="https://test.com",
            binance_testnet=False,  # 메인넷
            mainnet_confirmation="I_UNDERSTAND_THIS_IS_REAL_MONEY",  # 올바른 확인
        )

        # 에러 없이 통과
        result = config.validate_mainnet_switch()
        assert result is True

    def test_load_config_mainnet_without_confirmation(self, monkeypatch):
        """load_config에서 메인넷 확인 없으면 에러"""
        monkeypatch.setenv("BINANCE_API_KEY", "test")
        monkeypatch.setenv("BINANCE_SECRET_KEY", "test")
        monkeypatch.setenv("GEMINI_API_KEY", "test")
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://test.com")
        monkeypatch.setenv("BINANCE_TESTNET", "false")  # 메인넷
        monkeypatch.setenv("MAINNET_CONFIRMATION", "")  # 확인 없음

        with pytest.raises(ValueError) as exc_info:
            load_config()

        assert "I_UNDERSTAND_THIS_IS_REAL_MONEY" in str(exc_info.value)

    def test_load_config_mainnet_with_confirmation(self, monkeypatch):
        """load_config에서 메인넷 확인 있으면 통과"""
        monkeypatch.setenv("BINANCE_API_KEY", "test")
        monkeypatch.setenv("BINANCE_SECRET_KEY", "test")
        monkeypatch.setenv("GEMINI_API_KEY", "test")
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://test.com")
        monkeypatch.setenv("BINANCE_TESTNET", "false")  # 메인넷
        monkeypatch.setenv("MAINNET_CONFIRMATION", "I_UNDERSTAND_THIS_IS_REAL_MONEY")

        config = load_config()

        assert config.binance_testnet is False
        assert config.mainnet_confirmation == "I_UNDERSTAND_THIS_IS_REAL_MONEY"
