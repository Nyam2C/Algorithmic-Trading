"""Discord 트레이딩 봇 클라이언트.

메인 봇 클라이언트와 명령어 핸들러를 정의합니다.
Phase 4.1: 리팩토링된 모듈 구조
"""
import os
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

import aiohttp
import discord
from discord import app_commands
from loguru import logger

from src.discord_bot.commands import (
    register_control_commands,
    register_monitoring_commands,
    register_multibot_commands,
)
from src.discord_bot.constants import Colors, Emojis, Timeouts
from src.discord_bot.embeds import (
    create_account_embed,
    create_bot_list_embed,
    create_bot_status_embed,
    create_history_embed,
    create_position_embed,
    create_stats_embed,
    create_status_embed,
)
from src.discord_bot.utils import validate_bot_name as _validate_bot_name
from src.discord_bot.views import DashboardView

# Discord 메시지/임베드 길이 제한 상수
MAX_MESSAGE_LENGTH = 500
MAX_EMBED_FIELD_LENGTH = 400
MAX_PROMPT_DISPLAY_LENGTH = 1500
MAX_EMBED_FIELD_VALUE_LENGTH = 1024
STATUS_UPDATE_INTERVAL = 60

# HTTP 상태 코드 상수
HTTP_SERVER_ERROR = 500
HTTP_CLIENT_ERROR = 400

if TYPE_CHECKING:
    from src.bot_manager import MultiBotManager


class TradingBotClient(discord.Client):
    """Discord 트레이딩 봇 클라이언트.

    단일 봇 모드와 멀티봇 모드를 모두 지원합니다.
    - 단일 봇 모드: bot_state dict를 사용
    - 멀티봇 모드: MultiBotManager를 사용

    Phase 4.1 리팩토링:
    - 명령어, 뷰, 임베드를 별도 모듈로 분리
    - 상수 중앙 관리
    - 유틸리티 함수 분리
    """

    def __init__(
        self,
        bot_state: dict,
        trade_db=None,
        binance_client=None,
        bot_manager: Optional["MultiBotManager"] = None,
    ):
        """TradingBotClient 초기화.

        Args:
            bot_state: 공유 상태 딕셔너리
            trade_db: TradeHistoryDB 인스턴스 (선택)
            binance_client: BinanceTestnetClient 인스턴스 (선택)
            bot_manager: MultiBotManager 인스턴스 (선택, 멀티봇 모드)
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

        # Phase 7: 감사 로그
        self._audit_log: Any | None = None

        # 명령어 등록
        register_monitoring_commands(self)
        register_control_commands(self)
        register_multibot_commands(self)


    def set_audit_log(self, audit_log: Any) -> None:
        """감사 로그 매니저 설정.

        Args:
            audit_log: AuditLogManager 인스턴스
        """
        self._audit_log = audit_log
        logger.info("Discord 봇 감사 로그 설정 완료")

    async def _audit_command(
        self, command: str, user: str, bot_name: str = "", details: str = ""
    ) -> None:
        """Discord 명령어 감사 로그 기록.

        Args:
            command: 명령어 이름
            user: Discord 사용자
            bot_name: 대상 봇 이름
            details: 추가 상세 정보
        """
        if self._audit_log is None:
            return
        try:
            await self._audit_log.log_event(
                event_type="DISCORD_COMMAND",
                bot_name=bot_name or "global",
                details={
                    "command": command,
                    "discord_user": str(user),
                    "details": details,
                },
            )
        except Exception as e:
            logger.warning(f"감사 로그 기록 실패: {e}")

    # =========================================================================
    # Embed Getters (Helper Methods)
    # =========================================================================

    async def _get_status_embed(self) -> discord.Embed:
        """봇 상태 임베드 반환."""
        return create_status_embed(self.bot_state)

    async def _get_position_embed(self) -> discord.Embed:
        """포지션 임베드 반환."""
        return create_position_embed(self.bot_state)

    async def _get_stats_embed(self, hours: int = 24) -> discord.Embed:
        """통계 임베드 반환."""
        if not self.trade_db:
            return discord.Embed(
                title="❌ 데이터베이스 연결 안 됨",
                description="거래 데이터베이스를 사용할 수 없습니다",
                color=Colors.ERROR
            )

        stats_data = await self.trade_db.get_statistics(hours=hours)
        return create_stats_embed(stats_data, hours)

    async def _get_history_embed(self, limit: int = 5) -> discord.Embed:
        """내역 임베드 반환."""
        if not self.trade_db:
            return discord.Embed(
                title="❌ 데이터베이스 연결 안 됨",
                description="거래 데이터베이스를 사용할 수 없습니다",
                color=Colors.ERROR
            )

        limit = min(limit, 10)
        trades = await self.trade_db.get_recent_trades(limit=limit)
        return create_history_embed(trades)

    async def _get_account_embed(self) -> discord.Embed:
        """계정 임베드 반환."""
        if not self.binance_client:
            return discord.Embed(
                title="❌ Binance 클라이언트 연결 안 됨",
                description="Binance API를 사용할 수 없습니다",
                color=Colors.ERROR
            )

        try:
            balance = await self.binance_client.get_account_balance()
            positions = await self.binance_client.get_all_positions()
            return create_account_embed(balance, positions)
        except Exception as e:
            logger.error(f"계정 조회 에러: {e}")
            return discord.Embed(
                title="❌ 계정 조회 실패",
                description=f"오류: {e!s}",
                color=Colors.ERROR
            )

    # =========================================================================
    # REST API Helper
    # =========================================================================

    async def _call_bot_api(
        self,
        method: str,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """REST API 호출 헬퍼.

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
        timeout = aiohttp.ClientTimeout(total=Timeouts.API_CALL)

        try:
            async with (
                aiohttp.ClientSession(timeout=timeout) as session,
                session.request(method, url, json=json_data) as resp,
            ):
                    if resp.status >= HTTP_SERVER_ERROR:
                        error_text = await resp.text()
                        logger.error(
                        f"API 서버 오류: {method} {url} - {resp.status}"
                    )
                        raise Exception(
                        f"API 서버 오류 ({resp.status}): {error_text}"
                    )
                    if resp.status >= HTTP_CLIENT_ERROR:
                        error_text = await resp.text()
                        logger.warning(
                        f"API 클라이언트 오류: {method} {url} - {resp.status}"
                    )
                        raise ValueError(
                        f"API 요청 오류 ({resp.status}): {error_text}"
                    )
                    return await resp.json()
        except aiohttp.ClientError as e:
            logger.error(f"API 호출 실패: {method} {url} - {e}")
            raise Exception(f"API 서버 연결 실패: {e!s}") from e

    # =========================================================================
    # Command Implementations
    # =========================================================================

    async def _dashboard_command(self, interaction: discord.Interaction):
        """대시보드 명령어 구현."""
        await interaction.response.defer()

        try:
            is_running = self.bot_state.get("is_running", False)
            is_paused = self.bot_state.get("is_paused", False)
            current_price = self.bot_state.get("current_price", 0)
            position = self.bot_state.get("position")
            last_signal = self.bot_state.get("last_signal", "WAIT")

            # 상태 문자열
            if is_running:
                status_str = "⏸️ 일시정지" if is_paused else "✅ 실행 중"
                color = Colors.WARNING if is_paused else Colors.SUCCESS
            else:
                status_str = "🛑 중지됨"
                color = Colors.ERROR

            # 포지션 문자열
            if position and position.get("side"):
                side = position.get("side")
                entry = position.get("entry_price", 0)
                emoji = Emojis.LONG if side == "LONG" else Emojis.SHORT
                position_str = f"{emoji} {side} @ ${entry:,.2f}"
            else:
                position_str = "없음"

            # Last signal time
            last_signal_time = self.bot_state.get("last_signal_time")
            if last_signal_time and isinstance(last_signal_time, datetime):
                time_diff = datetime.now() - last_signal_time
                mins_ago = int(time_diff.total_seconds() / 60)
                if mins_ago < STATUS_UPDATE_INTERVAL:
                    signal_time_str = f"{mins_ago}분 전"
                else:
                    hours_ago = mins_ago // 60
                    signal_time_str = f"{hours_ago}시간 전"
            else:
                signal_time_str = "N/A"

            embed = discord.Embed(
                title="🤖 트레이딩 봇 대시보드",
                description=(
                    f"**상태:** {status_str} | **가격:** ${current_price:,.2f}\n"
                    f"**포지션:** {position_str}\n"
                    f"**마지막 신호:** {last_signal} ({signal_time_str})"
                ),
                color=color
            )

            embed.set_footer(text="아래 버튼을 클릭하여 상세 정보를 확인하세요")

            view = DashboardView(bot_client=self, timeout=Timeouts.DASHBOARD_VIEW)
            await interaction.followup.send(embed=embed, view=view)
            logger.info(f"Discord 명령어 /대시보드 실행: {interaction.user}")

        except Exception as e:
            logger.error(f"/대시보드 명령어 에러: {e}")
            await interaction.followup.send(f"❌ 오류: {e!s}", ephemeral=True)

    async def _status_command(self, interaction: discord.Interaction):
        """상태 조회 명령어 구현."""
        await interaction.response.defer()

        try:
            embed = await self._get_status_embed()
            await interaction.followup.send(embed=embed)
            logger.info(f"Discord 명령어 /상태 실행: {interaction.user}")
        except Exception as e:
            logger.error(f"/상태 명령어 에러: {e}")
            await interaction.followup.send(
                f"❌ 봇 상태 조회 오류: {e!s}", ephemeral=True
            )

    async def _position_command(self, interaction: discord.Interaction):
        """포지션 조회 명령어 구현."""
        await interaction.response.defer()

        try:
            embed = await self._get_position_embed()
            await interaction.followup.send(embed=embed)
            logger.info(f"Discord 명령어 /포지션 실행: {interaction.user}")
        except Exception as e:
            logger.error(f"/포지션 명령어 에러: {e}")
            await interaction.followup.send(
                f"❌ 포지션 조회 오류: {e!s}", ephemeral=True
            )

    async def _stats_command(self, interaction: discord.Interaction, hours: int = 24):
        """통계 조회 명령어 구현."""
        await interaction.response.defer()

        try:
            embed = await self._get_stats_embed(hours=hours)
            await interaction.followup.send(embed=embed)
            logger.info(
                f"Discord 명령어 /통계 실행 (hours={hours}): {interaction.user}"
            )
        except Exception as e:
            logger.error(f"/통계 명령어 에러: {e}")
            await interaction.followup.send(
                f"❌ 통계 조회 오류: {e!s}", ephemeral=True
            )

    async def _history_command(self, interaction: discord.Interaction, count: int = 5):
        """내역 조회 명령어 구현."""
        await interaction.response.defer()

        try:
            embed = await self._get_history_embed(limit=count)
            await interaction.followup.send(embed=embed)
            logger.info(
                f"Discord 명령어 /내역 실행 (count={count}): {interaction.user}"
            )
        except Exception as e:
            logger.error(f"/내역 명령어 에러: {e}")
            await interaction.followup.send(
                f"❌ 내역 조회 오류: {e!s}", ephemeral=True
            )

    async def _stop_command(self, interaction: discord.Interaction):
        """일시정지 명령어 구현."""
        await interaction.response.defer()

        try:
            # BotInstance 실제 제어
            if self.bot_manager and self.bot_manager.bot_count > 0:
                first_bot = next(iter(self.bot_manager.bots.values()))
                self.bot_manager.pause_bot(first_bot.bot_name)
            # bot_state 호환성 동기화
            self.bot_state["is_paused"] = True
            self.bot_state["paused_by"] = str(interaction.user)
            self.bot_state["paused_at"] = datetime.now()

            embed = discord.Embed(
                title="⏸️ 봇 일시정지",
                description="트레이딩 봇이 일시정지되었습니다",
                color=Colors.WARNING
            )

            embed.add_field(name="🛑 새 포지션", value="진입 중지", inline=True)
            embed.add_field(
                name="📍 기존 포지션",
                value="계속 관리 (TP/SL 작동)",
                inline=True,
            )
            embed.add_field(
                name="⚠️ 재시작",
                value="`/재시작` 명령어로 정상 거래 재개",
                inline=False
            )
            embed.add_field(
                name="👤 일시정지한 사용자",
                value=str(interaction.user),
                inline=True,
            )

            await interaction.followup.send(embed=embed)
            logger.warning(f"봇 일시정지: {interaction.user}")

            bot_name = ""
            if self.bot_manager and self.bot_manager.bot_count > 0:
                bot_name = first_bot.bot_name
            await self._audit_command(
                "일시정지", str(interaction.user),
                bot_name=bot_name,
            )

        except Exception as e:
            logger.error(f"/일시정지 명령어 에러: {e}")
            await interaction.followup.send(
                f"❌ 일시정지 오류: {e!s}", ephemeral=True
            )

    async def _start_command(self, interaction: discord.Interaction):
        """재시작 명령어 구현."""
        await interaction.response.defer()

        try:
            was_paused = self.bot_state.get("is_paused", False)
            # BotInstance 실제 제어
            if self.bot_manager and self.bot_manager.bot_count > 0:
                first_bot = next(iter(self.bot_manager.bots.values()))
                self.bot_manager.resume_bot(first_bot.bot_name)
            # bot_state 호환성 동기화
            self.bot_state["is_paused"] = False
            self.bot_state["resumed_by"] = str(interaction.user)
            self.bot_state["resumed_at"] = datetime.now()

            embed = discord.Embed(
                title="▶️ 봇 재시작",
                description="트레이딩 봇이 정상 작동합니다",
                color=Colors.SUCCESS
            )

            embed.add_field(name="✅ 거래", value="활성화", inline=True)
            embed.add_field(
                name="🔄 다음 신호",
                value="다음 루프에서 생성됩니다",
                inline=True,
            )
            embed.add_field(
                name="👤 재시작한 사용자",
                value=str(interaction.user),
                inline=False,
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

            bot_name = ""
            if self.bot_manager and self.bot_manager.bot_count > 0:
                bot_name = first_bot.bot_name
            await self._audit_command(
                "재시작", str(interaction.user),
                bot_name=bot_name,
            )

        except Exception as e:
            logger.error(f"/재시작 명령어 에러: {e}")
            await interaction.followup.send(f"❌ 재시작 오류: {e!s}", ephemeral=True)

    async def _emergency_command(self, interaction: discord.Interaction):
        """긴급청산 명령어 구현."""
        await interaction.response.defer()

        try:
            position = self.bot_state.get("position")

            if not position or not position.get("side"):
                embed = discord.Embed(
                    title="⚠️ 포지션 없음",
                    description="청산할 포지션이 없습니다",
                    color=Colors.WARNING
                )
                await interaction.followup.send(embed=embed)
                return

            # BotInstance 실제 긴급 청산
            if self.bot_manager and self.bot_manager.bot_count > 0:
                first_bot = next(iter(self.bot_manager.bots.values()))
                bot = self.bot_manager.get_bot(first_bot.bot_name)
                if bot:
                    bot.request_emergency_close()
            # bot_state 호환성 동기화
            self.bot_state["emergency_close"] = True
            self.bot_state["emergency_by"] = str(interaction.user)
            self.bot_state["emergency_at"] = datetime.now()
            self.bot_state["is_paused"] = True

            side = position.get("side")
            entry_price = position.get("entry_price", 0)
            size = position.get("quantity", position.get("size", 0))

            embed = discord.Embed(
                title="🚨 긴급 청산 시작",
                description="포지션이 시장가로 청산됩니다",
                color=Colors.ERROR
            )

            emoji = Emojis.LONG if side == "LONG" else Emojis.SHORT
            embed.add_field(
                name=f"{emoji} 포지션",
                value=f"{side} @ ${entry_price:,.2f}",
                inline=True,
            )
            embed.add_field(name="📊 수량", value=f"{size:.4f} BTC", inline=True)
            embed.add_field(
                name="⚠️ 작업",
                value="다음 루프에서 시장가 청산",
                inline=False,
            )
            embed.add_field(
                name="⏸️ 봇 상태",
                value="자동 일시정지 (`/재시작`으로 재개)",
                inline=False
            )
            embed.add_field(
                name="👤 요청한 사용자",
                value=str(interaction.user),
                inline=True,
            )

            await interaction.followup.send(embed=embed)
            logger.critical(f"긴급 청산 시작: {interaction.user}")

            em_bot_name = ""
            if self.bot_manager and self.bot_manager.bot_count > 0:
                em_bot_name = first_bot.bot_name
            await self._audit_command(
                "긴급청산", str(interaction.user),
                bot_name=em_bot_name,
                details=f"side={side}, entry=${entry_price:,.2f}",
            )

        except Exception as e:
            logger.error(f"/긴급청산 명령어 에러: {e}")
            await interaction.followup.send(f"❌ 긴급청산 오류: {e!s}", ephemeral=True)

    async def _account_command(self, interaction: discord.Interaction):
        """계정 조회 명령어 구현."""
        await interaction.response.defer()

        try:
            embed = await self._get_account_embed()
            await interaction.followup.send(embed=embed)
            logger.info(f"Discord 명령어 /계정 실행: {interaction.user}")
        except Exception as e:
            logger.error(f"/계정 명령어 에러: {e}")
            await interaction.followup.send(f"❌ 계정 조회 오류: {e!s}", ephemeral=True)

    async def _prompt_command(
        self, interaction: discord.Interaction, bot_name: str = ""
    ):
        """마지막 AI 프롬프트/응답 조회 명령어 구현."""
        await interaction.response.defer()

        try:
            if not self.bot_manager:
                await interaction.followup.send(
                    "❌ 멀티봇 매니저가 설정되지 않았습니다.", ephemeral=True
                )
                return

            bots = self.bot_manager.bots
            if not bots:
                await interaction.followup.send(
                    "❌ 등록된 봇이 없습니다.", ephemeral=True
                )
                return

            # bot_name이 빈 문자열이면 첫 번째 봇 사용
            if not bot_name:
                target_bot = next(iter(bots.values()))
                bot_name = target_bot.bot_name
            else:
                target_bot_or_none = bots.get(bot_name)
                if not target_bot_or_none:
                    available = ", ".join(bots.keys())
                    await interaction.followup.send(
                        f"❌ 봇 '{bot_name}'을(를) 찾을 수 없습니다.\n"
                        f"사용 가능: {available}",
                        ephemeral=True,
                    )
                    return
                target_bot = target_bot_or_none

            last_call = target_bot.get_last_ai_call()
            if not last_call:
                embed = discord.Embed(
                    title=f"🤖 AI 프롬프트 ({bot_name})",
                    description="아직 AI 호출 기록이 없습니다.",
                    color=Colors.WARNING,
                )
                await interaction.followup.send(embed=embed)
                return

            # 프롬프트 truncate (Embed field 제한 대응)
            prompt_text = last_call.get("prompt", "") or ""
            if len(prompt_text) > MAX_PROMPT_DISPLAY_LENGTH:
                prompt_text = (
                    prompt_text[:MAX_PROMPT_DISPLAY_LENGTH]
                    + "\n...(truncated)"
                )

            response_text = last_call.get("response", "") or "(없음)"
            model = last_call.get("model", "unknown")
            signal = last_call.get("signal", "N/A")
            timestamp = last_call.get("timestamp")
            time_str = (
                timestamp.strftime("%Y-%m-%d %H:%M:%S")
                if timestamp
                else "N/A"
            )

            embed = discord.Embed(
                title=f"🤖 AI 프롬프트 ({bot_name})",
                color=Colors.INFO,
            )
            embed.add_field(
                name="📝 프롬프트",
                value=f"```\n{prompt_text[:MAX_EMBED_FIELD_VALUE_LENGTH]}\n```",
                inline=False,
            )
            if len(prompt_text) > MAX_EMBED_FIELD_VALUE_LENGTH:
                embed.add_field(
                    name="📝 프롬프트 (계속)",
                    value=f"```\n{prompt_text[MAX_EMBED_FIELD_VALUE_LENGTH:]}\n```",
                    inline=False,
                )
            embed.add_field(
                name="💬 응답",
                value=f"**{response_text}**",
                inline=True,
            )
            embed.add_field(
                name="📊 시그널",
                value=signal,
                inline=True,
            )
            embed.add_field(
                name="🔧 모델",
                value=model,
                inline=True,
            )
            embed.add_field(
                name="🕐 시간",
                value=time_str,
                inline=True,
            )

            await interaction.followup.send(embed=embed)
            logger.info(
                f"Discord 명령어 /프롬프트 실행 (bot={bot_name}): "
                f"{interaction.user}"
            )

        except Exception as e:
            logger.error(f"/프롬프트 명령어 에러: {e}")
            await interaction.followup.send(
                f"❌ AI 프롬프트 조회 오류: {e!s}", ephemeral=True
            )

    # =========================================================================
    # Multi-Bot Command Implementations
    # =========================================================================

    async def _bot_list_command(self, interaction: discord.Interaction):
        """봇 목록 조회 명령어 구현 (REST API 사용)."""
        await interaction.response.defer()

        try:
            result = await self._call_bot_api("GET", "/api/bots")
            data = result.get("data", result)
            embed = create_bot_list_embed(data)

            await interaction.followup.send(embed=embed)
            logger.info(f"Discord 명령어 /봇목록 실행: {interaction.user}")

        except Exception as e:
            logger.error(f"/봇목록 명령어 에러: {e}")
            await interaction.followup.send(
                f"❌ 봇 목록 조회 오류: {e!s}", ephemeral=True
            )

    async def _bot_status_command(
        self, interaction: discord.Interaction, bot_name: str
    ):
        """봇 상태 조회 명령어 구현 (REST API 사용)."""
        await interaction.response.defer()

        try:
            bot_name = _validate_bot_name(bot_name)
            result = await self._call_bot_api("GET", f"/api/bots/{bot_name}")
            data = result.get("data", result)
            state = data.get("state", data)
            embed = create_bot_status_embed(bot_name, state)

            await interaction.followup.send(embed=embed)
            logger.info(f"Discord 명령어 /봇상태 {bot_name} 실행: {interaction.user}")

        except Exception as e:
            logger.error(f"/봇상태 명령어 에러: {e}")
            await interaction.followup.send(
                f"❌ 봇 상태 조회 오류: {e!s}", ephemeral=True
            )

    async def _bot_start_command(self, interaction: discord.Interaction, bot_name: str):
        """봇 시작 명령어 구현 (REST API 사용)."""
        await interaction.response.defer()

        try:
            bot_name = _validate_bot_name(bot_name)
            await self._call_bot_api("POST", f"/api/bots/{bot_name}/start")

            embed = discord.Embed(
                title="▶️ 봇 시작",
                description=f"봇 **{bot_name}**이(가) 시작되었습니다.",
                color=Colors.SUCCESS
            )
            embed.add_field(
                name="👤 시작한 사용자",
                value=str(interaction.user),
                inline=True,
            )

            await interaction.followup.send(embed=embed)
            logger.info(f"Discord 명령어 /봇시작 {bot_name} 실행: {interaction.user}")

        except Exception as e:
            logger.error(f"/봇시작 명령어 에러: {e}")
            await interaction.followup.send(f"❌ 봇 시작 오류: {e!s}", ephemeral=True)

    async def _bot_stop_command(self, interaction: discord.Interaction, bot_name: str):
        """봇 정지 명령어 구현 (REST API 사용)."""
        await interaction.response.defer()

        try:
            bot_name = _validate_bot_name(bot_name)
            await self._call_bot_api("POST", f"/api/bots/{bot_name}/stop")

            embed = discord.Embed(
                title="⏹️ 봇 정지",
                description=f"봇 **{bot_name}**이(가) 정지되었습니다.",
                color=Colors.ERROR
            )
            embed.add_field(
                name="👤 정지한 사용자",
                value=str(interaction.user),
                inline=True,
            )

            await interaction.followup.send(embed=embed)
            logger.info(f"Discord 명령어 /봇정지 {bot_name} 실행: {interaction.user}")

        except Exception as e:
            logger.error(f"/봇정지 명령어 에러: {e}")
            await interaction.followup.send(f"❌ 봇 정지 오류: {e!s}", ephemeral=True)

    async def _bot_pause_command(self, interaction: discord.Interaction, bot_name: str):
        """봇 일시정지 명령어 구현 (REST API 사용)."""
        await interaction.response.defer()

        try:
            bot_name = _validate_bot_name(bot_name)
            await self._call_bot_api("POST", f"/api/bots/{bot_name}/pause")

            embed = discord.Embed(
                title="⏸️ 봇 일시정지",
                description=f"봇 **{bot_name}**이(가) 일시정지되었습니다.",
                color=Colors.WARNING
            )
            embed.add_field(
                name="ℹ️ 안내",  # noqa: RUF001
                value="새 포지션 진입이 중지됩니다.\n기존 포지션은 계속 관리됩니다.",
                inline=False
            )
            embed.add_field(
                name="👤 일시정지한 사용자",
                value=str(interaction.user),
                inline=True,
            )

            await interaction.followup.send(embed=embed)
            logger.info(
                f"Discord 명령어 /봇일시정지 {bot_name} 실행: {interaction.user}"
            )

        except Exception as e:
            logger.error(f"/봇일시정지 명령어 에러: {e}")
            await interaction.followup.send(
                f"❌ 봇 일시정지 오류: {e!s}", ephemeral=True
            )

    async def _bot_resume_command(
        self, interaction: discord.Interaction, bot_name: str
    ):
        """봇 재개 명령어 구현 (REST API 사용)."""
        await interaction.response.defer()

        try:
            bot_name = _validate_bot_name(bot_name)
            await self._call_bot_api("POST", f"/api/bots/{bot_name}/resume")

            embed = discord.Embed(
                title="▶️ 봇 재개",
                description=f"봇 **{bot_name}**이(가) 재개되었습니다.",
                color=Colors.SUCCESS
            )
            embed.add_field(
                name="ℹ️ 안내",  # noqa: RUF001
                value="정상 거래가 재개됩니다.",
                inline=False,
            )
            embed.add_field(
                name="👤 재개한 사용자",
                value=str(interaction.user),
                inline=True,
            )

            await interaction.followup.send(embed=embed)
            logger.info(f"Discord 명령어 /봇재개 {bot_name} 실행: {interaction.user}")

        except Exception as e:
            logger.error(f"/봇재개 명령어 에러: {e}")
            await interaction.followup.send(f"❌ 봇 재개 오류: {e!s}", ephemeral=True)

    async def _start_all_command(self, interaction: discord.Interaction):
        """전체 봇 시작 명령어 구현 (REST API 사용)."""
        await interaction.response.defer()

        try:
            result = await self._call_bot_api("POST", "/api/bots/start-all")
            data = result.get("data", result)
            started_count = data.get("started", 0)

            embed = discord.Embed(
                title="▶️ 전체 봇 시작",
                description=f"모든 봇({started_count}개)이 시작되었습니다.",
                color=Colors.SUCCESS
            )
            embed.add_field(
                name="👤 시작한 사용자",
                value=str(interaction.user),
                inline=True,
            )

            await interaction.followup.send(embed=embed)
            logger.info(f"Discord 명령어 /전체시작 실행: {interaction.user}")

        except Exception as e:
            logger.error(f"/전체시작 명령어 에러: {e}")
            await interaction.followup.send(f"❌ 전체 시작 오류: {e!s}", ephemeral=True)

    async def _stop_all_command(self, interaction: discord.Interaction):
        """전체 봇 정지 명령어 구현 (REST API 사용)."""
        await interaction.response.defer()

        try:
            result = await self._call_bot_api("POST", "/api/bots/stop-all")
            data = result.get("data", result)
            stopped_count = data.get("stopped", 0)

            embed = discord.Embed(
                title="⏹️ 전체 봇 정지",
                description=f"모든 봇({stopped_count}개)이 정지되었습니다.",
                color=Colors.ERROR
            )
            embed.add_field(
                name="👤 정지한 사용자",
                value=str(interaction.user),
                inline=True,
            )

            await interaction.followup.send(embed=embed)
            logger.info(f"Discord 명령어 /전체정지 실행: {interaction.user}")

        except Exception as e:
            logger.error(f"/전체정지 명령어 에러: {e}")
            await interaction.followup.send(f"❌ 전체 정지 오류: {e!s}", ephemeral=True)

    # =========================================================================
    # Event Handlers
    # =========================================================================

    async def on_ready(self):
        """봇이 준비되면 호출."""
        logger.info(f"Discord 봇 로그인: {self.user}")
        logger.info(f"서버 수: {len(self.guilds)}")

        try:
            synced = await self.tree.sync()
            logger.info(f"명령어 동기화 완료: {len(synced)}개")
        except Exception as e:
            logger.error(f"명령어 동기화 실패: {e}")

    async def on_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError
    ):
        """명령어 에러 핸들러."""
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
    """Discord 봇 시작.

    Args:
        token: Discord 봇 토큰
        bot_state: 공유 상태 딕셔너리
        trade_db: TradeHistoryDB 인스턴스 (선택)
        binance_client: BinanceTestnetClient 인스턴스 (선택)
        bot_manager: MultiBotManager 인스턴스 (선택, 멀티봇 모드)
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
