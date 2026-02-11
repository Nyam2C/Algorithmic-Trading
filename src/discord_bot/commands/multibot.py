"""멀티봇 관련 슬래시 명령어

봇 목록, 상태, 시작/정지, 일시정지/재개, 전체 시작/정지 명령어를 제공합니다.

권한 레벨:
- /봇목록, /봇상태: VIEWER (모든 사용자)
- /봇일시정지, /봇재개: TRADER 이상
- /봇시작, /봇정지, /전체시작, /전체정지: ADMIN 이상
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


def register_multibot_commands(client: "TradingBotClient") -> None:
    """멀티봇 슬래시 명령어 등록

    Args:
        client: TradingBotClient 인스턴스
    """
    tree = client.tree
    config = get_permission_config()

    # =========================================================================
    # /봇목록 (Bot List)
    # =========================================================================

    @tree.command(name="봇목록", description="📋 등록된 봇 목록 조회")
    async def bot_list_korean(interaction: discord.Interaction):
        """봇 목록 조회 (한글)"""
        await client._bot_list_command(interaction)

    @tree.command(name="bots", description="📋 List all registered bots")
    async def bot_list_english(interaction: discord.Interaction):
        """Bot list command (English)"""
        await client._bot_list_command(interaction)

    # =========================================================================
    # /봇상태 (Bot Status)
    # =========================================================================

    @tree.command(name="봇상태", description="📊 특정 봇 상태 조회")
    async def bot_status_korean(
        interaction: discord.Interaction,
        bot_name: str,
    ):
        """봇 상태 조회 (한글)"""
        await client._bot_status_command(interaction, bot_name)

    @tree.command(name="bot-status", description="📊 Get specific bot status")
    async def bot_status_english(
        interaction: discord.Interaction,
        bot_name: str,
    ):
        """Bot status command (English)"""
        await client._bot_status_command(interaction, bot_name)

    # =========================================================================
    # /봇시작 (Bot Start) - ADMIN 권한 필요
    # =========================================================================

    @tree.command(name="봇시작", description="▶️ 특정 봇 시작")
    async def bot_start_korean(
        interaction: discord.Interaction,
        bot_name: str,
    ):
        """봇 시작 (한글) - ADMIN 권한 필요"""
        if not check_permission(interaction, PermissionLevel.ADMIN, config):
            await interaction.response.send_message(
                "🚫 권한이 없습니다. 이 명령어는 **ADMIN** 이상의 권한이 필요합니다.",
                ephemeral=True,
            )
            logger.warning(f"권한 부족 (봇시작): {interaction.user}")
            return
        await client._bot_start_command(interaction, bot_name)

    @tree.command(name="bot-start", description="▶️ Start specific bot")
    async def bot_start_english(
        interaction: discord.Interaction,
        bot_name: str,
    ):
        """Bot start command (English) - ADMIN permission required"""
        if not check_permission(interaction, PermissionLevel.ADMIN, config):
            await interaction.response.send_message(
                "🚫 Permission denied. This command requires **ADMIN** permission.",
                ephemeral=True,
            )
            logger.warning(f"Permission denied (bot-start): {interaction.user}")
            return
        await client._bot_start_command(interaction, bot_name)

    # =========================================================================
    # /봇정지 (Bot Stop) - ADMIN 권한 필요
    # =========================================================================

    @tree.command(name="봇정지", description="⏹️ 특정 봇 정지")
    async def bot_stop_korean(
        interaction: discord.Interaction,
        bot_name: str,
    ):
        """봇 정지 (한글) - ADMIN 권한 필요"""
        if not check_permission(interaction, PermissionLevel.ADMIN, config):
            await interaction.response.send_message(
                "🚫 권한이 없습니다. 이 명령어는 **ADMIN** 이상의 권한이 필요합니다.",
                ephemeral=True,
            )
            logger.warning(f"권한 부족 (봇정지): {interaction.user}")
            return
        await client._bot_stop_command(interaction, bot_name)

    @tree.command(name="bot-stop", description="⏹️ Stop specific bot")
    async def bot_stop_english(
        interaction: discord.Interaction,
        bot_name: str,
    ):
        """Bot stop command (English) - ADMIN permission required"""
        if not check_permission(interaction, PermissionLevel.ADMIN, config):
            await interaction.response.send_message(
                "🚫 Permission denied. This command requires **ADMIN** permission.",
                ephemeral=True,
            )
            logger.warning(f"Permission denied (bot-stop): {interaction.user}")
            return
        await client._bot_stop_command(interaction, bot_name)

    # =========================================================================
    # /봇일시정지 (Bot Pause) - TRADER 권한 필요
    # =========================================================================

    @tree.command(name="봇일시정지", description="⏸️ 특정 봇 일시정지")
    async def bot_pause_korean(
        interaction: discord.Interaction,
        bot_name: str,
    ):
        """봇 일시정지 (한글) - TRADER 권한 필요"""
        if not check_permission(interaction, PermissionLevel.TRADER, config):
            await interaction.response.send_message(
                "🚫 권한이 없습니다. 이 명령어는 **TRADER** 이상의 권한이 필요합니다.",
                ephemeral=True,
            )
            logger.warning(f"권한 부족 (봇일시정지): {interaction.user}")
            return
        await client._bot_pause_command(interaction, bot_name)

    @tree.command(name="bot-pause", description="⏸️ Pause specific bot")
    async def bot_pause_english(
        interaction: discord.Interaction,
        bot_name: str,
    ):
        """Bot pause command (English) - TRADER permission required"""
        if not check_permission(interaction, PermissionLevel.TRADER, config):
            await interaction.response.send_message(
                "🚫 Permission denied. This command requires **TRADER** or higher permission.",
                ephemeral=True,
            )
            logger.warning(f"Permission denied (bot-pause): {interaction.user}")
            return
        await client._bot_pause_command(interaction, bot_name)

    # =========================================================================
    # /봇재개 (Bot Resume) - TRADER 권한 필요
    # =========================================================================

    @tree.command(name="봇재개", description="▶️ 일시정지된 봇 재개")
    async def bot_resume_korean(
        interaction: discord.Interaction,
        bot_name: str,
    ):
        """봇 재개 (한글) - TRADER 권한 필요"""
        if not check_permission(interaction, PermissionLevel.TRADER, config):
            await interaction.response.send_message(
                "🚫 권한이 없습니다. 이 명령어는 **TRADER** 이상의 권한이 필요합니다.",
                ephemeral=True,
            )
            logger.warning(f"권한 부족 (봇재개): {interaction.user}")
            return
        await client._bot_resume_command(interaction, bot_name)

    @tree.command(name="bot-resume", description="▶️ Resume paused bot")
    async def bot_resume_english(
        interaction: discord.Interaction,
        bot_name: str,
    ):
        """Bot resume command (English) - TRADER permission required"""
        if not check_permission(interaction, PermissionLevel.TRADER, config):
            await interaction.response.send_message(
                "🚫 Permission denied. This command requires **TRADER** or higher permission.",
                ephemeral=True,
            )
            logger.warning(f"Permission denied (bot-resume): {interaction.user}")
            return
        await client._bot_resume_command(interaction, bot_name)

    # =========================================================================
    # /전체시작 (Start All) - ADMIN 권한 필요
    # =========================================================================

    @tree.command(name="전체시작", description="▶️ 모든 봇 시작")
    async def start_all_korean(interaction: discord.Interaction):
        """전체 봇 시작 (한글) - ADMIN 권한 필요"""
        if not check_permission(interaction, PermissionLevel.ADMIN, config):
            await interaction.response.send_message(
                "🚫 권한이 없습니다. 이 명령어는 **ADMIN** 이상의 권한이 필요합니다.",
                ephemeral=True,
            )
            logger.warning(f"권한 부족 (전체시작): {interaction.user}")
            return
        await client._start_all_command(interaction)

    @tree.command(name="start-all", description="▶️ Start all bots")
    async def start_all_english(interaction: discord.Interaction):
        """Start all command (English) - ADMIN permission required"""
        if not check_permission(interaction, PermissionLevel.ADMIN, config):
            await interaction.response.send_message(
                "🚫 Permission denied. This command requires **ADMIN** permission.",
                ephemeral=True,
            )
            logger.warning(f"Permission denied (start-all): {interaction.user}")
            return
        await client._start_all_command(interaction)

    # =========================================================================
    # /전체정지 (Stop All) - ADMIN 권한 필요
    # =========================================================================

    @tree.command(name="전체정지", description="⏹️ 모든 봇 정지")
    async def stop_all_korean(interaction: discord.Interaction):
        """전체 봇 정지 (한글) - ADMIN 권한 필요"""
        if not check_permission(interaction, PermissionLevel.ADMIN, config):
            await interaction.response.send_message(
                "🚫 권한이 없습니다. 이 명령어는 **ADMIN** 이상의 권한이 필요합니다.",
                ephemeral=True,
            )
            logger.warning(f"권한 부족 (전체정지): {interaction.user}")
            return
        await client._stop_all_command(interaction)

    @tree.command(name="stop-all", description="⏹️ Stop all bots")
    async def stop_all_english(interaction: discord.Interaction):
        """Stop all command (English) - ADMIN permission required"""
        if not check_permission(interaction, PermissionLevel.ADMIN, config):
            await interaction.response.send_message(
                "🚫 Permission denied. This command requires **ADMIN** permission.",
                ephemeral=True,
            )
            logger.warning(f"Permission denied (stop-all): {interaction.user}")
            return
        await client._stop_all_command(interaction)

    logger.debug("멀티봇 명령어 등록 완료 (권한 시스템 적용)")
