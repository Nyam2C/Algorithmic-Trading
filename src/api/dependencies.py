"""
FastAPI 의존성 주입 모듈

MultiBotManager 및 기타 의존성을 주입합니다.
"""
from typing import Optional

from src.bot_manager import MultiBotManager
from src.api.config import APIConfig

# 전역 상태 (앱 시작 시 설정됨)
_bot_manager: Optional[MultiBotManager] = None
_api_config: Optional[APIConfig] = None


def set_bot_manager(manager: MultiBotManager) -> None:
    """MultiBotManager 인스턴스 설정

    Args:
        manager: MultiBotManager 인스턴스
    """
    global _bot_manager
    _bot_manager = manager


def get_bot_manager() -> MultiBotManager:
    """MultiBotManager 인스턴스 반환

    Returns:
        MultiBotManager 인스턴스

    Raises:
        RuntimeError: MultiBotManager가 설정되지 않은 경우
    """
    if _bot_manager is None:
        raise RuntimeError("MultiBotManager not configured")
    return _bot_manager


def get_bot_manager_optional() -> Optional[MultiBotManager]:
    """MultiBotManager 인스턴스 반환 (Optional)

    Returns:
        MultiBotManager 인스턴스 또는 None
    """
    return _bot_manager


def set_api_config(config: APIConfig) -> None:
    """API 설정 저장

    Args:
        config: APIConfig 인스턴스
    """
    global _api_config
    _api_config = config


def get_api_config() -> APIConfig:
    """API 설정 반환

    Returns:
        APIConfig 인스턴스
    """
    if _api_config is None:
        return APIConfig.from_env()
    return _api_config
