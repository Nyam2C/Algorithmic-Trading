"""
BotService 테스트

봇 CRUD 로직 테스트입니다.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock

from src.api.services.bot_service import BotService
from src.api.schemas.bot import BotCreateRequest, BotUpdateRequest
from src.bot_manager import MultiBotManager
from src.bot_config import BotConfig
from src.bot_instance import BotInstance


@pytest.fixture
def mock_manager():
    """Mock MultiBotManager fixture"""
    manager = MagicMock(spec=MultiBotManager)
    manager.bots = {}
    manager.bot_count = 0
    manager.running_count = 0
    manager.paused_count = 0
    return manager


@pytest.fixture
def mock_bot():
    """Mock BotInstance fixture"""
    bot = MagicMock(spec=BotInstance)
    bot.bot_name = "test-bot"
    bot.symbol = "BTCUSDT"
    bot.is_running = False
    bot.is_paused = False
    bot.config = BotConfig(bot_name="test-bot", symbol="BTCUSDT", risk_level="medium")
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
def service(mock_manager):
    """BotService fixture"""
    return BotService(mock_manager)


class TestBotServiceListBots:
    """list_bots 테스트"""

    def test_list_bots_empty(self, service, mock_manager):
        """봇이 없을 때 빈 목록 반환"""
        mock_manager.bots = {}
        mock_manager.bot_count = 0
        mock_manager.running_count = 0
        mock_manager.paused_count = 0

        result = service.list_bots()

        assert result["total_bots"] == 0
        assert result["running_bots"] == 0
        assert result["paused_bots"] == 0
        assert result["bots"] == []

    def test_list_bots_with_bots(self, service, mock_manager, mock_bot):
        """봇이 있을 때 목록 반환"""
        mock_manager.bots = {"test-bot": mock_bot}
        mock_manager.bot_count = 1
        mock_manager.running_count = 0
        mock_manager.paused_count = 0

        result = service.list_bots()

        assert result["total_bots"] == 1
        assert len(result["bots"]) == 1
        assert result["bots"][0]["bot_name"] == "test-bot"


class TestBotServiceGetBot:
    """get_bot_state 테스트"""

    def test_get_bot_state_success(self, service, mock_manager, mock_bot):
        """봇 상태 조회 성공"""
        mock_manager.get_bot.return_value = mock_bot

        result = service.get_bot_state("test-bot")

        assert result["bot_name"] == "test-bot"
        assert result["symbol"] == "BTCUSDT"
        mock_manager.get_bot.assert_called_once_with("test-bot")

    def test_get_bot_state_not_found(self, service, mock_manager):
        """봇이 없을 때 에러"""
        mock_manager.get_bot.return_value = None

        with pytest.raises(ValueError, match="not found"):
            service.get_bot_state("nonexistent-bot")


class TestBotServiceCreateBot:
    """create_bot 테스트"""

    def test_create_bot_success(self, service, mock_manager, mock_bot):
        """봇 생성 성공"""
        request = BotCreateRequest(
            bot_name="new-bot",
            symbol="ETHUSDT",
            risk_level="low",
        )
        mock_manager.add_bot.return_value = mock_bot

        result = service.create_bot(request)

        assert result["bot_name"] == "test-bot"  # mock 반환값
        mock_manager.add_bot.assert_called_once()

    def test_create_bot_already_exists(self, service, mock_manager):
        """봇이 이미 존재할 때 에러"""
        request = BotCreateRequest(bot_name="existing-bot")
        mock_manager.add_bot.side_effect = ValueError("Bot 'existing-bot' already exists")

        with pytest.raises(ValueError, match="already exists"):
            service.create_bot(request)


class TestBotServiceUpdateBot:
    """update_bot 테스트"""

    def test_update_bot_success(self, service, mock_manager, mock_bot):
        """봇 설정 수정 성공"""
        mock_manager.get_bot.return_value = mock_bot
        request = BotUpdateRequest(risk_level="high")

        result = service.update_bot("test-bot", request)

        assert result is not None

    def test_update_bot_not_found(self, service, mock_manager):
        """봇이 없을 때 에러"""
        mock_manager.get_bot.return_value = None
        request = BotUpdateRequest(risk_level="high")

        with pytest.raises(ValueError, match="not found"):
            service.update_bot("nonexistent-bot", request)


class TestBotServiceDeleteBot:
    """delete_bot 테스트"""

    def test_delete_bot_success(self, service, mock_manager, mock_bot):
        """봇 삭제 성공"""
        mock_manager.get_bot.return_value = mock_bot
        mock_bot.is_running = False

        service.delete_bot("test-bot")

        mock_manager.remove_bot.assert_called_once_with("test-bot")

    def test_delete_bot_not_found(self, service, mock_manager):
        """봇이 없을 때 에러"""
        mock_manager.get_bot.return_value = None

        with pytest.raises(ValueError, match="not found"):
            service.delete_bot("nonexistent-bot")

    def test_delete_running_bot_fails(self, service, mock_manager, mock_bot):
        """실행 중인 봇 삭제 실패"""
        mock_manager.get_bot.return_value = mock_bot
        mock_bot.is_running = True

        with pytest.raises(ValueError, match="running"):
            service.delete_bot("test-bot")


class TestBotServiceControl:
    """봇 제어 테스트"""

    @pytest.mark.asyncio
    async def test_start_bot(self, service, mock_manager, mock_bot):
        """봇 시작"""
        mock_manager.get_bot.return_value = mock_bot
        mock_manager.start_bot = AsyncMock()

        await service.start_bot("test-bot")

        mock_manager.start_bot.assert_called_once_with("test-bot")

    @pytest.mark.asyncio
    async def test_stop_bot(self, service, mock_manager, mock_bot):
        """봇 정지"""
        mock_manager.get_bot.return_value = mock_bot
        mock_manager.stop_bot = AsyncMock()

        await service.stop_bot("test-bot")

        mock_manager.stop_bot.assert_called_once_with("test-bot")

    def test_pause_bot(self, service, mock_manager, mock_bot):
        """봇 일시정지"""
        mock_manager.get_bot.return_value = mock_bot

        service.pause_bot("test-bot")

        mock_manager.pause_bot.assert_called_once_with("test-bot")

    def test_resume_bot(self, service, mock_manager, mock_bot):
        """봇 재개"""
        mock_manager.get_bot.return_value = mock_bot

        service.resume_bot("test-bot")

        mock_manager.resume_bot.assert_called_once_with("test-bot")

    def test_emergency_close(self, service, mock_manager, mock_bot):
        """긴급 청산"""
        mock_manager.get_bot.return_value = mock_bot

        service.emergency_close("test-bot")

        mock_bot.request_emergency_close.assert_called_once()
