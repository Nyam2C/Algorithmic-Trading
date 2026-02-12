"""
Tests for Discord Bot
"""
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import discord
import pytest

from src.discord_bot.client import (
    TradingBotClient,
    start_discord_bot,
)
from src.discord_bot.constants import Colors
from src.discord_bot.embeds import (
    create_account_embed,
    create_bot_list_embed,
    create_bot_status_embed,
    create_history_embed,
    create_position_embed,
    create_stats_embed,
    create_status_embed,
)
from src.discord_bot.utils import (
    calculate_pnl,
    format_duration,
    format_pause_duration,
    format_percentage,
    format_price,
    format_time_ago,
    format_timecut_remaining,
    format_uptime,
    get_pnl_emoji,
    get_position_emoji,
    get_status_emoji,
    get_status_text,
    truncate_id,
)
from src.discord_bot.views import ConfirmationView, DashboardView

# RefactoredClient is now the same as TradingBotClient (bot.py removed)
RefactoredClient = TradingBotClient
from src.discord_bot.commands.control import register_control_commands
from src.discord_bot.commands.monitoring import register_monitoring_commands
from src.discord_bot.commands.multibot import register_multibot_commands

# Note: ConfirmationView and DashboardView 테스트는 Discord.py의 이벤트 루프 요구사항으로 인해
# TradingBotClient의 메서드 테스트로 대체합니다.


class TestTradingBotClientInit:
    """TradingBotClient 초기화 테스트"""

    def test_init(self):
        """기본 초기화"""
        bot_state = {"is_running": True}

        with patch("src.discord_bot.commands.monitoring.register_monitoring_commands"), patch("src.discord_bot.commands.control.register_control_commands"), patch("src.discord_bot.commands.multibot.register_multibot_commands"):
            client = TradingBotClient(bot_state=bot_state)

            assert client.bot_state == bot_state
            assert client.trade_db is None
            assert client.binance_client is None

    def test_init_with_db(self):
        """DB와 함께 초기화"""
        bot_state = {}
        mock_db = Mock()

        with patch("src.discord_bot.commands.monitoring.register_monitoring_commands"), patch("src.discord_bot.commands.control.register_control_commands"), patch("src.discord_bot.commands.multibot.register_multibot_commands"):
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
        with patch("src.discord_bot.commands.monitoring.register_monitoring_commands"), patch("src.discord_bot.commands.control.register_control_commands"), patch("src.discord_bot.commands.multibot.register_multibot_commands"):
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
        with patch("src.discord_bot.commands.monitoring.register_monitoring_commands"), patch("src.discord_bot.commands.control.register_control_commands"), patch("src.discord_bot.commands.multibot.register_multibot_commands"):
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
        with patch("src.discord_bot.commands.monitoring.register_monitoring_commands"), patch("src.discord_bot.commands.control.register_control_commands"), patch("src.discord_bot.commands.multibot.register_multibot_commands"):
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
        with patch("src.discord_bot.commands.monitoring.register_monitoring_commands"), patch("src.discord_bot.commands.control.register_control_commands"), patch("src.discord_bot.commands.multibot.register_multibot_commands"):
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
        with patch("src.discord_bot.commands.monitoring.register_monitoring_commands"), patch("src.discord_bot.commands.control.register_control_commands"), patch("src.discord_bot.commands.multibot.register_multibot_commands"):
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
        with patch("src.discord_bot.commands.monitoring.register_monitoring_commands"), patch("src.discord_bot.commands.control.register_control_commands"), patch("src.discord_bot.commands.multibot.register_multibot_commands"):
            client = TradingBotClient(bot_state=bot_state)

        embed = await client._get_position_embed()

        assert embed.color.value == 0xFF0000  # Red for SHORT


class TestGetStatsEmbed:
    """_get_stats_embed 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_get_stats_embed_no_db(self):
        """DB 없음"""
        bot_state = {}
        with patch("src.discord_bot.commands.monitoring.register_monitoring_commands"), patch("src.discord_bot.commands.control.register_control_commands"), patch("src.discord_bot.commands.multibot.register_multibot_commands"):
            client = TradingBotClient(bot_state=bot_state, trade_db=None)

        embed = await client._get_stats_embed()

        assert "데이터베이스 연결 안 됨" in embed.title

    @pytest.mark.asyncio
    async def test_get_stats_embed_no_trades(self):
        """거래 없음"""
        mock_db = AsyncMock()
        mock_db.get_statistics.return_value = {"total_trades": 0}

        bot_state = {}
        with patch("src.discord_bot.commands.monitoring.register_monitoring_commands"), patch("src.discord_bot.commands.control.register_control_commands"), patch("src.discord_bot.commands.multibot.register_multibot_commands"):
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
        with patch("src.discord_bot.commands.monitoring.register_monitoring_commands"), patch("src.discord_bot.commands.control.register_control_commands"), patch("src.discord_bot.commands.multibot.register_multibot_commands"):
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
        with patch("src.discord_bot.commands.monitoring.register_monitoring_commands"), patch("src.discord_bot.commands.control.register_control_commands"), patch("src.discord_bot.commands.multibot.register_multibot_commands"):
            client = TradingBotClient(bot_state=bot_state, trade_db=None)

        embed = await client._get_history_embed()

        assert "데이터베이스 연결 안 됨" in embed.title

    @pytest.mark.asyncio
    async def test_get_history_embed_no_trades(self):
        """거래 없음"""
        mock_db = AsyncMock()
        mock_db.get_recent_trades.return_value = []

        bot_state = {}
        with patch("src.discord_bot.commands.monitoring.register_monitoring_commands"), patch("src.discord_bot.commands.control.register_control_commands"), patch("src.discord_bot.commands.multibot.register_multibot_commands"):
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
        with patch("src.discord_bot.commands.monitoring.register_monitoring_commands"), patch("src.discord_bot.commands.control.register_control_commands"), patch("src.discord_bot.commands.multibot.register_multibot_commands"):
            client = TradingBotClient(bot_state=bot_state, trade_db=mock_db)

        embed = await client._get_history_embed()

        assert "최근 거래" in embed.title


class TestGetAccountEmbed:
    """_get_account_embed 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_get_account_embed_no_client(self):
        """Binance 클라이언트 없음"""
        bot_state = {}
        with patch("src.discord_bot.commands.monitoring.register_monitoring_commands"), patch("src.discord_bot.commands.control.register_control_commands"), patch("src.discord_bot.commands.multibot.register_multibot_commands"):
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
        with patch("src.discord_bot.commands.monitoring.register_monitoring_commands"), patch("src.discord_bot.commands.control.register_control_commands"), patch("src.discord_bot.commands.multibot.register_multibot_commands"):
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
        with patch("src.discord_bot.commands.monitoring.register_monitoring_commands"), patch("src.discord_bot.commands.control.register_control_commands"), patch("src.discord_bot.commands.multibot.register_multibot_commands"):
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
        with patch("src.discord_bot.commands.monitoring.register_monitoring_commands"), patch("src.discord_bot.commands.control.register_control_commands"), patch("src.discord_bot.commands.multibot.register_multibot_commands"):
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
        from src.discord_bot.client import start_discord_bot

        with patch("src.discord_bot.commands.monitoring.register_monitoring_commands"), patch("src.discord_bot.commands.control.register_control_commands"), patch("src.discord_bot.commands.multibot.register_multibot_commands"):
            with patch.object(TradingBotClient, "start", new_callable=AsyncMock) as mock_start:
                bot_state = {}
                await start_discord_bot(
                    token="test_token",
                    bot_state=bot_state
                )

                mock_start.assert_called_once_with("test_token")


# ============================================================================
# From test_discord_bot_coverage.py
# ============================================================================

# ============================================================================
# utils.py 테스트
# ============================================================================


class TestFormatUptime:
    """format_uptime 함수 테스트"""

    def test_none_start_time(self):
        assert format_uptime(None) == "N/A"

    def test_with_start_time(self):
        start = datetime.now() - timedelta(hours=2, minutes=30)
        result = format_uptime(start)
        assert "2시간" in result
        assert "30분" in result

    def test_zero_uptime(self):
        result = format_uptime(datetime.now())
        assert "0시간 0분" == result


class TestFormatTimeAgo:
    """format_time_ago 함수 테스트"""

    def test_none_timestamp(self):
        assert format_time_ago(None) == "N/A"

    def test_non_datetime_value(self):
        assert format_time_ago("not a datetime") == "N/A"

    def test_minutes_ago(self):
        ts = datetime.now() - timedelta(minutes=15)
        result = format_time_ago(ts)
        assert "15분 전" == result

    def test_hours_ago(self):
        ts = datetime.now() - timedelta(hours=3, minutes=10)
        result = format_time_ago(ts)
        assert "3시간 전" == result


class TestFormatDuration:
    """format_duration 함수 테스트"""

    def test_none_start_time(self):
        assert format_duration(None) == "N/A"

    def test_non_datetime_value(self):
        assert format_duration("string") == "N/A"

    def test_minutes_duration(self):
        start = datetime.now() - timedelta(minutes=45)
        result = format_duration(start)
        assert "45분" == result

    def test_hours_minutes_duration(self):
        start = datetime.now() - timedelta(hours=1, minutes=30)
        result = format_duration(start)
        assert "1시간 30분" == result


class TestFormatPauseDuration:
    """format_pause_duration 함수 테스트"""

    def test_none_paused_at(self):
        assert format_pause_duration(None) == ""

    def test_with_paused_at(self):
        paused_at = datetime.now() - timedelta(hours=1, minutes=15)
        result = format_pause_duration(paused_at)
        assert "1시간 15분" in result

    def test_with_paused_by(self):
        paused_at = datetime.now() - timedelta(minutes=30)
        result = format_pause_duration(paused_at, "TestUser")
        assert "TestUser" in result
        assert "30분" in result

    def test_without_paused_by(self):
        paused_at = datetime.now() - timedelta(minutes=10)
        result = format_pause_duration(paused_at)
        assert "10분" in result
        # paused_by가 없으면 이름 없음
        assert "(" not in result


class TestFormatTimecutRemaining:
    """format_timecut_remaining 함수 테스트"""

    def test_none_timecut(self):
        assert format_timecut_remaining(None) == "N/A"

    def test_non_datetime_value(self):
        assert format_timecut_remaining("not datetime") == "N/A"

    def test_future_timecut(self):
        timecut = datetime.now() + timedelta(minutes=45)
        result = format_timecut_remaining(timecut)
        assert "남음" in result

    def test_expired_timecut(self):
        timecut = datetime.now() - timedelta(minutes=10)
        result = format_timecut_remaining(timecut)
        assert result == "만료됨"


class TestCalculatePnl:
    """calculate_pnl 함수 테스트"""

    def test_long_profit(self):
        pnl_pct, pnl_usd = calculate_pnl(100000, 101000, "LONG", 10, 0.01)
        assert pnl_pct == pytest.approx(10.0, abs=0.1)
        assert pnl_usd == pytest.approx(10.0, abs=0.1)

    def test_long_loss(self):
        pnl_pct, pnl_usd = calculate_pnl(100000, 99000, "LONG", 10, 0.01)
        assert pnl_pct < 0
        assert pnl_usd < 0

    def test_short_profit(self):
        pnl_pct, pnl_usd = calculate_pnl(100000, 99000, "SHORT", 10, 0.01)
        assert pnl_pct > 0
        assert pnl_usd > 0

    def test_short_loss(self):
        pnl_pct, pnl_usd = calculate_pnl(100000, 101000, "SHORT", 10, 0.01)
        assert pnl_pct < 0
        assert pnl_usd < 0

    def test_default_leverage_and_size(self):
        pnl_pct, pnl_usd = calculate_pnl(100000, 101000, "LONG")
        assert pnl_pct == pytest.approx(1.0, abs=0.1)
        assert pnl_usd == 0  # size=0


class TestGetStatusEmoji:
    """get_status_emoji 함수 테스트"""

    def test_running(self):
        assert get_status_emoji(True, False) == "🟢"

    def test_paused(self):
        assert get_status_emoji(True, True) == "🟡"

    def test_stopped(self):
        assert get_status_emoji(False, False) == "🔴"

    def test_stopped_but_paused(self):
        assert get_status_emoji(False, True) == "🔴"


class TestGetStatusText:
    """get_status_text 함수 테스트"""

    def test_running(self):
        assert "실행 중" in get_status_text(True, False)

    def test_paused(self):
        assert "일시정지" in get_status_text(True, True)

    def test_stopped(self):
        assert "중지됨" in get_status_text(False, False)


class TestGetPositionEmoji:
    """get_position_emoji 함수 테스트"""

    def test_long(self):
        assert get_position_emoji("LONG") == "🟢"

    def test_short(self):
        assert get_position_emoji("SHORT") == "🔴"


class TestGetPnlEmoji:
    """get_pnl_emoji 함수 테스트"""

    def test_positive(self):
        assert get_pnl_emoji(100.0) == "💰"

    def test_zero(self):
        assert get_pnl_emoji(0) == "💰"

    def test_negative(self):
        assert get_pnl_emoji(-50.0) == "📉"


class TestFormatPrice:
    """format_price 함수 테스트"""

    def test_basic_price(self):
        assert format_price(105000.0) == "$105,000.00"

    def test_custom_decimals(self):
        assert format_price(100.5, decimals=4) == "$100.5000"

    def test_zero_price(self):
        assert format_price(0) == "$0.00"


class TestFormatPercentage:
    """format_percentage 함수 테스트"""

    def test_positive_with_sign(self):
        assert format_percentage(1.5) == "+1.50%"

    def test_negative_with_sign(self):
        assert format_percentage(-2.3) == "-2.30%"

    def test_without_sign(self):
        assert format_percentage(1.5, with_sign=False) == "1.50%"


class TestTruncateId:
    """truncate_id 함수 테스트"""

    def test_long_id(self):
        assert truncate_id("abcdefghijklmnop") == "abcdefgh"

    def test_short_id(self):
        assert truncate_id("abc") == "abc"

    def test_empty_id(self):
        assert truncate_id("") == "N/A"

    def test_none_id(self):
        assert truncate_id(None) == "N/A"

    def test_custom_length(self):
        assert truncate_id("abcdefgh", length=4) == "abcd"


# ============================================================================
# embeds.py 테스트
# ============================================================================


class TestCreateStatusEmbed:
    """create_status_embed 함수 테스트"""

    def test_running_state(self):
        bot_state = {
            "is_running": True,
            "is_paused": False,
            "current_price": 105000.0,
            "last_signal": "LONG",
            "last_signal_time": datetime.now() - timedelta(minutes=30),
            "uptime_start": datetime.now() - timedelta(hours=2),
            "symbol": "BTCUSDT",
            "position": None,
        }
        embed = create_status_embed(bot_state)
        assert embed.title == "🤖 봇 상태"
        assert embed.color.value == Colors.SUCCESS

    def test_paused_state(self):
        bot_state = {
            "is_running": True,
            "is_paused": True,
            "current_price": 0,
            "last_signal": "WAIT",
        }
        embed = create_status_embed(bot_state)
        assert embed.color.value == Colors.ERROR

    def test_stopped_state(self):
        bot_state = {
            "is_running": False,
            "is_paused": False,
            "current_price": 0,
            "last_signal": "WAIT",
        }
        embed = create_status_embed(bot_state)
        assert embed.color.value == Colors.ERROR

    def test_with_position(self):
        bot_state = {
            "is_running": True,
            "is_paused": False,
            "current_price": 106000.0,
            "last_signal": "LONG",
            "position": {"side": "LONG", "entry_price": 105000.0},
        }
        embed = create_status_embed(bot_state)
        pos_field = next((f for f in embed.fields if f.name == "📍 포지션"), None)
        assert pos_field is not None
        assert "LONG" in pos_field.value

    def test_no_position(self):
        bot_state = {
            "is_running": True,
            "is_paused": False,
            "current_price": 0,
            "last_signal": "WAIT",
            "position": None,
        }
        embed = create_status_embed(bot_state)
        pos_field = next((f for f in embed.fields if f.name == "📍 포지션"), None)
        assert pos_field is not None
        assert "없음" in pos_field.value

    def test_no_uptime_start(self):
        bot_state = {
            "is_running": True,
            "is_paused": False,
            "current_price": 0,
            "last_signal": "WAIT",
        }
        embed = create_status_embed(bot_state)
        uptime_field = next((f for f in embed.fields if f.name == "⏰ 가동시간"), None)
        assert uptime_field is not None
        assert "N/A" in uptime_field.value

    def test_signal_time_hours_ago(self):
        """마지막 신호가 시간 단위 전인 경우"""
        bot_state = {
            "is_running": True,
            "is_paused": False,
            "current_price": 105000.0,
            "last_signal": "LONG",
            "last_signal_time": datetime.now() - timedelta(hours=3),
        }
        embed = create_status_embed(bot_state)
        signal_field = next((f for f in embed.fields if f.name == "🔄 마지막 신호"), None)
        assert signal_field is not None
        assert "시간 전" in signal_field.value

    def test_position_short(self):
        bot_state = {
            "is_running": True,
            "is_paused": False,
            "current_price": 104000.0,
            "last_signal": "SHORT",
            "position": {"side": "SHORT", "entry_price": 105000.0},
        }
        embed = create_status_embed(bot_state)
        pos_field = next((f for f in embed.fields if f.name == "📍 포지션"), None)
        assert "SHORT" in pos_field.value


class TestCreatePositionEmbed:
    """create_position_embed 함수 테스트"""

    def test_no_position(self):
        bot_state = {"position": None, "last_signal": "WAIT"}
        embed = create_position_embed(bot_state)
        assert "포지션 없음" in embed.title
        assert embed.color.value == Colors.WARNING

    def test_position_empty_side(self):
        bot_state = {"position": {"side": None}, "last_signal": "WAIT"}
        embed = create_position_embed(bot_state)
        assert "포지션 없음" in embed.title

    def test_long_position(self):
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
                "timecut_at": datetime.now() + timedelta(minutes=30),
            },
        }
        embed = create_position_embed(bot_state)
        assert "현재 포지션" in embed.title
        assert embed.color.value == Colors.LONG

    def test_short_position(self):
        bot_state = {
            "current_price": 104000.0,
            "position": {
                "side": "SHORT",
                "entry_price": 105000.0,
                "quantity": 0.01,
                "leverage": 15,
                "entry_time": datetime.now(),
                "tp_price": 104580.0,
                "sl_price": 105420.0,
            },
        }
        embed = create_position_embed(bot_state)
        assert embed.color.value == Colors.SHORT

    def test_position_no_entry_time(self):
        bot_state = {
            "current_price": 106000.0,
            "position": {
                "side": "LONG",
                "entry_price": 105000.0,
                "quantity": 0.01,
                "leverage": 15,
            },
        }
        embed = create_position_embed(bot_state)
        duration_field = next((f for f in embed.fields if f.name == "⏱️ 경과시간"), None)
        assert duration_field is not None
        assert "N/A" in duration_field.value

    def test_position_with_size_key(self):
        """size 키 사용 (quantity 없을 때)"""
        bot_state = {
            "current_price": 106000.0,
            "position": {
                "side": "LONG",
                "entry_price": 105000.0,
                "size": 0.02,
                "leverage": 10,
            },
        }
        embed = create_position_embed(bot_state)
        qty_field = next((f for f in embed.fields if f.name == "📊 수량"), None)
        assert qty_field is not None
        assert "0.0200" in qty_field.value

    def test_position_hours_duration(self):
        """경과시간이 시간 단위인 경우"""
        bot_state = {
            "current_price": 106000.0,
            "position": {
                "side": "LONG",
                "entry_price": 105000.0,
                "quantity": 0.01,
                "leverage": 15,
                "entry_time": datetime.now() - timedelta(hours=2, minutes=15),
            },
        }
        embed = create_position_embed(bot_state)
        duration_field = next((f for f in embed.fields if f.name == "⏱️ 경과시간"), None)
        assert "2시간" in duration_field.value

    def test_position_expired_timecut(self):
        bot_state = {
            "current_price": 106000.0,
            "position": {
                "side": "LONG",
                "entry_price": 105000.0,
                "quantity": 0.01,
                "leverage": 15,
                "timecut_at": datetime.now() - timedelta(minutes=5),
            },
        }
        embed = create_position_embed(bot_state)
        timecut_field = next((f for f in embed.fields if f.name == "⏰ 타임컷"), None)
        assert "만료됨" in timecut_field.value


class TestCreateStatsEmbed:
    """create_stats_embed 함수 테스트"""

    def test_no_trades(self):
        stats_data = {"total_trades": 0}
        embed = create_stats_embed(stats_data, hours=24)
        assert "거래 없음" in embed.title
        assert embed.color.value == Colors.WARNING

    def test_positive_pnl(self):
        stats_data = {
            "total_trades": 10,
            "winners": 7,
            "losers": 3,
            "win_rate": 70.0,
            "total_pnl": 250.0,
            "best_trade": 3.5,
            "worst_trade": -1.2,
            "long_trades": 6,
            "short_trades": 4,
        }
        embed = create_stats_embed(stats_data, hours=48)
        assert "거래 통계" in embed.title
        assert embed.color.value == Colors.SUCCESS
        assert "48시간" in embed.description

    def test_negative_pnl(self):
        stats_data = {
            "total_trades": 5,
            "winners": 1,
            "losers": 4,
            "win_rate": 20.0,
            "total_pnl": -100.0,
            "best_trade": 1.0,
            "worst_trade": -5.0,
            "long_trades": 3,
            "short_trades": 2,
        }
        embed = create_stats_embed(stats_data, hours=12)
        assert embed.color.value == Colors.ERROR


class TestCreateHistoryEmbed:
    """create_history_embed 함수 테스트"""

    def test_no_trades(self):
        embed = create_history_embed([])
        assert "거래 내역 없음" in embed.title

    def test_with_trades(self):
        trades = [
            {
                "id": "uuid1",
                "side": "LONG",
                "entry_price": 105000.0,
                "exit_price": 105500.0,
                "exit_reason": "TAKE_PROFIT",
                "pnl": 7.5,
                "pnl_pct": 0.48,
                "exit_time": datetime.now() - timedelta(hours=1),
            },
            {
                "id": "uuid2",
                "side": "SHORT",
                "entry_price": 106000.0,
                "exit_price": 106500.0,
                "exit_reason": "STOP_LOSS",
                "pnl": -5.0,
                "pnl_pct": -0.47,
                "exit_time": datetime.now() - timedelta(minutes=30),
            },
        ]
        embed = create_history_embed(trades)
        assert "최근 거래" in embed.title
        assert len(embed.fields) == 2

    def test_trade_with_no_exit_time(self):
        trades = [
            {
                "id": "uuid1",
                "side": "LONG",
                "entry_price": 105000.0,
                "exit_price": None,
                "exit_reason": "MANUAL",
                "pnl": None,
                "pnl_pct": None,
                "exit_time": None,
            },
        ]
        embed = create_history_embed(trades)
        assert len(embed.fields) == 1

    def test_trade_with_tzinfo_exit_time(self):
        """exit_time에 tzinfo가 있는 경우 (replace 호출 필요)"""
        mock_time = MagicMock()
        mock_time.replace.return_value = datetime.now() - timedelta(hours=2, minutes=15)
        mock_time.__sub__ = lambda self, other: timedelta(hours=2, minutes=15)

        trades = [
            {
                "id": "uuid1",
                "side": "LONG",
                "entry_price": 105000.0,
                "exit_price": 105500.0,
                "exit_reason": "TP",
                "pnl": 5.0,
                "pnl_pct": 0.3,
                "exit_time": mock_time,
            },
        ]
        embed = create_history_embed(trades)
        assert len(embed.fields) == 1

    def test_trade_hours_ago(self):
        """exit_time이 시간 전인 경우"""
        trades = [
            {
                "id": "uuid1",
                "side": "LONG",
                "entry_price": 105000.0,
                "exit_price": 105500.0,
                "exit_reason": "TP",
                "pnl": 5.0,
                "pnl_pct": 0.3,
                "exit_time": datetime.now() - timedelta(hours=3, minutes=20),
            },
        ]
        embed = create_history_embed(trades)
        assert "시간" in embed.fields[0].value

    def test_trade_minutes_ago(self):
        """exit_time이 분 전인 경우"""
        trades = [
            {
                "id": "uuid1",
                "side": "SHORT",
                "entry_price": 106000.0,
                "exit_price": 105500.0,
                "exit_reason": "TP",
                "pnl": 5.0,
                "pnl_pct": 0.3,
                "exit_time": datetime.now() - timedelta(minutes=15),
            },
        ]
        embed = create_history_embed(trades)
        assert "분 전" in embed.fields[0].value


class TestCreateAccountEmbed:
    """create_account_embed 함수 테스트"""

    def test_with_positions(self):
        balance = {"balance": 10000.0, "available": 9500.0}
        positions = [
            {
                "symbol": "BTCUSDT",
                "side": "LONG",
                "entry_price": 105000.0,
                "current_price": 106000.0,
                "quantity": 0.01,
                "leverage": 15,
                "unrealized_pnl": 150.0,
                "pnl_pct": 1.43,
                "liquidation_price": 80000.0,
            }
        ]
        embed = create_account_embed(balance, positions)
        assert "계정 현황" in embed.title
        # 포지션 필드가 있어야 함
        assert len(embed.fields) > 4

    def test_no_positions(self):
        balance = {"balance": 10000.0, "available": 10000.0}
        positions = []
        embed = create_account_embed(balance, positions)
        assert "계정 현황" in embed.title
        # 포지션 없음 필드 확인
        pos_field = next((f for f in embed.fields if "포지션" in f.name), None)
        assert pos_field is not None

    def test_negative_unrealized_pnl(self):
        balance = {"balance": 10000.0, "available": 9000.0}
        positions = [
            {
                "symbol": "ETHUSDT",
                "side": "SHORT",
                "entry_price": 3000.0,
                "current_price": 3100.0,
                "quantity": 1.0,
                "leverage": 10,
                "unrealized_pnl": -100.0,
                "pnl_pct": -3.33,
                "liquidation_price": 3500.0,
            }
        ]
        embed = create_account_embed(balance, positions)
        assert "계정 현황" in embed.title

    def test_multiple_positions(self):
        balance = {"balance": 50000.0, "available": 40000.0}
        positions = [
            {
                "symbol": "BTCUSDT",
                "side": "LONG",
                "entry_price": 105000.0,
                "current_price": 106000.0,
                "quantity": 0.01,
                "leverage": 15,
                "unrealized_pnl": 150.0,
                "pnl_pct": 1.43,
                "liquidation_price": 80000.0,
            },
            {
                "symbol": "ETHUSDT",
                "side": "SHORT",
                "entry_price": 3000.0,
                "current_price": 2950.0,
                "quantity": 1.0,
                "leverage": 10,
                "unrealized_pnl": 50.0,
                "pnl_pct": 1.67,
                "liquidation_price": 3500.0,
            },
        ]
        embed = create_account_embed(balance, positions)
        # 2개 포지션이 번호로 표시되어야 함 (1. BTCUSDT, 2. ETHUSDT)
        symbol_fields = [f for f in embed.fields if f.name.startswith(("1.", "2."))]
        assert len(symbol_fields) == 2


class TestCreateBotListEmbed:
    """create_bot_list_embed 함수 테스트"""

    def test_with_bots(self):
        data = {
            "total_bots": 2,
            "running_bots": 1,
            "paused_bots": 1,
            "bots": [
                {
                    "name": "bot1",
                    "symbol": "BTCUSDT",
                    "risk_level": "medium",
                    "is_running": True,
                    "is_paused": False,
                },
                {
                    "name": "bot2",
                    "symbol": "ETHUSDT",
                    "risk_level": "high",
                    "is_running": True,
                    "is_paused": True,
                },
            ],
        }
        embed = create_bot_list_embed(data)
        assert "봇 목록" in embed.title
        assert "2개" in embed.description

    def test_no_bots(self):
        data = {
            "total_bots": 0,
            "running_bots": 0,
            "paused_bots": 0,
            "bots": [],
        }
        embed = create_bot_list_embed(data)
        info_field = next((f for f in embed.fields if "정보" in f.name), None)
        assert info_field is not None
        assert "등록된 봇이 없습니다" in info_field.value

    def test_stopped_bot(self):
        data = {
            "total_bots": 1,
            "running_bots": 0,
            "paused_bots": 0,
            "bots": [
                {
                    "name": "bot1",
                    "symbol": "BTCUSDT",
                    "risk_level": "low",
                    "is_running": False,
                    "is_paused": False,
                },
            ],
        }
        embed = create_bot_list_embed(data)
        assert len(embed.fields) >= 2


class TestCreateBotStatusEmbed:
    """create_bot_status_embed 함수 테스트"""

    def test_running(self):
        state = {
            "is_running": True,
            "is_paused": False,
            "symbol": "BTCUSDT",
            "risk_level": "medium",
            "leverage": 15,
            "current_price": 105000.0,
            "loop_count": 42,
            "last_signal": "LONG",
        }
        embed = create_bot_status_embed("test_bot", state)
        assert "test_bot" in embed.title
        assert embed.color.value == Colors.SUCCESS

    def test_paused(self):
        state = {
            "is_running": True,
            "is_paused": True,
            "symbol": "BTCUSDT",
            "risk_level": "medium",
            "leverage": 15,
            "current_price": 105000.0,
            "loop_count": 42,
            "last_signal": "WAIT",
        }
        embed = create_bot_status_embed("test_bot", state)
        assert embed.color.value == Colors.WARNING

    def test_stopped(self):
        state = {
            "is_running": False,
            "is_paused": False,
            "symbol": "BTCUSDT",
            "risk_level": "low",
            "leverage": 10,
            "current_price": 0,
            "loop_count": 0,
            "last_signal": "WAIT",
        }
        embed = create_bot_status_embed("test_bot", state)
        assert embed.color.value == Colors.ERROR

    def test_with_position(self):
        state = {
            "is_running": True,
            "is_paused": False,
            "symbol": "BTCUSDT",
            "risk_level": "medium",
            "leverage": 15,
            "current_price": 106000.0,
            "loop_count": 100,
            "last_signal": "LONG",
            "position": {"side": "LONG", "entry_price": 105000.0},
        }
        embed = create_bot_status_embed("test_bot", state)
        pos_field = next((f for f in embed.fields if "포지션" in f.name), None)
        assert pos_field is not None
        assert "LONG" in pos_field.value

    def test_no_position(self):
        state = {
            "is_running": True,
            "is_paused": False,
            "symbol": "BTCUSDT",
            "risk_level": "medium",
            "leverage": 15,
            "current_price": 105000.0,
            "loop_count": 10,
            "last_signal": "WAIT",
            "position": None,
        }
        embed = create_bot_status_embed("test_bot", state)
        # position 필드가 없어야 함 (None이므로)
        pos_fields = [f for f in embed.fields if "포지션" in f.name]
        assert len(pos_fields) == 0


# ============================================================================
# views.py 테스트 (ConfirmationView, DashboardView)
# ============================================================================


def _make_interaction(user_id=12345, user_name="TestUser#1234", roles=None):
    """테스트용 mock interaction 생성"""
    interaction = AsyncMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.user.id = user_id
    interaction.user.name = user_name
    interaction.user.__str__ = lambda self: user_name
    interaction.user.roles = roles or []
    interaction.response = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.followup = AsyncMock()
    interaction.followup.send = AsyncMock()
    return interaction


def _get_view_callback(view, button_name):
    """View에서 버튼 콜백을 가져오는 헬퍼.
    discord.ui.button 데코레이터가 Button 객체를 만들기 때문에
    view.children에서 콜백을 직접 추출해야 함."""
    for child in view.children:
        if hasattr(child, "label") and child.label and button_name in child.label:
            return child.callback
        # custom_id나 기타 속성으로도 검색
        if hasattr(child, "callback") and hasattr(child.callback, "__name__"):
            if button_name in child.callback.__name__:
                return child.callback
    raise ValueError(f"Button '{button_name}' not found in view children")


class TestConfirmationView:
    """ConfirmationView 테스트"""

    @pytest.mark.asyncio
    async def test_cancel_button(self):
        """취소 버튼 동작"""
        bot_state = {"is_paused": False}
        view = ConfirmationView("pause", bot_state)
        interaction = _make_interaction()

        callback = _get_view_callback(view, "취소")
        await callback(interaction)
        assert view.cancelled is True
        interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.discord_bot.views.check_permission", return_value=True)
    async def test_confirm_pause(self, mock_perm):
        """일시정지 확인"""
        bot_state = {"is_paused": False}
        view = ConfirmationView("pause", bot_state)
        interaction = _make_interaction()

        callback = _get_view_callback(view, "예, 실행")
        await callback(interaction)
        assert view.confirmed is True
        assert bot_state["is_paused"] is True

    @pytest.mark.asyncio
    @patch("src.discord_bot.views.check_permission", return_value=True)
    async def test_confirm_resume(self, mock_perm):
        """재시작 확인"""
        bot_state = {
            "is_paused": True,
            "paused_at": datetime.now() - timedelta(hours=1),
            "paused_by": "OtherUser",
        }
        view = ConfirmationView("resume", bot_state)
        interaction = _make_interaction()

        callback = _get_view_callback(view, "예, 실행")
        await callback(interaction)
        assert view.confirmed is True
        assert bot_state["is_paused"] is False

    @pytest.mark.asyncio
    @patch("src.discord_bot.views.check_permission", return_value=True)
    async def test_confirm_resume_no_pause_info(self, mock_perm):
        """일시정지 정보 없이 재시작"""
        bot_state = {"is_paused": False}
        view = ConfirmationView("resume", bot_state)
        interaction = _make_interaction()

        callback = _get_view_callback(view, "예, 실행")
        await callback(interaction)
        assert bot_state["is_paused"] is False

    @pytest.mark.asyncio
    @patch("src.discord_bot.views.check_permission", return_value=True)
    async def test_confirm_emergency_with_position(self, mock_perm):
        """긴급청산 확인 - 포지션 있음"""
        bot_state = {
            "is_paused": False,
            "position": {"side": "LONG", "entry_price": 105000.0},
        }
        view = ConfirmationView("emergency", bot_state)
        interaction = _make_interaction()

        callback = _get_view_callback(view, "예, 실행")
        await callback(interaction)
        assert bot_state["emergency_close"] is True
        assert bot_state["is_paused"] is True

    @pytest.mark.asyncio
    @patch("src.discord_bot.views.check_permission", return_value=True)
    async def test_confirm_emergency_no_position(self, mock_perm):
        """긴급청산 확인 - 포지션 없음"""
        bot_state = {"is_paused": False, "position": None}
        view = ConfirmationView("emergency", bot_state)
        interaction = _make_interaction()

        callback = _get_view_callback(view, "예, 실행")
        await callback(interaction)
        # emergency_close가 설정되지 않아야 함
        assert "emergency_close" not in bot_state

    @pytest.mark.asyncio
    @patch("src.discord_bot.views.check_permission", return_value=False)
    async def test_confirm_permission_denied(self, mock_perm):
        """권한 부족으로 확인 실패"""
        bot_state = {"is_paused": False}
        view = ConfirmationView("pause", bot_state)
        interaction = _make_interaction()

        callback = _get_view_callback(view, "예, 실행")
        await callback(interaction)
        assert view.confirmed is False
        assert bot_state["is_paused"] is False

    @pytest.mark.asyncio
    @patch("src.discord_bot.views.check_permission", return_value=True)
    async def test_confirm_button_exception(self, mock_perm):
        """확인 버튼에서 예외 발생"""
        bot_state = {"is_paused": False}
        view = ConfirmationView("pause", bot_state)
        interaction = _make_interaction()
        # 응답에서 예외 발생시키기
        interaction.response.send_message.side_effect = [
            Exception("test error"),
            None,  # 두 번째 호출 (에러 핸들러에서)
        ]

        callback = _get_view_callback(view, "예, 실행")
        # _handle_pause 호출 시 에러 -> except 블록 실행
        await callback(interaction)


class TestDashboardView:
    """DashboardView 테스트"""

    def _make_bot_client(self):
        """테스트용 mock bot client"""
        client = MagicMock()
        client.bot_state = {"is_running": True, "is_paused": False}
        client._get_status_embed = AsyncMock(return_value=discord.Embed(title="Status"))
        client._get_position_embed = AsyncMock(return_value=discord.Embed(title="Position"))
        client._get_stats_embed = AsyncMock(return_value=discord.Embed(title="Stats"))
        client._get_history_embed = AsyncMock(return_value=discord.Embed(title="History"))
        return client

    @pytest.mark.asyncio
    @patch("src.discord_bot.views.get_permission_config")
    async def test_status_button(self, mock_config):
        mock_config.return_value = MagicMock()
        client = self._make_bot_client()
        view = DashboardView(bot_client=client)
        interaction = _make_interaction()

        callback = _get_view_callback(view, "상태")
        await callback(interaction)
        interaction.response.defer.assert_called_once_with(ephemeral=True)
        client._get_status_embed.assert_called_once()
        interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.discord_bot.views.get_permission_config")
    async def test_position_button(self, mock_config):
        mock_config.return_value = MagicMock()
        client = self._make_bot_client()
        view = DashboardView(bot_client=client)
        interaction = _make_interaction()

        callback = _get_view_callback(view, "포지션")
        await callback(interaction)
        client._get_position_embed.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.discord_bot.views.get_permission_config")
    async def test_stats_button(self, mock_config):
        mock_config.return_value = MagicMock()
        client = self._make_bot_client()
        view = DashboardView(bot_client=client)
        interaction = _make_interaction()

        callback = _get_view_callback(view, "통계")
        await callback(interaction)
        client._get_stats_embed.assert_called_once_with(hours=24)

    @pytest.mark.asyncio
    @patch("src.discord_bot.views.get_permission_config")
    async def test_history_button(self, mock_config):
        mock_config.return_value = MagicMock()
        client = self._make_bot_client()
        view = DashboardView(bot_client=client)
        interaction = _make_interaction()

        callback = _get_view_callback(view, "내역")
        await callback(interaction)
        client._get_history_embed.assert_called_once_with(limit=5)

    @pytest.mark.asyncio
    @patch("src.discord_bot.views.get_permission_config")
    async def test_status_button_error(self, mock_config):
        """상태 버튼에서 예외 발생"""
        mock_config.return_value = MagicMock()
        client = self._make_bot_client()
        client._get_status_embed.side_effect = Exception("test error")
        view = DashboardView(bot_client=client)
        interaction = _make_interaction()

        callback = _get_view_callback(view, "상태")
        await callback(interaction)
        assert interaction.followup.send.called

    @pytest.mark.asyncio
    @patch("src.discord_bot.views.get_permission_config")
    async def test_position_button_error(self, mock_config):
        mock_config.return_value = MagicMock()
        client = self._make_bot_client()
        client._get_position_embed.side_effect = Exception("test error")
        view = DashboardView(bot_client=client)
        interaction = _make_interaction()

        callback = _get_view_callback(view, "포지션")
        await callback(interaction)
        assert interaction.followup.send.called

    @pytest.mark.asyncio
    @patch("src.discord_bot.views.get_permission_config")
    async def test_stats_button_error(self, mock_config):
        mock_config.return_value = MagicMock()
        client = self._make_bot_client()
        client._get_stats_embed.side_effect = Exception("test error")
        view = DashboardView(bot_client=client)
        interaction = _make_interaction()

        callback = _get_view_callback(view, "통계")
        await callback(interaction)
        assert interaction.followup.send.called

    @pytest.mark.asyncio
    @patch("src.discord_bot.views.get_permission_config")
    async def test_history_button_error(self, mock_config):
        mock_config.return_value = MagicMock()
        client = self._make_bot_client()
        client._get_history_embed.side_effect = Exception("test error")
        view = DashboardView(bot_client=client)
        interaction = _make_interaction()

        callback = _get_view_callback(view, "내역")
        await callback(interaction)
        assert interaction.followup.send.called

    @pytest.mark.asyncio
    @patch("src.discord_bot.views.check_permission", return_value=True)
    @patch("src.discord_bot.views.get_permission_config")
    async def test_pause_button_already_paused(self, mock_config, mock_perm):
        """이미 일시정지 상태"""
        mock_config.return_value = MagicMock()
        client = self._make_bot_client()
        client.bot_state["is_paused"] = True
        view = DashboardView(bot_client=client)
        interaction = _make_interaction()

        callback = _get_view_callback(view, "일시정지")
        await callback(interaction)
        interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.discord_bot.views.check_permission", return_value=True)
    @patch("src.discord_bot.views.get_permission_config")
    async def test_pause_button_shows_confirmation(self, mock_config, mock_perm):
        """일시정지 확인 대화상자 표시"""
        mock_config.return_value = MagicMock()
        client = self._make_bot_client()
        client.bot_state["is_paused"] = False
        view = DashboardView(bot_client=client)
        interaction = _make_interaction()

        callback = _get_view_callback(view, "일시정지")
        await callback(interaction)
        interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.discord_bot.views.check_permission", return_value=False)
    @patch("src.discord_bot.views.get_permission_config")
    async def test_pause_button_permission_denied(self, mock_config, mock_perm):
        mock_config.return_value = MagicMock()
        client = self._make_bot_client()
        view = DashboardView(bot_client=client)
        interaction = _make_interaction()

        callback = _get_view_callback(view, "일시정지")
        await callback(interaction)
        call_args = interaction.response.send_message.call_args
        assert "권한" in call_args[0][0]

    @pytest.mark.asyncio
    @patch("src.discord_bot.views.check_permission", return_value=True)
    @patch("src.discord_bot.views.get_permission_config")
    async def test_pause_button_exception(self, mock_config, mock_perm):
        """일시정지 버튼 예외"""
        mock_config.return_value = MagicMock()
        client = self._make_bot_client()
        client.bot_state["is_paused"] = False
        view = DashboardView(bot_client=client)
        interaction = _make_interaction()
        interaction.response.send_message.side_effect = [Exception("test"), None]

        callback = _get_view_callback(view, "일시정지")
        await callback(interaction)

    @pytest.mark.asyncio
    @patch("src.discord_bot.views.check_permission", return_value=True)
    @patch("src.discord_bot.views.get_permission_config")
    async def test_resume_button_already_running(self, mock_config, mock_perm):
        """이미 실행 중인 봇에서 재시작 버튼"""
        mock_config.return_value = MagicMock()
        client = self._make_bot_client()
        client.bot_state["is_paused"] = False
        view = DashboardView(bot_client=client)
        interaction = _make_interaction()

        callback = _get_view_callback(view, "재시작")
        await callback(interaction)
        interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.discord_bot.views.check_permission", return_value=True)
    @patch("src.discord_bot.views.get_permission_config")
    async def test_resume_button_shows_confirmation(self, mock_config, mock_perm):
        """재시작 확인 대화상자 표시"""
        mock_config.return_value = MagicMock()
        client = self._make_bot_client()
        client.bot_state["is_paused"] = True
        view = DashboardView(bot_client=client)
        interaction = _make_interaction()

        callback = _get_view_callback(view, "재시작")
        await callback(interaction)
        interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.discord_bot.views.check_permission", return_value=False)
    @patch("src.discord_bot.views.get_permission_config")
    async def test_resume_button_permission_denied(self, mock_config, mock_perm):
        mock_config.return_value = MagicMock()
        client = self._make_bot_client()
        client.bot_state["is_paused"] = True
        view = DashboardView(bot_client=client)
        interaction = _make_interaction()

        callback = _get_view_callback(view, "재시작")
        await callback(interaction)
        call_args = interaction.response.send_message.call_args
        assert "권한" in call_args[0][0]

    @pytest.mark.asyncio
    @patch("src.discord_bot.views.check_permission", return_value=True)
    @patch("src.discord_bot.views.get_permission_config")
    async def test_resume_button_exception(self, mock_config, mock_perm):
        mock_config.return_value = MagicMock()
        client = self._make_bot_client()
        client.bot_state["is_paused"] = True
        view = DashboardView(bot_client=client)
        interaction = _make_interaction()
        interaction.response.send_message.side_effect = [Exception("test"), None]

        callback = _get_view_callback(view, "재시작")
        await callback(interaction)

    @pytest.mark.asyncio
    @patch("src.discord_bot.views.check_permission", return_value=True)
    @patch("src.discord_bot.views.get_permission_config")
    async def test_emergency_button_no_position(self, mock_config, mock_perm):
        """긴급청산 - 포지션 없음"""
        mock_config.return_value = MagicMock()
        client = self._make_bot_client()
        client.bot_state["position"] = None
        view = DashboardView(bot_client=client)
        interaction = _make_interaction()

        callback = _get_view_callback(view, "긴급청산")
        await callback(interaction)
        interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.discord_bot.views.check_permission", return_value=True)
    @patch("src.discord_bot.views.get_permission_config")
    async def test_emergency_button_with_position(self, mock_config, mock_perm):
        """긴급청산 확인 대화상자"""
        mock_config.return_value = MagicMock()
        client = self._make_bot_client()
        client.bot_state["position"] = {
            "side": "LONG",
            "entry_price": 105000.0,
        }
        client.bot_state["current_price"] = 106000.0
        view = DashboardView(bot_client=client)
        interaction = _make_interaction()

        callback = _get_view_callback(view, "긴급청산")
        await callback(interaction)
        interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.discord_bot.views.check_permission", return_value=True)
    @patch("src.discord_bot.views.get_permission_config")
    async def test_emergency_button_short_position(self, mock_config, mock_perm):
        """긴급청산 SHORT 포지션"""
        mock_config.return_value = MagicMock()
        client = self._make_bot_client()
        client.bot_state["position"] = {
            "side": "SHORT",
            "entry_price": 105000.0,
        }
        client.bot_state["current_price"] = 104000.0
        view = DashboardView(bot_client=client)
        interaction = _make_interaction()

        callback = _get_view_callback(view, "긴급청산")
        await callback(interaction)
        interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.discord_bot.views.check_permission", return_value=False)
    @patch("src.discord_bot.views.get_permission_config")
    async def test_emergency_button_permission_denied(self, mock_config, mock_perm):
        mock_config.return_value = MagicMock()
        client = self._make_bot_client()
        client.bot_state["position"] = {"side": "LONG", "entry_price": 105000.0}
        view = DashboardView(bot_client=client)
        interaction = _make_interaction()

        callback = _get_view_callback(view, "긴급청산")
        await callback(interaction)
        call_args = interaction.response.send_message.call_args
        assert "권한" in call_args[0][0]

    @pytest.mark.asyncio
    @patch("src.discord_bot.views.check_permission", return_value=True)
    @patch("src.discord_bot.views.get_permission_config")
    async def test_emergency_button_exception(self, mock_config, mock_perm):
        mock_config.return_value = MagicMock()
        client = self._make_bot_client()
        client.bot_state["position"] = {"side": "LONG", "entry_price": 105000.0}
        client.bot_state["current_price"] = 106000.0
        view = DashboardView(bot_client=client)
        interaction = _make_interaction()
        interaction.response.send_message.side_effect = [Exception("err"), None]

        callback = _get_view_callback(view, "긴급청산")
        await callback(interaction)


# ============================================================================
# client.py 테스트 (TradingBotClient)
# ============================================================================


def _create_client(bot_state=None, trade_db=None, binance_client=None, bot_manager=None):
    """테스트용 TradingBotClient 생성 (명령어 등록을 패치)"""
    bot_state = bot_state or {}
    with patch("src.discord_bot.client.register_monitoring_commands"), \
         patch("src.discord_bot.client.register_control_commands"), \
         patch("src.discord_bot.client.register_multibot_commands"):
        return RefactoredClient(
            bot_state=bot_state,
            trade_db=trade_db,
            binance_client=binance_client,
            bot_manager=bot_manager,
        )


class TestRefactoredClientInit:
    """리팩토링된 TradingBotClient 초기화 테스트"""

    def test_init_basic(self):
        client = _create_client({"is_running": True})
        assert client.bot_state == {"is_running": True}
        assert client.trade_db is None
        assert client.binance_client is None

    def test_init_with_all_deps(self):
        mock_db = Mock()
        mock_binance = Mock()
        mock_manager = Mock()
        client = _create_client(
            {"is_running": True},
            trade_db=mock_db,
            binance_client=mock_binance,
            bot_manager=mock_manager,
        )
        assert client.trade_db is mock_db
        assert client.binance_client is mock_binance
        assert client.bot_manager is mock_manager


class TestRefactoredClientEmbedGetters:
    """리팩토링된 클라이언트의 embed getter 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_get_status_embed(self):
        client = _create_client({
            "is_running": True,
            "is_paused": False,
            "current_price": 105000.0,
            "last_signal": "LONG",
        })
        embed = await client._get_status_embed()
        assert embed.title == "🤖 봇 상태"

    @pytest.mark.asyncio
    async def test_get_position_embed(self):
        client = _create_client({"position": None, "last_signal": "WAIT"})
        embed = await client._get_position_embed()
        assert "포지션 없음" in embed.title

    @pytest.mark.asyncio
    async def test_get_stats_embed_no_db(self):
        client = _create_client({}, trade_db=None)
        embed = await client._get_stats_embed()
        assert "데이터베이스 연결 안 됨" in embed.title

    @pytest.mark.asyncio
    async def test_get_stats_embed_with_db(self):
        mock_db = AsyncMock()
        mock_db.get_statistics.return_value = {
            "total_trades": 5,
            "winners": 3,
            "losers": 2,
            "win_rate": 60.0,
            "total_pnl": 100.0,
            "best_trade": 2.0,
            "worst_trade": -1.0,
            "long_trades": 3,
            "short_trades": 2,
        }
        client = _create_client({}, trade_db=mock_db)
        embed = await client._get_stats_embed(hours=48)
        assert "거래 통계" in embed.title

    @pytest.mark.asyncio
    async def test_get_history_embed_no_db(self):
        client = _create_client({}, trade_db=None)
        embed = await client._get_history_embed()
        assert "데이터베이스 연결 안 됨" in embed.title

    @pytest.mark.asyncio
    async def test_get_history_embed_with_db(self):
        mock_db = AsyncMock()
        mock_db.get_recent_trades.return_value = [
            {
                "id": "1",
                "side": "LONG",
                "entry_price": 105000.0,
                "exit_price": 105500.0,
                "exit_reason": "TP",
                "pnl": 5.0,
                "pnl_pct": 0.3,
                "exit_time": datetime.now(),
            }
        ]
        client = _create_client({}, trade_db=mock_db)
        embed = await client._get_history_embed(limit=5)
        assert "최근 거래" in embed.title

    @pytest.mark.asyncio
    async def test_get_history_embed_limit_capped(self):
        """limit가 10을 초과하면 10으로 제한"""
        mock_db = AsyncMock()
        mock_db.get_recent_trades.return_value = []
        client = _create_client({}, trade_db=mock_db)
        await client._get_history_embed(limit=20)
        mock_db.get_recent_trades.assert_called_once_with(limit=10)

    @pytest.mark.asyncio
    async def test_get_account_embed_no_binance(self):
        client = _create_client({}, binance_client=None)
        embed = await client._get_account_embed()
        assert "Binance 클라이언트 연결 안 됨" in embed.title

    @pytest.mark.asyncio
    async def test_get_account_embed_success(self):
        mock_binance = AsyncMock()
        mock_binance.get_account_balance.return_value = {
            "balance": 10000.0,
            "available": 9500.0,
        }
        mock_binance.get_all_positions.return_value = []
        client = _create_client({}, binance_client=mock_binance)
        embed = await client._get_account_embed()
        assert "계정 현황" in embed.title

    @pytest.mark.asyncio
    async def test_get_account_embed_error(self):
        mock_binance = AsyncMock()
        mock_binance.get_account_balance.side_effect = Exception("API error")
        client = _create_client({}, binance_client=mock_binance)
        embed = await client._get_account_embed()
        assert "계정 조회 실패" in embed.title


class TestRefactoredClientCommands:
    """리팩토링된 클라이언트의 명령어 구현 테스트"""

    @pytest.mark.asyncio
    async def test_dashboard_command_running(self):
        client = _create_client({
            "is_running": True,
            "is_paused": False,
            "current_price": 105000.0,
            "last_signal": "LONG",
            "last_signal_time": datetime.now() - timedelta(minutes=10),
            "position": None,
        })
        interaction = _make_interaction()
        await client._dashboard_command(interaction)
        interaction.response.defer.assert_called_once()
        interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_dashboard_command_paused(self):
        client = _create_client({
            "is_running": True,
            "is_paused": True,
            "current_price": 105000.0,
            "last_signal": "WAIT",
            "position": None,
        })
        interaction = _make_interaction()
        await client._dashboard_command(interaction)
        interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_dashboard_command_stopped(self):
        client = _create_client({
            "is_running": False,
            "is_paused": False,
            "current_price": 0,
            "last_signal": "WAIT",
        })
        interaction = _make_interaction()
        await client._dashboard_command(interaction)
        interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_dashboard_command_with_position(self):
        client = _create_client({
            "is_running": True,
            "is_paused": False,
            "current_price": 106000.0,
            "last_signal": "LONG",
            "position": {"side": "LONG", "entry_price": 105000.0},
        })
        interaction = _make_interaction()
        await client._dashboard_command(interaction)
        interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_dashboard_command_short_position(self):
        client = _create_client({
            "is_running": True,
            "is_paused": False,
            "current_price": 104000.0,
            "last_signal": "SHORT",
            "position": {"side": "SHORT", "entry_price": 105000.0},
        })
        interaction = _make_interaction()
        await client._dashboard_command(interaction)
        interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_dashboard_command_signal_hours_ago(self):
        client = _create_client({
            "is_running": True,
            "is_paused": False,
            "current_price": 105000.0,
            "last_signal": "LONG",
            "last_signal_time": datetime.now() - timedelta(hours=3),
            "position": None,
        })
        interaction = _make_interaction()
        await client._dashboard_command(interaction)
        interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_dashboard_command_error(self):
        client = _create_client({
            "is_running": True,
            "is_paused": False,
            "current_price": 105000.0,
            "last_signal": "WAIT",
        })
        interaction = _make_interaction()
        interaction.followup.send.side_effect = [Exception("test"), None]
        # 에러 경로도 호출됨
        await client._dashboard_command(interaction)

    @pytest.mark.asyncio
    async def test_status_command(self):
        client = _create_client({
            "is_running": True,
            "is_paused": False,
            "current_price": 105000.0,
            "last_signal": "WAIT",
        })
        interaction = _make_interaction()
        await client._status_command(interaction)
        interaction.response.defer.assert_called_once()
        interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_status_command_error(self):
        client = _create_client({
            "is_running": True,
            "is_paused": False,
            "current_price": 105000.0,
            "last_signal": "WAIT",
        })
        interaction = _make_interaction()
        interaction.followup.send.side_effect = [Exception("err"), None]
        await client._status_command(interaction)

    @pytest.mark.asyncio
    async def test_position_command(self):
        client = _create_client({"position": None, "last_signal": "WAIT"})
        interaction = _make_interaction()
        await client._position_command(interaction)
        interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_position_command_error(self):
        client = _create_client({"position": None, "last_signal": "WAIT"})
        interaction = _make_interaction()
        interaction.followup.send.side_effect = [Exception("err"), None]
        await client._position_command(interaction)

    @pytest.mark.asyncio
    async def test_stats_command(self):
        mock_db = AsyncMock()
        mock_db.get_statistics.return_value = {"total_trades": 0}
        client = _create_client({}, trade_db=mock_db)
        interaction = _make_interaction()
        await client._stats_command(interaction, hours=12)
        interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_stats_command_error(self):
        mock_db = AsyncMock()
        mock_db.get_statistics.side_effect = Exception("DB error")
        client = _create_client({}, trade_db=mock_db)
        interaction = _make_interaction()
        await client._stats_command(interaction, hours=24)
        # 에러 메시지 전송
        assert interaction.followup.send.called

    @pytest.mark.asyncio
    async def test_history_command(self):
        mock_db = AsyncMock()
        mock_db.get_recent_trades.return_value = []
        client = _create_client({}, trade_db=mock_db)
        interaction = _make_interaction()
        await client._history_command(interaction, count=5)
        interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_history_command_error(self):
        mock_db = AsyncMock()
        mock_db.get_recent_trades.side_effect = Exception("DB error")
        client = _create_client({}, trade_db=mock_db)
        interaction = _make_interaction()
        await client._history_command(interaction, count=5)
        assert interaction.followup.send.called

    @pytest.mark.asyncio
    async def test_stop_command(self):
        client = _create_client({"is_paused": False})
        interaction = _make_interaction()
        await client._stop_command(interaction)
        assert client.bot_state["is_paused"] is True
        interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_command_error(self):
        client = _create_client({"is_paused": False})
        interaction = _make_interaction()
        interaction.followup.send.side_effect = [Exception("err"), None]
        await client._stop_command(interaction)

    @pytest.mark.asyncio
    async def test_start_command(self):
        client = _create_client({"is_paused": True})
        interaction = _make_interaction()
        await client._start_command(interaction)
        assert client.bot_state["is_paused"] is False
        interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_command_was_paused_with_time(self):
        client = _create_client({
            "is_paused": True,
            "paused_by": "OtherUser",
            "paused_at": datetime.now() - timedelta(hours=1),
        })
        interaction = _make_interaction()
        await client._start_command(interaction)
        assert client.bot_state["is_paused"] is False

    @pytest.mark.asyncio
    async def test_start_command_was_not_paused(self):
        client = _create_client({"is_paused": False})
        interaction = _make_interaction()
        await client._start_command(interaction)
        assert client.bot_state["is_paused"] is False

    @pytest.mark.asyncio
    async def test_start_command_error(self):
        client = _create_client({"is_paused": True})
        interaction = _make_interaction()
        interaction.followup.send.side_effect = [Exception("err"), None]
        await client._start_command(interaction)

    @pytest.mark.asyncio
    async def test_emergency_command_no_position(self):
        client = _create_client({"position": None})
        interaction = _make_interaction()
        await client._emergency_command(interaction)
        assert "emergency_close" not in client.bot_state

    @pytest.mark.asyncio
    async def test_emergency_command_with_position(self):
        client = _create_client({
            "is_paused": False,
            "position": {
                "side": "LONG",
                "entry_price": 105000.0,
                "quantity": 0.01,
            },
        })
        interaction = _make_interaction()
        await client._emergency_command(interaction)
        assert client.bot_state["emergency_close"] is True
        assert client.bot_state["is_paused"] is True

    @pytest.mark.asyncio
    async def test_emergency_command_short_position(self):
        client = _create_client({
            "is_paused": False,
            "position": {
                "side": "SHORT",
                "entry_price": 105000.0,
                "size": 0.01,
            },
        })
        interaction = _make_interaction()
        await client._emergency_command(interaction)
        assert client.bot_state["emergency_close"] is True

    @pytest.mark.asyncio
    async def test_emergency_command_error(self):
        client = _create_client({
            "is_paused": False,
            "position": {"side": "LONG", "entry_price": 105000.0, "quantity": 0.01},
        })
        interaction = _make_interaction()
        interaction.followup.send.side_effect = [Exception("err"), None]
        await client._emergency_command(interaction)

    @pytest.mark.asyncio
    async def test_account_command(self):
        mock_binance = AsyncMock()
        mock_binance.get_account_balance.return_value = {
            "balance": 10000.0,
            "available": 9500.0,
        }
        mock_binance.get_all_positions.return_value = []
        client = _create_client({}, binance_client=mock_binance)
        interaction = _make_interaction()
        await client._account_command(interaction)
        interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_account_command_error(self):
        client = _create_client({}, binance_client=None)
        interaction = _make_interaction()
        interaction.followup.send.side_effect = [Exception("err"), None]
        await client._account_command(interaction)




class TestControlCommandsBotManagerIntegration:
    """P1-1: 싱글봇 제어 명령어가 BotManager를 통해 BotInstance를 실제 제어하는지 테스트"""

    def _make_bot_manager(self):
        """BotManager mock with one bot."""
        mock_bot = MagicMock()
        mock_bot.bot_name = "btc-default"
        mock_bot.pause = MagicMock()
        mock_bot.resume = MagicMock()
        mock_bot.request_emergency_close = MagicMock()

        mock_manager = MagicMock()
        mock_manager.bot_count = 1
        mock_manager.bots = {"btc-default": mock_bot}
        mock_manager.pause_bot = MagicMock()
        mock_manager.resume_bot = MagicMock()
        mock_manager.get_bot = MagicMock(return_value=mock_bot)
        return mock_manager, mock_bot

    @pytest.mark.asyncio
    async def test_stop_command_calls_bot_manager_pause(self):
        """일시정지 시 BotManager.pause_bot 호출 확인"""
        mock_manager, mock_bot = self._make_bot_manager()
        client = _create_client({"is_paused": False}, bot_manager=mock_manager)
        interaction = _make_interaction()
        await client._stop_command(interaction)

        mock_manager.pause_bot.assert_called_once_with("btc-default")
        assert client.bot_state["is_paused"] is True

    @pytest.mark.asyncio
    async def test_start_command_calls_bot_manager_resume(self):
        """재시작 시 BotManager.resume_bot 호출 확인"""
        mock_manager, mock_bot = self._make_bot_manager()
        client = _create_client({"is_paused": True}, bot_manager=mock_manager)
        interaction = _make_interaction()
        await client._start_command(interaction)

        mock_manager.resume_bot.assert_called_once_with("btc-default")
        assert client.bot_state["is_paused"] is False

    @pytest.mark.asyncio
    async def test_emergency_command_calls_bot_request_emergency_close(self):
        """긴급청산 시 bot.request_emergency_close() 호출 확인"""
        mock_manager, mock_bot = self._make_bot_manager()
        client = _create_client({
            "is_paused": False,
            "position": {"side": "LONG", "entry_price": 105000.0, "quantity": 0.01},
        }, bot_manager=mock_manager)
        interaction = _make_interaction()
        await client._emergency_command(interaction)

        mock_manager.get_bot.assert_called_once_with("btc-default")
        mock_bot.request_emergency_close.assert_called_once()
        assert client.bot_state["emergency_close"] is True
        assert client.bot_state["is_paused"] is True

    @pytest.mark.asyncio
    async def test_stop_command_without_bot_manager(self):
        """BotManager 없이도 bot_state는 정상 업데이트"""
        client = _create_client({"is_paused": False}, bot_manager=None)
        interaction = _make_interaction()
        await client._stop_command(interaction)
        assert client.bot_state["is_paused"] is True

    @pytest.mark.asyncio
    async def test_start_command_without_bot_manager(self):
        """BotManager 없이도 bot_state는 정상 업데이트"""
        client = _create_client({"is_paused": True}, bot_manager=None)
        interaction = _make_interaction()
        await client._start_command(interaction)
        assert client.bot_state["is_paused"] is False

    @pytest.mark.asyncio
    async def test_emergency_command_without_bot_manager(self):
        """BotManager 없이도 bot_state는 정상 업데이트"""
        client = _create_client({
            "is_paused": False,
            "position": {"side": "LONG", "entry_price": 105000.0, "quantity": 0.01},
        }, bot_manager=None)
        interaction = _make_interaction()
        await client._emergency_command(interaction)
        assert client.bot_state["emergency_close"] is True

    @pytest.mark.asyncio
    async def test_emergency_command_no_position_skips_bot_manager(self):
        """포지션이 없으면 BotManager 호출 안 함"""
        mock_manager, mock_bot = self._make_bot_manager()
        client = _create_client({"position": None}, bot_manager=mock_manager)
        interaction = _make_interaction()
        await client._emergency_command(interaction)

        mock_manager.get_bot.assert_not_called()
        mock_bot.request_emergency_close.assert_not_called()

    @pytest.mark.asyncio
    async def test_stop_command_empty_bots(self):
        """봇이 0개일 때 BotManager 호출 스킵"""
        mock_manager = MagicMock()
        mock_manager.bot_count = 0
        mock_manager.bots = {}
        client = _create_client({"is_paused": False}, bot_manager=mock_manager)
        interaction = _make_interaction()
        await client._stop_command(interaction)

        mock_manager.pause_bot.assert_not_called()
        assert client.bot_state["is_paused"] is True


class TestHttpStatusConstants:
    """P1-2: HTTP 상태코드 상수가 올바르게 사용되는지 테스트"""

    def test_http_constants_defined(self):
        from src.discord_bot.client import HTTP_CLIENT_ERROR, HTTP_SERVER_ERROR
        assert HTTP_SERVER_ERROR == 500
        assert HTTP_CLIENT_ERROR == 400

    def test_http_constants_different_from_discord_constants(self):
        from src.discord_bot.client import (
            HTTP_CLIENT_ERROR,
            HTTP_SERVER_ERROR,
            MAX_EMBED_FIELD_LENGTH,
            MAX_MESSAGE_LENGTH,
        )
        # 값은 우연히 같을 수 있지만, 의미적으로 분리된 상수임을 확인
        assert HTTP_SERVER_ERROR == 500
        assert HTTP_CLIENT_ERROR == 400
        assert MAX_MESSAGE_LENGTH == 500  # Discord 메시지 길이
        assert MAX_EMBED_FIELD_LENGTH == 400  # Discord embed 필드 길이

    @pytest.mark.asyncio
    async def test_api_call_server_error_500(self):
        """HTTP 500이 서버 오류로 처리됨"""
        client = _create_client({})

        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Internal Server Error")

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.request = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=False),
        ))

        with patch("src.discord_bot.client.aiohttp.ClientSession", return_value=mock_session):
            with pytest.raises(Exception, match="API 서버 오류"):
                await client._call_bot_api("GET", "/api/test")

    @pytest.mark.asyncio
    async def test_api_call_client_error_404(self):
        """HTTP 404가 클라이언트 오류로 처리됨"""
        client = _create_client({})

        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.text = AsyncMock(return_value="Not Found")

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.request = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=False),
        ))

        with patch("src.discord_bot.client.aiohttp.ClientSession", return_value=mock_session):
            with pytest.raises(ValueError, match="API 요청 오류"):
                await client._call_bot_api("GET", "/api/test")

    @pytest.mark.asyncio
    async def test_api_call_success_200(self):
        """HTTP 200이 정상 처리됨"""
        client = _create_client({})

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"ok": True})

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.request = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=False),
        ))

        with patch("src.discord_bot.client.aiohttp.ClientSession", return_value=mock_session):
            result = await client._call_bot_api("GET", "/api/test")
            assert result == {"ok": True}

class TestRefactoredClientMultibotCommands:
    """멀티봇 관련 명령어 테스트"""

    @pytest.mark.asyncio
    async def test_bot_list_command(self):
        client = _create_client({})
        client._call_bot_api = AsyncMock(return_value={
            "data": {
                "total_bots": 1,
                "running_bots": 1,
                "paused_bots": 0,
                "bots": [
                    {
                        "name": "bot1",
                        "symbol": "BTCUSDT",
                        "risk_level": "medium",
                        "is_running": True,
                        "is_paused": False,
                    }
                ],
            }
        })
        interaction = _make_interaction()
        await client._bot_list_command(interaction)
        interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_bot_list_command_error(self):
        client = _create_client({})
        client._call_bot_api = AsyncMock(side_effect=Exception("API error"))
        interaction = _make_interaction()
        await client._bot_list_command(interaction)
        assert interaction.followup.send.called

    @pytest.mark.asyncio
    async def test_bot_status_command(self):
        client = _create_client({})
        client._call_bot_api = AsyncMock(return_value={
            "data": {
                "state": {
                    "is_running": True,
                    "is_paused": False,
                    "symbol": "BTCUSDT",
                    "risk_level": "medium",
                    "leverage": 15,
                    "current_price": 105000.0,
                    "loop_count": 42,
                    "last_signal": "LONG",
                }
            }
        })
        interaction = _make_interaction()
        await client._bot_status_command(interaction, "test_bot")
        interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_bot_status_command_error(self):
        client = _create_client({})
        client._call_bot_api = AsyncMock(side_effect=Exception("API error"))
        interaction = _make_interaction()
        await client._bot_status_command(interaction, "test_bot")
        assert interaction.followup.send.called

    @pytest.mark.asyncio
    async def test_bot_start_command(self):
        client = _create_client({})
        client._call_bot_api = AsyncMock(return_value={"status": "ok"})
        interaction = _make_interaction()
        await client._bot_start_command(interaction, "test_bot")
        interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_bot_start_command_error(self):
        client = _create_client({})
        client._call_bot_api = AsyncMock(side_effect=Exception("API error"))
        interaction = _make_interaction()
        await client._bot_start_command(interaction, "test_bot")
        assert interaction.followup.send.called

    @pytest.mark.asyncio
    async def test_bot_stop_command(self):
        client = _create_client({})
        client._call_bot_api = AsyncMock(return_value={"status": "ok"})
        interaction = _make_interaction()
        await client._bot_stop_command(interaction, "test_bot")
        interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_bot_stop_command_error(self):
        client = _create_client({})
        client._call_bot_api = AsyncMock(side_effect=Exception("API error"))
        interaction = _make_interaction()
        await client._bot_stop_command(interaction, "test_bot")
        assert interaction.followup.send.called

    @pytest.mark.asyncio
    async def test_bot_pause_command(self):
        client = _create_client({})
        client._call_bot_api = AsyncMock(return_value={"status": "ok"})
        interaction = _make_interaction()
        await client._bot_pause_command(interaction, "test_bot")
        interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_bot_pause_command_error(self):
        client = _create_client({})
        client._call_bot_api = AsyncMock(side_effect=Exception("API error"))
        interaction = _make_interaction()
        await client._bot_pause_command(interaction, "test_bot")
        assert interaction.followup.send.called

    @pytest.mark.asyncio
    async def test_bot_resume_command(self):
        client = _create_client({})
        client._call_bot_api = AsyncMock(return_value={"status": "ok"})
        interaction = _make_interaction()
        await client._bot_resume_command(interaction, "test_bot")
        interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_bot_resume_command_error(self):
        client = _create_client({})
        client._call_bot_api = AsyncMock(side_effect=Exception("API error"))
        interaction = _make_interaction()
        await client._bot_resume_command(interaction, "test_bot")
        assert interaction.followup.send.called

    @pytest.mark.asyncio
    async def test_start_all_command(self):
        client = _create_client({})
        client._call_bot_api = AsyncMock(return_value={
            "data": {"started": 3}
        })
        interaction = _make_interaction()
        await client._start_all_command(interaction)
        interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_all_command_error(self):
        client = _create_client({})
        client._call_bot_api = AsyncMock(side_effect=Exception("API error"))
        interaction = _make_interaction()
        await client._start_all_command(interaction)
        assert interaction.followup.send.called

    @pytest.mark.asyncio
    async def test_stop_all_command(self):
        client = _create_client({})
        client._call_bot_api = AsyncMock(return_value={
            "data": {"stopped": 3}
        })
        interaction = _make_interaction()
        await client._stop_all_command(interaction)
        interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_all_command_error(self):
        client = _create_client({})
        client._call_bot_api = AsyncMock(side_effect=Exception("API error"))
        interaction = _make_interaction()
        await client._stop_all_command(interaction)
        assert interaction.followup.send.called


class TestRefactoredClientCallBotApi:
    """_call_bot_api REST API 호출 테스트"""

    @pytest.mark.asyncio
    async def test_successful_api_call(self):
        client = _create_client({})

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"result": "ok"})

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.request = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=False),
        ))

        with patch("src.discord_bot.client.aiohttp.ClientSession", return_value=mock_session):
            result = await client._call_bot_api("GET", "/api/test")
            assert result == {"result": "ok"}

    @pytest.mark.asyncio
    async def test_api_call_error_status(self):
        client = _create_client({})

        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.text = AsyncMock(return_value="Not found")

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.request = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=False),
        ))

        with patch("src.discord_bot.client.aiohttp.ClientSession", return_value=mock_session):
            with pytest.raises(ValueError, match="API 요청 오류"):
                await client._call_bot_api("GET", "/api/test")

    @pytest.mark.asyncio
    async def test_api_call_client_error(self):
        import aiohttp
        client = _create_client({})

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.request = MagicMock(side_effect=aiohttp.ClientError("Connection error"))

        with patch("src.discord_bot.client.aiohttp.ClientSession", return_value=mock_session):
            with pytest.raises(Exception, match="API 서버 연결 실패"):
                await client._call_bot_api("POST", "/api/test")


class TestRefactoredClientEvents:
    """이벤트 핸들러 테스트"""

    @pytest.mark.asyncio
    async def test_on_ready(self):
        client = _create_client({})
        # client.user은 discord.Client에서 property라 직접 설정 불가, _user 사용
        mock_user = MagicMock()
        mock_user.__str__ = lambda self: "TestBot#1234"
        type(client).user = property(lambda self: mock_user)
        type(client).guilds = property(lambda self: [MagicMock(), MagicMock()])
        client.tree = AsyncMock()
        client.tree.sync = AsyncMock(return_value=[MagicMock(), MagicMock()])

        await client.on_ready()
        client.tree.sync.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_ready_sync_error(self):
        client = _create_client({})
        mock_user = MagicMock()
        type(client).user = property(lambda self: mock_user)
        type(client).guilds = property(lambda self: [])
        client.tree = AsyncMock()
        client.tree.sync = AsyncMock(side_effect=Exception("Sync failed"))

        # 예외가 전파되지 않아야 함 (로그만 남김)
        await client.on_ready()

    @pytest.mark.asyncio
    async def test_on_command_error(self):
        client = _create_client({})
        interaction = _make_interaction()
        error = MagicMock(spec=discord.app_commands.AppCommandError)
        error.__str__ = lambda self: "Test error"

        await client.on_command_error(interaction, error)
        interaction.response.send_message.assert_called_once()


class TestStartDiscordBotFunction:
    """start_discord_bot 함수 테스트"""

    @pytest.mark.asyncio
    async def test_start_discord_bot(self):
        with patch("src.discord_bot.client.register_monitoring_commands"), \
             patch("src.discord_bot.client.register_control_commands"), \
             patch("src.discord_bot.client.register_multibot_commands"), \
             patch.object(RefactoredClient, "start", new_callable=AsyncMock) as mock_start:
            await start_discord_bot(token="test_token", bot_state={})
            mock_start.assert_called_once_with("test_token")

    @pytest.mark.asyncio
    async def test_start_discord_bot_error(self):
        with patch("src.discord_bot.client.register_monitoring_commands"), \
             patch("src.discord_bot.client.register_control_commands"), \
             patch("src.discord_bot.client.register_multibot_commands"), \
             patch.object(RefactoredClient, "start", new_callable=AsyncMock) as mock_start:
            mock_start.side_effect = Exception("Connection error")
            with pytest.raises(Exception, match="Connection error"):
                await start_discord_bot(token="test_token", bot_state={})


# ============================================================================
# commands/monitoring.py 테스트
# ============================================================================


class TestRegisterMonitoringCommands:
    """모니터링 명령어 등록 테스트"""

    def test_registers_commands(self):
        """명령어가 tree에 등록되는지 확인"""
        mock_client = MagicMock()
        mock_tree = MagicMock()
        mock_client.tree = mock_tree

        register_monitoring_commands(mock_client)

        # tree.command가 여러 번 호출되어야 함
        assert mock_tree.command.called
        # 데코레이터로 감싸므로 .command()가 호출됨
        call_count = mock_tree.command.call_count
        assert call_count >= 10  # 한글+영어 쌍으로 여러 명령어


# ============================================================================
# commands/control.py 테스트
# ============================================================================


class TestRegisterControlCommands:
    """제어 명령어 등록 테스트"""

    def test_registers_commands(self):
        mock_client = MagicMock()
        mock_tree = MagicMock()
        mock_client.tree = mock_tree

        with patch("src.discord_bot.commands.control.get_permission_config"):
            register_control_commands(mock_client)
            assert mock_tree.command.called
            assert mock_tree.command.call_count >= 6  # stop/start/emergency x 2


# ============================================================================
# commands/multibot.py 테스트
# ============================================================================


class TestRegisterMultibotCommands:
    """멀티봇 명령어 등록 테스트"""

    def test_registers_commands(self):
        mock_client = MagicMock()
        mock_tree = MagicMock()
        mock_client.tree = mock_tree

        with patch("src.discord_bot.commands.multibot.get_permission_config"):
            register_multibot_commands(mock_client)
            assert mock_tree.command.called
            # 봇목록, 봇상태, 봇시작, 봇정지, 봇일시정지, 봇재개, 전체시작, 전체정지 x 2
            assert mock_tree.command.call_count >= 16


# ============================================================================
# From test_discord_commands_coverage.py
# ============================================================================

# ============================================================================
# Helper: tree.command 데코레이터에서 콜백 함수를 캡처
# ============================================================================

def capture_commands(register_func):
    """register_*_commands 호출 시 등록된 콜백들을 캡처하여 반환"""
    commands = {}

    def command_decorator(**kwargs):
        name = kwargs.get("name", "unknown")

        def wrapper(func):
            commands[name] = func
            return func

        return wrapper

    mock_client = AsyncMock()
    mock_client.tree.command = command_decorator
    register_func(mock_client)
    return commands, mock_client


def make_interaction(user_id=12345, roles=None):
    """모의 Discord Interaction 생성"""
    interaction = AsyncMock()
    interaction.user = MagicMock()
    interaction.user.id = user_id
    interaction.user.roles = []
    interaction.response = AsyncMock()

    if roles:
        for role_id in roles:
            role = MagicMock()
            role.id = role_id
            interaction.user.roles.append(role)

    return interaction


# ============================================================================
# monitoring.py 테스트
# ============================================================================

class TestMonitoringCommands:
    """monitoring.py 내부 콜백 함수 테스트"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.commands, self.client = capture_commands(register_monitoring_commands)

    @pytest.mark.asyncio
    async def test_dashboard_korean(self):
        interaction = make_interaction()
        await self.commands["대시보드"](interaction)
        self.client._dashboard_command.assert_called_once_with(interaction)

    @pytest.mark.asyncio
    async def test_dashboard_english(self):
        interaction = make_interaction()
        await self.commands["dashboard"](interaction)
        self.client._dashboard_command.assert_called_with(interaction)

    @pytest.mark.asyncio
    async def test_status_korean(self):
        interaction = make_interaction()
        await self.commands["상태"](interaction)
        self.client._status_command.assert_called_once_with(interaction)

    @pytest.mark.asyncio
    async def test_status_english(self):
        interaction = make_interaction()
        await self.commands["status"](interaction)
        self.client._status_command.assert_called_with(interaction)

    @pytest.mark.asyncio
    async def test_position_korean(self):
        interaction = make_interaction()
        await self.commands["포지션"](interaction)
        self.client._position_command.assert_called_once_with(interaction)

    @pytest.mark.asyncio
    async def test_position_english(self):
        interaction = make_interaction()
        await self.commands["position"](interaction)
        self.client._position_command.assert_called_with(interaction)

    @pytest.mark.asyncio
    async def test_stats_korean(self):
        interaction = make_interaction()
        await self.commands["통계"](interaction, hours=12)
        self.client._stats_command.assert_called_once_with(interaction, 12)

    @pytest.mark.asyncio
    async def test_stats_english(self):
        interaction = make_interaction()
        await self.commands["stats"](interaction, hours=48)
        self.client._stats_command.assert_called_with(interaction, 48)

    @pytest.mark.asyncio
    async def test_history_korean(self):
        interaction = make_interaction()
        await self.commands["내역"](interaction, count=10)
        self.client._history_command.assert_called_once_with(interaction, 10)

    @pytest.mark.asyncio
    async def test_history_english(self):
        interaction = make_interaction()
        await self.commands["history"](interaction, count=3)
        self.client._history_command.assert_called_with(interaction, 3)

    @pytest.mark.asyncio
    async def test_account_korean(self):
        interaction = make_interaction()
        await self.commands["계정"](interaction)
        self.client._account_command.assert_called_once_with(interaction)

    @pytest.mark.asyncio
    async def test_account_english(self):
        interaction = make_interaction()
        await self.commands["account"](interaction)
        self.client._account_command.assert_called_with(interaction)

    @pytest.mark.asyncio
    async def test_ping_korean(self):
        interaction = make_interaction()
        await self.commands["핑"](interaction)
        interaction.response.send_message.assert_called_once_with(
            "🏓 퐁!", ephemeral=True
        )

    @pytest.mark.asyncio
    async def test_ping_english(self):
        interaction = make_interaction()
        await self.commands["ping"](interaction)
        interaction.response.send_message.assert_called_once_with(
            "🏓 Pong!", ephemeral=True
        )


# ============================================================================
# control.py 테스트
# ============================================================================

class TestControlCommands:
    """control.py 내부 콜백 함수 테스트"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.commands, self.client = capture_commands(register_control_commands)

    def _make_admin_interaction(self):
        interaction = make_interaction(user_id=99999)
        interaction.user.roles = []
        return interaction

    @pytest.mark.asyncio
    @patch("src.discord_bot.commands.control.check_permission", return_value=True)
    async def test_stop_korean_allowed(self, mock_perm):
        interaction = make_interaction()
        await self.commands["일시정지"](interaction)
        self.client._stop_command.assert_called_once_with(interaction)

    @pytest.mark.asyncio
    @patch("src.discord_bot.commands.control.check_permission", return_value=False)
    async def test_stop_korean_denied(self, mock_perm):
        interaction = make_interaction()
        await self.commands["일시정지"](interaction)
        interaction.response.send_message.assert_called_once()
        self.client._stop_command.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.discord_bot.commands.control.check_permission", return_value=True)
    async def test_stop_english_allowed(self, mock_perm):
        interaction = make_interaction()
        await self.commands["stop"](interaction)
        self.client._stop_command.assert_called_once_with(interaction)

    @pytest.mark.asyncio
    @patch("src.discord_bot.commands.control.check_permission", return_value=False)
    async def test_stop_english_denied(self, mock_perm):
        interaction = make_interaction()
        await self.commands["stop"](interaction)
        interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.discord_bot.commands.control.check_permission", return_value=True)
    async def test_start_korean_allowed(self, mock_perm):
        interaction = make_interaction()
        await self.commands["재시작"](interaction)
        self.client._start_command.assert_called_once_with(interaction)

    @pytest.mark.asyncio
    @patch("src.discord_bot.commands.control.check_permission", return_value=False)
    async def test_start_korean_denied(self, mock_perm):
        interaction = make_interaction()
        await self.commands["재시작"](interaction)
        interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.discord_bot.commands.control.check_permission", return_value=True)
    async def test_start_english_allowed(self, mock_perm):
        interaction = make_interaction()
        await self.commands["start"](interaction)
        self.client._start_command.assert_called_once_with(interaction)

    @pytest.mark.asyncio
    @patch("src.discord_bot.commands.control.check_permission", return_value=False)
    async def test_start_english_denied(self, mock_perm):
        interaction = make_interaction()
        await self.commands["start"](interaction)
        interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.discord_bot.commands.control.check_permission", return_value=True)
    async def test_emergency_korean_allowed(self, mock_perm):
        interaction = make_interaction()
        await self.commands["긴급청산"](interaction)
        self.client._emergency_command.assert_called_once_with(interaction)

    @pytest.mark.asyncio
    @patch("src.discord_bot.commands.control.check_permission", return_value=False)
    async def test_emergency_korean_denied(self, mock_perm):
        interaction = make_interaction()
        await self.commands["긴급청산"](interaction)
        interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.discord_bot.commands.control.check_permission", return_value=True)
    async def test_emergency_english_allowed(self, mock_perm):
        interaction = make_interaction()
        await self.commands["emergency"](interaction)
        self.client._emergency_command.assert_called_once_with(interaction)

    @pytest.mark.asyncio
    @patch("src.discord_bot.commands.control.check_permission", return_value=False)
    async def test_emergency_english_denied(self, mock_perm):
        interaction = make_interaction()
        await self.commands["emergency"](interaction)
        interaction.response.send_message.assert_called_once()


# ============================================================================
# multibot.py 테스트
# ============================================================================

class TestMultibotCommands:
    """multibot.py 내부 콜백 함수 테스트"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.commands, self.client = capture_commands(register_multibot_commands)

    # --- 봇 목록 / 상태 (VIEWER - 권한 체크 없음) ---

    @pytest.mark.asyncio
    async def test_bot_list_korean(self):
        interaction = make_interaction()
        await self.commands["봇목록"](interaction)
        self.client._bot_list_command.assert_called_once_with(interaction)

    @pytest.mark.asyncio
    async def test_bot_list_english(self):
        interaction = make_interaction()
        await self.commands["bots"](interaction)
        self.client._bot_list_command.assert_called_with(interaction)

    @pytest.mark.asyncio
    async def test_bot_status_korean(self):
        interaction = make_interaction()
        await self.commands["봇상태"](interaction, "btc-bot")
        self.client._bot_status_command.assert_called_once_with(interaction, "btc-bot")

    @pytest.mark.asyncio
    async def test_bot_status_english(self):
        interaction = make_interaction()
        await self.commands["bot-status"](interaction, "eth-bot")
        self.client._bot_status_command.assert_called_with(interaction, "eth-bot")

    # --- 봇 시작/정지 (ADMIN) ---

    @pytest.mark.asyncio
    @patch("src.discord_bot.commands.multibot.check_permission", return_value=True)
    async def test_bot_start_korean_allowed(self, mock_perm):
        interaction = make_interaction()
        await self.commands["봇시작"](interaction, "btc-bot")
        self.client._bot_start_command.assert_called_once_with(interaction, "btc-bot")

    @pytest.mark.asyncio
    @patch("src.discord_bot.commands.multibot.check_permission", return_value=False)
    async def test_bot_start_korean_denied(self, mock_perm):
        interaction = make_interaction()
        await self.commands["봇시작"](interaction, "btc-bot")
        interaction.response.send_message.assert_called_once()
        self.client._bot_start_command.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.discord_bot.commands.multibot.check_permission", return_value=True)
    async def test_bot_start_english_allowed(self, mock_perm):
        interaction = make_interaction()
        await self.commands["bot-start"](interaction, "btc-bot")
        self.client._bot_start_command.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.discord_bot.commands.multibot.check_permission", return_value=False)
    async def test_bot_start_english_denied(self, mock_perm):
        interaction = make_interaction()
        await self.commands["bot-start"](interaction, "btc-bot")
        interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.discord_bot.commands.multibot.check_permission", return_value=True)
    async def test_bot_stop_korean_allowed(self, mock_perm):
        interaction = make_interaction()
        await self.commands["봇정지"](interaction, "btc-bot")
        self.client._bot_stop_command.assert_called_once_with(interaction, "btc-bot")

    @pytest.mark.asyncio
    @patch("src.discord_bot.commands.multibot.check_permission", return_value=False)
    async def test_bot_stop_korean_denied(self, mock_perm):
        interaction = make_interaction()
        await self.commands["봇정지"](interaction, "btc-bot")
        interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.discord_bot.commands.multibot.check_permission", return_value=True)
    async def test_bot_stop_english_allowed(self, mock_perm):
        interaction = make_interaction()
        await self.commands["bot-stop"](interaction, "btc-bot")
        self.client._bot_stop_command.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.discord_bot.commands.multibot.check_permission", return_value=False)
    async def test_bot_stop_english_denied(self, mock_perm):
        interaction = make_interaction()
        await self.commands["bot-stop"](interaction, "btc-bot")
        interaction.response.send_message.assert_called_once()

    # --- 봇 일시정지/재개 (TRADER) ---

    @pytest.mark.asyncio
    @patch("src.discord_bot.commands.multibot.check_permission", return_value=True)
    async def test_bot_pause_korean_allowed(self, mock_perm):
        interaction = make_interaction()
        await self.commands["봇일시정지"](interaction, "btc-bot")
        self.client._bot_pause_command.assert_called_once_with(interaction, "btc-bot")

    @pytest.mark.asyncio
    @patch("src.discord_bot.commands.multibot.check_permission", return_value=False)
    async def test_bot_pause_korean_denied(self, mock_perm):
        interaction = make_interaction()
        await self.commands["봇일시정지"](interaction, "btc-bot")
        interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.discord_bot.commands.multibot.check_permission", return_value=True)
    async def test_bot_pause_english_allowed(self, mock_perm):
        interaction = make_interaction()
        await self.commands["bot-pause"](interaction, "btc-bot")
        self.client._bot_pause_command.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.discord_bot.commands.multibot.check_permission", return_value=False)
    async def test_bot_pause_english_denied(self, mock_perm):
        interaction = make_interaction()
        await self.commands["bot-pause"](interaction, "btc-bot")
        interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.discord_bot.commands.multibot.check_permission", return_value=True)
    async def test_bot_resume_korean_allowed(self, mock_perm):
        interaction = make_interaction()
        await self.commands["봇재개"](interaction, "btc-bot")
        self.client._bot_resume_command.assert_called_once_with(interaction, "btc-bot")

    @pytest.mark.asyncio
    @patch("src.discord_bot.commands.multibot.check_permission", return_value=False)
    async def test_bot_resume_korean_denied(self, mock_perm):
        interaction = make_interaction()
        await self.commands["봇재개"](interaction, "btc-bot")
        interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.discord_bot.commands.multibot.check_permission", return_value=True)
    async def test_bot_resume_english_allowed(self, mock_perm):
        interaction = make_interaction()
        await self.commands["bot-resume"](interaction, "btc-bot")
        self.client._bot_resume_command.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.discord_bot.commands.multibot.check_permission", return_value=False)
    async def test_bot_resume_english_denied(self, mock_perm):
        interaction = make_interaction()
        await self.commands["bot-resume"](interaction, "btc-bot")
        interaction.response.send_message.assert_called_once()

    # --- 전체 시작/정지 (ADMIN) ---

    @pytest.mark.asyncio
    @patch("src.discord_bot.commands.multibot.check_permission", return_value=True)
    async def test_start_all_korean_allowed(self, mock_perm):
        interaction = make_interaction()
        await self.commands["전체시작"](interaction)
        self.client._start_all_command.assert_called_once_with(interaction)

    @pytest.mark.asyncio
    @patch("src.discord_bot.commands.multibot.check_permission", return_value=False)
    async def test_start_all_korean_denied(self, mock_perm):
        interaction = make_interaction()
        await self.commands["전체시작"](interaction)
        interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.discord_bot.commands.multibot.check_permission", return_value=True)
    async def test_start_all_english_allowed(self, mock_perm):
        interaction = make_interaction()
        await self.commands["start-all"](interaction)
        self.client._start_all_command.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.discord_bot.commands.multibot.check_permission", return_value=False)
    async def test_start_all_english_denied(self, mock_perm):
        interaction = make_interaction()
        await self.commands["start-all"](interaction)
        interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.discord_bot.commands.multibot.check_permission", return_value=True)
    async def test_stop_all_korean_allowed(self, mock_perm):
        interaction = make_interaction()
        await self.commands["전체정지"](interaction)
        self.client._stop_all_command.assert_called_once_with(interaction)

    @pytest.mark.asyncio
    @patch("src.discord_bot.commands.multibot.check_permission", return_value=False)
    async def test_stop_all_korean_denied(self, mock_perm):
        interaction = make_interaction()
        await self.commands["전체정지"](interaction)
        interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.discord_bot.commands.multibot.check_permission", return_value=True)
    async def test_stop_all_english_allowed(self, mock_perm):
        interaction = make_interaction()
        await self.commands["stop-all"](interaction)
        self.client._stop_all_command.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.discord_bot.commands.multibot.check_permission", return_value=False)
    async def test_stop_all_english_denied(self, mock_perm):
        interaction = make_interaction()
        await self.commands["stop-all"](interaction)
        interaction.response.send_message.assert_called_once()
