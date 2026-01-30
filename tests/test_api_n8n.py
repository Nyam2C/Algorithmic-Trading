"""
n8n API 테스트

/api/n8n 엔드포인트 테스트입니다.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.bot_manager import MultiBotManager
from src.bot_config import BotConfig
from src.bot_instance import BotInstance


@pytest.fixture
def mock_bot():
    """Mock BotInstance fixture"""
    bot = MagicMock(spec=BotInstance)
    bot.bot_name = "test-bot"
    bot.symbol = "BTCUSDT"
    bot.is_running = True
    bot.is_paused = False
    bot.config = BotConfig(
        bot_name="test-bot",
        symbol="BTCUSDT",
        risk_level="medium",
    )
    return bot


@pytest.fixture
def mock_manager(mock_bot):
    """Mock MultiBotManager fixture"""
    manager = MagicMock(spec=MultiBotManager)
    manager.bots = {"test-bot": mock_bot}
    manager.bot_count = 1
    manager.running_count = 1
    manager.paused_count = 0
    manager.get_bot.return_value = mock_bot
    manager.start_bot = AsyncMock()
    manager.stop_bot = AsyncMock()
    manager.start_all = AsyncMock()
    manager.stop_all = AsyncMock()
    return manager


@pytest.fixture
def client(mock_manager):
    """테스트 클라이언트 fixture"""
    app = create_app(bot_manager=mock_manager)
    return TestClient(app)


class TestN8NSignal:
    """POST /api/n8n/signal 테스트"""

    def test_receive_signal_long(self, client, mock_manager):
        """LONG 시그널 수신"""
        response = client.post(
            "/api/n8n/signal",
            json={
                "signal": "LONG",
                "source": "tradingview",
                "confidence": 0.85,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Signal" in data["message"]

    def test_receive_signal_short(self, client, mock_manager):
        """SHORT 시그널 수신"""
        response = client.post(
            "/api/n8n/signal",
            json={
                "signal": "SHORT",
                "source": "custom",
            },
        )

        assert response.status_code == 200

    def test_receive_signal_with_bot_name(self, client, mock_manager):
        """특정 봇에 시그널 전송"""
        response = client.post(
            "/api/n8n/signal",
            json={
                "bot_name": "test-bot",
                "signal": "LONG",
                "source": "n8n",
            },
        )

        assert response.status_code == 200
        mock_manager.get_bot.assert_called_with("test-bot")

    def test_receive_signal_bot_not_found(self, client, mock_manager):
        """존재하지 않는 봇에 시그널 전송"""
        mock_manager.get_bot.return_value = None

        response = client.post(
            "/api/n8n/signal",
            json={
                "bot_name": "nonexistent",
                "signal": "LONG",
                "source": "n8n",
            },
        )

        assert response.status_code == 404

    def test_receive_signal_invalid_signal(self, client):
        """잘못된 시그널 값"""
        response = client.post(
            "/api/n8n/signal",
            json={
                "signal": "INVALID",
                "source": "n8n",
            },
        )

        # Pydantic validation error
        assert response.status_code == 422

    def test_receive_signal_with_metadata(self, client, mock_manager):
        """메타데이터 포함 시그널"""
        response = client.post(
            "/api/n8n/signal",
            json={
                "signal": "LONG",
                "source": "tradingview",
                "confidence": 0.9,
                "metadata": {
                    "strategy": "rsi_divergence",
                    "timeframe": "1h",
                },
            },
        )

        assert response.status_code == 200


class TestN8NCommand:
    """POST /api/n8n/command 테스트"""

    def test_command_start(self, client, mock_manager):
        """시작 명령"""
        response = client.post(
            "/api/n8n/command",
            json={
                "bot_name": "test-bot",
                "command": "start",
            },
        )

        assert response.status_code == 200
        mock_manager.start_bot.assert_called_once_with("test-bot")

    def test_command_stop(self, client, mock_manager):
        """정지 명령"""
        response = client.post(
            "/api/n8n/command",
            json={
                "bot_name": "test-bot",
                "command": "stop",
            },
        )

        assert response.status_code == 200
        mock_manager.stop_bot.assert_called_once_with("test-bot")

    def test_command_pause(self, client, mock_manager):
        """일시정지 명령"""
        response = client.post(
            "/api/n8n/command",
            json={
                "bot_name": "test-bot",
                "command": "pause",
            },
        )

        assert response.status_code == 200
        mock_manager.pause_bot.assert_called_once_with("test-bot")

    def test_command_resume(self, client, mock_manager):
        """재개 명령"""
        response = client.post(
            "/api/n8n/command",
            json={
                "bot_name": "test-bot",
                "command": "resume",
            },
        )

        assert response.status_code == 200
        mock_manager.resume_bot.assert_called_once_with("test-bot")

    def test_command_emergency_close(self, client, mock_manager, mock_bot):
        """긴급 청산 명령"""
        response = client.post(
            "/api/n8n/command",
            json={
                "bot_name": "test-bot",
                "command": "emergency_close",
            },
        )

        assert response.status_code == 200
        mock_bot.request_emergency_close.assert_called_once()

    def test_command_all_bots_start(self, client, mock_manager):
        """전체 봇 시작 명령"""
        response = client.post(
            "/api/n8n/command",
            json={
                "command": "start",
            },
        )

        assert response.status_code == 200
        mock_manager.start_all.assert_called_once()

    def test_command_all_bots_stop(self, client, mock_manager):
        """전체 봇 정지 명령"""
        response = client.post(
            "/api/n8n/command",
            json={
                "command": "stop",
            },
        )

        assert response.status_code == 200
        mock_manager.stop_all.assert_called_once()

    def test_command_all_bots_pause(self, client, mock_manager):
        """전체 봇 일시정지 명령"""
        response = client.post(
            "/api/n8n/command",
            json={
                "command": "pause",
            },
        )

        assert response.status_code == 200
        mock_manager.pause_all.assert_called_once()

    def test_command_invalid(self, client):
        """잘못된 명령"""
        response = client.post(
            "/api/n8n/command",
            json={
                "command": "invalid_command",
            },
        )

        # Pydantic validation error
        assert response.status_code == 422

    def test_command_bot_not_found(self, client, mock_manager):
        """존재하지 않는 봇에 명령"""
        mock_manager.start_bot.side_effect = ValueError("Bot not found")

        response = client.post(
            "/api/n8n/command",
            json={
                "bot_name": "nonexistent",
                "command": "start",
            },
        )

        assert response.status_code == 404


class TestN8NPayloadValidation:
    """페이로드 검증 테스트"""

    def test_signal_missing_required_field(self, client):
        """필수 필드 누락"""
        response = client.post(
            "/api/n8n/signal",
            json={
                "source": "n8n",
                # signal 필드 누락
            },
        )

        assert response.status_code == 422

    def test_command_missing_required_field(self, client):
        """필수 필드 누락"""
        response = client.post(
            "/api/n8n/command",
            json={
                "bot_name": "test-bot",
                # command 필드 누락
            },
        )

        assert response.status_code == 422

    def test_signal_confidence_out_of_range(self, client):
        """신뢰도 범위 초과"""
        response = client.post(
            "/api/n8n/signal",
            json={
                "signal": "LONG",
                "confidence": 1.5,  # 1 초과
            },
        )

        assert response.status_code == 422
