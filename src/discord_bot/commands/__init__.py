"""Discord 봇 슬래시 명령어 모듈.

모니터링 (8개) + 제어 (3개) = 11개 한글 명령어를 제공합니다.
"""
from src.discord_bot.commands.control import register_control_commands
from src.discord_bot.commands.monitoring import register_monitoring_commands

__all__ = [
    "register_control_commands",
    "register_monitoring_commands",
]
