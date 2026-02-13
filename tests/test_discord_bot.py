"""Tests for Discord Bot — 리뉴얼 버전 (11개 한글 명령어)."""
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import discord
import pytest

from src.discord_bot.client import (
    DEFAULT_ALERT_SETTINGS,
    TradingBotClient,
    start_discord_bot,
)
from src.discord_bot.constants import Colors, Messages
from src.discord_bot.embeds import (
    create_account_embed,
    create_alert_settings_embed,
    create_bot_list_embed,
    create_bot_status_embed,
    create_history_embed,
    create_pnl_embed,
    create_position_embed,
    create_status_embed,
)
from src.discord_bot.utils import (
    PERIOD_LABELS,
    PERIOD_MAP,
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
    validate_bot_name,
)
from src.discord_bot.views import DashboardView

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_bot_manager():
    """Mock MultiBotManager."""
    manager = MagicMock()
    manager.bots = {}
    manager.bot_count = 0
    manager.get_bot.return_value = None
    return manager


@pytest.fixture
def client(mock_bot_manager):
    """TradingBotClient with mocked dependencies."""
    with (
        patch(
            "src.discord_bot.commands.monitoring.register_monitoring_commands"
        ),
        patch("src.discord_bot.commands.control.register_control_commands"),
    ):
        return TradingBotClient(
            bot_manager=mock_bot_manager,
            trade_db=Mock(),
            binance_client=Mock(),
        )


@pytest.fixture
def mock_interaction():
    """Mock Discord Interaction."""
    interaction = AsyncMock(spec=discord.Interaction)
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()
    interaction.user = MagicMock()
    interaction.user.id = 12345
    interaction.user.__str__ = lambda self: "TestUser#1234"
    return interaction


# =============================================================================
# Utils Tests (기존 유지)
# =============================================================================


class TestFormatUptime:
    """format_uptime 테스트."""

    def test_none(self):
        assert format_uptime(None) == "N/A"

    def test_hours_and_minutes(self):
        start = datetime.now() - timedelta(hours=2, minutes=30)
        result = format_uptime(start)
        assert "2시간" in result
        assert "30분" in result

    def test_zero_uptime(self):
        result = format_uptime(datetime.now())
        assert "0시간 0분" == result


class TestFormatTimeAgo:
    """format_time_ago 테스트."""

    def test_none(self):
        assert format_time_ago(None) == "N/A"

    def test_minutes(self):
        ts = datetime.now() - timedelta(minutes=15)
        result = format_time_ago(ts)
        assert "15분 전" == result

    def test_hours(self):
        ts = datetime.now() - timedelta(hours=3)
        result = format_time_ago(ts)
        assert "3시간 전" == result

    def test_non_datetime(self):
        assert format_time_ago("not a datetime") == "N/A"


class TestFormatDuration:
    """format_duration 테스트."""

    def test_none(self):
        assert format_duration(None) == "N/A"

    def test_minutes(self):
        start = datetime.now() - timedelta(minutes=45)
        result = format_duration(start)
        assert "45분" == result

    def test_hours_and_minutes(self):
        start = datetime.now() - timedelta(hours=1, minutes=30)
        result = format_duration(start)
        assert "1시간" in result
        assert "30분" in result


class TestFormatPauseDuration:
    """format_pause_duration 테스트."""

    def test_none(self):
        assert format_pause_duration(None) == ""

    def test_with_user(self):
        paused_at = datetime.now() - timedelta(hours=1)
        result = format_pause_duration(paused_at, "admin")
        assert "1시간" in result
        assert "admin" in result


class TestFormatTimecutRemaining:
    """format_timecut_remaining 테스트."""

    def test_none(self):
        assert format_timecut_remaining(None) == "N/A"

    def test_remaining(self):
        future = datetime.now() + timedelta(minutes=45)
        result = format_timecut_remaining(future)
        assert "남음" in result

    def test_expired(self):
        past = datetime.now() - timedelta(minutes=10)
        result = format_timecut_remaining(past)
        assert "만료됨" == result


class TestCalculatePnl:
    """calculate_pnl 테스트."""

    def test_long_profit(self):
        pnl_pct, pnl_usd = calculate_pnl(100, 110, "LONG", 10, 1.0)
        assert pnl_pct == pytest.approx(100.0)  # 10% * 10x
        assert pnl_usd == pytest.approx(10.0)

    def test_short_profit(self):
        pnl_pct, pnl_usd = calculate_pnl(100, 90, "SHORT", 10, 1.0)
        assert pnl_pct == pytest.approx(100.0)
        assert pnl_usd == pytest.approx(10.0)


class TestStatusEmoji:
    """get_status_emoji / get_status_text 테스트."""

    def test_running(self):
        assert get_status_emoji(True, False) == "🟢"
        assert "실행 중" in get_status_text(True, False)

    def test_paused(self):
        assert get_status_emoji(True, True) == "🟡"
        assert "일시정지" in get_status_text(True, True)

    def test_stopped(self):
        assert get_status_emoji(False, False) == "🔴"
        assert "중지" in get_status_text(False, False)


class TestPositionEmoji:
    """get_position_emoji 테스트."""

    def test_long(self):
        assert get_position_emoji("LONG") == "🟢"

    def test_short(self):
        assert get_position_emoji("SHORT") == "🔴"


class TestPnlEmoji:
    """get_pnl_emoji 테스트."""

    def test_profit(self):
        assert get_pnl_emoji(10.0) == "💰"

    def test_loss(self):
        assert get_pnl_emoji(-5.0) == "📉"

    def test_zero(self):
        assert get_pnl_emoji(0.0) == "💰"


class TestFormatPrice:
    """format_price 테스트."""

    def test_default(self):
        assert format_price(1234.56) == "$1,234.56"

    def test_custom_decimals(self):
        assert format_price(1234.567, 3) == "$1,234.567"


class TestFormatPercentage:
    """format_percentage 테스트."""

    def test_positive(self):
        assert format_percentage(5.5) == "+5.50%"

    def test_negative(self):
        assert format_percentage(-3.2) == "-3.20%"

    def test_no_sign(self):
        assert format_percentage(5.5, with_sign=False) == "5.50%"


class TestTruncateId:
    """truncate_id 테스트."""

    def test_long_id(self):
        assert truncate_id("abcdefghij") == "abcdefgh"

    def test_short_id(self):
        assert truncate_id("abc") == "abc"

    def test_none(self):
        assert truncate_id("") == "N/A"


class TestValidateBotName:
    """validate_bot_name 테스트."""

    def test_valid(self):
        assert validate_bot_name("btc-conservative") == "btc-conservative"

    def test_single_char(self):
        assert validate_bot_name("a") == "a"

    def test_invalid_chars(self):
        with pytest.raises(ValueError):
            validate_bot_name("../hack")

    def test_empty(self):
        with pytest.raises(ValueError):
            validate_bot_name("")


class TestPeriodMap:
    """PERIOD_MAP / PERIOD_LABELS 테스트."""

    def test_period_map_keys(self):
        assert "일간" in PERIOD_MAP
        assert "주간" in PERIOD_MAP
        assert "월간" in PERIOD_MAP

    def test_period_map_values(self):
        assert PERIOD_MAP["일간"] == 24
        assert PERIOD_MAP["주간"] == 168
        assert PERIOD_MAP["월간"] == 720

    def test_period_labels(self):
        assert "24시간" in PERIOD_LABELS["일간"]
        assert "7일" in PERIOD_LABELS["주간"]
        assert "30일" in PERIOD_LABELS["월간"]


# =============================================================================
# Embed Tests
# =============================================================================


class TestCreateStatusEmbed:
    """create_status_embed 테스트."""

    def test_running(self):
        state = {
            "is_running": True,
            "is_paused": False,
            "current_price": 105000.0,
            "last_signal": "LONG",
        }
        embed = create_status_embed(state)
        assert embed.title == "🤖 봇 상태"
        assert embed.color.value == Colors.SUCCESS

    def test_paused(self):
        state = {"is_running": True, "is_paused": True, "current_price": 0}
        embed = create_status_embed(state)
        assert embed.color.value == Colors.ERROR


class TestCreatePositionEmbed:
    """create_position_embed 테스트."""

    def test_no_position(self):
        state = {"position": None, "last_signal": "WAIT"}
        embed = create_position_embed(state)
        assert "포지션 없음" in embed.title

    def test_long_position(self):
        state = {
            "position": {
                "side": "LONG",
                "entry_price": 100000,
                "quantity": 0.01,
                "leverage": 10,
                "tp_price": 101000,
                "sl_price": 99500,
            },
            "current_price": 100500,
        }
        embed = create_position_embed(state)
        assert "현재 포지션" in embed.title


class TestCreatePnlEmbed:
    """create_pnl_embed 테스트 (기존 create_stats_embed 대체)."""

    def test_no_trades(self):
        stats = {"total_trades": 0, "total_pnl": 0}
        embed = create_pnl_embed(stats, "일간 (24시간)")
        assert "거래 없음" in embed.title

    def test_positive_pnl(self):
        stats = {
            "total_trades": 5,
            "total_pnl": 150.0,
            "winners": 4,
            "losers": 1,
            "win_rate": 80.0,
            "best_trade": 5.0,
            "worst_trade": -1.0,
            "long_trades": 3,
            "short_trades": 2,
        }
        embed = create_pnl_embed(stats, "일간 (24시간)")
        assert "수익 리포트" in embed.title
        assert embed.color.value == Colors.SUCCESS

    def test_negative_pnl(self):
        stats = {
            "total_trades": 3,
            "total_pnl": -50.0,
            "winners": 1,
            "losers": 2,
            "win_rate": 33.3,
            "best_trade": 2.0,
            "worst_trade": -5.0,
            "long_trades": 2,
            "short_trades": 1,
        }
        embed = create_pnl_embed(stats, "주간 (7일)")
        assert embed.color.value == Colors.ERROR
        assert "주간" in embed.description

    def test_with_bot_name(self):
        stats = {
            "total_trades": 1,
            "total_pnl": 10.0,
            "winners": 1,
            "losers": 0,
            "win_rate": 100.0,
            "best_trade": 3.0,
            "worst_trade": 0.0,
            "long_trades": 1,
            "short_trades": 0,
        }
        embed = create_pnl_embed(stats, "일간 (24시간)", "btc-bot")
        assert "btc-bot" in embed.title

    def test_period_labels(self):
        """기간 라벨이 올바르게 표시되는지 확인."""
        stats = {"total_trades": 0, "total_pnl": 0}
        for _period_key, label in PERIOD_LABELS.items():
            embed = create_pnl_embed(stats, label)
            assert label in (embed.description or "")


class TestCreateAlertSettingsEmbed:
    """create_alert_settings_embed 테스트."""

    def test_all_on(self):
        settings = {"entry": True, "exit": True, "pnl_daily": True, "error": True}
        embed = create_alert_settings_embed(settings)
        assert "알림 설정" in embed.title
        # 4개 필드
        assert len(embed.fields) == 4

    def test_mixed(self):
        settings = {"entry": True, "exit": False, "pnl_daily": True, "error": False}
        embed = create_alert_settings_embed(settings)
        values = [f.value for f in embed.fields]
        assert "✅ 켜짐" in values[0]  # entry
        assert "❌ 꺼짐" in values[1]  # exit

    def test_defaults(self):
        """기본값(True)이 적용되는지 확인."""
        embed = create_alert_settings_embed({})
        for field in embed.fields:
            assert "켜짐" in field.value


class TestCreateHistoryEmbed:
    """create_history_embed 테스트."""

    def test_empty(self):
        embed = create_history_embed([])
        assert "내역 없음" in embed.title

    def test_with_trades(self):
        trades = [
            {
                "side": "LONG",
                "entry_price": 100000,
                "exit_price": 101000,
                "exit_reason": "TP",
                "pnl": 10.0,
                "pnl_pct": 1.0,
                "id": "1",
            }
        ]
        embed = create_history_embed(trades)
        assert "최근 거래" in embed.title
        assert len(embed.fields) == 1


class TestCreateAccountEmbed:
    """create_account_embed 테스트."""

    def test_no_positions(self):
        balance = {"balance": 10000, "available": 9500}
        embed = create_account_embed(balance, [])
        assert "계정 현황" in embed.title

    def test_with_positions(self):
        balance = {"balance": 10000, "available": 9000}
        positions = [
            {
                "side": "LONG",
                "leverage": 10,
                "entry_price": 100000,
                "current_price": 101000,
                "quantity": 0.01,
                "unrealized_pnl": 10.0,
                "pnl_pct": 1.0,
                "liquidation_price": 90000,
                "symbol": "BTCUSDT",
            }
        ]
        embed = create_account_embed(balance, positions)
        assert len(embed.fields) > 4


class TestCreateBotListEmbed:
    """create_bot_list_embed 테스트."""

    def test_empty(self):
        data = {"total_bots": 0, "running_bots": 0, "paused_bots": 0, "bots": []}
        embed = create_bot_list_embed(data)
        assert "봇 목록" in embed.title

    def test_with_bots(self):
        data = {
            "total_bots": 2,
            "running_bots": 1,
            "paused_bots": 1,
            "bots": [
                {"name": "bot1", "is_running": True, "is_paused": False, "symbol": "BTCUSDT", "risk_level": "low"},
                {"name": "bot2", "is_running": True, "is_paused": True, "symbol": "ETHUSDT", "risk_level": "high"},
            ],
        }
        embed = create_bot_list_embed(data)
        assert len(embed.fields) == 3  # summary + 2 bots


class TestCreateBotStatusEmbed:
    """create_bot_status_embed 테스트."""

    def test_running(self):
        state = {
            "is_running": True,
            "is_paused": False,
            "symbol": "BTCUSDT",
            "risk_level": "medium",
            "leverage": 10,
            "current_price": 105000,
            "loop_count": 42,
            "last_signal": "WAIT",
        }
        embed = create_bot_status_embed("test-bot", state)
        assert "test-bot" in embed.title
        assert embed.color.value == Colors.SUCCESS


# =============================================================================
# Client Init Tests
# =============================================================================


class TestTradingBotClientInit:
    """TradingBotClient 초기화 테스트."""

    def test_init_with_bot_manager(self, mock_bot_manager):
        """bot_manager 필수 초기화."""
        with (
            patch(
                "src.discord_bot.commands.monitoring.register_monitoring_commands"
            ),
            patch(
                "src.discord_bot.commands.control.register_control_commands"
            ),
        ):
            client = TradingBotClient(bot_manager=mock_bot_manager)
            assert client.bot_manager is mock_bot_manager
            assert client.trade_db is None
            assert client.binance_client is None
            assert client.bot_state == {}

    def test_init_with_all_params(self, mock_bot_manager):
        """모든 파라미터와 함께 초기화."""
        mock_db = Mock()
        mock_binance = Mock()
        bot_state = {"is_running": True}
        with (
            patch(
                "src.discord_bot.commands.monitoring.register_monitoring_commands"
            ),
            patch(
                "src.discord_bot.commands.control.register_control_commands"
            ),
        ):
            client = TradingBotClient(
                bot_manager=mock_bot_manager,
                trade_db=mock_db,
                binance_client=mock_binance,
                bot_state=bot_state,
            )
            assert client.trade_db is mock_db
            assert client.binance_client is mock_binance
            assert client.bot_state == {"is_running": True}

    def test_audit_log(self, client):
        """감사 로그 설정."""
        mock_audit = Mock()
        client.set_audit_log(mock_audit)
        assert client._audit_log is mock_audit


# =============================================================================
# Client Command Method Tests (bot_manager 기반)
# =============================================================================


class TestStatusAllCommand:
    """_status_all_command 테스트."""

    @pytest.mark.asyncio
    async def test_success(self, client, mock_interaction):
        client._call_bot_api = AsyncMock(
            return_value={
                "data": {
                    "total_bots": 1,
                    "running_bots": 1,
                    "paused_bots": 0,
                    "bots": [
                        {
                            "name": "bot1",
                            "is_running": True,
                            "is_paused": False,
                            "symbol": "BTCUSDT",
                            "risk_level": "low",
                        }
                    ],
                }
            }
        )
        await client._status_all_command(mock_interaction)
        mock_interaction.followup.send.assert_called_once()
        embed = mock_interaction.followup.send.call_args[1].get("embed") or mock_interaction.followup.send.call_args[0][0]
        assert isinstance(embed, discord.Embed)

    @pytest.mark.asyncio
    async def test_api_error(self, client, mock_interaction):
        client._call_bot_api = AsyncMock(side_effect=Exception("API error"))
        await client._status_all_command(mock_interaction)
        call_args = mock_interaction.followup.send.call_args
        assert "오류" in str(call_args)


class TestStatusBotCommand:
    """_status_bot_command 테스트."""

    @pytest.mark.asyncio
    async def test_success(self, client, mock_interaction):
        client._call_bot_api = AsyncMock(
            return_value={
                "data": {
                    "state": {
                        "is_running": True,
                        "is_paused": False,
                        "symbol": "BTCUSDT",
                        "risk_level": "medium",
                        "leverage": 10,
                        "current_price": 105000,
                        "loop_count": 42,
                        "last_signal": "WAIT",
                    }
                }
            }
        )
        await client._status_bot_command(mock_interaction, "test-bot")
        mock_interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalid_bot_name(self, client, mock_interaction):
        await client._status_bot_command(mock_interaction, "../hack")
        call_args = mock_interaction.followup.send.call_args
        assert "유효하지 않은" in str(call_args)


class TestPositionCommand:
    """_position_command 테스트."""

    @pytest.mark.asyncio
    async def test_all_positions(self, client, mock_interaction):
        client._call_bot_api = AsyncMock(
            return_value={
                "data": {
                    "bots": [
                        {
                            "name": "bot1",
                            "position": {
                                "side": "LONG",
                                "entry_price": 100000,
                            },
                        },
                        {"name": "bot2", "position": None},
                    ]
                }
            }
        )
        await client._position_command(mock_interaction, "")
        mock_interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_single_bot_position(self, client, mock_interaction):
        client._call_bot_api = AsyncMock(
            return_value={
                "data": {
                    "state": {
                        "position": {
                            "side": "LONG",
                            "entry_price": 100000,
                            "quantity": 0.01,
                            "leverage": 10,
                            "tp_price": 101000,
                            "sl_price": 99000,
                        },
                        "current_price": 100500,
                    }
                }
            }
        )
        await client._position_command(mock_interaction, "bot1")
        mock_interaction.followup.send.assert_called_once()


class TestPnlCommand:
    """_pnl_command 테스트."""

    @pytest.mark.asyncio
    async def test_daily(self, client, mock_interaction):
        client.trade_db = AsyncMock()
        client.trade_db.get_statistics = AsyncMock(
            return_value={
                "total_trades": 3,
                "total_pnl": 50.0,
                "winners": 2,
                "losers": 1,
                "win_rate": 66.7,
                "best_trade": 3.0,
                "worst_trade": -1.0,
                "long_trades": 2,
                "short_trades": 1,
            }
        )
        await client._pnl_command(
            mock_interaction, hours=24, period_label="일간 (24시간)"
        )
        client.trade_db.get_statistics.assert_called_once_with(hours=24)
        mock_interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_weekly(self, client, mock_interaction):
        client.trade_db = AsyncMock()
        client.trade_db.get_statistics = AsyncMock(
            return_value={
                "total_trades": 10,
                "total_pnl": 200.0,
                "winners": 7,
                "losers": 3,
                "win_rate": 70.0,
                "best_trade": 5.0,
                "worst_trade": -2.0,
                "long_trades": 6,
                "short_trades": 4,
            }
        )
        await client._pnl_command(
            mock_interaction, hours=168, period_label="주간 (7일)"
        )
        client.trade_db.get_statistics.assert_called_once_with(hours=168)

    @pytest.mark.asyncio
    async def test_no_db(self, client, mock_interaction):
        client.trade_db = None
        await client._pnl_command(mock_interaction)
        call_args = mock_interaction.followup.send.call_args
        assert Messages.NO_DATABASE in str(call_args)


class TestHistoryCommand:
    """_history_command 테스트."""

    @pytest.mark.asyncio
    async def test_success(self, client, mock_interaction):
        client.trade_db = AsyncMock()
        client.trade_db.get_recent_trades = AsyncMock(return_value=[])
        await client._history_command(mock_interaction, count=5)
        client.trade_db.get_recent_trades.assert_called_once_with(limit=5)

    @pytest.mark.asyncio
    async def test_max_limit(self, client, mock_interaction):
        client.trade_db = AsyncMock()
        client.trade_db.get_recent_trades = AsyncMock(return_value=[])
        await client._history_command(mock_interaction, count=20)
        # Should be capped at 10
        client.trade_db.get_recent_trades.assert_called_once_with(limit=10)


class TestAccountCommand:
    """_account_command 테스트."""

    @pytest.mark.asyncio
    async def test_success(self, client, mock_interaction):
        client.binance_client = AsyncMock()
        client.binance_client.get_account_balance = AsyncMock(
            return_value={"balance": 10000, "available": 9500}
        )
        client.binance_client.get_all_positions = AsyncMock(return_value=[])
        await client._account_command(mock_interaction)
        mock_interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_binance(self, client, mock_interaction):
        client.binance_client = None
        await client._account_command(mock_interaction)
        call_args = mock_interaction.followup.send.call_args
        assert Messages.NO_BINANCE in str(call_args)


class TestControlCommand:
    """_control_command 테스트."""

    @pytest.mark.asyncio
    async def test_single_bot_start(self, client, mock_interaction):
        client._call_bot_api = AsyncMock(return_value={"status": "ok"})
        await client._control_command(mock_interaction, "bot1", "start")
        client._call_bot_api.assert_called_with(
            "POST", "/api/bots/bot1/start"
        )
        mock_interaction.followup.send.assert_called_once()
        embed = mock_interaction.followup.send.call_args[1]["embed"]
        assert "시작" in embed.title

    @pytest.mark.asyncio
    async def test_single_bot_pause(self, client, mock_interaction):
        client._call_bot_api = AsyncMock(return_value={"status": "ok"})
        await client._control_command(mock_interaction, "bot1", "pause")
        client._call_bot_api.assert_called_with(
            "POST", "/api/bots/bot1/pause"
        )

    @pytest.mark.asyncio
    async def test_all_bots_start(self, client, mock_interaction):
        client._call_bot_api = AsyncMock(
            return_value={"data": {"started": 3}}
        )
        await client._control_command(mock_interaction, "전체", "start")
        client._call_bot_api.assert_called_with("POST", "/api/bots/start-all")

    @pytest.mark.asyncio
    async def test_all_bots_stop(self, client, mock_interaction):
        client._call_bot_api = AsyncMock(
            return_value={"data": {"stopped": 2}}
        )
        await client._control_command(mock_interaction, "전체", "stop")
        client._call_bot_api.assert_called_with("POST", "/api/bots/stop-all")

    @pytest.mark.asyncio
    async def test_all_bots_pause(self, client, mock_interaction):
        """pause-all: 개별 봇 순회."""
        call_count = 0

        async def mock_api(method, endpoint, **kwargs):
            nonlocal call_count
            call_count += 1
            if endpoint == "/api/bots":
                return {
                    "data": {
                        "bots": [
                            {"name": "bot1"},
                            {"name": "bot2"},
                        ]
                    }
                }
            return {"status": "ok"}

        client._call_bot_api = AsyncMock(side_effect=mock_api)
        await client._control_command(mock_interaction, "전체", "pause")
        # GET /api/bots + POST bot1/pause + POST bot2/pause = 3 calls
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_invalid_target(self, client, mock_interaction):
        """유효하지 않은 봇 이름."""
        await client._control_command(mock_interaction, "../hack", "start")
        call_args = mock_interaction.followup.send.call_args
        assert "유효하지 않은" in str(call_args) or "오류" in str(call_args)


class TestEmergencyCommand:
    """_emergency_command 테스트."""

    @pytest.mark.asyncio
    async def test_single_bot(self, client, mock_interaction):
        mock_bot = MagicMock()
        client.bot_manager.get_bot.return_value = mock_bot
        await client._emergency_command(mock_interaction, "bot1")
        mock_bot.request_emergency_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_all_bots(self, client, mock_interaction):
        mock_bot1 = MagicMock()
        mock_bot2 = MagicMock()
        client.bot_manager.bots = {"bot1": mock_bot1, "bot2": mock_bot2}
        await client._emergency_command(mock_interaction, "전체")
        mock_bot1.request_emergency_close.assert_called_once()
        mock_bot2.request_emergency_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_bot_not_found(self, client, mock_interaction):
        client.bot_manager.get_bot.return_value = None
        await client._emergency_command(mock_interaction, "nonexistent")
        call_args = mock_interaction.followup.send.call_args
        assert "찾을 수 없습니다" in str(call_args)


class TestAlertCommand:
    """_alert_command 테스트."""

    @pytest.mark.asyncio
    async def test_show_settings(self, client, mock_interaction):
        """인자 없으면 현재 설정 표시."""
        await client._alert_command(mock_interaction, None, None)
        call_args = mock_interaction.followup.send.call_args
        embed = call_args[1].get("embed")
        assert embed is not None
        assert "알림 설정" in embed.title

    @pytest.mark.asyncio
    async def test_toggle_on(self, client, mock_interaction):
        """알림 켜기."""
        await client._alert_command(mock_interaction, "entry", "on")
        user_id = str(mock_interaction.user.id)
        assert client._alert_settings[user_id]["entry"] is True

    @pytest.mark.asyncio
    async def test_toggle_off(self, client, mock_interaction):
        """알림 끄기."""
        await client._alert_command(mock_interaction, "exit", "off")
        user_id = str(mock_interaction.user.id)
        assert client._alert_settings[user_id]["exit"] is False

    @pytest.mark.asyncio
    async def test_default_settings(self, client, mock_interaction):
        """처음 접근 시 기본값."""
        await client._alert_command(mock_interaction, None, None)
        user_id = str(mock_interaction.user.id)
        assert client._alert_settings[user_id] == DEFAULT_ALERT_SETTINGS


class TestPromptCommand:
    """_prompt_command 테스트."""

    @pytest.mark.asyncio
    async def test_no_bots(self, client, mock_interaction):
        client.bot_manager.bots = {}
        await client._prompt_command(mock_interaction)
        call_args = mock_interaction.followup.send.call_args
        assert "등록된 봇이 없습니다" in str(call_args)

    @pytest.mark.asyncio
    async def test_bot_not_found(self, client, mock_interaction):
        mock_bot = MagicMock()
        mock_bot.bot_name = "bot1"
        client.bot_manager.bots = {"bot1": mock_bot}
        await client._prompt_command(mock_interaction, "nonexistent")
        call_args = mock_interaction.followup.send.call_args
        assert "찾을 수 없습니다" in str(call_args)

    @pytest.mark.asyncio
    async def test_no_ai_calls(self, client, mock_interaction):
        mock_bot = MagicMock()
        mock_bot.bot_name = "bot1"
        mock_bot.get_last_ai_call.return_value = None
        client.bot_manager.bots = {"bot1": mock_bot}
        await client._prompt_command(mock_interaction, "bot1")
        call_args = mock_interaction.followup.send.call_args
        embed = call_args[1].get("embed")
        assert "호출 기록이 없습니다" in embed.description

    @pytest.mark.asyncio
    async def test_with_ai_call(self, client, mock_interaction):
        mock_bot = MagicMock()
        mock_bot.bot_name = "bot1"
        mock_bot.get_last_ai_call.return_value = {
            "prompt": "test prompt",
            "response": "LONG",
            "model": "gemini-2.0",
            "signal": "LONG",
            "timestamp": datetime.now(),
        }
        client.bot_manager.bots = {"bot1": mock_bot}
        await client._prompt_command(mock_interaction, "bot1")
        call_args = mock_interaction.followup.send.call_args
        embed = call_args[1].get("embed")
        assert "bot1" in embed.title


class TestDashboardCommand:
    """_dashboard_command 테스트."""

    @pytest.mark.asyncio
    async def test_success(self, client, mock_interaction):
        client._call_bot_api = AsyncMock(
            return_value={
                "data": {
                    "total_bots": 2,
                    "running_bots": 1,
                    "paused_bots": 0,
                    "bots": [
                        {
                            "name": "bot1",
                            "is_running": True,
                            "is_paused": False,
                            "symbol": "BTCUSDT",
                        },
                        {
                            "name": "bot2",
                            "is_running": False,
                            "is_paused": False,
                            "symbol": "ETHUSDT",
                        },
                    ],
                }
            }
        )
        await client._dashboard_command(mock_interaction)
        mock_interaction.followup.send.assert_called_once()
        kwargs = mock_interaction.followup.send.call_args[1]
        assert "embed" in kwargs
        assert "view" in kwargs


# =============================================================================
# Dashboard helper Tests
# =============================================================================


class TestGetPnlEmbed:
    """_get_pnl_embed 테스트 (대시보드 버튼용)."""

    @pytest.mark.asyncio
    async def test_no_db(self, client):
        client.trade_db = None
        embed = await client._get_pnl_embed()
        assert "데이터베이스" in embed.title

    @pytest.mark.asyncio
    async def test_success(self, client):
        client.trade_db = AsyncMock()
        client.trade_db.get_statistics = AsyncMock(
            return_value={
                "total_trades": 1,
                "total_pnl": 10.0,
                "winners": 1,
                "losers": 0,
                "win_rate": 100.0,
                "best_trade": 2.0,
                "worst_trade": 0.0,
                "long_trades": 1,
                "short_trades": 0,
            }
        )
        embed = await client._get_pnl_embed(hours=24)
        assert "수익 리포트" in embed.title


class TestGetHistoryEmbed:
    """_get_history_embed 테스트."""

    @pytest.mark.asyncio
    async def test_no_db(self, client):
        client.trade_db = None
        embed = await client._get_history_embed()
        assert "데이터베이스" in embed.title

    @pytest.mark.asyncio
    async def test_success(self, client):
        client.trade_db = AsyncMock()
        client.trade_db.get_recent_trades = AsyncMock(return_value=[])
        embed = await client._get_history_embed()
        assert "내역" in embed.title


class TestGetAccountEmbed:
    """_get_account_embed 테스트."""

    @pytest.mark.asyncio
    async def test_no_binance(self, client):
        client.binance_client = None
        embed = await client._get_account_embed()
        assert "Binance" in embed.title

    @pytest.mark.asyncio
    async def test_success(self, client):
        client.binance_client = AsyncMock()
        client.binance_client.get_account_balance = AsyncMock(
            return_value={"balance": 10000, "available": 9500}
        )
        client.binance_client.get_all_positions = AsyncMock(return_value=[])
        embed = await client._get_account_embed()
        assert "계정 현황" in embed.title


# =============================================================================
# Command Registration Tests (11개 한글 명령어)
# =============================================================================


class TestCommandRegistration:
    """명령어 등록 테스트."""

    def test_monitoring_commands_registered(self, mock_bot_manager):
        """모니터링 8개 명령어 등록 확인."""
        with patch(
            "src.discord_bot.commands.control.register_control_commands"
        ):
            client = TradingBotClient(bot_manager=mock_bot_manager)

        command_names = [cmd.name for cmd in client.tree.get_commands()]
        # 8 monitoring commands
        for name in ["대시보드", "상태", "포지션", "수익", "내역", "계정", "프롬프트", "핑"]:
            assert name in command_names, f"/{name} 명령어 미등록"

    def test_control_commands_registered(self, mock_bot_manager):
        """제어 3개 명령어 등록 확인."""
        with patch(
            "src.discord_bot.commands.monitoring.register_monitoring_commands"
        ):
            client = TradingBotClient(bot_manager=mock_bot_manager)

        command_names = [cmd.name for cmd in client.tree.get_commands()]
        for name in ["제어", "긴급청산", "알림"]:
            assert name in command_names, f"/{name} 명령어 미등록"

    def test_exactly_11_commands(self, mock_bot_manager):
        """정확히 11개 명령어만 등록되어야 함."""
        client = TradingBotClient(bot_manager=mock_bot_manager)
        commands = client.tree.get_commands()
        assert len(commands) == 11, (
            f"Expected 11 commands, got {len(commands)}: "
            f"{[c.name for c in commands]}"
        )

    def test_no_english_commands(self, mock_bot_manager):
        """영어 명령어가 없어야 함."""
        client = TradingBotClient(bot_manager=mock_bot_manager)
        command_names = [cmd.name for cmd in client.tree.get_commands()]
        english_names = [
            "dashboard", "status", "position", "stats", "history",
            "account", "prompt", "ping", "stop", "start", "emergency",
            "bots", "bot-status", "bot-start", "bot-stop", "bot-pause",
            "bot-resume", "start-all", "stop-all",
        ]
        for name in english_names:
            assert name not in command_names, f"영어 명령어 /{name} 가 존재"

    def test_command_names_list(self, mock_bot_manager):
        """전체 명령어 이름 목록 확인."""
        client = TradingBotClient(bot_manager=mock_bot_manager)
        command_names = sorted([cmd.name for cmd in client.tree.get_commands()])
        expected = sorted([
            "대시보드", "상태", "포지션", "수익", "내역", "계정", "프롬프트",
            "핑", "제어", "긴급청산", "알림",
        ])
        assert command_names == expected


# =============================================================================
# DashboardView Tests
# =============================================================================


class TestDashboardView:
    """DashboardView 테스트."""

    @pytest.mark.asyncio
    async def test_button_count(self, client):
        """7개 버튼 확인."""
        view = DashboardView(bot_client=client)
        buttons = [
            child
            for child in view.children
            if isinstance(child, discord.ui.Button)
        ]
        assert len(buttons) == 7

    @pytest.mark.asyncio
    async def test_button_rows(self, client):
        """Row 0: 4개, Row 1: 3개."""
        view = DashboardView(bot_client=client)
        buttons = [
            child
            for child in view.children
            if isinstance(child, discord.ui.Button)
        ]
        row0 = [b for b in buttons if b.row == 0]
        row1 = [b for b in buttons if b.row == 1]
        assert len(row0) == 4
        assert len(row1) == 3

    @pytest.mark.asyncio
    async def test_cooldown(self, client):
        """쿨다운 체크."""
        view = DashboardView(bot_client=client)
        assert view._check_cooldown(12345) is True
        assert view._check_cooldown(12345) is False  # within cooldown


# =============================================================================
# start_discord_bot Tests
# =============================================================================


class TestStartDiscordBot:
    """start_discord_bot 함수 테스트."""

    @pytest.mark.asyncio
    async def test_signature(self, mock_bot_manager):
        """시그니처 확인 — bot_manager 필수."""
        with (
            patch(
                "src.discord_bot.commands.monitoring.register_monitoring_commands"
            ),
            patch(
                "src.discord_bot.commands.control.register_control_commands"
            ),
            patch.object(TradingBotClient, "start", new_callable=AsyncMock),
        ):
            await start_discord_bot(
                token="test-token",
                bot_manager=mock_bot_manager,
                trade_db=Mock(),
            )

    @pytest.mark.asyncio
    async def test_backward_compat(self, mock_bot_manager):
        """bot_state 하위 호환."""
        with (
            patch(
                "src.discord_bot.commands.monitoring.register_monitoring_commands"
            ),
            patch(
                "src.discord_bot.commands.control.register_control_commands"
            ),
            patch.object(TradingBotClient, "start", new_callable=AsyncMock),
        ):
            await start_discord_bot(
                token="test-token",
                bot_manager=mock_bot_manager,
                bot_state={"is_running": True},
            )


# =============================================================================
# Audit Command Tests
# =============================================================================


class TestAuditCommand:
    """_audit_command 테스트."""

    @pytest.mark.asyncio
    async def test_no_audit_log(self, client):
        """감사 로그 미설정 시 무시."""
        client._audit_log = None
        await client._audit_command("test", "user")  # no error

    @pytest.mark.asyncio
    async def test_with_audit_log(self, client):
        """감사 로그 기록."""
        mock_audit = AsyncMock()
        client._audit_log = mock_audit
        await client._audit_command("제어/시작", "TestUser", bot_name="bot1")
        mock_audit.log_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_audit_error_handled(self, client):
        """감사 로그 에러는 경고만."""
        mock_audit = AsyncMock()
        mock_audit.log_event.side_effect = Exception("DB error")
        client._audit_log = mock_audit
        await client._audit_command("test", "user")  # no raise


# =============================================================================
# Messages Constants Tests
# =============================================================================


class TestMessages:
    """Messages 상수 테스트."""

    def test_bot_not_found(self):
        msg = Messages.BOT_NOT_FOUND.format(name="test-bot")
        assert "test-bot" in msg
        assert "찾을 수 없습니다" in msg

    def test_control_success(self):
        msg = Messages.CONTROL_SUCCESS.format(action="시작", target="bot1")
        assert "시작" in msg
        assert "bot1" in msg

    def test_alert_updated(self):
        msg = Messages.ALERT_UPDATED.format(alert_type="진입 알림", state="켜기")
        assert "진입 알림" in msg
        assert "켜기" in msg
