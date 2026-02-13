"""모니터링 관련 슬래시 명령어.

8개 한글 명령어: 대시보드, 상태, 포지션, 수익, 내역, 계정, 프롬프트, 핑
"""
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from loguru import logger

from src.discord_bot.utils import PERIOD_LABELS, PERIOD_MAP

if TYPE_CHECKING:
    from src.discord_bot.client import TradingBotClient


def register_monitoring_commands(client: "TradingBotClient") -> None:
    """모니터링 슬래시 명령어 등록.

    Args:
        client: TradingBotClient 인스턴스
    """
    tree = client.tree

    # /대시보드
    @tree.command(name="대시보드", description="트레이딩 봇 대시보드 (버튼 UI)")
    async def dashboard_cmd(interaction: discord.Interaction):
        await client._dashboard_command(interaction)

    # /상태 [봇이름?]
    @tree.command(name="상태", description="봇 상태 조회 (이름 생략 시 전체)")
    @app_commands.describe(봇이름="조회할 봇 (생략 시 전체 봇 목록)")
    async def status_cmd(
        interaction: discord.Interaction, 봇이름: str = ""  # noqa: N803, PLC2401
    ):
        if 봇이름:
            await client._status_bot_command(interaction, 봇이름)
        else:
            await client._status_all_command(interaction)

    # /포지션 [봇이름?]
    @tree.command(name="포지션", description="현재 포지션 상세 정보")
    @app_commands.describe(봇이름="조회할 봇 (생략 시 전체)")
    async def position_cmd(
        interaction: discord.Interaction, 봇이름: str = ""  # noqa: N803, PLC2401
    ):
        await client._position_command(interaction, 봇이름)

    # /수익 [기간] [봇이름?]
    @tree.command(name="수익", description="거래 수익 리포트")
    @app_commands.describe(
        기간="조회 기간 (기본: 일간)",
        봇이름="조회할 봇 (생략 시 전체)",
    )
    @app_commands.choices(
        기간=[
            app_commands.Choice(name="일간 (24시간)", value="일간"),
            app_commands.Choice(name="주간 (7일)", value="주간"),
            app_commands.Choice(name="월간 (30일)", value="월간"),
        ]
    )
    async def pnl_cmd(
        interaction: discord.Interaction,
        기간: app_commands.Choice[str] | None = None,  # noqa: N803, PLC2401
        봇이름: str = "",  # noqa: N803, PLC2401
    ):
        period_key = 기간.value if 기간 else "일간"
        hours = PERIOD_MAP.get(period_key, 24)
        period_label = PERIOD_LABELS.get(period_key, "일간 (24시간)")
        await client._pnl_command(interaction, hours, period_label, 봇이름)

    # /내역 [봇이름?] [개수]
    @tree.command(name="내역", description="최근 거래 내역")
    @app_commands.describe(개수="표시할 거래 수 (기본 5, 최대 10)")
    async def history_cmd(
        interaction: discord.Interaction,
        개수: int = 5,  # noqa: N803, PLC2401
    ):
        await client._history_command(interaction, 개수)

    # /계정
    @tree.command(name="계정", description="계정 전체 포지션 및 잔고 조회")
    async def account_cmd(interaction: discord.Interaction):
        await client._account_command(interaction)

    # /프롬프트 [봇이름]
    @tree.command(name="프롬프트", description="마지막 AI 프롬프트 및 응답 조회")
    @app_commands.describe(봇이름="조회할 봇 (생략 시 첫 번째 봇)")
    async def prompt_cmd(
        interaction: discord.Interaction, 봇이름: str = ""  # noqa: N803, PLC2401
    ):
        await client._prompt_command(interaction, 봇이름)

    # /핑
    @tree.command(name="핑", description="봇 응답 확인")
    async def ping_cmd(interaction: discord.Interaction):
        await interaction.response.send_message("🏓 퐁!", ephemeral=True)
        logger.info(f"Discord 명령어 /핑 실행: {interaction.user}")

    logger.debug("모니터링 명령어 등록 완료 (8개)")
