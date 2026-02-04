"""
Bots API 테스트

/api/bots 엔드포인트 테스트입니다.
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
TEST_API_KEY = "test-api-key-12345"


@pytest.fixture(autouse=True)
def set_api_key_env():
    """모든 테스트에서 API_KEY 환경변수 설정"""
    with patch.dict(os.environ, {"API_KEY": TEST_API_KEY}):
        yield


@pytest.fixture
def mock_bot():
    """Mock BotInstance fixture"""
    bot = MagicMock(spec=BotInstance)
    bot.bot_name = "test-bot"
    bot.symbol = "BTCUSDT"
    bot.is_running = False
    bot.is_paused = False
    bot.config = BotConfig(
        bot_name="test-bot",
        symbol="BTCUSDT",
        risk_level="medium",
    )
    bot.get_state.return_value = {
        "bot_id": str(bot.config.bot_id),
        "bot_name": "test-bot",
        "symbol": "BTCUSDT",
        "risk_level": "medium",
        "is_running": False,
        "is_paused": False,
        "uptime_start": None,
        "loop_count": 0,
        "current_price": 50000.0,
        "last_signal": "WAIT",
        "last_signal_time": None,
        "position": None,
        "leverage": 15,
    }
    return bot


@pytest.fixture
def mock_manager(mock_bot):
    """Mock MultiBotManager fixture"""
    manager = MagicMock(spec=MultiBotManager)
    manager.bots = {"test-bot": mock_bot}
    manager.bot_count = 1
    manager.running_count = 0
    manager.paused_count = 0
    manager.get_bot.return_value = mock_bot
    manager.add_bot.return_value = mock_bot
    manager.start_bot = AsyncMock()
    manager.stop_bot = AsyncMock()
    return manager


@pytest.fixture
def api_headers():
    """API 인증 헤더"""
    return {"X-API-Key": TEST_API_KEY}


@pytest.fixture
def client(mock_manager, api_headers):
    """테스트 클라이언트 fixture"""
    app = create_app(bot_manager=mock_manager)
    client = TestClient(app)
    client.headers.update(api_headers)
    return client


class TestListBots:
    """GET /api/bots 테스트"""

    def test_list_bots_success(self, client):
        """봇 목록 조회 성공"""
        response = client.get("/api/bots")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert data["data"]["total_bots"] == 1
        assert len(data["data"]["bots"]) == 1

    def test_list_bots_empty(self, api_headers):
        """빈 봇 목록"""
        manager = MagicMock(spec=MultiBotManager)
        manager.bots = {}
        manager.bot_count = 0
        manager.running_count = 0
        manager.paused_count = 0

        app = create_app(bot_manager=manager)
        client = TestClient(app)

        response = client.get("/api/bots", headers=api_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["total_bots"] == 0
        assert data["data"]["bots"] == []


class TestGetBot:
    """GET /api/bots/{bot_name} 테스트"""

    def test_get_bot_success(self, client, mock_manager, mock_bot):
        """봇 상세 조회 성공"""
        response = client.get("/api/bots/test-bot")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["bot_name"] == "test-bot"
        mock_manager.get_bot.assert_called_with("test-bot")

    def test_get_bot_not_found(self, client, mock_manager):
        """존재하지 않는 봇 조회"""
        mock_manager.get_bot.return_value = None

        response = client.get("/api/bots/nonexistent")

        assert response.status_code == 404


class TestCreateBot:
    """POST /api/bots 테스트"""

    def test_create_bot_success(self, client, mock_manager, mock_bot):
        """봇 생성 성공"""
        response = client.post(
            "/api/bots",
            json={
                "bot_name": "new-bot",
                "symbol": "ETHUSDT",
                "risk_level": "low",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        mock_manager.add_bot.assert_called_once()

    def test_create_bot_already_exists(self, client, mock_manager):
        """이미 존재하는 봇 생성 시도"""
        mock_manager.add_bot.side_effect = ValueError(
            "Bot 'existing-bot' already exists"
        )

        response = client.post(
            "/api/bots",
            json={"bot_name": "existing-bot"},
        )

        assert response.status_code == 409

    def test_create_bot_invalid_leverage(self, client):
        """잘못된 레버리지로 봇 생성"""
        response = client.post(
            "/api/bots",
            json={
                "bot_name": "invalid-bot",
                "symbol": "BTCUSDT",
                "leverage": 200,  # 125 초과 (Pydantic Field에서 le=125)
            },
        )

        # Pydantic validation에서 걸림 (leverage max 125)
        assert response.status_code == 422


class TestUpdateBot:
    """PUT /api/bots/{bot_name} 테스트"""

    def test_update_bot_success(self, client, mock_manager, mock_bot):
        """봇 설정 수정 성공"""
        response = client.put(
            "/api/bots/test-bot",
            json={"risk_level": "high"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_update_bot_not_found(self, client, mock_manager):
        """존재하지 않는 봇 수정"""
        mock_manager.get_bot.return_value = None

        response = client.put(
            "/api/bots/nonexistent",
            json={"risk_level": "high"},
        )

        assert response.status_code == 404


class TestDeleteBot:
    """DELETE /api/bots/{bot_name} 테스트"""

    def test_delete_bot_success(self, client, mock_manager, mock_bot):
        """봇 삭제 성공"""
        mock_bot.is_running = False

        response = client.delete("/api/bots/test-bot")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_manager.remove_bot.assert_called_once_with("test-bot")

    def test_delete_bot_not_found(self, client, mock_manager):
        """존재하지 않는 봇 삭제"""
        mock_manager.get_bot.return_value = None

        response = client.delete("/api/bots/nonexistent")

        assert response.status_code == 404

    def test_delete_running_bot_fails(self, api_headers):
        """실행 중인 봇 삭제 실패"""
        # 새로운 mock 생성
        mock_bot = MagicMock(spec=BotInstance)
        mock_bot.bot_name = "running-bot"
        mock_bot.is_running = True  # 실행 중
        mock_bot.config = BotConfig(
            bot_name="running-bot",
            symbol="BTCUSDT",
            risk_level="medium",
        )

        manager = MagicMock(spec=MultiBotManager)
        manager.bots = {"running-bot": mock_bot}
        manager.bot_count = 1
        manager.running_count = 1
        manager.paused_count = 0
        manager.get_bot.return_value = mock_bot

        app = create_app(bot_manager=manager)
        client = TestClient(app)

        response = client.delete("/api/bots/running-bot", headers=api_headers)

        # 실행 중인 봇은 409 Conflict
        assert response.status_code == 409


class TestBotControl:
    """봇 제어 엔드포인트 테스트"""

    def test_start_bot(self, client, mock_manager):
        """봇 시작"""
        response = client.post("/api/bots/test-bot/start")

        assert response.status_code == 200
        mock_manager.start_bot.assert_called_once_with("test-bot")

    def test_stop_bot(self, client, mock_manager):
        """봇 정지"""
        response = client.post("/api/bots/test-bot/stop")

        assert response.status_code == 200
        mock_manager.stop_bot.assert_called_once_with("test-bot")

    def test_pause_bot(self, client, mock_manager):
        """봇 일시정지"""
        response = client.post("/api/bots/test-bot/pause")

        assert response.status_code == 200
        mock_manager.pause_bot.assert_called_once_with("test-bot")

    def test_resume_bot(self, client, mock_manager):
        """봇 재개"""
        response = client.post("/api/bots/test-bot/resume")

        assert response.status_code == 200
        mock_manager.resume_bot.assert_called_once_with("test-bot")

    def test_emergency_close(self, client, mock_manager, mock_bot):
        """긴급 청산"""
        response = client.post("/api/bots/test-bot/emergency-close")

        assert response.status_code == 200
        mock_bot.request_emergency_close.assert_called_once()

    def test_control_not_found(self, client, mock_manager):
        """존재하지 않는 봇 제어"""
        mock_manager.get_bot.return_value = None

        response = client.post("/api/bots/nonexistent/start")

        assert response.status_code == 404
