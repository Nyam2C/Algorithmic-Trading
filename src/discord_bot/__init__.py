"""Discord 봇 모듈.

원격 모니터링 및 제어를 위한 Discord 봇을 제공합니다.

Phase 4.1 리팩토링:
- client.py: 메인 클라이언트
- views.py: UI 컴포넌트
- embeds.py: 임베드 생성
- commands/: 슬래시 명령어
- constants.py: 상수
- utils.py: 유틸리티
"""
from src.discord_bot.client import TradingBotClient, start_discord_bot

__all__ = [
    "TradingBotClient",
    "start_discord_bot",
]
