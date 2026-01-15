"""
Pytest configuration and shared fixtures
"""
import os
import pytest
from pathlib import Path


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """테스트 환경 설정"""
    # 테스트용 환경 변수 설정
    os.environ["BOT_NAME"] = "test-bot"
    os.environ["BINANCE_TESTNET"] = "true"
    os.environ["BINANCE_API_KEY"] = "test_binance_key"
    os.environ["BINANCE_SECRET_KEY"] = "test_binance_secret"
    os.environ["GEMINI_API_KEY"] = "test_gemini_key"
    os.environ["DISCORD_WEBHOOK_URL"] = "https://test.discord.com/webhook"
    os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"
    os.environ["SYMBOL"] = "BTCUSDT"
    os.environ["LEVERAGE"] = "15"
    os.environ["POSITION_SIZE_PCT"] = "0.05"
    os.environ["TAKE_PROFIT_PCT"] = "0.004"
    os.environ["STOP_LOSS_PCT"] = "0.004"

    yield

    # 테스트 후 정리 (필요시)


@pytest.fixture
def test_data_dir():
    """테스트 데이터 디렉토리"""
    return Path(__file__).parent / "data"


@pytest.fixture
def sample_trade_data():
    """샘플 거래 데이터"""
    return {
        "symbol": "BTCUSDT",
        "side": "LONG",
        "entry_price": 100000.0,
        "quantity": 0.01,
        "leverage": 15,
    }
