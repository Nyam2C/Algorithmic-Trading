"""
모니터링 관련 슬래시 명령어

상태, 포지션, 통계, 내역, 계정 조회 명령어를 제공합니다.
"""
from typing import TYPE_CHECKING

import discord
from loguru import logger

if TYPE_CHECKING:
    from src.discord_bot.client import TradingBotClient


def register_monitoring_commands(client: "TradingBotClient") -> None:
    """모니터링 슬래시 명령어 등록

    Args:
        client: TradingBotClient 인스턴스
    """
    tree = client.tree

    # =========================================================================
    # /대시보드 (Dashboard)
    # =========================================================================

    @tree.command(name="대시보드", description="📊 트레이딩 봇 대시보드 (버튼 UI)")
    async def dashboard_korean(interaction: discord.Interaction):
        """대시보드 명령어 (한글)"""
        await client._dashboard_command(interaction)

    @tree.command(name="dashboard", description="📊 Trading Bot Dashboard (Button UI)")
    async def dashboard_english(interaction: discord.Interaction):
        """Dashboard command (English)"""
        await client._dashboard_command(interaction)

    # =========================================================================
    # /상태 (Status)
    # =========================================================================

    @tree.command(name="상태", description="봇 실행 상태 및 현재 포지션 확인")
    async def status_korean(interaction: discord.Interaction):
        """상태 조회 (한글)"""
        await client._status_command(interaction)

    @tree.command(name="status", description="Show bot status and current position")
    async def status_english(interaction: discord.Interaction):
        """Status command (English)"""
        await client._status_command(interaction)

    # =========================================================================
    # /포지션 (Position)
    # =========================================================================

    @tree.command(name="포지션", description="현재 포지션 상세 정보")
    async def position_korean(interaction: discord.Interaction):
        """포지션 조회 (한글)"""
        await client._position_command(interaction)

    @tree.command(name="position", description="Show detailed position information")
    async def position_english(interaction: discord.Interaction):
        """Position command (English)"""
        await client._position_command(interaction)

    # =========================================================================
    # /통계 (Stats)
    # =========================================================================

    @tree.command(name="통계", description="거래 통계 (최근 N시간)")
    async def stats_korean(interaction: discord.Interaction, hours: int = 24):
        """통계 조회 (한글)"""
        await client._stats_command(interaction, hours)

    @tree.command(name="stats", description="Trading statistics (recent N hours)")
    async def stats_english(interaction: discord.Interaction, hours: int = 24):
        """Stats command (English)"""
        await client._stats_command(interaction, hours)

    # =========================================================================
    # /내역 (History)
    # =========================================================================

    @tree.command(name="내역", description="최근 거래 내역")
    async def history_korean(interaction: discord.Interaction, count: int = 5):
        """내역 조회 (한글)"""
        await client._history_command(interaction, count)

    @tree.command(name="history", description="Recent trade history")
    async def history_english(interaction: discord.Interaction, count: int = 5):
        """History command (English)"""
        await client._history_command(interaction, count)

    # =========================================================================
    # /계정 (Account)
    # =========================================================================

    @tree.command(name="계정", description="💼 계정 전체 포지션 및 잔고 조회")
    async def account_korean(interaction: discord.Interaction):
        """계정 조회 (한글)"""
        await client._account_command(interaction)

    @tree.command(name="account", description="💼 View all account positions and balance")
    async def account_english(interaction: discord.Interaction):
        """Account command (English)"""
        await client._account_command(interaction)

    # =========================================================================
    # /핑 (Ping)
    # =========================================================================

    @tree.command(name="핑", description="봇 응답 확인")
    async def ping_korean(interaction: discord.Interaction):
        """핑 (한글)"""
        await interaction.response.send_message("🏓 퐁!", ephemeral=True)
        logger.info(f"Discord 명령어 /핑 실행: {interaction.user}")

    @tree.command(name="ping", description="Check if bot is responding")
    async def ping_english(interaction: discord.Interaction):
        """Ping command (English)"""
        await interaction.response.send_message("🏓 Pong!", ephemeral=True)
        logger.info(f"Discord command /ping executed by {interaction.user}")

    logger.debug("모니터링 명령어 등록 완료")
