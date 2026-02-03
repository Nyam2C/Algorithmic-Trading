"""
Discord UI Views

버튼 및 인터랙티브 UI 컴포넌트를 정의합니다.
"""
from datetime import datetime
from typing import Optional, Dict, Any, TYPE_CHECKING

import discord
from loguru import logger

from src.discord_bot.constants import Colors, Timeouts, Emojis, Messages

if TYPE_CHECKING:
    from src.discord_bot.client import TradingBotClient


class ConfirmationView(discord.ui.View):
    """확인 대화상자 (위험한 작업용)

    일시정지, 재시작, 긴급청산 등 확인이 필요한 작업에 사용됩니다.
    """

    def __init__(
        self,
        action: str,
        bot_state: dict,
        action_data: Optional[Dict[str, Any]] = None,
        timeout: int = Timeouts.CONFIRMATION_VIEW
    ):
        """ConfirmationView 초기화

        Args:
            action: 작업 유형 ("pause", "resume", "emergency")
            bot_state: 공유 봇 상태 딕셔너리
            action_data: 작업 관련 추가 데이터
            timeout: 타임아웃 (초)
        """
        super().__init__(timeout=timeout)
        self.action = action
        self.bot_state = bot_state
        self.action_data = action_data or {}
        self.confirmed = False
        self.cancelled = False

    @discord.ui.button(label="✅ 예, 실행", style=discord.ButtonStyle.green)
    async def confirm_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """확인 버튼"""
        try:
            self.confirmed = True

            if self.action == "pause":
                await self._handle_pause(interaction)
            elif self.action == "resume":
                await self._handle_resume(interaction)
            elif self.action == "emergency":
                await self._handle_emergency(interaction)

            self.stop()

        except Exception as e:
            logger.error(f"확인 버튼 에러: {e}")
            await interaction.response.send_message(
                f"❌ 오류: {str(e)}",
                ephemeral=True
            )

    @discord.ui.button(label="❌ 취소", style=discord.ButtonStyle.red)
    async def cancel_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """취소 버튼"""
        self.cancelled = True
        await interaction.response.send_message(
            Messages.CANCELLED,
            ephemeral=True
        )
        self.stop()

    async def _handle_pause(self, interaction: discord.Interaction):
        """일시정지 처리"""
        self.bot_state["is_paused"] = True
        self.bot_state["paused_by"] = str(interaction.user)
        self.bot_state["paused_at"] = datetime.now()

        await interaction.response.send_message(
            f"{Messages.BOT_PAUSED}\n새 포지션 진입이 중지됩니다. 기존 포지션은 계속 관리됩니다.",
            ephemeral=True
        )
        logger.warning(f"봇 일시정지: {interaction.user}")

    async def _handle_resume(self, interaction: discord.Interaction):
        """재시작 처리"""
        was_paused = self.bot_state.get("is_paused", False)
        self.bot_state["is_paused"] = False
        self.bot_state["resumed_by"] = str(interaction.user)
        self.bot_state["resumed_at"] = datetime.now()

        pause_info = ""
        if was_paused and self.bot_state.get("paused_at"):
            pause_duration = datetime.now() - self.bot_state["paused_at"]
            hours = int(pause_duration.total_seconds() / 3600)
            mins = int((pause_duration.total_seconds() % 3600) / 60)
            paused_by = self.bot_state.get("paused_by", "알 수 없음")
            pause_info = f"\n일시정지 시간: {hours}시간 {mins}분 ({paused_by})"

        await interaction.response.send_message(
            f"{Messages.BOT_RESUMED}\n정상 거래가 재개됩니다.{pause_info}",
            ephemeral=True
        )
        logger.info(f"봇 재시작: {interaction.user}")

    async def _handle_emergency(self, interaction: discord.Interaction):
        """긴급 청산 처리"""
        position = self.bot_state.get("position")

        if not position or not position.get("side"):
            await interaction.response.send_message(
                Messages.NO_POSITION,
                ephemeral=True
            )
            self.stop()
            return

        # 긴급 청산 플래그 설정
        self.bot_state["emergency_close"] = True
        self.bot_state["emergency_by"] = str(interaction.user)
        self.bot_state["emergency_at"] = datetime.now()
        self.bot_state["is_paused"] = True

        side = position.get("side")
        entry = position.get("entry_price", 0)

        await interaction.response.send_message(
            f"{Emojis.EMERGENCY} **긴급 청산 요청**\n"
            f"포지션: {side} @ ${entry:,.2f}\n"
            f"다음 루프에서 시장가로 청산됩니다.\n"
            f"봇은 자동으로 일시정지됩니다.",
            ephemeral=True
        )
        logger.critical(f"긴급 청산 요청: {interaction.user}")


class DashboardView(discord.ui.View):
    """대시보드 메인 UI (7개 버튼)

    정보 조회 버튼 (Row 0): 상태, 포지션, 통계, 내역
    제어 버튼 (Row 1): 일시정지, 재시작, 긴급청산
    """

    def __init__(
        self,
        bot_client: "TradingBotClient",
        timeout: int = Timeouts.DASHBOARD_VIEW
    ):
        """DashboardView 초기화

        Args:
            bot_client: TradingBotClient 인스턴스
            timeout: 타임아웃 (초)
        """
        super().__init__(timeout=timeout)
        self.bot_client = bot_client

    # =========================================================================
    # Row 0: 정보 조회 버튼
    # =========================================================================

    @discord.ui.button(label="📊 상태", style=discord.ButtonStyle.primary, row=0)
    async def status_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """상태 조회 버튼"""
        await interaction.response.defer(ephemeral=True)
        try:
            embed = await self.bot_client._get_status_embed()
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"대시보드 상태 버튼 클릭: {interaction.user}")
        except Exception as e:
            logger.error(f"상태 버튼 에러: {e}")
            await interaction.followup.send(f"❌ 오류: {str(e)}", ephemeral=True)

    @discord.ui.button(label="📍 포지션", style=discord.ButtonStyle.primary, row=0)
    async def position_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """포지션 조회 버튼"""
        await interaction.response.defer(ephemeral=True)
        try:
            embed = await self.bot_client._get_position_embed()
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"대시보드 포지션 버튼 클릭: {interaction.user}")
        except Exception as e:
            logger.error(f"포지션 버튼 에러: {e}")
            await interaction.followup.send(f"❌ 오류: {str(e)}", ephemeral=True)

    @discord.ui.button(label="📈 통계", style=discord.ButtonStyle.primary, row=0)
    async def stats_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """통계 조회 버튼"""
        await interaction.response.defer(ephemeral=True)
        try:
            embed = await self.bot_client._get_stats_embed(hours=24)
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"대시보드 통계 버튼 클릭: {interaction.user}")
        except Exception as e:
            logger.error(f"통계 버튼 에러: {e}")
            await interaction.followup.send(f"❌ 오류: {str(e)}", ephemeral=True)

    @discord.ui.button(label="📜 내역", style=discord.ButtonStyle.primary, row=0)
    async def history_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """거래 내역 버튼"""
        await interaction.response.defer(ephemeral=True)
        try:
            embed = await self.bot_client._get_history_embed(limit=5)
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"대시보드 내역 버튼 클릭: {interaction.user}")
        except Exception as e:
            logger.error(f"내역 버튼 에러: {e}")
            await interaction.followup.send(f"❌ 오류: {str(e)}", ephemeral=True)

    # =========================================================================
    # Row 1: 제어 버튼
    # =========================================================================

    @discord.ui.button(label="⏸️ 일시정지", style=discord.ButtonStyle.secondary, row=1)
    async def pause_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """일시정지 버튼 (확인 필요)"""
        try:
            if self.bot_client.bot_state.get("is_paused", False):
                await interaction.response.send_message(
                    Messages.ALREADY_PAUSED,
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title="⚠️ 일시정지 확인",
                description=(
                    "봇을 일시정지하시겠습니까?\n\n"
                    "**변경사항:**\n"
                    "• 새 포지션 진입 중지\n"
                    "• 기존 포지션은 계속 관리 (TP/SL)\n\n"
                    "정말 실행하시겠습니까?"
                ),
                color=Colors.WARNING
            )
            view = ConfirmationView("pause", self.bot_client.bot_state)
            await interaction.response.send_message(
                embed=embed,
                view=view,
                ephemeral=True
            )
            logger.info(f"일시정지 확인 대화상자 표시: {interaction.user}")

        except Exception as e:
            logger.error(f"일시정지 버튼 에러: {e}")
            await interaction.response.send_message(
                f"❌ 오류: {str(e)}",
                ephemeral=True
            )

    @discord.ui.button(label="▶️ 재시작", style=discord.ButtonStyle.success, row=1)
    async def resume_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """재시작 버튼 (확인 필요)"""
        try:
            if not self.bot_client.bot_state.get("is_paused", False):
                await interaction.response.send_message(
                    Messages.ALREADY_RUNNING,
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title="⚠️ 재시작 확인",
                description=(
                    "봇을 재시작하시겠습니까?\n\n"
                    "**변경사항:**\n"
                    "• 정상 거래 재개\n"
                    "• 다음 루프부터 신호 생성 및 진입\n\n"
                    "정말 실행하시겠습니까?"
                ),
                color=Colors.SUCCESS
            )
            view = ConfirmationView("resume", self.bot_client.bot_state)
            await interaction.response.send_message(
                embed=embed,
                view=view,
                ephemeral=True
            )
            logger.info(f"재시작 확인 대화상자 표시: {interaction.user}")

        except Exception as e:
            logger.error(f"재시작 버튼 에러: {e}")
            await interaction.response.send_message(
                f"❌ 오류: {str(e)}",
                ephemeral=True
            )

    @discord.ui.button(label="🚨 긴급청산", style=discord.ButtonStyle.danger, row=1)
    async def emergency_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        """긴급청산 버튼 (확인 필요)"""
        try:
            position = self.bot_client.bot_state.get("position")

            if not position or not position.get("side"):
                await interaction.response.send_message(
                    Messages.NO_POSITION,
                    ephemeral=True
                )
                return

            side = position.get("side")
            entry_price = position.get("entry_price", 0)
            current_price = self.bot_client.bot_state.get("current_price", 0)

            embed = discord.Embed(
                title="🚨 긴급청산 확인",
                description=(
                    "**현재 포지션을 즉시 청산하고 봇을 정지합니다**\n\n"
                    "⚠️ **주의: 이 작업은 되돌릴 수 없습니다**"
                ),
                color=Colors.ERROR
            )

            emoji = Emojis.LONG if side == "LONG" else Emojis.SHORT
            embed.add_field(name=f"{emoji} 포지션", value=f"{side}", inline=True)
            embed.add_field(name="💵 진입가", value=f"${entry_price:,.2f}", inline=True)
            embed.add_field(name="📊 현재가", value=f"${current_price:,.2f}", inline=True)
            embed.add_field(
                name="⚠️ 안내",
                value=(
                    "• 다음 루프에서 시장가로 청산\n"
                    "• 봇은 자동으로 일시정지\n"
                    "• 재시작하려면 `/재시작` 명령 사용"
                ),
                inline=False
            )

            view = ConfirmationView("emergency", self.bot_client.bot_state)
            await interaction.response.send_message(
                embed=embed,
                view=view,
                ephemeral=True
            )
            logger.warning(f"긴급청산 확인 대화상자 표시: {interaction.user}")

        except Exception as e:
            logger.error(f"긴급청산 버튼 에러: {e}")
            await interaction.response.send_message(
                f"❌ 오류: {str(e)}",
                ephemeral=True
            )
