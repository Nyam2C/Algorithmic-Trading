"""
n8n API 테스트

/api/n8n 엔드포인트 테스트입니다.
Phase 4.1: API 키 인증 테스트 추가
"""
import os
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.bot_manager import MultiBotManager
from src.bot_config import BotConfig
from src.bot_instance import BotInstance


# 테스트용 API 키
TEST_N8N_API_KEY = "test-api-key-12345"


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


@pytest.fixture(autouse=True)
def set_n8n_api_key_env():
    """모든 테스트에서 N8N_API_KEY 환경변수 설정"""
    with patch.dict(os.environ, {"N8N_API_KEY": TEST_N8N_API_KEY}):
        yield


@pytest.fixture
def client(mock_manager):
    """테스트 클라이언트 fixture"""
    app = create_app(bot_manager=mock_manager)
    return TestClient(app)


@pytest.fixture
def api_headers():
    """n8n API 헤더 fixture"""
    return {"X-N8N-API-Key": TEST_N8N_API_KEY}


class TestN8NSignal:
    """POST /api/n8n/signal 테스트"""

    def test_receive_signal_long(self, client, mock_manager, api_headers):
        """LONG 시그널 수신"""
        response = client.post(
            "/api/n8n/signal",
            json={
                "signal": "LONG",
                "source": "tradingview",
                "confidence": 0.85,
            },
            headers=api_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Signal" in data["message"]

    def test_receive_signal_short(self, client, mock_manager, api_headers):
        """SHORT 시그널 수신"""
        response = client.post(
            "/api/n8n/signal",
            json={
                "signal": "SHORT",
                "source": "custom",
            },
            headers=api_headers,
        )

        assert response.status_code == 200

    def test_receive_signal_with_bot_name(self, client, mock_manager, api_headers):
        """특정 봇에 시그널 전송"""
        response = client.post(
            "/api/n8n/signal",
            json={
                "bot_name": "test-bot",
                "signal": "LONG",
                "source": "n8n",
            },
            headers=api_headers,
        )

        assert response.status_code == 200
        mock_manager.get_bot.assert_called_with("test-bot")

    def test_receive_signal_bot_not_found(self, client, mock_manager, api_headers):
        """존재하지 않는 봇에 시그널 전송"""
        mock_manager.get_bot.return_value = None

        response = client.post(
            "/api/n8n/signal",
            json={
                "bot_name": "nonexistent",
                "signal": "LONG",
                "source": "n8n",
            },
            headers=api_headers,
        )

        assert response.status_code == 404

    def test_receive_signal_invalid_signal(self, client, api_headers):
        """잘못된 시그널 값"""
        response = client.post(
            "/api/n8n/signal",
            json={
                "signal": "INVALID",
                "source": "n8n",
            },
            headers=api_headers,
        )

        # Pydantic validation error
        assert response.status_code == 422

    def test_receive_signal_with_metadata(self, client, mock_manager, api_headers):
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
            headers=api_headers,
        )

        assert response.status_code == 200


class TestN8NCommand:
    """POST /api/n8n/command 테스트"""

    def test_command_start(self, client, mock_manager, api_headers):
        """시작 명령"""
        response = client.post(
            "/api/n8n/command",
            json={
                "bot_name": "test-bot",
                "command": "start",
            },
            headers=api_headers,
        )

        assert response.status_code == 200
        mock_manager.start_bot.assert_called_once_with("test-bot")

    def test_command_stop(self, client, mock_manager, api_headers):
        """정지 명령"""
        response = client.post(
            "/api/n8n/command",
            json={
                "bot_name": "test-bot",
                "command": "stop",
            },
            headers=api_headers,
        )

        assert response.status_code == 200
        mock_manager.stop_bot.assert_called_once_with("test-bot")

    def test_command_pause(self, client, mock_manager, api_headers):
        """일시정지 명령"""
        response = client.post(
            "/api/n8n/command",
            json={
                "bot_name": "test-bot",
                "command": "pause",
            },
            headers=api_headers,
        )

        assert response.status_code == 200
        mock_manager.pause_bot.assert_called_once_with("test-bot")

    def test_command_resume(self, client, mock_manager, api_headers):
        """재개 명령"""
        response = client.post(
            "/api/n8n/command",
            json={
                "bot_name": "test-bot",
                "command": "resume",
            },
            headers=api_headers,
        )

        assert response.status_code == 200
        mock_manager.resume_bot.assert_called_once_with("test-bot")

    def test_command_emergency_close(self, client, mock_manager, mock_bot, api_headers):
        """긴급 청산 명령"""
        response = client.post(
            "/api/n8n/command",
            json={
                "bot_name": "test-bot",
                "command": "emergency_close",
            },
            headers=api_headers,
        )

        assert response.status_code == 200
        mock_bot.request_emergency_close.assert_called_once()

    def test_command_all_bots_start(self, client, mock_manager, api_headers):
        """전체 봇 시작 명령"""
        response = client.post(
            "/api/n8n/command",
            json={
                "command": "start",
            },
            headers=api_headers,
        )

        assert response.status_code == 200
        mock_manager.start_all.assert_called_once()

    def test_command_all_bots_stop(self, client, mock_manager, api_headers):
        """전체 봇 정지 명령"""
        response = client.post(
            "/api/n8n/command",
            json={
                "command": "stop",
            },
            headers=api_headers,
        )

        assert response.status_code == 200
        mock_manager.stop_all.assert_called_once()

    def test_command_all_bots_pause(self, client, mock_manager, api_headers):
        """전체 봇 일시정지 명령"""
        response = client.post(
            "/api/n8n/command",
            json={
                "command": "pause",
            },
            headers=api_headers,
        )

        assert response.status_code == 200
        mock_manager.pause_all.assert_called_once()

    def test_command_invalid(self, client, api_headers):
        """잘못된 명령"""
        response = client.post(
            "/api/n8n/command",
            json={
                "command": "invalid_command",
            },
            headers=api_headers,
        )

        # Pydantic validation error
        assert response.status_code == 422

    def test_command_bot_not_found(self, client, mock_manager, api_headers):
        """존재하지 않는 봇에 명령"""
        mock_manager.start_bot.side_effect = ValueError("Bot not found")

        response = client.post(
            "/api/n8n/command",
            json={
                "bot_name": "nonexistent",
                "command": "start",
            },
            headers=api_headers,
        )

        assert response.status_code == 404


class TestN8NPayloadValidation:
    """페이로드 검증 테스트"""

    def test_signal_missing_required_field(self, client, api_headers):
        """필수 필드 누락"""
        response = client.post(
            "/api/n8n/signal",
            json={
                "source": "n8n",
                # signal 필드 누락
            },
            headers=api_headers,
        )

        assert response.status_code == 422

    def test_command_missing_required_field(self, client, api_headers):
        """필수 필드 누락"""
        response = client.post(
            "/api/n8n/command",
            json={
                "bot_name": "test-bot",
                # command 필드 누락
            },
            headers=api_headers,
        )

        assert response.status_code == 422

    def test_signal_confidence_out_of_range(self, client, api_headers):
        """신뢰도 범위 초과"""
        response = client.post(
            "/api/n8n/signal",
            json={
                "signal": "LONG",
                "confidence": 1.5,  # 1 초과
            },
            headers=api_headers,
        )

        assert response.status_code == 422


class TestN8NAuthValidation:
    """API 키 인증 테스트"""

    def test_missing_api_key(self, client):
        """API 키 누락 시 422 반환"""
        response = client.post(
            "/api/n8n/signal",
            json={
                "signal": "LONG",
                "source": "n8n",
            },
            # headers 없음
        )

        assert response.status_code == 422

    def test_invalid_api_key(self, client):
        """잘못된 API 키 시 401 반환"""
        response = client.post(
            "/api/n8n/signal",
            json={
                "signal": "LONG",
                "source": "n8n",
            },
            headers={"X-N8N-API-Key": "wrong-key"},
        )

        assert response.status_code == 401
