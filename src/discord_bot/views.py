"""Discord UI Views.

버튼 및 인터랙티브 UI 컴포넌트를 정의합니다.

권한 체크:
- 정보 조회 버튼: VIEWER (모든 사용자)
- 일시정지/재개 버튼: TRADER 이상
- 긴급청산 버튼: ADMIN 이상
"""
import time
from typing import TYPE_CHECKING

import discord
from loguru import logger

from src.discord_bot.constants import Colors, Messages, Timeouts
from src.discord_bot.permissions import (
    PermissionLevel,
    check_permission,
    get_permission_config,
)

if TYPE_CHECKING:
    from src.discord_bot.client import TradingBotClient


class DashboardView(discord.ui.View):
    """대시보드 메인 UI (7개 버튼).

    Row 0: 상태(전체), 포지션(전체), 수익(일간), 내역 — VIEWER 권한
    Row 1: 일시정지(전체), 재개(전체), 긴급청산(전체) — TRADER/ADMIN 권한
    """

    # 버튼 클릭 쿨다운 (초)
    BUTTON_COOLDOWN = 3.0

    def __init__(
        self,
        bot_client: "TradingBotClient",
        timeout: int = Timeouts.DASHBOARD_VIEW,
    ):
        super().__init__(timeout=timeout)
        self.bot_client = bot_client
        self._permission_config = get_permission_config()
        self._last_interaction: dict[int, float] = {}

    def _check_cooldown(self, user_id: int) -> bool:
        now = time.monotonic()
        last_time = self._last_interaction.get(user_id, 0.0)
        if now - last_time < self.BUTTON_COOLDOWN:
            return False
        self._last_interaction[user_id] = now
        return True

    # =========================================================================
    # Row 0: 정보 조회 버튼
    # =========================================================================

    @discord.ui.button(label="📊 상태", style=discord.ButtonStyle.primary, row=0)
    async def status_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """전체 봇 상태 조회."""
        if not self._check_cooldown(interaction.user.id):
            await interaction.response.send_message(
                "⏳ 잠시 후 다시 시도해주세요.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        try:
            result = await self.bot_client._call_bot_api("GET", "/api/bots")
            data = result.get("data", result)
            from src.discord_bot.embeds import create_bot_list_embed  # noqa: PLC0415
            embed = create_bot_list_embed(data)
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"대시보드 상태 버튼 클릭: {interaction.user}")
        except Exception as e:
            logger.error(f"상태 버튼 에러: {e}")
            await interaction.followup.send(f"❌ 오류: {e!s}", ephemeral=True)

    @discord.ui.button(label="📍 포지션", style=discord.ButtonStyle.primary, row=0)
    async def position_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """전체 포지션 조회."""
        if not self._check_cooldown(interaction.user.id):
            await interaction.response.send_message(
                "⏳ 잠시 후 다시 시도해주세요.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        try:
            result = await self.bot_client._call_bot_api("GET", "/api/bots")
            data = result.get("data", result)
            bots = data.get("bots", [])

            embed = discord.Embed(title="📍 전체 포지션", color=Colors.INFO)
            has_position = False
            for bot_info in bots:
                name = bot_info.get("name", "unknown")
                position = bot_info.get("position")
                if position and position.get("side"):
                    has_position = True
                    side = position["side"]
                    entry = position.get("entry_price", 0)
                    emoji = "🟢" if side == "LONG" else "🔴"
                    embed.add_field(
                        name=f"{emoji} {name}",
                        value=f"{side} @ ${entry:,.2f}",
                        inline=True,
                    )
            if not has_position:
                embed.description = "열린 포지션이 없습니다"

            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"대시보드 포지션 버튼 클릭: {interaction.user}")
        except Exception as e:
            logger.error(f"포지션 버튼 에러: {e}")
            await interaction.followup.send(f"❌ 오류: {e!s}", ephemeral=True)

    @discord.ui.button(label="💰 수익", style=discord.ButtonStyle.primary, row=0)
    async def pnl_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """일간 수익 조회."""
        if not self._check_cooldown(interaction.user.id):
            await interaction.response.send_message(
                "⏳ 잠시 후 다시 시도해주세요.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        try:
            embed = await self.bot_client._get_pnl_embed(hours=24)
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"대시보드 수익 버튼 클릭: {interaction.user}")
        except Exception as e:
            logger.error(f"수익 버튼 에러: {e}")
            await interaction.followup.send(f"❌ 오류: {e!s}", ephemeral=True)

    @discord.ui.button(label="📜 내역", style=discord.ButtonStyle.primary, row=0)
    async def history_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """거래 내역 조회."""
        if not self._check_cooldown(interaction.user.id):
            await interaction.response.send_message(
                "⏳ 잠시 후 다시 시도해주세요.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        try:
            embed = await self.bot_client._get_history_embed(limit=5)
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"대시보드 내역 버튼 클릭: {interaction.user}")
        except Exception as e:
            logger.error(f"내역 버튼 에러: {e}")
            await interaction.followup.send(f"❌ 오류: {e!s}", ephemeral=True)

    # =========================================================================
    # Row 1: 제어 버튼 (REST API)
    # =========================================================================

    @discord.ui.button(
        label="⏸️ 일시정지", style=discord.ButtonStyle.secondary, row=1
    )
    async def pause_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """전체 일시정지 (REST API)."""
        if not self._check_cooldown(interaction.user.id):
            await interaction.response.send_message(
                "⏳ 잠시 후 다시 시도해주세요.", ephemeral=True
            )
            return
        if not check_permission(
            interaction, PermissionLevel.TRADER, self._permission_config
        ):
            await interaction.response.send_message(
                Messages.PERMISSION_DENIED_BUTTON, ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        try:
            # 전체 봇 일시정지
            result = await self.bot_client._call_bot_api("GET", "/api/bots")
            bots = result.get("data", result).get("bots", [])
            count = 0
            for bot_info in bots:
                name = bot_info.get("name")
                if name:
                    try:
                        await self.bot_client._call_bot_api(
                            "POST", f"/api/bots/{name}/pause"
                        )
                        count += 1
                    except Exception:  # noqa: S110
                        pass
            await interaction.followup.send(
                f"⏸️ {count}개 봇 일시정지 완료", ephemeral=True
            )
            logger.warning(f"대시보드 일시정지 버튼: {interaction.user}")
        except Exception as e:
            logger.error(f"일시정지 버튼 에러: {e}")
            await interaction.followup.send(f"❌ 오류: {e!s}", ephemeral=True)

    @discord.ui.button(
        label="▶️ 재개", style=discord.ButtonStyle.success, row=1
    )
    async def resume_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """전체 재개 (REST API)."""
        if not self._check_cooldown(interaction.user.id):
            await interaction.response.send_message(
                "⏳ 잠시 후 다시 시도해주세요.", ephemeral=True
            )
            return
        if not check_permission(
            interaction, PermissionLevel.TRADER, self._permission_config
        ):
            await interaction.response.send_message(
                Messages.PERMISSION_DENIED_BUTTON, ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        try:
            result = await self.bot_client._call_bot_api("GET", "/api/bots")
            bots = result.get("data", result).get("bots", [])
            count = 0
            for bot_info in bots:
                name = bot_info.get("name")
                if name:
                    try:
                        await self.bot_client._call_bot_api(
                            "POST", f"/api/bots/{name}/resume"
                        )
                        count += 1
                    except Exception:  # noqa: S110
                        pass
            await interaction.followup.send(
                f"▶️ {count}개 봇 재개 완료", ephemeral=True
            )
            logger.info(f"대시보드 재개 버튼: {interaction.user}")
        except Exception as e:
            logger.error(f"재개 버튼 에러: {e}")
            await interaction.followup.send(f"❌ 오류: {e!s}", ephemeral=True)

    @discord.ui.button(
        label="🚨 긴급청산", style=discord.ButtonStyle.danger, row=1
    )
    async def emergency_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """전체 긴급청산 (bot_manager 직접 호출)."""
        if not self._check_cooldown(interaction.user.id):
            await interaction.response.send_message(
                "⏳ 잠시 후 다시 시도해주세요.", ephemeral=True
            )
            return
        if not check_permission(
            interaction, PermissionLevel.ADMIN, self._permission_config
        ):
            await interaction.response.send_message(
                Messages.PERMISSION_DENIED_BUTTON, ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        try:
            bots = self.bot_client.bot_manager.bots
            count = 0
            for _name, bot in bots.items():
                bot.request_emergency_close()
                count += 1
            await interaction.followup.send(
                f"🚨 {count}개 봇 긴급 청산 요청 완료\n"
                "각 봇은 다음 루프에서 시장가로 청산됩니다.",
                ephemeral=True,
            )
            logger.critical(f"대시보드 긴급청산 버튼: {interaction.user}")
        except Exception as e:
            logger.error(f"긴급청산 버튼 에러: {e}")
            await interaction.followup.send(f"❌ 오류: {e!s}", ephemeral=True)
