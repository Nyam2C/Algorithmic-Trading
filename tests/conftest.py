"""
Pytest configuration and shared fixtures
"""
import os
from pathlib import Path

import pytest


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

# =============================================================================
# Shared fixtures for executor / safety / lifecycle tests
# =============================================================================


@pytest.fixture
def mock_config():
    """Mock TradingConfig (leverage=15, tp/sl=0.004)."""
    from src.config import TradingConfig

    return TradingConfig(
        bot_name="test-bot",
        binance_api_key="test_key",
        binance_secret_key="test_secret",
        gemini_api_key="test_gemini",
        discord_webhook_url="https://test.com",
        symbol="BTCUSDT",
        leverage=15,
        position_size_pct=0.05,
        take_profit_pct=0.004,
        stop_loss_pct=0.004,
    )


@pytest.fixture
def mock_binance_client():
    """Mock Binance client (superset of all executor test needs)."""
    from unittest.mock import AsyncMock, Mock

    client = Mock()
    client.set_leverage = AsyncMock(return_value={"leverage": 15})
    client.get_position = AsyncMock(return_value=None)
    client.create_market_order = AsyncMock(return_value={
        "orderId": 12345,
        "symbol": "BTCUSDT",
        "side": "BUY",
        "status": "FILLED",
    })
    client.close_position = AsyncMock(return_value={
        "orderId": 67890,
        "status": "FILLED",
        "executedQty": "0.01",
    })
    client.get_account_balance = AsyncMock(return_value={
        "asset": "USDT",
        "balance": 5000.0,
        "available": 4500.0,
        "unrealized_pnl": 100.0,
    })
    client.create_stop_market_order = AsyncMock(return_value={
        "orderId": 77777, "type": "STOP_MARKET", "status": "NEW",
    })
    client.create_take_profit_market_order = AsyncMock(return_value={
        "orderId": 88888, "type": "TAKE_PROFIT_MARKET", "status": "NEW",
    })
    client.cancel_all_open_orders = AsyncMock(return_value={
        "code": 200, "msg": "success",
    })
    return client


@pytest.fixture
def executor(mock_binance_client, mock_config):
    """TradingExecutor instance with mock client and config."""
    from src.trading.executor import TradingExecutor

    return TradingExecutor(mock_binance_client, mock_config)

