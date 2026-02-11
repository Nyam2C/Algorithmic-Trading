"""Discord 명령어 모듈 커버리지 테스트

commands/monitoring.py, commands/control.py, commands/multibot.py의
데코레이터 내부 콜백 함수를 직접 호출하여 커버리지를 확보합니다.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
        from src.discord_bot.commands.monitoring import register_monitoring_commands
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
        from src.discord_bot.commands.control import register_control_commands
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
        from src.discord_bot.commands.multibot import register_multibot_commands
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
