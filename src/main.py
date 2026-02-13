"""High-Win Survival System - Main Entry Point.

멀티봇 통합 진입점.

하나의 프로세스에서 실행:
- MultiBotManager: 봇 생명주기 관리
- FastAPI 서버: REST API
- Discord 봇: 원격 제어
"""
import asyncio
import contextlib
import logging
import os
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Union

import aiohttp
from loguru import logger

from src.api.main import create_app
from src.bot_config import BotConfig
from src.bot_manager import MultiBotManager
from src.config import get_config
from src.config_loader import load_bots_from_yaml_optional
from src.discord_bot.client import start_discord_bot
from src.storage.redis_state import (
    DummyRedisStateManager,
    RedisStateManager,
    create_redis_manager,
)
from src.storage.trade_history import TradeHistoryDB
from src.utils.logging import setup_logging_from_env


def setup_logging() -> None:
    """Configure structured JSON logging for Loki/Promtail.

    환경변수 ENABLE_JSON_LOGGING=true 시 JSON 로깅,
    그렇지 않으면 기존 텍스트 로깅을 사용합니다.
    """
    enable_json = os.getenv("ENABLE_JSON_LOGGING", "true").lower() == "true"

    if enable_json:
        setup_logging_from_env()
        return

    # 기존 텍스트 로깅 (fallback)
    logger.remove()
    Path("logs").mkdir(exist_ok=True)

    logger.add(
        sys.stdout,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
        level="INFO",
        colorize=True,
    )

    logger.add(
        "logs/bot.log",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
            "{name}:{function}:{line} - {message}"
        ),
        level="DEBUG",
        rotation="100 MB",
        retention="30 days",
        compression="zip",
        serialize=False,
    )

    logger.add(
        "logs/error.log",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
            "{name}:{function}:{line} - {message}"
        ),
        level="ERROR",
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        serialize=False,
    )


async def send_discord_embed(
    webhook_url: str,
    title: str,
    description: str,
    color: int,
    fields: list | None = None,
) -> bool:
    """Send Discord embed message.

    Args:
        webhook_url: Discord webhook URL
        title: Embed title
        description: Embed description
        color: Embed color (int)
        fields: List of field dicts (optional)

    Returns:
        True if successful
    """
    if not webhook_url:
        logger.warning("[DISCORD] WEBHOOK_URL not set")
        return False

    embed = {
        "title": title,
        "description": description,
        "color": color,
        "timestamp": datetime.utcnow().isoformat(),
    }

    if fields:
        embed["fields"] = fields

    payload = {"embeds": [embed], "username": "Trading Bot"}

    try:
        async with aiohttp.ClientSession() as session, session.post(
            webhook_url, json=payload
        ) as resp:
                http_no_content = 204
                if resp.status == http_no_content:
                    logger.info(f"[DISCORD] embed sent: {title}")
                    return True
                logger.error(f"[DISCORD] webhook failed: {resp.status}")
                return False
    except Exception as e:
        logger.error(f"[DISCORD] webhook error: {e}")
        return False


class _EndpointLogFilter(logging.Filter):
    """Uvicorn access log에서 반복 엔드포인트 필터링."""

    _excluded = ("/health", "/metrics")

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not any(ep in msg for ep in self._excluded)


async def run_embedded_api(
    app, host: str = "0.0.0.0", port: int = 8000  # noqa: S104
) -> None:
    """FastAPI 서버를 내장 모드로 실행 (non-blocking).

    Args:
        app: FastAPI 앱 인스턴스
        host: 바인딩 호스트
        port: 포트 번호
    """
    import uvicorn  # noqa: PLC0415

    logging.getLogger("uvicorn.access").addFilter(_EndpointLogFilter())
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def main() -> None:
    """통합 메인 진입점.

    MultiBotManager + FastAPI + Discord 봇을 하나의 프로세스에서 실행합니다.
    """
    logger.info("=" * 60)
    logger.info("High-Win Survival System - MultiBotManager Mode")
    logger.info("=" * 60)

    # 1. 설정 로드
    config = get_config()

    # 2. Redis 초기화
    redis_manager: Union[RedisStateManager, DummyRedisStateManager] | None = None
    if config.enable_redis_state and config.redis_url:
        try:
            redis_manager = await create_redis_manager(
                redis_url=config.redis_url,
                redis_password=config.redis_password,
                redis_db=config.redis_db,
                fallback_on_error=True,
            )
            if redis_manager.is_connected:
                logger.info("Redis state manager connected")
            else:
                logger.warning("Redis 연결 실패 - 메모리 기반 상태 관리 사용")
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}")
            logger.warning("Continuing without Redis state management")
    else:
        logger.warning("REDIS_URL not set or disabled - state will not be persisted")

    # 3. PostgreSQL 연결
    trade_db: TradeHistoryDB | None = None
    if config.database_url:
        try:
            trade_db = TradeHistoryDB(config.database_url)
            await trade_db.connect()
            logger.info("PostgreSQL trade history database connected")
        except Exception as e:
            logger.error(f"Failed to connect to trade database: {e}")
            logger.warning("Continuing without trade history database")
    else:
        logger.warning("DATABASE_URL not set - trade history will not be saved")

    # 4. MultiBotManager 생성
    manager = MultiBotManager(
        binance_api_key=config.binance_api_key,
        binance_secret_key=config.binance_secret_key,
        gemini_api_key=config.gemini_api_key,
        discord_webhook_url=config.discord_webhook_url,
        database_url=config.database_url,
        loop_interval_seconds=config.loop_interval_seconds,
        redis_state_manager=redis_manager,
    )

    # 5. 봇 설정 로드 (YAML 우선, 없으면 환경변수 fallback)
    yaml_bot_configs, _yaml_global = load_bots_from_yaml_optional()

    if yaml_bot_configs:
        # YAML 설정 기반 멀티봇 추가
        active_count = 0
        for bot_config in yaml_bot_configs:
            if bot_config.is_active:
                manager.add_bot(bot_config)
                logger.info(
                    f"YAML 봇 추가: {bot_config.bot_name} "
                    f"({bot_config.symbol}, {bot_config.risk_level})"
                )
                active_count += 1
        logger.info(f"YAML에서 {active_count}개 활성 봇 로드 완료")
    else:
        # 하위 호환성: 기존 환경변수 방식
        default_bot_config = BotConfig(
            bot_name=config.bot_name,
            symbol=config.symbol,
            risk_level="medium",
            leverage=config.leverage,
            position_size_pct=config.position_size_pct,
            take_profit_pct=config.take_profit_pct,
            stop_loss_pct=config.stop_loss_pct,
            time_cut_minutes=config.time_cut_minutes,
            is_testnet=config.binance_testnet,
            is_active=True,
        )
        manager.add_bot(default_bot_config)
        logger.info(
            f"기본 봇 추가: {config.bot_name} - 환경변수 기반 ({config.symbol})"
        )

    # 6. 공유 상태 (Discord 봇 호환성)
    bot_state = {
        "is_running": True,
        "is_paused": False,
        "emergency_close": False,
        "uptime_start": datetime.now(),
        "current_price": 0,
        "last_signal": "WAIT",
        "last_signal_time": None,
        "position": None,
        "symbol": config.symbol,
        "leverage": config.leverage,
    }

    # 7. FastAPI 앱 생성 (MultiBotManager 주입)
    api_app = create_app(bot_manager=manager)
    api_host = os.getenv("API_HOST", "0.0.0.0")  # noqa: S104
    api_port = int(os.getenv("API_PORT", "8000"))

    # 8. 모든 태스크 생성
    tasks = []

    # API 서버 태스크
    api_task = asyncio.create_task(
        run_embedded_api(api_app, host=api_host, port=api_port),
        name="api_server",
    )
    tasks.append(api_task)
    logger.info(f"API server starting on {api_host}:{api_port}")

    # Discord 봇 태스크
    discord_task: asyncio.Task | None = None
    if config.discord_bot_token and config.discord_bot_token != "your_bot_token_here":  # noqa: S105
        try:
            discord_task = asyncio.create_task(
                start_discord_bot(
                    token=config.discord_bot_token,
                    bot_state=bot_state,
                    trade_db=trade_db,
                    bot_manager=manager,
                ),
                name="discord_bot",
            )
            tasks.append(discord_task)
            logger.info("Discord bot starting")
        except Exception as e:
            logger.error(f"Failed to start Discord bot: {e}")
    else:
        logger.warning("DISCORD_BOT_TOKEN not set - Discord commands disabled")

    # MultiBotManager 실행 태스크
    manager_task = asyncio.create_task(manager.run(), name="bot_manager")
    tasks.append(manager_task)

    # 9. 시작 알림
    await send_discord_embed(
        webhook_url=config.discord_webhook_url,
        title="🤖 Bot Started (MultiBotManager)",
        description=f"**{config.bot_name}** started in MultiBotManager mode",
        color=0x00FF00,
        fields=[
            {"name": "Symbol", "value": config.symbol, "inline": True},
            {"name": "Leverage", "value": f"{config.leverage}x", "inline": True},
            {
                "name": "Mode",
                "value": "Testnet" if config.binance_testnet else "LIVE",
                "inline": True,
            },
            {"name": "API", "value": f"http://{api_host}:{api_port}", "inline": True},
        ],
    )

    logger.info("All services started")

    # 10. 종료 처리
    shutdown_event = asyncio.Event()

    def handle_shutdown(signum, _frame):
        logger.info(f"Received signal {signum}, initiating shutdown...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    try:
        # 종료 신호 대기
        await shutdown_event.wait()
    except asyncio.CancelledError:
        logger.info("Main task cancelled")
    finally:
        logger.info("Shutting down services...")

        # 모든 봇 정지
        await manager.stop_all()

        # 태스크 취소
        for task in tasks:
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

        # Redis 연결 해제
        if redis_manager and redis_manager.is_connected:
            await redis_manager.disconnect()
            logger.info("Redis connection closed")

        # PostgreSQL 연결 해제
        if trade_db:
            await trade_db.disconnect()
            logger.info("Database connection closed")

        # 종료 알림
        await send_discord_embed(
            webhook_url=config.discord_webhook_url,
            title="🛑 Bot Stopped",
            description=f"**{config.bot_name}** stopped",
            color=0xFF0000,
        )

        logger.info("Shutdown complete")


if __name__ == "__main__":
    setup_logging()
    asyncio.run(main())
