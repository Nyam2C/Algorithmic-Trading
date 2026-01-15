"""
High-Win Survival System - Main Entry Point
Version: 0.1.0
"""
import os
import asyncio
from datetime import datetime

import asyncpg
import aiohttp
from loguru import logger


async def check_database() -> bool:
    """PostgreSQL 연결 테스트"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.warning("DATABASE_URL not set")
        return False

    try:
        conn = await asyncpg.connect(database_url)
        version = await conn.fetchval("SELECT version()")
        logger.info(f"Database connected: {version[:50]}...")
        await conn.close()
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


async def send_discord_message(message: str) -> bool:
    """Discord Webhook으로 메시지 전송"""
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        logger.warning("DISCORD_WEBHOOK_URL not set")
        return False

    payload = {
        "content": message,
        "username": "Trading Bot",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload) as resp:
                if resp.status == 204:
                    logger.info("Discord message sent successfully")
                    return True
                else:
                    logger.error(f"Discord webhook failed: {resp.status}")
                    return False
    except Exception as e:
        logger.error(f"Discord webhook error: {e}")
        return False


async def main():
    """메인 실행 함수"""
    bot_name = os.getenv("BOT_NAME", "trading-bot")
    logger.info(f"=== {bot_name} Starting ===")
    logger.info(f"Time: {datetime.now().isoformat()}")

    # 1. Database 연결 테스트
    db_ok = await check_database()
    logger.info(f"Database: {'OK' if db_ok else 'FAILED'}")

    # 2. Discord 알림 테스트
    await send_discord_message(
        f"**{bot_name}** started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    logger.info("=== Initialization Complete ===")

    # 메인 루프 (테스트용 - 60초마다 heartbeat)
    while True:
        logger.debug("Heartbeat...")
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
