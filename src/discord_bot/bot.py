"""Discord Bot for Trading Bot Remote Control

한글 지원 + 인터랙티브 버튼 UI + 멀티봇 지원

Phase 3 업데이트:
- MultiBotManager 주입 지원
- 멀티봇 제어 슬래시 명령 추가
- 봇별 상태 조회 및 제어
"""
import os
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

import aiohttp
import discord
from discord import app_commands
from loguru import logger

if TYPE_CHECKING:
    from src.bot_manager import MultiBotManager


# =============================================================================
# View Classes (Buttons & Interactive UI)
# =============================================================================

class ConfirmationView(discord.ui.View):
    """확인 대화상자 (위험한 작업용)"""

    def __init__(self, action: str, bot_state: dict, action_data: Dict[str, Any] | None = None, timeout=30):
        super().__init__(timeout=timeout)
        self.action = action  # "pause", "resume", "emergency"
        self.bot_state = bot_state
        self.action_data = action_data or {}
        self.confirmed = False
        self.cancelled = False

    @discord.ui.button(label="✅ 예, 실행", style=discord.ButtonStyle.green)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """확인 버튼"""
        try:
            self.confirmed = True

            # 작업 실행
            if self.action == "pause":
                self.bot_state["is_paused"] = True
                self.bot_state["paused_by"] = str(interaction.user)
                self.bot_state["paused_at"] = datetime.now()

                await interaction.response.send_message(
                    "⏸️ **봇이 일시정지되었습니다**\n새 포지션 진입이 중지됩니다. 기존 포지션은 계속 관리됩니다.",
                    ephemeral=True
                )
                logger.warning(f"봇 일시정지: {interaction.user}")

            elif self.action == "resume":
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
                    f"▶️ **봇이 재시작되었습니다**\n정상 거래가 재개됩니다.{pause_info}",
                    ephemeral=True
                )
                logger.info(f"봇 재시작: {interaction.user}")

            elif self.action == "emergency":
                position = self.bot_state.get("position")

                if not position or not position.get("side"):
                    await interaction.response.send_message(
                        "❌ 청산할 포지션이 없습니다",
                        ephemeral=True
                    )
                    self.stop()
                    return

                # 긴급 청산 플래그 설정 (메인 루프에서 감지)
                self.bot_state["emergency_close"] = True
                self.bot_state["emergency_by"] = str(interaction.user)
                self.bot_state["emergency_at"] = datetime.now()
                self.bot_state["is_paused"] = True

                side = position.get("side")
                entry = position.get("entry_price", 0)

                await interaction.response.send_message(
                    f"🚨 **긴급 청산 요청**\n"
                    f"포지션: {side} @ ${entry:,.2f}\n"
                    f"다음 루프에서 시장가로 청산됩니다.\n"
                    f"봇은 자동으로 일시정지됩니다.",
                    ephemeral=True
                )
                logger.critical(f"긴급 청산 요청: {interaction.user}")

            # 버튼 비활성화
            self.stop()

        except Exception as e:
            logger.error(f"확인 버튼 에러: {e}")
            await interaction.response.send_message(
                f"❌ 오류: {e!s}",
                ephemeral=True
            )

    @discord.ui.button(label="❌ 취소", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """취소 버튼"""
        self.cancelled = True
        await interaction.response.send_message("취소되었습니다", ephemeral=True)
        self.stop()


class DashboardView(discord.ui.View):
    """대시보드 메인 UI (7개 버튼)"""

    def __init__(self, bot_client, timeout=180):
        super().__init__(timeout=timeout)
        self.bot_client = bot_client

    # Row 0: 정보 조회 버튼
    @discord.ui.button(label="📊 상태", style=discord.ButtonStyle.primary, row=0)
    async def status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """상태 조회 버튼"""
        await interaction.response.defer(ephemeral=True)
        try:
            embed = await self.bot_client._get_status_embed()
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"대시보드 상태 버튼 클릭: {interaction.user}")
        except Exception as e:
            logger.error(f"상태 버튼 에러: {e}")
            await interaction.followup.send(f"❌ 오류: {e!s}", ephemeral=True)

    @discord.ui.button(label="📍 포지션", style=discord.ButtonStyle.primary, row=0)
    async def position_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """포지션 조회 버튼"""
        await interaction.response.defer(ephemeral=True)
        try:
            embed = await self.bot_client._get_position_embed()
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"대시보드 포지션 버튼 클릭: {interaction.user}")
        except Exception as e:
            logger.error(f"포지션 버튼 에러: {e}")
            await interaction.followup.send(f"❌ 오류: {e!s}", ephemeral=True)

    @discord.ui.button(label="📈 통계", style=discord.ButtonStyle.primary, row=0)
    async def stats_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """통계 조회 버튼"""
        await interaction.response.defer(ephemeral=True)
        try:
            embed = await self.bot_client._get_stats_embed(hours=24)
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"대시보드 통계 버튼 클릭: {interaction.user}")
        except Exception as e:
            logger.error(f"통계 버튼 에러: {e}")
            await interaction.followup.send(f"❌ 오류: {e!s}", ephemeral=True)

    @discord.ui.button(label="📜 내역", style=discord.ButtonStyle.primary, row=0)
    async def history_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """거래 내역 버튼"""
        await interaction.response.defer(ephemeral=True)
        try:
            embed = await self.bot_client._get_history_embed(limit=5)
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"대시보드 내역 버튼 클릭: {interaction.user}")
        except Exception as e:
            logger.error(f"내역 버튼 에러: {e}")
            await interaction.followup.send(f"❌ 오류: {e!s}", ephemeral=True)

    # Row 1: 제어 버튼
    @discord.ui.button(label="⏸️ 일시정지", style=discord.ButtonStyle.secondary, row=1)
    async def pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """일시정지 버튼 (확인 필요)"""
        try:
            # 이미 일시정지 상태인지 확인
            if self.bot_client.bot_state.get("is_paused", False):
                await interaction.response.send_message(
                    "⚠️ 봇이 이미 일시정지 상태입니다",
                    ephemeral=True
                )
                return

            # 확인 대화상자 표시
            embed = discord.Embed(
                title="⚠️ 일시정지 확인",
                description="봇을 일시정지하시겠습니까?\n\n"
                           "**변경사항:**\n"
                           "• 새 포지션 진입 중지\n"
                           "• 기존 포지션은 계속 관리 (TP/SL)\n\n"
                           "정말 실행하시겠습니까?",
                color=0xFFFF00
            )
            view = ConfirmationView("pause", self.bot_client.bot_state)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            logger.info(f"일시정지 확인 대화상자 표시: {interaction.user}")

        except Exception as e:
            logger.error(f"일시정지 버튼 에러: {e}")
            await interaction.response.send_message(f"❌ 오류: {e!s}", ephemeral=True)

    @discord.ui.button(label="▶️ 재시작", style=discord.ButtonStyle.success, row=1)
    async def resume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """재시작 버튼 (확인 필요)"""
        try:
            # 이미 실행 중인지 확인
            if not self.bot_client.bot_state.get("is_paused", False):
                await interaction.response.send_message(
                    "⚠️ 봇이 이미 실행 중입니다",
                    ephemeral=True
                )
                return

            # 확인 대화상자 표시
            embed = discord.Embed(
                title="⚠️ 재시작 확인",
                description="봇을 재시작하시겠습니까?\n\n"
                           "**변경사항:**\n"
                           "• 정상 거래 재개\n"
                           "• 다음 루프부터 신호 생성 및 진입\n\n"
                           "정말 실행하시겠습니까?",
                color=0x00FF00
            )
            view = ConfirmationView("resume", self.bot_client.bot_state)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            logger.info(f"재시작 확인 대화상자 표시: {interaction.user}")

        except Exception as e:
            logger.error(f"재시작 버튼 에러: {e}")
            await interaction.response.send_message(f"❌ 오류: {e!s}", ephemeral=True)

    @discord.ui.button(label="🚨 긴급청산", style=discord.ButtonStyle.danger, row=1)
    async def emergency_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """긴급청산 버튼 (확인 필요)"""
        try:
            position = self.bot_client.bot_state.get("position")

            if not position or not position.get("side"):
                await interaction.response.send_message(
                    "❌ 청산할 포지션이 없습니다",
                    ephemeral=True
                )
                return

            # 포지션 정보
            side = position.get("side")
            entry_price = position.get("entry_price", 0)
            current_price = self.bot_client.bot_state.get("current_price", 0)

            # 확인 대화상자 표시
            embed = discord.Embed(
                title="🚨 긴급청산 확인",
                description="**현재 포지션을 즉시 청산하고 봇을 정지합니다**\n\n"
                           "⚠️ **주의: 이 작업은 되돌릴 수 없습니다**",
                color=0xFF0000
            )

            emoji = "🟢" if side == "LONG" else "🔴"
            embed.add_field(
                name=f"{emoji} 포지션",
                value=f"{side}",
                inline=True
            )
            embed.add_field(
                name="💵 진입가",
                value=f"${entry_price:,.2f}",
                inline=True
            )
            embed.add_field(
                name="📊 현재가",
                value=f"${current_price:,.2f}",
                inline=True
            )
            embed.add_field(
                name="⚠️ 안내",
                value="• 다음 루프에서 시장가로 청산\n• 봇은 자동으로 일시정지\n• 재시작하려면 `/재시작` 명령 사용",
                inline=False
            )

            view = ConfirmationView("emergency", self.bot_client.bot_state)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            logger.warning(f"긴급청산 확인 대화상자 표시: {interaction.user}")

        except Exception as e:
            logger.error(f"긴급청산 버튼 에러: {e}")
            await interaction.response.send_message(f"❌ 오류: {e!s}", ephemeral=True)


# =============================================================================
# Main Bot Client
# =============================================================================

class TradingBotClient(discord.Client):
    """Discord 트레이딩 봇 클라이언트

    단일 봇 모드와 멀티봇 모드를 모두 지원합니다.
    - 단일 봇 모드: bot_state dict를 사용
    - 멀티봇 모드: MultiBotManager를 사용
    """

    def __init__(
        self,
        bot_state: dict,
        trade_db=None,
        binance_client=None,
        bot_manager: Optional["MultiBotManager"] = None,
    ):
        """Initialize Discord bot client

        Args:
            bot_state: Shared state dictionary with trading bot
            trade_db: TradeHistoryDB instance (optional)
            binance_client: BinanceTestnetClient instance (optional)
            bot_manager: MultiBotManager instance (optional, for multi-bot mode)
        """
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)

        self.tree = app_commands.CommandTree(self)
        self.bot_state = bot_state
        self.trade_db = trade_db
        self.binance_client = binance_client
        self.bot_manager = bot_manager
        self._api_url = os.getenv("TRADING_BOT_API_URL", "http://localhost:8000")
        self.setup_commands()

        # 멀티봇 명령어 항상 등록 (REST API를 통해 동작)
        self.setup_multibot_commands()

    # =========================================================================
    # Helper Methods (재사용 가능한 임베드 생성)
    # =========================================================================

    async def _get_status_embed(self) -> discord.Embed:
        """봇 상태 임베드 생성"""
        # Get bot state
        is_running = self.bot_state.get("is_running", False)
        current_price = self.bot_state.get("current_price", 0)
        last_signal = self.bot_state.get("last_signal", "WAIT")
        last_signal_time = self.bot_state.get("last_signal_time")
        is_paused = self.bot_state.get("is_paused", False)

        # Uptime 계산
        uptime_start = self.bot_state.get("uptime_start")
        if uptime_start:
            uptime_duration = datetime.now() - uptime_start
            hours = int(uptime_duration.total_seconds() / 3600)
            mins = int((uptime_duration.total_seconds() % 3600) / 60)
            uptime = f"{hours}시간 {mins}분"
        else:
            uptime = "N/A"

        # Last signal time 포맷
        if last_signal_time and isinstance(last_signal_time, datetime):
            time_diff = datetime.now() - last_signal_time
            mins_ago = int(time_diff.total_seconds() / 60)
            if mins_ago < 60:
                signal_time_str = f"{mins_ago}분 전"
            else:
                hours_ago = mins_ago // 60
                signal_time_str = f"{hours_ago}시간 전"
        else:
            signal_time_str = "N/A"

        # Get position
        position = self.bot_state.get("position")

        # Build embed
        embed = discord.Embed(
            title="🤖 봇 상태",
            color=0x00FF00 if (is_running and not is_paused) else 0xFF0000
        )

        # 상태 표시
        if is_running:
            if is_paused:
                status_value = "⏸️ 일시정지"
                status_color = "🟡"
            else:
                status_value = "✅ 실행 중"
                status_color = "🟢"
        else:
            status_value = "🛑 중지됨"
            status_color = "🔴"

        embed.add_field(
            name="⚡ 상태",
            value=f"{status_color} {status_value}",
            inline=True
        )
        embed.add_field(
            name="⏰ 가동시간",
            value=uptime,
            inline=True
        )
        embed.add_field(
            name="💰 심볼",
            value=self.bot_state.get("symbol", "BTCUSDT"),
            inline=True
        )
        embed.add_field(
            name="📊 현재가",
            value=f"${current_price:,.2f}",
            inline=True
        )

        # Position info
        if position and position.get("side"):
            side = position.get("side")
            emoji = "🟢" if side == "LONG" else "🔴"
            embed.add_field(
                name="📍 포지션",
                value=f"{emoji} {side}",
                inline=True
            )
        else:
            embed.add_field(
                name="📍 포지션",
                value="없음",
                inline=True
            )

        embed.add_field(
            name="🔄 마지막 신호",
            value=f"{last_signal} ({signal_time_str})",
            inline=False
        )
        embed.add_field(
            name="📈 전략",
            value="Rule-Based (RSI + MA)",
            inline=False
        )

        return embed

    async def _get_position_embed(self) -> discord.Embed:
        """포지션 상세 임베드 생성"""
        position = self.bot_state.get("position")

        if not position or not position.get("side"):
            embed = discord.Embed(
                title="📍 포지션 없음",
                description="⏸️ 신호를 기다리는 중...",
                color=0xFFFF00
            )
            embed.add_field(
                name="🔄 마지막 신호",
                value=self.bot_state.get("last_signal", "WAIT"),
                inline=False
            )
            return embed

        # Build position details
        side = position.get("side")
        entry_price = position.get("entry_price", 0)
        size = position.get("quantity", position.get("size", 0))
        leverage = position.get("leverage", 15)

        # Entry time
        entry_time = position.get("entry_time")
        if entry_time and isinstance(entry_time, datetime):
            duration_delta = datetime.now() - entry_time
            duration_mins = int(duration_delta.total_seconds() / 60)
            if duration_mins < 60:
                duration = f"{duration_mins}분"
            else:
                duration_hours = duration_mins // 60
                duration_mins_remain = duration_mins % 60
                duration = f"{duration_hours}시간 {duration_mins_remain}분"
        else:
            duration = "N/A"

        tp_price = position.get("tp_price", 0)
        sl_price = position.get("sl_price", 0)

        # Timecut
        timecut_at = position.get("timecut_at")
        if timecut_at and isinstance(timecut_at, datetime):
            timecut_remaining_delta = timecut_at - datetime.now()
            timecut_mins = int(timecut_remaining_delta.total_seconds() / 60)
            if timecut_mins > 0:
                timecut_remaining = f"{timecut_mins}분 남음"
            else:
                timecut_remaining = "만료됨"
        else:
            timecut_remaining = "N/A"

        current_price = self.bot_state.get("current_price", 0)

        # PnL 계산
        if side == "LONG":
            pnl_pct = ((current_price - entry_price) / entry_price) * 100 * leverage
        else:  # SHORT
            pnl_pct = ((entry_price - current_price) / entry_price) * 100 * leverage

        pnl_usd = (current_price - entry_price) * size if side == "LONG" else (entry_price - current_price) * size

        emoji = "🟢" if side == "LONG" else "🔴"
        color = 0x00FF00 if side == "LONG" else 0xFF0000

        embed = discord.Embed(
            title="📍 현재 포지션",
            color=color
        )

        embed.add_field(
            name=f"{emoji} 방향",
            value=side,
            inline=True
        )
        embed.add_field(
            name="💵 진입가",
            value=f"${entry_price:,.2f}",
            inline=True
        )
        embed.add_field(
            name="📊 수량",
            value=f"{size:.4f} BTC ({leverage}x)",
            inline=True
        )
        embed.add_field(
            name="⏱️ 경과시간",
            value=duration,
            inline=True
        )
        embed.add_field(
            name="🎯 익절가",
            value=f"${tp_price:,.2f} (+0.4%)",
            inline=True
        )
        embed.add_field(
            name="🛑 손절가",
            value=f"${sl_price:,.2f} (-0.4%)",
            inline=True
        )
        embed.add_field(
            name="⏰ 타임컷",
            value=f"{timecut_remaining}",
            inline=False
        )

        pnl_emoji = "💰" if pnl_usd > 0 else "📉"
        embed.add_field(
            name=f"{pnl_emoji} 현재 손익",
            value=f"${pnl_usd:+.2f} ({pnl_pct:+.2f}%)",
            inline=False
        )

        return embed

    async def _get_stats_embed(self, hours: int = 24) -> discord.Embed:
        """거래 통계 임베드 생성"""
        if not self.trade_db:
            embed = discord.Embed(
                title="❌ 데이터베이스 연결 안 됨",
                description="거래 데이터베이스를 사용할 수 없습니다",
                color=0xFF0000
            )
            return embed

        # Get statistics
        stats_data = await self.trade_db.get_statistics(hours=hours)

        if stats_data["total_trades"] == 0:
            embed = discord.Embed(
                title=f"📊 거래 없음 (최근 {hours}시간)",
                description="이 기간에 완료된 거래가 없습니다",
                color=0xFFFF00
            )
            return embed

        # Build embed
        embed = discord.Embed(
            title="📊 거래 통계",
            description=f"최근 {hours}시간",
            color=0x00FF00 if stats_data["total_pnl"] > 0 else 0xFF0000
        )

        embed.add_field(
            name="🎯 총 거래",
            value=str(stats_data["total_trades"]),
            inline=True
        )
        embed.add_field(
            name="✅ 승",
            value=f"{stats_data['winners']}회 ({stats_data['win_rate']:.1f}%)",
            inline=True
        )
        embed.add_field(
            name="❌ 패",
            value=f"{stats_data['losers']}회",
            inline=True
        )

        pnl_emoji = "💰" if stats_data["total_pnl"] > 0 else "📉"
        embed.add_field(
            name=f"{pnl_emoji} 총 손익",
            value=f"${stats_data['total_pnl']:+.2f}",
            inline=False
        )
        embed.add_field(
            name="📈 최고 거래",
            value=f"+{stats_data['best_trade']:.2f}%",
            inline=True
        )
        embed.add_field(
            name="📉 최악 거래",
            value=f"{stats_data['worst_trade']:.2f}%",
            inline=True
        )
        embed.add_field(
            name="🟢 LONG",
            value=f"{stats_data['long_trades']}회",
            inline=True
        )
        embed.add_field(
            name="🔴 SHORT",
            value=f"{stats_data['short_trades']}회",
            inline=True
        )

        return embed

    async def _get_history_embed(self, limit: int = 5) -> discord.Embed:
        """거래 내역 임베드 생성"""
        if not self.trade_db:
            embed = discord.Embed(
                title="❌ 데이터베이스 연결 안 됨",
                description="거래 데이터베이스를 사용할 수 없습니다",
                color=0xFF0000
            )
            return embed

        # Limit count
        limit = min(limit, 10)

        # Get recent trades
        trades = await self.trade_db.get_recent_trades(limit=limit)

        if not trades:
            embed = discord.Embed(
                title="📜 거래 내역 없음",
                description="완료된 거래를 찾을 수 없습니다",
                color=0xFFFF00
            )
            return embed

        # Build embed
        embed = discord.Embed(
            title=f"📜 최근 거래 (최근 {len(trades)}개)",
            color=0x00BFFF
        )

        for i, trade in enumerate(trades, 1):
            side = trade["side"]
            emoji = "🟢" if side == "LONG" else "🔴"
            entry = float(trade["entry_price"])
            exit_p = float(trade["exit_price"]) if trade["exit_price"] else 0
            exit_reason = trade["exit_reason"]
            pnl = float(trade.get("pnl", 0) or 0)
            pnl_pct = float(trade.get("pnl_pct", 0) or 0)

            # Time ago
            exit_time = trade["exit_time"]
            if exit_time:
                if hasattr(exit_time, 'replace'):
                    time_diff = datetime.now() - exit_time.replace(tzinfo=None)
                else:
                    time_diff = datetime.now() - exit_time
                hours_ago = int(time_diff.total_seconds() / 3600)
                mins_ago = int((time_diff.total_seconds() % 3600) / 60)

                if hours_ago > 0:
                    time_ago = f"{hours_ago}시간 {mins_ago}분 전"
                else:
                    time_ago = f"{mins_ago}분 전"
            else:
                time_ago = "N/A"

            pnl_emoji = "💰" if pnl > 0 else "📉"

            value = (
                f"{emoji} **{side}** | 진입: ${entry:,.2f} → 청산: ${exit_p:,.2f} ({exit_reason})\n"
                f"{pnl_emoji} 손익: ${pnl:+.2f} ({pnl_pct:+.2f}%) | {time_ago}"
            )

            embed.add_field(
                name=f"{i}️⃣ 거래 #{trade['id']}",
                value=value,
                inline=False
            )

        return embed

    async def _get_account_embed(self) -> discord.Embed:
        """계정 전체 포지션 임베드 생성"""
        if not self.binance_client:
            embed = discord.Embed(
                title="❌ Binance 클라이언트 연결 안 됨",
                description="Binance API를 사용할 수 없습니다",
                color=0xFF0000
            )
            return embed

        try:
            # 잔고 조회
            balance = await self.binance_client.get_account_balance()

            # 전체 포지션 조회
            positions = await self.binance_client.get_all_positions()

            # 총 미실현 손익 계산
            total_unrealized_pnl = sum(p["unrealized_pnl"] for p in positions)

            # 임베드 생성
            embed = discord.Embed(
                title="💼 계정 현황",
                color=0x00BFFF
            )

            # 잔고 정보
            embed.add_field(
                name="💰 USDT 잔고",
                value=f"${balance['balance']:,.2f}",
                inline=True
            )
            embed.add_field(
                name="💵 사용 가능",
                value=f"${balance['available']:,.2f}",
                inline=True
            )
            embed.add_field(
                name="📊 열린 포지션",
                value=f"{len(positions)}개",
                inline=True
            )

            # 총 미실현 손익
            pnl_emoji = "💰" if total_unrealized_pnl >= 0 else "📉"
            embed.add_field(
                name=f"{pnl_emoji} 총 미실현 손익",
                value=f"${total_unrealized_pnl:+,.2f}",
                inline=False
            )

            # 각 포지션 표시
            if positions:
                embed.add_field(
                    name="─" * 20,
                    value="**📍 열린 포지션 목록**",
                    inline=False
                )

                for i, pos in enumerate(positions, 1):
                    side = pos["side"]
                    emoji = "🟢" if side == "LONG" else "🔴"
                    pnl_emoji = "💰" if pos["unrealized_pnl"] >= 0 else "📉"

                    value = (
                        f"{emoji} **{side}** {pos['leverage']}x\n"
                        f"진입: ${pos['entry_price']:,.2f} → 현재: ${pos['current_price']:,.2f}\n"
                        f"수량: {pos['quantity']:.4f}\n"
                        f"{pnl_emoji} 손익: ${pos['unrealized_pnl']:+,.2f} ({pos['pnl_pct']:+.2f}%)\n"
                        f"청산가: ${pos['liquidation_price']:,.2f}"
                    )

                    embed.add_field(
                        name=f"{i}. {pos['symbol']}",
                        value=value,
                        inline=True
                    )
            else:
                embed.add_field(
                    name="📍 포지션",
                    value="열린 포지션이 없습니다",
                    inline=False
                )

            return embed

        except Exception as e:
            logger.error(f"계정 조회 에러: {e}")
            embed = discord.Embed(
                title="❌ 계정 조회 실패",
                description=f"오류: {e!s}",
                color=0xFF0000
            )
            return embed

    # =========================================================================
    # Slash Commands (한글 + 영어)
    # =========================================================================

    def setup_commands(self):
        """Register slash commands (한글 + 영어)"""
        # =====================================================================
        # /대시보드 (Dashboard) - 신규
        # =====================================================================

        @self.tree.command(name="대시보드", description="📊 트레이딩 봇 대시보드 (버튼 UI)")
        async def dashboard_korean(interaction: discord.Interaction):
            """대시보드 명령어 (한글)"""
            await self._dashboard_command(interaction)

        @self.tree.command(name="dashboard", description="📊 Trading Bot Dashboard (Button UI)")
        async def dashboard_english(interaction: discord.Interaction):
            """Dashboard command (English)"""
            await self._dashboard_command(interaction)

        # =====================================================================
        # /상태 (Status)
        # =====================================================================

        @self.tree.command(name="상태", description="봇 실행 상태 및 현재 포지션 확인")
        async def status_korean(interaction: discord.Interaction):
            """상태 조회 (한글)"""
            await self._status_command(interaction)

        @self.tree.command(name="status", description="Show bot status and current position")
        async def status_english(interaction: discord.Interaction):
            """Status command (English)"""
            await self._status_command(interaction)

        # =====================================================================
        # /포지션 (Position)
        # =====================================================================

        @self.tree.command(name="포지션", description="현재 포지션 상세 정보")
        async def position_korean(interaction: discord.Interaction):
            """포지션 조회 (한글)"""
            await self._position_command(interaction)

        @self.tree.command(name="position", description="Show detailed position information")
        async def position_english(interaction: discord.Interaction):
            """Position command (English)"""
            await self._position_command(interaction)

        # =====================================================================
        # /통계 (Stats)
        # =====================================================================

        @self.tree.command(name="통계", description="거래 통계 (최근 N시간)")
        async def stats_korean(interaction: discord.Interaction, hours: int = 24):
            """통계 조회 (한글)"""
            await self._stats_command(interaction, hours)

        @self.tree.command(name="stats", description="Trading statistics (recent N hours)")
        async def stats_english(interaction: discord.Interaction, hours: int = 24):
            """Stats command (English)"""
            await self._stats_command(interaction, hours)

        # =====================================================================
        # /내역 (History)
        # =====================================================================

        @self.tree.command(name="내역", description="최근 거래 내역")
        async def history_korean(interaction: discord.Interaction, count: int = 5):
            """내역 조회 (한글)"""
            await self._history_command(interaction, count)

        @self.tree.command(name="history", description="Recent trade history")
        async def history_english(interaction: discord.Interaction, count: int = 5):
            """History command (English)"""
            await self._history_command(interaction, count)

        # =====================================================================
        # /일시정지 (Stop)
        # =====================================================================

        @self.tree.command(name="일시정지", description="봇 일시 정지 (새 포지션 진입 중지)")
        async def stop_korean(interaction: discord.Interaction):
            """일시정지 (한글)"""
            await self._stop_command(interaction)

        @self.tree.command(name="stop", description="Pause the trading bot (stop new positions)")
        async def stop_english(interaction: discord.Interaction):
            """Stop command (English)"""
            await self._stop_command(interaction)

        # =====================================================================
        # /재시작 (Start)
        # =====================================================================

        @self.tree.command(name="재시작", description="봇 재시작 (정상 거래 재개)")
        async def start_korean(interaction: discord.Interaction):
            """재시작 (한글)"""
            await self._start_command(interaction)

        @self.tree.command(name="start", description="Resume the trading bot (normal trading)")
        async def start_english(interaction: discord.Interaction):
            """Start command (English)"""
            await self._start_command(interaction)

        # =====================================================================
        # /긴급청산 (Emergency)
        # =====================================================================

        @self.tree.command(name="긴급청산", description="🚨 긴급 청산 (현재 포지션 즉시 청산 + 봇 정지)")
        async def emergency_korean(interaction: discord.Interaction):
            """긴급청산 (한글)"""
            await self._emergency_command(interaction)

        @self.tree.command(name="emergency", description="🚨 Emergency close (close position + pause bot)")
        async def emergency_english(interaction: discord.Interaction):
            """Emergency command (English)"""
            await self._emergency_command(interaction)

        # =====================================================================
        # /계정 (Account) - 신규
        # =====================================================================

        @self.tree.command(name="계정", description="💼 계정 전체 포지션 및 잔고 조회")
        async def account_korean(interaction: discord.Interaction):
            """계정 조회 (한글)"""
            await self._account_command(interaction)

        @self.tree.command(name="account", description="💼 View all account positions and balance")
        async def account_english(interaction: discord.Interaction):
            """Account command (English)"""
            await self._account_command(interaction)

        # =====================================================================
        # /핑 (Ping)
        # =====================================================================

        @self.tree.command(name="핑", description="봇 응답 확인")
        async def ping_korean(interaction: discord.Interaction):
            """핑 (한글)"""
            await interaction.response.send_message("🏓 퐁!", ephemeral=True)
            logger.info(f"Discord 명령어 /핑 실행: {interaction.user}")

        @self.tree.command(name="ping", description="Check if bot is responding")
        async def ping_english(interaction: discord.Interaction):
            """Ping command (English)"""
            await interaction.response.send_message("🏓 Pong!", ephemeral=True)
            logger.info(f"Discord command /ping executed by {interaction.user}")

    # =========================================================================
    # Multi-Bot Commands (Phase 3)
    # =========================================================================

    def setup_multibot_commands(self):
        """멀티봇 슬래시 명령어 등록"""
        # =====================================================================
        # /봇목록 (Bot List)
        # =====================================================================

        @self.tree.command(name="봇목록", description="📋 등록된 봇 목록 조회")
        async def bot_list_korean(interaction: discord.Interaction):
            """봇 목록 조회 (한글)"""
            await self._bot_list_command(interaction)

        @self.tree.command(name="bots", description="📋 List all registered bots")
        async def bot_list_english(interaction: discord.Interaction):
            """Bot list command (English)"""
            await self._bot_list_command(interaction)

        # =====================================================================
        # /봇상태 (Bot Status)
        # =====================================================================

        @self.tree.command(name="봇상태", description="📊 특정 봇 상태 조회")
        async def bot_status_korean(
            interaction: discord.Interaction,
            bot_name: str,
        ):
            """봇 상태 조회 (한글)"""
            await self._bot_status_command(interaction, bot_name)

        @self.tree.command(name="bot-status", description="📊 Get specific bot status")
        async def bot_status_english(
            interaction: discord.Interaction,
            bot_name: str,
        ):
            """Bot status command (English)"""
            await self._bot_status_command(interaction, bot_name)

        # =====================================================================
        # /봇시작 (Bot Start)
        # =====================================================================

        @self.tree.command(name="봇시작", description="▶️ 특정 봇 시작")
        async def bot_start_korean(
            interaction: discord.Interaction,
            bot_name: str,
        ):
            """봇 시작 (한글)"""
            await self._bot_start_command(interaction, bot_name)

        @self.tree.command(name="bot-start", description="▶️ Start specific bot")
        async def bot_start_english(
            interaction: discord.Interaction,
            bot_name: str,
        ):
            """Bot start command (English)"""
            await self._bot_start_command(interaction, bot_name)

        # =====================================================================
        # /봇정지 (Bot Stop)
        # =====================================================================

        @self.tree.command(name="봇정지", description="⏹️ 특정 봇 정지")
        async def bot_stop_korean(
            interaction: discord.Interaction,
            bot_name: str,
        ):
            """봇 정지 (한글)"""
            await self._bot_stop_command(interaction, bot_name)

        @self.tree.command(name="bot-stop", description="⏹️ Stop specific bot")
        async def bot_stop_english(
            interaction: discord.Interaction,
            bot_name: str,
        ):
            """Bot stop command (English)"""
            await self._bot_stop_command(interaction, bot_name)

        # =====================================================================
        # /봇일시정지 (Bot Pause)
        # =====================================================================

        @self.tree.command(name="봇일시정지", description="⏸️ 특정 봇 일시정지")
        async def bot_pause_korean(
            interaction: discord.Interaction,
            bot_name: str,
        ):
            """봇 일시정지 (한글)"""
            await self._bot_pause_command(interaction, bot_name)

        @self.tree.command(name="bot-pause", description="⏸️ Pause specific bot")
        async def bot_pause_english(
            interaction: discord.Interaction,
            bot_name: str,
        ):
            """Bot pause command (English)"""
            await self._bot_pause_command(interaction, bot_name)

        # =====================================================================
        # /봇재개 (Bot Resume)
        # =====================================================================

        @self.tree.command(name="봇재개", description="▶️ 일시정지된 봇 재개")
        async def bot_resume_korean(
            interaction: discord.Interaction,
            bot_name: str,
        ):
            """봇 재개 (한글)"""
            await self._bot_resume_command(interaction, bot_name)

        @self.tree.command(name="bot-resume", description="▶️ Resume paused bot")
        async def bot_resume_english(
            interaction: discord.Interaction,
            bot_name: str,
        ):
            """Bot resume command (English)"""
            await self._bot_resume_command(interaction, bot_name)

        # =====================================================================
        # /전체시작 (Start All)
        # =====================================================================

        @self.tree.command(name="전체시작", description="▶️ 모든 봇 시작")
        async def start_all_korean(interaction: discord.Interaction):
            """전체 봇 시작 (한글)"""
            await self._start_all_command(interaction)

        @self.tree.command(name="start-all", description="▶️ Start all bots")
        async def start_all_english(interaction: discord.Interaction):
            """Start all command (English)"""
            await self._start_all_command(interaction)

        # =====================================================================
        # /전체정지 (Stop All)
        # =====================================================================

        @self.tree.command(name="전체정지", description="⏹️ 모든 봇 정지")
        async def stop_all_korean(interaction: discord.Interaction):
            """전체 봇 정지 (한글)"""
            await self._stop_all_command(interaction)

        @self.tree.command(name="stop-all", description="⏹️ Stop all bots")
        async def stop_all_english(interaction: discord.Interaction):
            """Stop all command (English)"""
            await self._stop_all_command(interaction)

    # =========================================================================
    # Command Implementations (헬퍼로 분리)
    # =========================================================================

    async def _dashboard_command(self, interaction: discord.Interaction):
        """대시보드 명령어 구현"""
        await interaction.response.defer()

        try:
            # 개요 임베드 생성
            is_running = self.bot_state.get("is_running", False)
            is_paused = self.bot_state.get("is_paused", False)
            current_price = self.bot_state.get("current_price", 0)
            position = self.bot_state.get("position")
            last_signal = self.bot_state.get("last_signal", "WAIT")

            # 상태 문자열
            if is_running:
                if is_paused:
                    status_str = "⏸️ 일시정지"
                    color = 0xFFFF00
                else:
                    status_str = "✅ 실행 중"
                    color = 0x00FF00
            else:
                status_str = "🛑 중지됨"
                color = 0xFF0000

            # 포지션 문자열
            if position and position.get("side"):
                side = position.get("side")
                entry = position.get("entry_price", 0)
                emoji = "🟢" if side == "LONG" else "🔴"
                position_str = f"{emoji} {side} @ ${entry:,.2f}"
            else:
                position_str = "없음"

            # Last signal time
            last_signal_time = self.bot_state.get("last_signal_time")
            if last_signal_time and isinstance(last_signal_time, datetime):
                time_diff = datetime.now() - last_signal_time
                mins_ago = int(time_diff.total_seconds() / 60)
                if mins_ago < 60:
                    signal_time_str = f"{mins_ago}분 전"
                else:
                    hours_ago = mins_ago // 60
                    signal_time_str = f"{hours_ago}시간 전"
            else:
                signal_time_str = "N/A"

            embed = discord.Embed(
                title="🤖 트레이딩 봇 대시보드",
                description=f"**상태:** {status_str} | **가격:** ${current_price:,.2f}\n"
                           f"**포지션:** {position_str}\n"
                           f"**마지막 신호:** {last_signal} ({signal_time_str})",
                color=color
            )

            embed.set_footer(text="아래 버튼을 클릭하여 상세 정보를 확인하세요")

            # DashboardView 첨부
            view = DashboardView(bot_client=self, timeout=180)

            await interaction.followup.send(embed=embed, view=view)
            logger.info(f"Discord 명령어 /대시보드 실행: {interaction.user}")

        except Exception as e:
            logger.error(f"/대시보드 명령어 에러: {e}")
            await interaction.followup.send(
                f"❌ 오류: {e!s}",
                ephemeral=True
            )

    async def _status_command(self, interaction: discord.Interaction):
        """상태 조회 명령어 구현"""
        await interaction.response.defer()

        try:
            embed = await self._get_status_embed()
            await interaction.followup.send(embed=embed)
            logger.info(f"Discord 명령어 /상태 실행: {interaction.user}")

        except Exception as e:
            logger.error(f"/상태 명령어 에러: {e}")
            await interaction.followup.send(
                f"❌ 봇 상태 조회 오류: {e!s}",
                ephemeral=True
            )

    async def _position_command(self, interaction: discord.Interaction):
        """포지션 조회 명령어 구현"""
        await interaction.response.defer()

        try:
            embed = await self._get_position_embed()
            await interaction.followup.send(embed=embed)
            logger.info(f"Discord 명령어 /포지션 실행: {interaction.user}")

        except Exception as e:
            logger.error(f"/포지션 명령어 에러: {e}")
            await interaction.followup.send(
                f"❌ 포지션 조회 오류: {e!s}",
                ephemeral=True
            )

    async def _stats_command(self, interaction: discord.Interaction, hours: int = 24):
        """통계 조회 명령어 구현"""
        await interaction.response.defer()

        try:
            embed = await self._get_stats_embed(hours=hours)
            await interaction.followup.send(embed=embed)
            logger.info(f"Discord 명령어 /통계 실행 (hours={hours}): {interaction.user}")

        except Exception as e:
            logger.error(f"/통계 명령어 에러: {e}")
            await interaction.followup.send(
                f"❌ 통계 조회 오류: {e!s}",
                ephemeral=True
            )

    async def _history_command(self, interaction: discord.Interaction, count: int = 5):
        """내역 조회 명령어 구현"""
        await interaction.response.defer()

        try:
            embed = await self._get_history_embed(limit=count)
            await interaction.followup.send(embed=embed)
            logger.info(f"Discord 명령어 /내역 실행 (count={count}): {interaction.user}")

        except Exception as e:
            logger.error(f"/내역 명령어 에러: {e}")
            await interaction.followup.send(
                f"❌ 내역 조회 오류: {e!s}",
                ephemeral=True
            )

    async def _stop_command(self, interaction: discord.Interaction):
        """일시정지 명령어 구현"""
        await interaction.response.defer()

        try:
            # Set bot state to paused
            self.bot_state["is_paused"] = True
            self.bot_state["paused_by"] = str(interaction.user)
            self.bot_state["paused_at"] = datetime.now()

            embed = discord.Embed(
                title="⏸️ 봇 일시정지",
                description="트레이딩 봇이 일시정지되었습니다",
                color=0xFFFF00
            )

            embed.add_field(
                name="🛑 새 포지션",
                value="진입 중지",
                inline=True
            )
            embed.add_field(
                name="📍 기존 포지션",
                value="계속 관리 (TP/SL 작동)",
                inline=True
            )
            embed.add_field(
                name="⚠️ 재시작",
                value="`/재시작` 명령어로 정상 거래 재개",
                inline=False
            )
            embed.add_field(
                name="👤 일시정지한 사용자",
                value=str(interaction.user),
                inline=True
            )

            await interaction.followup.send(embed=embed)
            logger.warning(f"봇 일시정지: {interaction.user}")

        except Exception as e:
            logger.error(f"/일시정지 명령어 에러: {e}")
            await interaction.followup.send(
                f"❌ 일시정지 오류: {e!s}",
                ephemeral=True
            )

    async def _start_command(self, interaction: discord.Interaction):
        """재시작 명령어 구현"""
        await interaction.response.defer()

        try:
            # Check if bot was paused
            was_paused = self.bot_state.get("is_paused", False)

            # Set bot state to active
            self.bot_state["is_paused"] = False
            self.bot_state["resumed_by"] = str(interaction.user)
            self.bot_state["resumed_at"] = datetime.now()

            embed = discord.Embed(
                title="▶️ 봇 재시작",
                description="트레이딩 봇이 정상 작동합니다",
                color=0x00FF00
            )

            embed.add_field(
                name="✅ 거래",
                value="활성화",
                inline=True
            )
            embed.add_field(
                name="🔄 다음 신호",
                value="다음 루프에서 생성됩니다",
                inline=True
            )
            embed.add_field(
                name="👤 재시작한 사용자",
                value=str(interaction.user),
                inline=False
            )

            if was_paused:
                paused_by = self.bot_state.get("paused_by", "알 수 없음")
                paused_at = self.bot_state.get("paused_at")
                if paused_at:
                    pause_duration = datetime.now() - paused_at
                    hours = int(pause_duration.total_seconds() / 3600)
                    mins = int((pause_duration.total_seconds() % 3600) / 60)
                    embed.add_field(
                        name="⏱️ 일시정지 시간",
                        value=f"{hours}시간 {mins}분 (일시정지: {paused_by})",
                        inline=False
                    )

            await interaction.followup.send(embed=embed)
            logger.info(f"봇 재시작: {interaction.user}")

        except Exception as e:
            logger.error(f"/재시작 명령어 에러: {e}")
            await interaction.followup.send(
                f"❌ 재시작 오류: {e!s}",
                ephemeral=True
            )

    async def _emergency_command(self, interaction: discord.Interaction):
        """긴급청산 명령어 구현"""
        await interaction.response.defer()

        try:
            position = self.bot_state.get("position")

            if not position or not position.get("side"):
                embed = discord.Embed(
                    title="⚠️ 포지션 없음",
                    description="청산할 포지션이 없습니다",
                    color=0xFFFF00
                )
                await interaction.followup.send(embed=embed)
                return

            # Set emergency flag
            self.bot_state["emergency_close"] = True
            self.bot_state["emergency_by"] = str(interaction.user)
            self.bot_state["emergency_at"] = datetime.now()

            # Also pause the bot
            self.bot_state["is_paused"] = True

            side = position.get("side")
            entry_price = position.get("entry_price", 0)
            size = position.get("quantity", position.get("size", 0))

            embed = discord.Embed(
                title="🚨 긴급 청산 시작",
                description="포지션이 시장가로 청산됩니다",
                color=0xFF0000
            )

            emoji = "🟢" if side == "LONG" else "🔴"
            embed.add_field(
                name=f"{emoji} 포지션",
                value=f"{side} @ ${entry_price:,.2f}",
                inline=True
            )
            embed.add_field(
                name="📊 수량",
                value=f"{size:.4f} BTC",
                inline=True
            )
            embed.add_field(
                name="⚠️ 작업",
                value="다음 루프에서 시장가 청산",
                inline=False
            )
            embed.add_field(
                name="⏸️ 봇 상태",
                value="자동 일시정지 (`/재시작`으로 재개)",
                inline=False
            )
            embed.add_field(
                name="👤 요청한 사용자",
                value=str(interaction.user),
                inline=True
            )

            await interaction.followup.send(embed=embed)
            logger.critical(f"긴급 청산 시작: {interaction.user}")

        except Exception as e:
            logger.error(f"/긴급청산 명령어 에러: {e}")
            await interaction.followup.send(
                f"❌ 긴급청산 오류: {e!s}",
                ephemeral=True
            )

    async def _account_command(self, interaction: discord.Interaction):
        """계정 조회 명령어 구현"""
        await interaction.response.defer()

        try:
            embed = await self._get_account_embed()
            await interaction.followup.send(embed=embed)
            logger.info(f"Discord 명령어 /계정 실행: {interaction.user}")

        except Exception as e:
            logger.error(f"/계정 명령어 에러: {e}")
            await interaction.followup.send(
                f"❌ 계정 조회 오류: {e!s}",
                ephemeral=True
            )

    # =========================================================================
    # REST API Helper (Phase 3)
    # =========================================================================

    async def _call_bot_api(
        self,
        method: str,
        endpoint: str,
        json_data: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """REST API 호출 헬퍼

        Args:
            method: HTTP 메서드 (GET, POST, PUT, DELETE)
            endpoint: API 엔드포인트 (예: /api/bots)
            json_data: 요청 본문 (선택)

        Returns:
            API 응답 JSON

        Raises:
            Exception: API 호출 실패 시
        """
        url = f"{self._api_url}{endpoint}"
        timeout = aiohttp.ClientTimeout(total=10)

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.request(method, url, json=json_data) as resp:
                    if resp.status >= 400:
                        error_text = await resp.text()
                        raise Exception(f"API 오류 ({resp.status}): {error_text}")
                    return await resp.json()
        except aiohttp.ClientError as e:
            logger.error(f"API 호출 실패: {method} {url} - {e}")
            raise Exception(f"API 서버 연결 실패: {e!s}")

    # =========================================================================
    # Multi-Bot Command Implementations (Phase 3)
    # =========================================================================

    async def _bot_list_command(self, interaction: discord.Interaction):
        """봇 목록 조회 명령어 구현 (REST API 사용)"""
        await interaction.response.defer()

        try:
            # REST API를 통해 봇 목록 조회
            result = await self._call_bot_api("GET", "/api/bots")
            data = result.get("data", result)

            total_bots = data.get("total_bots", 0)
            running_bots = data.get("running_bots", 0)
            paused_bots = data.get("paused_bots", 0)
            bots = data.get("bots", [])

            embed = discord.Embed(
                title="📋 봇 목록",
                description=f"총 {total_bots}개 봇 등록됨",
                color=0x00BFFF
            )

            embed.add_field(
                name="📊 요약",
                value=f"🟢 실행 중: {running_bots}개\n"
                      f"⏸️ 일시정지: {paused_bots}개",
                inline=False
            )

            if bots:
                for bot_info in bots:
                    is_running = bot_info.get('is_running', False)
                    is_paused = bot_info.get('is_paused', False)
                    status_emoji = "🟢" if is_running and not is_paused else \
                                  "⏸️" if is_paused else "🔴"
                    embed.add_field(
                        name=f"{status_emoji} {bot_info.get('name', 'unknown')}",
                        value=f"심볼: {bot_info.get('symbol', 'N/A')}\n"
                              f"위험도: {bot_info.get('risk_level', 'N/A')}",
                        inline=True
                    )
            else:
                embed.add_field(
                    name="ℹ️ 정보",
                    value="등록된 봇이 없습니다.",
                    inline=False
                )

            await interaction.followup.send(embed=embed)
            logger.info(f"Discord 명령어 /봇목록 실행: {interaction.user}")

        except Exception as e:
            logger.error(f"/봇목록 명령어 에러: {e}")
            await interaction.followup.send(
                f"❌ 봇 목록 조회 오류: {e!s}",
                ephemeral=True
            )

    async def _bot_status_command(self, interaction: discord.Interaction, bot_name: str):
        """봇 상태 조회 명령어 구현 (REST API 사용)"""
        await interaction.response.defer()

        try:
            # REST API를 통해 봇 상태 조회
            result = await self._call_bot_api("GET", f"/api/bots/{bot_name}")
            data = result.get("data", result)

            state = data.get("state", data)
            is_running = state.get('is_running', False)
            is_paused = state.get('is_paused', False)

            # 상태 색상 결정
            if is_running and not is_paused:
                color = 0x00FF00
                status_str = "🟢 실행 중"
            elif is_paused:
                color = 0xFFFF00
                status_str = "⏸️ 일시정지"
            else:
                color = 0xFF0000
                status_str = "🔴 중지됨"

            embed = discord.Embed(
                title=f"📊 {bot_name} 상태",
                color=color
            )

            embed.add_field(name="⚡ 상태", value=status_str, inline=True)
            embed.add_field(name="💰 심볼", value=state.get('symbol', 'N/A'), inline=True)
            embed.add_field(name="⚠️ 위험도", value=state.get('risk_level', 'N/A'), inline=True)
            embed.add_field(name="📈 레버리지", value=f"{state.get('leverage', 0)}x", inline=True)
            embed.add_field(name="💵 현재가", value=f"${state.get('current_price', 0):,.2f}", inline=True)
            embed.add_field(name="🔄 루프", value=str(state.get('loop_count', 0)), inline=True)

            # 포지션 정보
            position = state.get('position')
            if position and position.get('side'):
                side_emoji = "🟢" if position['side'] == "LONG" else "🔴"
                embed.add_field(
                    name=f"{side_emoji} 포지션",
                    value=f"{position['side']} @ ${position.get('entry_price', 0):,.2f}",
                    inline=False
                )

            # 마지막 시그널
            embed.add_field(
                name="🔄 마지막 시그널",
                value=state.get('last_signal', 'WAIT'),
                inline=True
            )

            await interaction.followup.send(embed=embed)
            logger.info(f"Discord 명령어 /봇상태 {bot_name} 실행: {interaction.user}")

        except Exception as e:
            logger.error(f"/봇상태 명령어 에러: {e}")
            await interaction.followup.send(
                f"❌ 봇 상태 조회 오류: {e!s}",
                ephemeral=True
            )

    async def _bot_start_command(self, interaction: discord.Interaction, bot_name: str):
        """봇 시작 명령어 구현 (REST API 사용)"""
        await interaction.response.defer()

        try:
            # REST API를 통해 봇 시작
            await self._call_bot_api("POST", f"/api/bots/{bot_name}/start")

            embed = discord.Embed(
                title="▶️ 봇 시작",
                description=f"봇 **{bot_name}**이(가) 시작되었습니다.",
                color=0x00FF00
            )
            embed.add_field(
                name="👤 시작한 사용자",
                value=str(interaction.user),
                inline=True
            )

            await interaction.followup.send(embed=embed)
            logger.info(f"Discord 명령어 /봇시작 {bot_name} 실행: {interaction.user}")

        except Exception as e:
            logger.error(f"/봇시작 명령어 에러: {e}")
            await interaction.followup.send(
                f"❌ 봇 시작 오류: {e!s}",
                ephemeral=True
            )

    async def _bot_stop_command(self, interaction: discord.Interaction, bot_name: str):
        """봇 정지 명령어 구현 (REST API 사용)"""
        await interaction.response.defer()

        try:
            # REST API를 통해 봇 정지
            await self._call_bot_api("POST", f"/api/bots/{bot_name}/stop")

            embed = discord.Embed(
                title="⏹️ 봇 정지",
                description=f"봇 **{bot_name}**이(가) 정지되었습니다.",
                color=0xFF0000
            )
            embed.add_field(
                name="👤 정지한 사용자",
                value=str(interaction.user),
                inline=True
            )

            await interaction.followup.send(embed=embed)
            logger.info(f"Discord 명령어 /봇정지 {bot_name} 실행: {interaction.user}")

        except Exception as e:
            logger.error(f"/봇정지 명령어 에러: {e}")
            await interaction.followup.send(
                f"❌ 봇 정지 오류: {e!s}",
                ephemeral=True
            )

    async def _bot_pause_command(self, interaction: discord.Interaction, bot_name: str):
        """봇 일시정지 명령어 구현 (REST API 사용)"""
        await interaction.response.defer()

        try:
            # REST API를 통해 봇 일시정지
            await self._call_bot_api("POST", f"/api/bots/{bot_name}/pause")

            embed = discord.Embed(
                title="⏸️ 봇 일시정지",
                description=f"봇 **{bot_name}**이(가) 일시정지되었습니다.",
                color=0xFFFF00
            )
            embed.add_field(
                name="ℹ️ 안내",
                value="새 포지션 진입이 중지됩니다.\n기존 포지션은 계속 관리됩니다.",
                inline=False
            )
            embed.add_field(
                name="👤 일시정지한 사용자",
                value=str(interaction.user),
                inline=True
            )

            await interaction.followup.send(embed=embed)
            logger.info(f"Discord 명령어 /봇일시정지 {bot_name} 실행: {interaction.user}")

        except Exception as e:
            logger.error(f"/봇일시정지 명령어 에러: {e}")
            await interaction.followup.send(
                f"❌ 봇 일시정지 오류: {e!s}",
                ephemeral=True
            )

    async def _bot_resume_command(self, interaction: discord.Interaction, bot_name: str):
        """봇 재개 명령어 구현 (REST API 사용)"""
        await interaction.response.defer()

        try:
            # REST API를 통해 봇 재개
            await self._call_bot_api("POST", f"/api/bots/{bot_name}/resume")

            embed = discord.Embed(
                title="▶️ 봇 재개",
                description=f"봇 **{bot_name}**이(가) 재개되었습니다.",
                color=0x00FF00
            )
            embed.add_field(
                name="ℹ️ 안내",
                value="정상 거래가 재개됩니다.",
                inline=False
            )
            embed.add_field(
                name="👤 재개한 사용자",
                value=str(interaction.user),
                inline=True
            )

            await interaction.followup.send(embed=embed)
            logger.info(f"Discord 명령어 /봇재개 {bot_name} 실행: {interaction.user}")

        except Exception as e:
            logger.error(f"/봇재개 명령어 에러: {e}")
            await interaction.followup.send(
                f"❌ 봇 재개 오류: {e!s}",
                ephemeral=True
            )

    async def _start_all_command(self, interaction: discord.Interaction):
        """전체 봇 시작 명령어 구현 (REST API 사용)"""
        await interaction.response.defer()

        try:
            # REST API를 통해 전체 봇 시작
            result = await self._call_bot_api("POST", "/api/bots/start-all")
            data = result.get("data", result)
            started_count = data.get("started", 0)

            embed = discord.Embed(
                title="▶️ 전체 봇 시작",
                description=f"모든 봇({started_count}개)이 시작되었습니다.",
                color=0x00FF00
            )
            embed.add_field(
                name="👤 시작한 사용자",
                value=str(interaction.user),
                inline=True
            )

            await interaction.followup.send(embed=embed)
            logger.info(f"Discord 명령어 /전체시작 실행: {interaction.user}")

        except Exception as e:
            logger.error(f"/전체시작 명령어 에러: {e}")
            await interaction.followup.send(
                f"❌ 전체 시작 오류: {e!s}",
                ephemeral=True
            )

    async def _stop_all_command(self, interaction: discord.Interaction):
        """전체 봇 정지 명령어 구현 (REST API 사용)"""
        await interaction.response.defer()

        try:
            # REST API를 통해 전체 봇 정지
            result = await self._call_bot_api("POST", "/api/bots/stop-all")
            data = result.get("data", result)
            stopped_count = data.get("stopped", 0)

            embed = discord.Embed(
                title="⏹️ 전체 봇 정지",
                description=f"모든 봇({stopped_count}개)이 정지되었습니다.",
                color=0xFF0000
            )
            embed.add_field(
                name="👤 정지한 사용자",
                value=str(interaction.user),
                inline=True
            )

            await interaction.followup.send(embed=embed)
            logger.info(f"Discord 명령어 /전체정지 실행: {interaction.user}")

        except Exception as e:
            logger.error(f"/전체정지 명령어 에러: {e}")
            await interaction.followup.send(
                f"❌ 전체 정지 오류: {e!s}",
                ephemeral=True
            )

    # =========================================================================
    # Event Handlers
    # =========================================================================

    async def on_ready(self):
        """Called when bot is ready"""
        logger.info(f"Discord 봇 로그인: {self.user}")
        logger.info(f"서버 수: {len(self.guilds)}")

        # Sync commands
        try:
            synced = await self.tree.sync()
            logger.info(f"명령어 동기화 완료: {len(synced)}개")
        except Exception as e:
            logger.error(f"명령어 동기화 실패: {e}")

    async def on_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handle command errors"""
        logger.error(f"명령어 에러: {error}")
        await interaction.response.send_message(
            f"❌ 명령어 오류: {error!s}",
            ephemeral=True
        )


async def start_discord_bot(
    token: str,
    bot_state: dict,
    trade_db=None,
    binance_client=None,
    bot_manager: Optional["MultiBotManager"] = None,
):
    """Start Discord bot

    Args:
        token: Discord bot token
        bot_state: Shared state dictionary with trading bot
        trade_db: TradeHistoryDB instance (optional)
        binance_client: BinanceTestnetClient instance (optional)
        bot_manager: MultiBotManager instance (optional, for multi-bot mode)
    """
    client = TradingBotClient(
        bot_state=bot_state,
        trade_db=trade_db,
        binance_client=binance_client,
        bot_manager=bot_manager,
    )

    try:
        await client.start(token)
    except Exception as e:
        logger.error(f"Discord 봇 에러: {e}")
        raise
