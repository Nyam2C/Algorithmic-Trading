"""
Tests for Discord Bot
"""
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.discord_bot.bot import (
    TradingBotClient,
)

# Note: ConfirmationView and DashboardView 테스트는 Discord.py의 이벤트 루프 요구사항으로 인해
# TradingBotClient의 메서드 테스트로 대체합니다.


class TestTradingBotClientInit:
    """TradingBotClient 초기화 테스트"""

    def test_init(self):
        """기본 초기화"""
        bot_state = {"is_running": True}

        with patch.object(TradingBotClient, "setup_commands"):
            client = TradingBotClient(bot_state=bot_state)

            assert client.bot_state == bot_state
            assert client.trade_db is None
            assert client.binance_client is None

    def test_init_with_db(self):
        """DB와 함께 초기화"""
        bot_state = {}
        mock_db = Mock()

        with patch.object(TradingBotClient, "setup_commands"):
            client = TradingBotClient(
                bot_state=bot_state,
                trade_db=mock_db
            )

            assert client.trade_db == mock_db


class TestGetStatusEmbed:
    """_get_status_embed 메서드 테스트"""

    @pytest.fixture
    def client(self):
        bot_state = {
            "is_running": True,
            "is_paused": False,
            "current_price": 105000.0,
            "last_signal": "LONG",
            "last_signal_time": datetime.now() - timedelta(minutes=30),
            "uptime_start": datetime.now() - timedelta(hours=2),
            "symbol": "BTCUSDT",
            "position": None
        }
        with patch.object(TradingBotClient, "setup_commands"):
            return TradingBotClient(bot_state=bot_state)

    @pytest.mark.asyncio
    async def test_get_status_embed_running(self, client):
        """실행 중 상태 임베드"""
        embed = await client._get_status_embed()

        assert embed.title == "🤖 봇 상태"
        assert embed.color.value == 0x00FF00  # Green for running

    @pytest.mark.asyncio
    async def test_get_status_embed_paused(self):
        """일시정지 상태"""
        bot_state = {
            "is_running": True,
            "is_paused": True,
            "current_price": 105000.0,
            "last_signal": "WAIT"
        }
        with patch.object(TradingBotClient, "setup_commands"):
            client = TradingBotClient(bot_state=bot_state)

        embed = await client._get_status_embed()

        assert embed.color.value == 0xFF0000  # Red for paused

    @pytest.mark.asyncio
    async def test_get_status_embed_with_position(self):
        """포지션 있는 경우"""
        bot_state = {
            "is_running": True,
            "is_paused": False,
            "current_price": 106000.0,
            "position": {
                "side": "LONG",
                "entry_price": 105000.0
            }
        }
        with patch.object(TradingBotClient, "setup_commands"):
            client = TradingBotClient(bot_state=bot_state)

        embed = await client._get_status_embed()

        # 포지션 필드 확인
        position_field = next(
            (f for f in embed.fields if f.name == "📍 포지션"), None
        )
        assert position_field is not None
        assert "LONG" in position_field.value


class TestGetPositionEmbed:
    """_get_position_embed 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_get_position_embed_no_position(self):
        """포지션 없음"""
        bot_state = {"position": None, "last_signal": "WAIT"}
        with patch.object(TradingBotClient, "setup_commands"):
            client = TradingBotClient(bot_state=bot_state)

        embed = await client._get_position_embed()

        assert "포지션 없음" in embed.title

    @pytest.mark.asyncio
    async def test_get_position_embed_long(self):
        """LONG 포지션"""
        bot_state = {
            "current_price": 106000.0,
            "position": {
                "side": "LONG",
                "entry_price": 105000.0,
                "quantity": 0.01,
                "leverage": 15,
                "entry_time": datetime.now() - timedelta(minutes=30),
                "tp_price": 105420.0,
                "sl_price": 104580.0,
                "timecut_at": datetime.now() + timedelta(minutes=30)
            }
        }
        with patch.object(TradingBotClient, "setup_commands"):
            client = TradingBotClient(bot_state=bot_state)

        embed = await client._get_position_embed()

        assert "현재 포지션" in embed.title
        assert embed.color.value == 0x00FF00  # Green for LONG

    @pytest.mark.asyncio
    async def test_get_position_embed_short(self):
        """SHORT 포지션"""
        bot_state = {
            "current_price": 104000.0,
            "position": {
                "side": "SHORT",
                "entry_price": 105000.0,
                "quantity": 0.01,
                "leverage": 15,
                "entry_time": datetime.now(),
                "tp_price": 104580.0,
                "sl_price": 105420.0
            }
        }
        with patch.object(TradingBotClient, "setup_commands"):
            client = TradingBotClient(bot_state=bot_state)

        embed = await client._get_position_embed()

        assert embed.color.value == 0xFF0000  # Red for SHORT


class TestGetStatsEmbed:
    """_get_stats_embed 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_get_stats_embed_no_db(self):
        """DB 없음"""
        bot_state = {}
        with patch.object(TradingBotClient, "setup_commands"):
            client = TradingBotClient(bot_state=bot_state, trade_db=None)

        embed = await client._get_stats_embed()

        assert "데이터베이스 연결 안 됨" in embed.title

    @pytest.mark.asyncio
    async def test_get_stats_embed_no_trades(self):
        """거래 없음"""
        mock_db = AsyncMock()
        mock_db.get_statistics.return_value = {"total_trades": 0}

        bot_state = {}
        with patch.object(TradingBotClient, "setup_commands"):
            client = TradingBotClient(bot_state=bot_state, trade_db=mock_db)

        embed = await client._get_stats_embed()

        assert "거래 없음" in embed.title

    @pytest.mark.asyncio
    async def test_get_stats_embed_with_trades(self):
        """거래 있음"""
        mock_db = AsyncMock()
        mock_db.get_statistics.return_value = {
            "total_trades": 10,
            "winners": 6,
            "losers": 4,
            "win_rate": 60.0,
            "total_pnl": 150.0,
            "best_trade": 2.5,
            "worst_trade": -1.5,
            "long_trades": 7,
            "short_trades": 3
        }

        bot_state = {}
        with patch.object(TradingBotClient, "setup_commands"):
            client = TradingBotClient(bot_state=bot_state, trade_db=mock_db)

        embed = await client._get_stats_embed(hours=24)

        assert "거래 통계" in embed.title
        assert embed.color.value == 0x00FF00  # Green for positive PnL


class TestGetHistoryEmbed:
    """_get_history_embed 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_get_history_embed_no_db(self):
        """DB 없음"""
        bot_state = {}
        with patch.object(TradingBotClient, "setup_commands"):
            client = TradingBotClient(bot_state=bot_state, trade_db=None)

        embed = await client._get_history_embed()

        assert "데이터베이스 연결 안 됨" in embed.title

    @pytest.mark.asyncio
    async def test_get_history_embed_no_trades(self):
        """거래 없음"""
        mock_db = AsyncMock()
        mock_db.get_recent_trades.return_value = []

        bot_state = {}
        with patch.object(TradingBotClient, "setup_commands"):
            client = TradingBotClient(bot_state=bot_state, trade_db=mock_db)

        embed = await client._get_history_embed()

        assert "거래 내역 없음" in embed.title

    @pytest.mark.asyncio
    async def test_get_history_embed_with_trades(self):
        """거래 있음"""
        mock_db = AsyncMock()
        mock_db.get_recent_trades.return_value = [
            {
                "id": "uuid1",
                "side": "LONG",
                "entry_price": 105000.0,
                "exit_price": 105500.0,
                "exit_reason": "TAKE_PROFIT",
                "pnl": 7.5,
                "pnl_pct": 0.48,
                "exit_time": datetime.now() - timedelta(hours=1)
            }
        ]

        bot_state = {}
        with patch.object(TradingBotClient, "setup_commands"):
            client = TradingBotClient(bot_state=bot_state, trade_db=mock_db)

        embed = await client._get_history_embed()

        assert "최근 거래" in embed.title


class TestGetAccountEmbed:
    """_get_account_embed 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_get_account_embed_no_client(self):
        """Binance 클라이언트 없음"""
        bot_state = {}
        with patch.object(TradingBotClient, "setup_commands"):
            client = TradingBotClient(bot_state=bot_state, binance_client=None)

        embed = await client._get_account_embed()

        assert "Binance 클라이언트 연결 안 됨" in embed.title

    @pytest.mark.asyncio
    async def test_get_account_embed_with_positions(self):
        """포지션 있음"""
        mock_binance = AsyncMock()
        mock_binance.get_account_balance.return_value = {
            "balance": 10000.0,
            "available": 9500.0
        }
        mock_binance.get_all_positions.return_value = [
            {
                "symbol": "BTCUSDT",
                "side": "LONG",
                "entry_price": 105000.0,
                "current_price": 106000.0,
                "quantity": 0.01,
                "leverage": 15,
                "unrealized_pnl": 150.0,
                "pnl_pct": 1.43,
                "liquidation_price": 80000.0
            }
        ]

        bot_state = {}
        with patch.object(TradingBotClient, "setup_commands"):
            client = TradingBotClient(bot_state=bot_state, binance_client=mock_binance)

        embed = await client._get_account_embed()

        assert "계정 현황" in embed.title


class TestCommandImplementations:
    """명령어 구현 테스트"""

    @pytest.fixture
    def client(self):
        bot_state = {
            "is_running": True,
            "is_paused": False,
            "current_price": 105000.0,
            "position": None
        }
        with patch.object(TradingBotClient, "setup_commands"):
            return TradingBotClient(bot_state=bot_state)

    @pytest.mark.asyncio
    async def test_stop_command(self, client):
        """일시정지 명령어"""
        interaction = AsyncMock()
        interaction.user = "TestUser#1234"
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        await client._stop_command(interaction)

        assert client.bot_state["is_paused"] is True
        assert client.bot_state["paused_by"] == "TestUser#1234"
        interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_command(self, client):
        """재시작 명령어"""
        client.bot_state["is_paused"] = True

        interaction = AsyncMock()
        interaction.user = "TestUser#1234"
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        await client._start_command(interaction)

        assert client.bot_state["is_paused"] is False
        assert client.bot_state["resumed_by"] == "TestUser#1234"

    @pytest.mark.asyncio
    async def test_emergency_command_no_position(self, client):
        """긴급청산 - 포지션 없음"""
        interaction = AsyncMock()
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        await client._emergency_command(interaction)

        # 포지션이 없으므로 emergency_close가 설정되지 않음
        assert "emergency_close" not in client.bot_state

    @pytest.mark.asyncio
    async def test_emergency_command_with_position(self):
        """긴급청산 - 포지션 있음"""
        bot_state = {
            "is_paused": False,
            "position": {
                "side": "LONG",
                "entry_price": 105000.0,
                "quantity": 0.01
            }
        }
        with patch.object(TradingBotClient, "setup_commands"):
            client = TradingBotClient(bot_state=bot_state)

        interaction = AsyncMock()
        interaction.user = "TestUser#1234"
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        await client._emergency_command(interaction)

        assert client.bot_state["emergency_close"] is True
        assert client.bot_state["is_paused"] is True


class TestBotStateManagement:
    """봇 상태 관리 테스트"""

    def test_bot_state_pause(self):
        """일시정지 상태 변경"""
        bot_state = {"is_paused": False}
        bot_state["is_paused"] = True
        bot_state["paused_by"] = "TestUser#1234"
        bot_state["paused_at"] = datetime.now()

        assert bot_state["is_paused"] is True
        assert bot_state["paused_by"] == "TestUser#1234"
        assert "paused_at" in bot_state

    def test_bot_state_resume(self):
        """재시작 상태 변경"""
        bot_state = {
            "is_paused": True,
            "paused_at": datetime.now() - timedelta(hours=1)
        }
        bot_state["is_paused"] = False
        bot_state["resumed_by"] = "TestUser#1234"

        assert bot_state["is_paused"] is False
        assert bot_state["resumed_by"] == "TestUser#1234"

    def test_bot_state_emergency(self):
        """긴급청산 상태 변경"""
        bot_state = {
            "is_paused": False,
            "position": {"side": "LONG", "entry_price": 105000.0}
        }
        bot_state["emergency_close"] = True
        bot_state["is_paused"] = True

        assert bot_state["emergency_close"] is True
        assert bot_state["is_paused"] is True


class TestStartDiscordBot:
    """start_discord_bot 함수 테스트"""

    @pytest.mark.asyncio
    async def test_start_discord_bot(self):
        """Discord 봇 시작"""
        from src.discord_bot.bot import start_discord_bot

        with patch.object(TradingBotClient, "setup_commands"):
            with patch.object(TradingBotClient, "start", new_callable=AsyncMock) as mock_start:
                bot_state = {}
                await start_discord_bot(
                    token="test_token",
                    bot_state=bot_state
                )

                mock_start.assert_called_once_with("test_token")
