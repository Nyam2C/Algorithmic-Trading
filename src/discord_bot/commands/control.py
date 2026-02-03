"""
제어 관련 슬래시 명령어

일시정지, 재시작, 긴급청산 명령어를 제공합니다.
"""
from typing import TYPE_CHECKING

import discord
from loguru import logger

if TYPE_CHECKING:
    from src.discord_bot.client import TradingBotClient


def register_control_commands(client: "TradingBotClient") -> None:
    """제어 슬래시 명령어 등록

    Args:
        client: TradingBotClient 인스턴스
    """
    tree = client.tree

    # =========================================================================
    # /일시정지 (Stop)
    # =========================================================================

    @tree.command(name="일시정지", description="봇 일시 정지 (새 포지션 진입 중지)")
    async def stop_korean(interaction: discord.Interaction):
        """일시정지 (한글)"""
        await client._stop_command(interaction)

    @tree.command(name="stop", description="Pause the trading bot (stop new positions)")
    async def stop_english(interaction: discord.Interaction):
        """Stop command (English)"""
        await client._stop_command(interaction)

    # =========================================================================
    # /재시작 (Start)
    # =========================================================================

    @tree.command(name="재시작", description="봇 재시작 (정상 거래 재개)")
    async def start_korean(interaction: discord.Interaction):
        """재시작 (한글)"""
        await client._start_command(interaction)

    @tree.command(name="start", description="Resume the trading bot (normal trading)")
    async def start_english(interaction: discord.Interaction):
        """Start command (English)"""
        await client._start_command(interaction)

    # =========================================================================
    # /긴급청산 (Emergency)
    # =========================================================================

    @tree.command(name="긴급청산", description="🚨 긴급 청산 (현재 포지션 즉시 청산 + 봇 정지)")
    async def emergency_korean(interaction: discord.Interaction):
        """긴급청산 (한글)"""
        await client._emergency_command(interaction)

    @tree.command(name="emergency", description="🚨 Emergency close (close position + pause bot)")
    async def emergency_english(interaction: discord.Interaction):
        """Emergency command (English)"""
        await client._emergency_command(interaction)

    logger.debug("제어 명령어 등록 완료")
