"""
Tests for configuration management
"""
import os
import pytest
from pathlib import Path
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
        # 필수 키 제거
        monkeypatch.delenv("BINANCE_API_KEY", raising=False)
        monkeypatch.delenv("BINANCE_SECRET_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)

        with pytest.raises(ValidationError):
            load_config()


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
