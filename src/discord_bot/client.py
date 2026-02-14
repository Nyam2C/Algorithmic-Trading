"""Discord 트레이딩 봇 클라이언트.

메인 봇 클라이언트와 명령어 핸들러를 정의합니다.
멀티봇 전용 — bot_manager가 필수이며, REST API를 통해 봇을 제어합니다.
"""
import os
from typing import TYPE_CHECKING, Any

import aiohttp
import discord
from discord import app_commands
from loguru import logger

from src.discord_bot.commands import (
    register_control_commands,
    register_monitoring_commands,
)
from src.discord_bot.constants import Colors, Emojis, Messages, Timeouts
from src.discord_bot.embeds import (
    create_account_embed,
    create_alert_settings_embed,
    create_bot_list_embed,
    create_bot_status_embed,
    create_history_embed,
    create_pnl_embed,
    create_position_embed,
)
from src.discord_bot.utils import (
    PERIOD_LABELS,
)
from src.discord_bot.utils import (
    validate_bot_name as _validate_bot_name,
)
from src.discord_bot.views import DashboardView

# Discord 메시지/임베드 길이 제한 상수
MAX_PROMPT_DISPLAY_LENGTH = 1500
MAX_EMBED_FIELD_VALUE_LENGTH = 1024

# HTTP 상태 코드 상수
HTTP_SERVER_ERROR = 500
HTTP_CLIENT_ERROR = 400

# 알림 설정 기본값
DEFAULT_ALERT_SETTINGS: dict[str, bool] = {
    "entry": True,
    "exit": True,
    "pnl_daily": True,
    "error": True,
}

if TYPE_CHECKING:
    from src.bot_manager import MultiBotManager


class TradingBotClient(discord.Client):
    """Discord 트레이딩 봇 클라이언트.

    멀티봇 모드 전용 — MultiBotManager와 REST API를 사용합니다.
    """

    def __init__(
        self,
        bot_manager: "MultiBotManager",
        trade_db: Any = None,
        binance_client: Any = None,
        bot_state: dict | None = None,
    ):
        """TradingBotClient 초기화.

        Args:
            bot_manager: MultiBotManager 인스턴스 (필수)
            trade_db: TradeHistoryDB 인스턴스 (선택)
            binance_client: BinanceTestnetClient 인스턴스 (선택)
            bot_state: 하위 호환용 상태 딕셔너리 (선택)
        """
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)

        self.tree = app_commands.CommandTree(self)
        self.bot_manager = bot_manager
        self.trade_db = trade_db
        self.binance_client = binance_client
        self.bot_state = bot_state or {}
        self._api_url = os.getenv("TRADING_BOT_API_URL", "http://localhost:8000")

        # Phase 7: 감사 로그
        self._audit_log: Any | None = None

        # 알림 설정 (인메모리, Redis 연동 가능)
        self._alert_settings: dict[str, dict[str, bool]] = {}

        # 명령어 등록
        register_monitoring_commands(self)
        register_control_commands(self)

    def set_audit_log(self, audit_log: Any) -> None:
        """감사 로그 매니저 설정."""
        self._audit_log = audit_log
        logger.info("Discord 봇 감사 로그 설정 완료")

    async def _audit_command(
        self, command: str, user: str, bot_name: str = "", details: str = ""
    ) -> None:
        """Discord 명령어 감사 로그 기록."""
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
    # Monitoring Command Implementations
    # =========================================================================

    async def _dashboard_command(self, interaction: discord.Interaction):
        """대시보드 명령어 구현 — REST API로 전체 봇 현황 표시."""
        await interaction.response.defer()

        try:
            result = await self._call_bot_api("GET", "/api/bots")
            data = result.get("data", result)
            bots = data.get("bots", [])
            total = data.get("total_bots", len(bots))
            running = data.get("running_bots", 0)

            # 전체 요약 임베드
            color = Colors.SUCCESS if running > 0 else Colors.ERROR
            embed = discord.Embed(
                title="🤖 트레이딩 봇 대시보드",
                description=(
                    f"**봇:** {total}개 등록 | 🟢 {running}개 실행 중\n"
                ),
                color=color,
            )

            # 각 봇 요약 (최대 5개)
            for bot_info in bots[:5]:
                name = bot_info.get("name", "unknown")
                is_running = bot_info.get("is_running", False)
                is_paused = bot_info.get("is_paused", False)
                symbol = bot_info.get("symbol", "N/A")
                if is_running and not is_paused:
                    status = "🟢 실행"
                elif is_paused:
                    status = "⏸️ 일시정지"
                else:
                    status = "🔴 정지"
                embed.add_field(
                    name=f"{name}",
                    value=f"{status} | {symbol}",
                    inline=True,
                )

            embed.set_footer(text="아래 버튼을 클릭하여 상세 정보를 확인하세요")

            view = DashboardView(bot_client=self, timeout=Timeouts.DASHBOARD_VIEW)
            await interaction.followup.send(embed=embed, view=view)
            logger.info(f"Discord 명령어 /대시보드 실행: {interaction.user}")

        except Exception as e:
            logger.error(f"/대시보드 명령어 에러: {e}")
            await interaction.followup.send(f"❌ 오류: {e!s}", ephemeral=True)

    async def _status_all_command(self, interaction: discord.Interaction):
        """전체 봇 목록 조회 (REST API)."""
        await interaction.response.defer()

        try:
            result = await self._call_bot_api("GET", "/api/bots")
            data = result.get("data", result)
            embed = create_bot_list_embed(data)
            await interaction.followup.send(embed=embed)
            logger.info(f"Discord 명령어 /상태 (전체) 실행: {interaction.user}")
        except Exception as e:
            logger.error(f"/상태 명령어 에러: {e}")
            await interaction.followup.send(
                f"❌ 봇 목록 조회 오류: {e!s}", ephemeral=True
            )

    async def _status_bot_command(
        self, interaction: discord.Interaction, bot_name: str
    ):
        """특정 봇 상태 조회 (REST API)."""
        await interaction.response.defer()

        try:
            bot_name = _validate_bot_name(bot_name)
            result = await self._call_bot_api("GET", f"/api/bots/{bot_name}")
            data = result.get("data", result)
            state = data.get("state", data)
            embed = create_bot_status_embed(bot_name, state)
            await interaction.followup.send(embed=embed)
            logger.info(
                f"Discord 명령어 /상태 {bot_name} 실행: {interaction.user}"
            )
        except ValueError as e:
            await interaction.followup.send(f"❌ {e}", ephemeral=True)
        except Exception as e:
            logger.error(f"/상태 명령어 에러: {e}")
            await interaction.followup.send(
                f"❌ 봇 상태 조회 오류: {e!s}", ephemeral=True
            )

    async def _position_command(
        self, interaction: discord.Interaction, bot_name: str = ""
    ):
        """포지션 조회 — 봇이름 유무에 따라 단일/전체 포지션."""
        await interaction.response.defer()

        try:
            if bot_name:
                bot_name = _validate_bot_name(bot_name)
                result = await self._call_bot_api(
                    "GET", f"/api/bots/{bot_name}"
                )
                data = result.get("data", result)
                state = data.get("state", data)
                embed = create_position_embed(state)
                embed.title = f"📍 포지션 — {bot_name}"
            else:
                # 전체 봇 포지션 요약
                result = await self._call_bot_api("GET", "/api/bots")
                data = result.get("data", result)
                bots = data.get("bots", [])

                embed = discord.Embed(
                    title="📍 전체 포지션",
                    color=Colors.INFO,
                )

                has_position = False
                for bot_info in bots:
                    name = bot_info.get("name", "unknown")
                    position = bot_info.get("position")
                    if position and position.get("side"):
                        has_position = True
                        side = position["side"]
                        entry = position.get("entry_price", 0)
                        emoji = Emojis.LONG if side == "LONG" else Emojis.SHORT
                        embed.add_field(
                            name=f"{emoji} {name}",
                            value=(
                                f"{side} @ ${entry:,.2f}"
                            ),
                            inline=True,
                        )

                if not has_position:
                    embed.description = "열린 포지션이 없습니다"

            await interaction.followup.send(embed=embed)
            logger.info(f"Discord 명령어 /포지션 실행: {interaction.user}")
        except ValueError as e:
            await interaction.followup.send(f"❌ {e}", ephemeral=True)
        except Exception as e:
            logger.error(f"/포지션 명령어 에러: {e}")
            await interaction.followup.send(
                f"❌ 포지션 조회 오류: {e!s}", ephemeral=True
            )

    async def _pnl_command(
        self,
        interaction: discord.Interaction,
        hours: int = 24,
        period_label: str = "일간 (24시간)",
        bot_name: str = "",
    ):
        """수익 리포트 명령어 구현."""
        await interaction.response.defer()

        try:
            if not self.trade_db:
                await interaction.followup.send(
                    Messages.NO_DATABASE, ephemeral=True
                )
                return

            stats_data = await self.trade_db.get_statistics(hours=hours)
            embed = create_pnl_embed(stats_data, period_label, bot_name)
            await interaction.followup.send(embed=embed)
            logger.info(
                f"Discord 명령어 /수익 실행 (hours={hours}): {interaction.user}"
            )
        except Exception as e:
            logger.error(f"/수익 명령어 에러: {e}")
            await interaction.followup.send(
                f"❌ 수익 조회 오류: {e!s}", ephemeral=True
            )

    async def _history_command(
        self, interaction: discord.Interaction, count: int = 5
    ):
        """내역 조회 명령어 구현."""
        await interaction.response.defer()

        try:
            if not self.trade_db:
                await interaction.followup.send(
                    Messages.NO_DATABASE, ephemeral=True
                )
                return

            limit = min(count, 10)
            trades = await self.trade_db.get_recent_trades(limit=limit)
            embed = create_history_embed(trades)
            await interaction.followup.send(embed=embed)
            logger.info(
                f"Discord 명령어 /내역 실행 (count={count}): {interaction.user}"
            )
        except Exception as e:
            logger.error(f"/내역 명령어 에러: {e}")
            await interaction.followup.send(
                f"❌ 내역 조회 오류: {e!s}", ephemeral=True
            )

    async def _account_command(self, interaction: discord.Interaction):
        """계정 조회 명령어 구현."""
        await interaction.response.defer()

        try:
            if not self.binance_client:
                await interaction.followup.send(
                    Messages.NO_BINANCE, ephemeral=True
                )
                return

            balance = await self.binance_client.get_account_balance()
            positions = await self.binance_client.get_all_positions()
            embed = create_account_embed(balance, positions)
            await interaction.followup.send(embed=embed)
            logger.info(f"Discord 명령어 /계정 실행: {interaction.user}")
        except Exception as e:
            logger.error(f"/계정 명령어 에러: {e}")
            await interaction.followup.send(
                f"❌ 계정 조회 오류: {e!s}", ephemeral=True
            )

    async def _prompt_command(
        self, interaction: discord.Interaction, bot_name: str = ""
    ):
        """마지막 AI 프롬프트/응답 조회 명령어 구현."""
        await interaction.response.defer()

        try:
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
                        Messages.BOT_NOT_FOUND.format(name=bot_name)
                        + f"\n사용 가능: {available}",
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
                name="💬 응답", value=f"**{response_text}**", inline=True
            )
            embed.add_field(name="📊 시그널", value=signal, inline=True)
            embed.add_field(name="🔧 모델", value=model, inline=True)
            embed.add_field(name="🕐 시간", value=time_str, inline=True)

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
    # Control Command Implementations
    # =========================================================================

    async def _control_all_bots(self, action: str, action_label: str) -> str:
        """전체 봇 제어 — start/stop은 전용 API, pause/resume은 순회."""
        if action == "start":
            result = await self._call_bot_api("POST", "/api/bots/start-all")
            count = result.get("data", result).get("started", 0)
        elif action == "stop":
            result = await self._call_bot_api("POST", "/api/bots/stop-all")
            count = result.get("data", result).get("stopped", 0)
        else:
            bot_result = await self._call_bot_api("GET", "/api/bots")
            bots = bot_result.get("data", bot_result).get("bots", [])
            count = 0
            for bot_info in bots:
                name = bot_info.get("name")
                if name:
                    try:
                        await self._call_bot_api(
                            "POST", f"/api/bots/{name}/{action}"
                        )
                        count += 1
                    except Exception:
                        logger.warning(f"봇 {name} {action_label} 실패")
        return f"모든 봇({count}개) {action_label} 완료"

    async def _control_command(
        self,
        interaction: discord.Interaction,
        target: str,
        action: str,
    ):
        """통합 제어 명령어 구현."""
        await interaction.response.defer()

        action_labels = {
            "start": "시작", "stop": "정지",
            "pause": "일시정지", "resume": "재개",
        }
        action_label = action_labels.get(action, action)

        try:
            is_all = target == Messages.ALL_BOTS_TARGET
            if is_all:
                desc = await self._control_all_bots(action, action_label)
            else:
                target = _validate_bot_name(target)
                await self._call_bot_api(
                    "POST", f"/api/bots/{target}/{action}"
                )
                desc = f"봇 **{target}** {action_label} 완료"

            if action in ("start", "resume"):
                color, title_emoji = Colors.SUCCESS, "▶️"
            elif action == "pause":
                color, title_emoji = Colors.WARNING, "⏸️"
            else:
                color, title_emoji = Colors.ERROR, "⏹️"

            embed = discord.Embed(
                title=f"{title_emoji} {action_label}",
                description=desc, color=color,
            )
            embed.add_field(
                name="👤 실행한 사용자",
                value=str(interaction.user), inline=True,
            )
            await interaction.followup.send(embed=embed)
            logger.info(
                f"Discord 명령어 /제어 {action} {target} 실행: "
                f"{interaction.user}"
            )
            await self._audit_command(
                f"제어/{action_label}",
                str(interaction.user),
                bot_name=target if not is_all else "전체",
            )
        except ValueError as e:
            await interaction.followup.send(f"❌ {e}", ephemeral=True)
        except Exception as e:
            logger.error(f"/제어 명령어 에러: {e}")
            await interaction.followup.send(
                f"❌ {action_label} 오류: {e!s}", ephemeral=True
            )

    async def _emergency_command(
        self, interaction: discord.Interaction, target: str
    ):
        """통합 긴급청산 명령어 구현."""
        await interaction.response.defer()

        try:
            is_all = target == Messages.ALL_BOTS_TARGET

            if is_all:
                # 전체 봇 긴급청산
                # Phase 3: 오케스트레이터 모드면 Redis 명령 채널 사용
                from src.api.dependencies import is_orchestrator_mode  # noqa: PLC0415
                if is_orchestrator_mode() and self.bot_manager.redis_state_manager:
                    redis_mgr = self.bot_manager.redis_state_manager
                    registered = await redis_mgr.get_registered_bots()
                    closed_count = len(registered)
                    for name in registered:
                        await redis_mgr.push_command(
                            name, {"action": "EMERGENCY_CLOSE"}
                        )
                else:
                    bots = self.bot_manager.bots
                    closed_count = 0
                    for _name, bot in bots.items():
                        bot.request_emergency_close()
                        closed_count += 1

                embed = discord.Embed(
                    title="🚨 전체 긴급 청산",
                    description=(
                        f"{closed_count}개 봇에 긴급 청산 요청 완료\n"
                        "각 봇은 다음 루프에서 시장가로 청산됩니다."
                    ),
                    color=Colors.ERROR,
                )
            else:
                target = _validate_bot_name(target)
                found_bot = self.bot_manager.get_bot(target)
                if not found_bot:
                    await interaction.followup.send(
                        Messages.BOT_NOT_FOUND.format(name=target),
                        ephemeral=True,
                    )
                    return

                # Phase 3: 오케스트레이터 모드면 Redis 명령 채널 사용
                from src.api.dependencies import is_orchestrator_mode  # noqa: PLC0415
                if is_orchestrator_mode() and self.bot_manager.redis_state_manager:
                    await self.bot_manager.redis_state_manager.push_command(
                        target, {"action": "EMERGENCY_CLOSE"}
                    )
                else:
                    found_bot.request_emergency_close()

                embed = discord.Embed(
                    title=f"🚨 긴급 청산 — {target}",
                    description=(
                        f"봇 **{target}**에 긴급 청산 요청 완료\n"
                        "다음 루프에서 시장가로 청산됩니다."
                    ),
                    color=Colors.ERROR,
                )

            embed.add_field(
                name="⏸️ 봇 상태",
                value="자동 일시정지됨",
                inline=True,
            )
            embed.add_field(
                name="👤 요청한 사용자",
                value=str(interaction.user),
                inline=True,
            )

            await interaction.followup.send(embed=embed)
            logger.critical(f"긴급 청산: {target} by {interaction.user}")

            await self._audit_command(
                "긴급청산",
                str(interaction.user),
                bot_name=target if not is_all else "전체",
            )

        except ValueError as e:
            await interaction.followup.send(f"❌ {e}", ephemeral=True)
        except Exception as e:
            logger.error(f"/긴급청산 명령어 에러: {e}")
            await interaction.followup.send(
                f"❌ 긴급청산 오류: {e!s}", ephemeral=True
            )

    async def _alert_command(
        self,
        interaction: discord.Interaction,
        alert_type: str | None = None,
        state: str | None = None,
    ):
        """알림 설정 명령어 구현.

        유형/설정이 없으면 현재 설정을 표시합니다.
        """
        await interaction.response.defer(ephemeral=True)

        try:
            user_id = str(interaction.user.id)

            # 현재 설정 로드
            if user_id not in self._alert_settings:
                self._alert_settings[user_id] = dict(DEFAULT_ALERT_SETTINGS)

            settings = self._alert_settings[user_id]

            if alert_type and state:
                # 설정 변경
                is_on = state == "on"
                settings[alert_type] = is_on

                state_label = "켜기" if is_on else "끄기"
                type_labels = {
                    "entry": "진입 알림",
                    "exit": "청산 알림",
                    "pnl_daily": "일간 리포트",
                    "error": "에러 알림",
                }
                type_label = type_labels.get(alert_type, alert_type)

                await interaction.followup.send(
                    Messages.ALERT_UPDATED.format(
                        alert_type=type_label, state=state_label
                    ),
                    ephemeral=True,
                )
                logger.info(
                    f"Discord 알림 설정: {interaction.user} "
                    f"- {type_label} → {state_label}"
                )
            else:
                # 현재 설정 표시
                embed = create_alert_settings_embed(settings)
                await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"/알림 명령어 에러: {e}")
            await interaction.followup.send(
                f"❌ 알림 설정 오류: {e!s}", ephemeral=True
            )

    # =========================================================================
    # Dashboard helper (for DashboardView buttons)
    # =========================================================================

    async def _get_pnl_embed(self, hours: int = 24) -> discord.Embed:
        """수익 임베드 반환 (대시보드 버튼용)."""
        if not self.trade_db:
            return discord.Embed(
                title="❌ 데이터베이스 연결 안 됨",
                description="거래 데이터베이스를 사용할 수 없습니다",
                color=Colors.ERROR,
            )

        stats_data = await self.trade_db.get_statistics(hours=hours)
        return create_pnl_embed(stats_data, PERIOD_LABELS.get("일간", "일간"))

    async def _get_history_embed(self, limit: int = 5) -> discord.Embed:
        """내역 임베드 반환 (대시보드 버튼용)."""
        if not self.trade_db:
            return discord.Embed(
                title="❌ 데이터베이스 연결 안 됨",
                description="거래 데이터베이스를 사용할 수 없습니다",
                color=Colors.ERROR,
            )

        limit = min(limit, 10)
        trades = await self.trade_db.get_recent_trades(limit=limit)
        return create_history_embed(trades)

    async def _get_account_embed(self) -> discord.Embed:
        """계정 임베드 반환 (대시보드 버튼용)."""
        if not self.binance_client:
            return discord.Embed(
                title="❌ Binance 클라이언트 연결 안 됨",
                description="Binance API를 사용할 수 없습니다",
                color=Colors.ERROR,
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
                color=Colors.ERROR,
            )

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
        error: app_commands.AppCommandError,
    ):
        """명령어 에러 핸들러."""
        logger.error(f"명령어 에러: {error}")
        await interaction.response.send_message(
            f"❌ 명령어 오류: {error!s}", ephemeral=True
        )


async def start_discord_bot(
    token: str,
    bot_manager: "MultiBotManager",
    trade_db: Any = None,
    binance_client: Any = None,
    bot_state: dict | None = None,
):
    """Discord 봇 시작.

    Args:
        token: Discord 봇 토큰
        bot_manager: MultiBotManager 인스턴스 (필수)
        trade_db: TradeHistoryDB 인스턴스 (선택)
        binance_client: BinanceTestnetClient 인스턴스 (선택)
        bot_state: 하위 호환용 상태 딕셔너리 (선택)
    """
    client = TradingBotClient(
        bot_manager=bot_manager,
        trade_db=trade_db,
        binance_client=binance_client,
        bot_state=bot_state,
    )

    try:
        await client.start(token)
    except Exception as e:
        logger.error(f"Discord 봇 에러: {e}")
        raise
