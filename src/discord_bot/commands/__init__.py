"""
Discord 봇 슬래시 명령어 모듈

모니터링, 제어, 멀티봇 명령어를 제공합니다.
"""
from src.discord_bot.commands.monitoring import register_monitoring_commands
from src.discord_bot.commands.control import register_control_commands
from src.discord_bot.commands.multibot import register_multibot_commands

__all__ = [
    "register_monitoring_commands",
    "register_control_commands",
    "register_multibot_commands",
]
