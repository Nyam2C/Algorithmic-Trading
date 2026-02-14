"""독립 봇 실행기.

각 봇을 별도 프로세스/컨테이너로 실행하기 위한 진입점.

Usage:
    python -m src.bot_runner --bot-name btc-conservative
    BOT_NAME=btc-conservative python -m src.bot_runner
"""
import argparse
import asyncio
import contextlib
import os
import signal
from typing import Union

from loguru import logger

from src.bot_config import BotConfig
from src.bot_instance import BotInstance
from src.config import get_config
from src.config_loader import load_bots_from_yaml_optional
from src.storage.redis_state import (
    DummyRedisStateManager,
    RedisStateManager,
    create_redis_manager,
)
from src.storage.trade_history import TradeHistoryDB


def find_bot_config(bot_name: str) -> BotConfig:
    """YAML에서 봇 설정을 찾아 반환.

    Args:
        bot_name: 봇 이름

    Returns:
        BotConfig 인스턴스

    Raises:
        ValueError: 봇 설정을 찾을 수 없는 경우
    """
    configs, _global = load_bots_from_yaml_optional()

    for config in configs:
        if config.bot_name == bot_name:
            return config

    available = [c.bot_name for c in configs] if configs else []
    raise ValueError(
        f"봇 '{bot_name}' 설정을 찾을 수 없습니다. "
        f"사용 가능: {available}"
    )


async def run_bot(bot_name: str) -> None:  # noqa: PLR0915
    """단일 봇 실행.

    Args:
        bot_name: 실행할 봇 이름
    """
    logger.info(f"봇 실행기 시작: {bot_name}")

    # 1. 설정 로드
    app_config = get_config()
    bot_config = find_bot_config(bot_name)

    if not bot_config.is_active:
        logger.warning(f"봇 '{bot_name}'이 비활성 상태입니다. 실행 중단.")
        return

    # 2. Redis 초기화
    redis_manager: Union[RedisStateManager, DummyRedisStateManager] | None = None
    if app_config.enable_redis_state and app_config.redis_url:
        try:
            redis_manager = await create_redis_manager(
                redis_url=app_config.redis_url,
                redis_password=app_config.redis_password,
                redis_db=app_config.redis_db,
                fallback_on_error=True,
            )
            logger.info("Redis 연결 성공")
        except Exception as e:
            logger.error(f"Redis 연결 실패: {e}")

    # 3. PostgreSQL 연결
    trade_db: TradeHistoryDB | None = None
    if app_config.database_url:
        try:
            trade_db = TradeHistoryDB(app_config.database_url)
            await trade_db.connect()
            logger.info("PostgreSQL 연결 성공")
        except Exception as e:
            logger.error(f"PostgreSQL 연결 실패: {e}")

    # 4. 분산 노출도 체크 콜백 (Redis 기반)
    max_exposure = float(os.getenv("MAX_TOTAL_EXPOSURE", "0"))

    async def distributed_exposure_check(
        _bot_name: str, position_value: float
    ) -> tuple[bool, str]:
        if redis_manager is None or max_exposure <= 0:
            return True, ""
        ok = await redis_manager.check_and_reserve_exposure(
            _bot_name, position_value, max_exposure
        )
        if not ok:
            return False, f"분산 노출도 한도 초과 (max=${max_exposure:,.2f})"
        return True, ""

    exposure_cb = distributed_exposure_check if max_exposure > 0 else None

    # 5. BotInstance 생성
    instance = BotInstance(
        config=bot_config,
        binance_api_key=app_config.binance_api_key,
        binance_secret_key=app_config.binance_secret_key,
        gemini_api_key=app_config.gemini_api_key,
        discord_webhook_url=app_config.discord_webhook_url,
        database_url=app_config.database_url,
        loop_interval_seconds=app_config.loop_interval_seconds,
        redis_state_manager=redis_manager,
        use_memory_signals=bool(app_config.gemini_api_key),
        on_exposure_check=exposure_cb,
    )

    # 6. 종료 처리
    shutdown_event = asyncio.Event()

    def handle_shutdown(signum, _frame):
        logger.info(f"종료 신호 수신 (signal={signum})")
        shutdown_event.set()

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # 7. 봇 실행
    bot_task = asyncio.create_task(instance.start(), name=f"bot-{bot_name}")

    try:
        # 종료 신호 대기
        await shutdown_event.wait()
    except asyncio.CancelledError:
        logger.info("봇 실행기 태스크 취소됨")
    finally:
        logger.info("봇 종료 중...")
        await instance.stop()

        if not bot_task.done():
            bot_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await bot_task

        # 연결 해제
        if redis_manager and redis_manager.is_connected:
            # 노출도 해제
            await redis_manager.release_exposure(bot_name)
            await redis_manager.disconnect()
            logger.info("Redis 연결 해제")

        if trade_db:
            await trade_db.disconnect()
            logger.info("PostgreSQL 연결 해제")

        logger.info(f"봇 '{bot_name}' 종료 완료")


def main() -> None:
    """CLI 진입점."""
    parser = argparse.ArgumentParser(
        description="독립 봇 실행기 - 단일 봇을 별도 프로세스로 실행"
    )
    parser.add_argument(
        "--bot-name",
        type=str,
        default=os.getenv("BOT_NAME"),
        help="실행할 봇 이름 (또는 BOT_NAME 환경변수)",
    )
    args = parser.parse_args()

    bot_name = args.bot_name
    if not bot_name:
        parser.error(
            "--bot-name 또는 BOT_NAME 환경변수를 설정하세요"
        )

    # 로깅 설정
    from src.main import setup_logging  # noqa: PLC0415
    setup_logging()

    asyncio.run(run_bot(bot_name))


if __name__ == "__main__":
    main()
