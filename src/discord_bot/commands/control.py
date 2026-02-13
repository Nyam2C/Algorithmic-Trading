"""제어 관련 슬래시 명령어.

3개 한글 명령어: 제어, 긴급청산, 알림

권한 레벨:
- /제어 (시작/정지): ADMIN 이상
- /제어 (일시정지/재개): TRADER 이상
- /긴급청산: ADMIN 이상
- /알림: TRADER 이상
"""
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from loguru import logger

from src.discord_bot.permissions import (
    PermissionLevel,
    check_permission,
    get_permission_config,
)

if TYPE_CHECKING:
    from src.discord_bot.client import TradingBotClient


def register_control_commands(client: "TradingBotClient") -> None:
    """제어 슬래시 명령어 등록.

    Args:
        client: TradingBotClient 인스턴스
    """
    tree = client.tree
    config = get_permission_config()

    # 동작별 필요 권한
    action_permissions = {
        "start": PermissionLevel.ADMIN,
        "stop": PermissionLevel.ADMIN,
        "pause": PermissionLevel.TRADER,
        "resume": PermissionLevel.TRADER,
    }

    # /제어
    @tree.command(name="제어", description="봇 제어 (시작/정지/일시정지/재개)")
    @app_commands.describe(
        대상="봇 이름 또는 '전체'",
        동작="실행할 동작",
    )
    @app_commands.choices(
        동작=[
            app_commands.Choice(name="시작", value="start"),
            app_commands.Choice(name="정지", value="stop"),
            app_commands.Choice(name="일시정지", value="pause"),
            app_commands.Choice(name="재개", value="resume"),
        ]
    )
    async def control_cmd(
        interaction: discord.Interaction,
        대상: str,  # noqa: N803, PLC2401
        동작: app_commands.Choice[str],  # noqa: N803, PLC2401
    ):
        action = 동작.value
        required_level = action_permissions.get(action, PermissionLevel.ADMIN)
        if not check_permission(interaction, required_level, config):
            await interaction.response.send_message(
                f"🚫 권한이 없습니다. 이 동작은 **{required_level.name}** "
                "이상의 권한이 필요합니다.",
                ephemeral=True,
            )
            logger.warning(f"권한 부족 (제어/{action}): {interaction.user}")
            return
        await client._control_command(interaction, 대상, action)

    # /긴급청산
    @tree.command(
        name="긴급청산",
        description="긴급 청산 (포지션 즉시 청산 + 봇 정지)",
    )
    @app_commands.describe(대상="봇 이름 또는 '전체'")
    async def emergency_cmd(
        interaction: discord.Interaction,
        대상: str,  # noqa: N803, PLC2401
    ):
        if not check_permission(interaction, PermissionLevel.ADMIN, config):
            await interaction.response.send_message(
                "🚫 권한이 없습니다. 이 명령어는 **ADMIN** 이상의 권한이 필요합니다.",
                ephemeral=True,
            )
            logger.warning(f"권한 부족 (긴급청산): {interaction.user}")
            return
        await client._emergency_command(interaction, 대상)

    # /알림
    @tree.command(name="알림", description="알림 설정 관리")
    @app_commands.describe(
        유형="알림 유형",
        설정="켜기 또는 끄기",
    )
    @app_commands.choices(
        유형=[
            app_commands.Choice(name="진입 알림", value="entry"),
            app_commands.Choice(name="청산 알림", value="exit"),
            app_commands.Choice(name="일간 리포트", value="pnl_daily"),
            app_commands.Choice(name="에러 알림", value="error"),
        ],
        설정=[
            app_commands.Choice(name="켜기", value="on"),
            app_commands.Choice(name="끄기", value="off"),
        ],
    )
    async def alert_cmd(
        interaction: discord.Interaction,
        유형: app_commands.Choice[str] | None = None,  # noqa: N803, PLC2401
        설정: app_commands.Choice[str] | None = None,  # noqa: N803, PLC2401
    ):
        if not check_permission(interaction, PermissionLevel.TRADER, config):
            await interaction.response.send_message(
                "🚫 권한이 없습니다. 이 명령어는 **TRADER** 이상의 권한이 필요합니다.",
                ephemeral=True,
            )
            logger.warning(f"권한 부족 (알림): {interaction.user}")
            return

        alert_type = 유형.value if 유형 else None
        state = 설정.value if 설정 else None
        await client._alert_command(interaction, alert_type, state)

    logger.debug("제어 명령어 등록 완료 (3개)")
