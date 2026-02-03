"""
제어 관련 슬래시 명령어

일시정지, 재시작, 긴급청산 명령어를 제공합니다.

권한 레벨:
- /일시정지, /재시작: TRADER 이상
- /긴급청산: ADMIN 이상
"""
from typing import TYPE_CHECKING

import discord
from loguru import logger

from src.discord_bot.permissions import (
    PermissionLevel,
    check_permission,
    get_permission_config,
)

if TYPE_CHECKING:
    from src.discord_bot.client import TradingBotClient


def register_control_commands(client: "TradingBotClient") -> None:
    """제어 슬래시 명령어 등록

    Args:
        client: TradingBotClient 인스턴스
    """
    tree = client.tree
    config = get_permission_config()

    # =========================================================================
    # /일시정지 (Stop) - TRADER 권한 필요
    # =========================================================================

    @tree.command(name="일시정지", description="봇 일시 정지 (새 포지션 진입 중지)")
    async def stop_korean(interaction: discord.Interaction):
        """일시정지 (한글) - TRADER 권한 필요"""
        if not check_permission(interaction, PermissionLevel.TRADER, config):
            await interaction.response.send_message(
                "🚫 권한이 없습니다. 이 명령어는 **TRADER** 이상의 권한이 필요합니다.",
                ephemeral=True,
            )
            logger.warning(f"권한 부족 (일시정지): {interaction.user}")
            return
        await client._stop_command(interaction)

    @tree.command(name="stop", description="Pause the trading bot (stop new positions)")
    async def stop_english(interaction: discord.Interaction):
        """Stop command (English) - TRADER permission required"""
        if not check_permission(interaction, PermissionLevel.TRADER, config):
            await interaction.response.send_message(
                "🚫 Permission denied. This command requires **TRADER** or higher permission.",
                ephemeral=True,
            )
            logger.warning(f"Permission denied (stop): {interaction.user}")
            return
        await client._stop_command(interaction)

    # =========================================================================
    # /재시작 (Start) - TRADER 권한 필요
    # =========================================================================

    @tree.command(name="재시작", description="봇 재시작 (정상 거래 재개)")
    async def start_korean(interaction: discord.Interaction):
        """재시작 (한글) - TRADER 권한 필요"""
        if not check_permission(interaction, PermissionLevel.TRADER, config):
            await interaction.response.send_message(
                "🚫 권한이 없습니다. 이 명령어는 **TRADER** 이상의 권한이 필요합니다.",
                ephemeral=True,
            )
            logger.warning(f"권한 부족 (재시작): {interaction.user}")
            return
        await client._start_command(interaction)

    @tree.command(name="start", description="Resume the trading bot (normal trading)")
    async def start_english(interaction: discord.Interaction):
        """Start command (English) - TRADER permission required"""
        if not check_permission(interaction, PermissionLevel.TRADER, config):
            await interaction.response.send_message(
                "🚫 Permission denied. This command requires **TRADER** or higher permission.",
                ephemeral=True,
            )
            logger.warning(f"Permission denied (start): {interaction.user}")
            return
        await client._start_command(interaction)

    # =========================================================================
    # /긴급청산 (Emergency) - ADMIN 권한 필요
    # =========================================================================

    @tree.command(name="긴급청산", description="🚨 긴급 청산 (현재 포지션 즉시 청산 + 봇 정지)")
    async def emergency_korean(interaction: discord.Interaction):
        """긴급청산 (한글) - ADMIN 권한 필요"""
        if not check_permission(interaction, PermissionLevel.ADMIN, config):
            await interaction.response.send_message(
                "🚫 권한이 없습니다. 이 명령어는 **ADMIN** 이상의 권한이 필요합니다.",
                ephemeral=True,
            )
            logger.warning(f"권한 부족 (긴급청산): {interaction.user}")
            return
        await client._emergency_command(interaction)

    @tree.command(name="emergency", description="🚨 Emergency close (close position + pause bot)")
    async def emergency_english(interaction: discord.Interaction):
        """Emergency command (English) - ADMIN permission required"""
        if not check_permission(interaction, PermissionLevel.ADMIN, config):
            await interaction.response.send_message(
                "🚫 Permission denied. This command requires **ADMIN** permission.",
                ephemeral=True,
            )
            logger.warning(f"Permission denied (emergency): {interaction.user}")
            return
        await client._emergency_command(interaction)

    logger.debug("제어 명령어 등록 완료 (권한 시스템 적용)")
