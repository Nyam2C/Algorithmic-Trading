"""
BotService 테스트

봇 CRUD 로직 테스트입니다.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api.schemas.bot import BotCreateRequest, BotUpdateRequest
from src.api.services.bot_service import BotService
from src.bot_config import BotConfig
from src.bot_instance import BotInstance
from src.bot_manager import MultiBotManager


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


# =============================================================================
# src/api/services/bot_service.py 커버리지 테스트 (from test_api_coverage.py)
# =============================================================================


class TestBotServiceControlErrors:
    """봇 제어 에러 케이스 (not found 시 ValueError)"""

    @pytest.fixture
    def mock_manager(self):
        manager = MagicMock()
        manager.get_bot.return_value = None
        manager.start_bot = AsyncMock()
        manager.stop_bot = AsyncMock()
        return manager

    @pytest.fixture
    def service(self, mock_manager):
        return BotService(mock_manager)

    @pytest.mark.asyncio
    async def test_start_bot_not_found(self, service):
        """존재하지 않는 봇 시작 시 ValueError"""
        with pytest.raises(ValueError, match="not found"):
            await service.start_bot("nonexistent")

    @pytest.mark.asyncio
    async def test_stop_bot_not_found(self, service):
        """존재하지 않는 봇 정지 시 ValueError"""
        with pytest.raises(ValueError, match="not found"):
            await service.stop_bot("nonexistent")

    def test_pause_bot_not_found(self, service):
        """존재하지 않는 봇 일시정지 시 ValueError"""
        with pytest.raises(ValueError, match="not found"):
            service.pause_bot("nonexistent")

    def test_resume_bot_not_found(self, service):
        """존재하지 않는 봇 재개 시 ValueError"""
        with pytest.raises(ValueError, match="not found"):
            service.resume_bot("nonexistent")

    def test_emergency_close_not_found(self, service):
        """존재하지 않는 봇 긴급 청산 시 ValueError"""
        with pytest.raises(ValueError, match="not found"):
            service.emergency_close("nonexistent")


class TestBotServiceStartStopAll:
    """전체 봇 시작/정지 테스트"""

    @pytest.fixture
    def mock_manager(self):
        manager = MagicMock()
        manager.start_all = AsyncMock()
        manager.stop_all = AsyncMock()
        manager.running_count = 3
        return manager

    @pytest.fixture
    def service(self, mock_manager):
        return BotService(mock_manager)

    @pytest.mark.asyncio
    async def test_start_all(self, service, mock_manager):
        """전체 봇 시작"""
        result = await service.start_all()
        assert result == 3
        mock_manager.start_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_all(self, service, mock_manager):
        """전체 봇 정지"""
        result = await service.stop_all()
        assert result == 3
        mock_manager.stop_all.assert_called_once()


class TestBotServiceUpdateBotAllFields:
    """봇 설정 수정 - 모든 필드 업데이트 테스트"""

    @pytest.fixture
    def mock_bot_full(self):
        bot = MagicMock(spec=BotInstance)
        bot.bot_name = "test-bot"
        bot.is_running = False
        bot.is_paused = False
        bot.config = BotConfig(bot_name="test-bot", symbol="BTCUSDT", risk_level="medium")
        return bot

    @pytest.fixture
    def service_with_bot(self, mock_bot_full):
        manager = MagicMock()
        manager.get_bot.return_value = mock_bot_full
        return BotService(manager), mock_bot_full

    def test_update_bot_all_fields(self, service_with_bot):
        """모든 필드 업데이트"""
        service, bot = service_with_bot
        request = BotUpdateRequest(
            risk_level="high",
            leverage=20,
            position_size_pct=0.05,
            take_profit_pct=3.0,
            stop_loss_pct=2.0,
            time_cut_minutes=180,
            rsi_oversold=30.0,
            rsi_overbought=70.0,
            volume_threshold=1.5,
            is_testnet=False,
            is_active=True,
            description="Updated bot",
        )

        result = service.update_bot("test-bot", request)

        assert result is not None
        assert bot.config.risk_level == "high"
        assert bot.config.leverage == 20
        assert bot.config.position_size_pct == 0.05
        assert bot.config.take_profit_pct == 3.0
        assert bot.config.stop_loss_pct == 2.0
        assert bot.config.time_cut_minutes == 180
        assert bot.config.rsi_oversold == 30.0
        assert bot.config.rsi_overbought == 70.0
        assert bot.config.volume_threshold == 1.5
        assert bot.config.is_testnet is False
        assert bot.config.is_active is True
        assert bot.config.description == "Updated bot"


class TestBotServiceCreateBotWithAllFields:
    """봇 생성 - 모든 옵셔널 필드 포함"""

    def test_create_bot_with_all_optional_fields(self):
        """모든 옵셔널 필드를 포함한 봇 생성"""
        mock_bot = MagicMock(spec=BotInstance)
        mock_bot.bot_name = "full-bot"
        mock_bot.is_running = False
        mock_bot.is_paused = False

        mock_manager = MagicMock()
        mock_manager.add_bot.return_value = mock_bot

        service = BotService(mock_manager)

        request = BotCreateRequest(
            bot_name="full-bot",
            symbol="ETHUSDT",
            risk_level="high",
            leverage=20,
            position_size_pct=0.05,
            take_profit_pct=3.0,
            stop_loss_pct=2.0,
            time_cut_minutes=180,
            rsi_oversold=30.0,
            rsi_overbought=70.0,
            volume_threshold=1.5,
            is_testnet=False,
            description="Full test bot",
        )

        result = service.create_bot(request)
        assert result["bot_name"] == "full-bot"
        mock_manager.add_bot.assert_called_once()
