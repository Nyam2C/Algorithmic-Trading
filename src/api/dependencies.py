"""
FastAPI 의존성 주입 모듈

MultiBotManager 및 기타 의존성을 주입합니다.
Phase 4: TradeHistoryAnalyzer 의존성 추가
Phase 4.1: n8n API 키 인증 추가
"""
import os
from typing import Optional, Union

from fastapi import Header, HTTPException

from src.bot_manager import MultiBotManager
from src.api.config import APIConfig
from src.storage.redis_state import RedisStateManager, DummyRedisStateManager
from src.analytics.trade_analyzer import TradeHistoryAnalyzer

# 전역 상태 (앱 시작 시 설정됨)
_bot_manager: Optional[MultiBotManager] = None
_api_config: Optional[APIConfig] = None
_redis_state_manager: Optional[Union[RedisStateManager, DummyRedisStateManager]] = None
_trade_analyzer: Optional[TradeHistoryAnalyzer] = None


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


def set_redis_state_manager(
    manager: Union[RedisStateManager, DummyRedisStateManager]
) -> None:
    """Redis 상태 관리자 설정

    Args:
        manager: Redis 상태 관리자 인스턴스
    """
    global _redis_state_manager
    _redis_state_manager = manager


def get_redis_state_manager() -> Optional[
    Union[RedisStateManager, DummyRedisStateManager]
]:
    """Redis 상태 관리자 반환

    Returns:
        Redis 상태 관리자 인스턴스 또는 None
    """
    return _redis_state_manager


async def check_redis_health() -> bool:
    """Redis 연결 상태 확인

    Returns:
        연결 성공 여부
    """
    if _redis_state_manager is None:
        return False

    try:
        return await _redis_state_manager.ping()
    except Exception:
        return False


# =============================================================================
# Phase 4: TradeHistoryAnalyzer 의존성
# =============================================================================


def set_trade_analyzer(analyzer: TradeHistoryAnalyzer) -> None:
    """TradeHistoryAnalyzer 인스턴스 설정

    Args:
        analyzer: TradeHistoryAnalyzer 인스턴스
    """
    global _trade_analyzer
    _trade_analyzer = analyzer


def get_trade_analyzer() -> Optional[TradeHistoryAnalyzer]:
    """TradeHistoryAnalyzer 인스턴스 반환

    Returns:
        TradeHistoryAnalyzer 인스턴스 또는 None
    """
    return _trade_analyzer


# =============================================================================
# Phase 4.1: n8n API 키 인증
# =============================================================================


async def verify_n8n_api_key(
    x_n8n_api_key: str = Header(..., alias="X-N8N-API-Key"),
) -> str:
    """n8n 웹훅 API 키 검증

    Args:
        x_n8n_api_key: 요청 헤더의 API 키

    Returns:
        검증된 API 키

    Raises:
        HTTPException: API 키가 유효하지 않은 경우
    """
    expected_key = os.getenv("N8N_API_KEY")
    if not expected_key:
        # N8N_API_KEY 환경변수 미설정 시 인증 건너뜀 (개발 환경)
        return x_n8n_api_key

    if x_n8n_api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_n8n_api_key
