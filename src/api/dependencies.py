"""FastAPI 의존성 주입 모듈.

MultiBotManager 및 기타 의존성을 주입합니다.
Phase 4: TradeHistoryAnalyzer 의존성 추가
Phase 4.1: n8n API 키 인증 추가
Phase 4.2: 보안 강화 (인증 우회 방지, Timing Attack 방지)
Phase 6.3: SignalTracker 의존성 추가
Phase 7: 프로덕션 보안 강화 (API_DEBUG 차단, 레이트 리밋)
"""
import hmac
import os
import time
from collections import defaultdict
from typing import Any, Union

from fastapi import Header, HTTPException, Request
from loguru import logger

from src.analytics.trade_analyzer import TradeHistoryAnalyzer
from src.api.config import APIConfig
from src.bot_manager import MultiBotManager
from src.storage.redis_state import DummyRedisStateManager, RedisStateManager

# 전역 상태 (앱 시작 시 설정됨)
_bot_manager: MultiBotManager | None = None
_api_config: APIConfig | None = None
_redis_state_manager: Union[RedisStateManager, DummyRedisStateManager] | None = None
_trade_analyzer: TradeHistoryAnalyzer | None = None
_signal_tracker: Any | None = None  # SignalTracker 타입


def set_bot_manager(manager: MultiBotManager) -> None:
    """MultiBotManager 인스턴스 설정.

    Args:
        manager: MultiBotManager 인스턴스
    """
    global _bot_manager  # noqa: PLW0603
    _bot_manager = manager


def get_bot_manager() -> MultiBotManager:
    """MultiBotManager 인스턴스 반환.

    Returns:
        MultiBotManager 인스턴스

    Raises:
        RuntimeError: MultiBotManager가 설정되지 않은 경우
    """
    if _bot_manager is None:
        raise RuntimeError("MultiBotManager not configured")
    return _bot_manager


def get_bot_manager_optional() -> MultiBotManager | None:
    """MultiBotManager 인스턴스 반환 (Optional).

    Returns:
        MultiBotManager 인스턴스 또는 None
    """
    return _bot_manager


def set_api_config(config: APIConfig) -> None:
    """API 설정 저장.

    Args:
        config: APIConfig 인스턴스
    """
    global _api_config  # noqa: PLW0603
    _api_config = config


def get_api_config() -> APIConfig:
    """API 설정 반환.

    Returns:
        APIConfig 인스턴스
    """
    if _api_config is None:
        return APIConfig.from_env()
    return _api_config


def set_redis_state_manager(
    manager: Union[RedisStateManager, DummyRedisStateManager]
) -> None:
    """Redis 상태 관리자 설정.

    Args:
        manager: Redis 상태 관리자 인스턴스
    """
    global _redis_state_manager  # noqa: PLW0603
    _redis_state_manager = manager


def get_redis_state_manager(
) -> Union[RedisStateManager, DummyRedisStateManager] | None:
    """Redis 상태 관리자 반환.

    Returns:
        Redis 상태 관리자 인스턴스 또는 None
    """
    return _redis_state_manager


async def check_redis_health() -> bool:
    """Redis 연결 상태 확인.

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
    """TradeHistoryAnalyzer 인스턴스 설정.

    Args:
        analyzer: TradeHistoryAnalyzer 인스턴스
    """
    global _trade_analyzer  # noqa: PLW0603
    _trade_analyzer = analyzer


def get_trade_analyzer() -> TradeHistoryAnalyzer | None:
    """TradeHistoryAnalyzer 인스턴스 반환.

    Returns:
        TradeHistoryAnalyzer 인스턴스 또는 None
    """
    return _trade_analyzer


# =============================================================================
# Phase 4.1: n8n API 키 인증
# =============================================================================


async def verify_n8n_api_key(
    request: Request,
    x_n8n_api_key: str = Header(..., alias="X-N8N-API-Key"),
) -> str:
    """n8n 웹훅 API 키 검증.

    Args:
        request: FastAPI Request 객체 (보안 감사 로그용)
        x_n8n_api_key: 요청 헤더의 API 키

    Returns:
        검증된 API 키

    Raises:
        HTTPException: API 키가 유효하지 않거나 미설정된 경우
    """
    expected_key = os.getenv("N8N_API_KEY")
    if not expected_key:
        raise HTTPException(
            status_code=500,
            detail="N8N_API_KEY not configured"
        )

    # Timing Attack 방지: 상수 시간 비교
    if not hmac.compare_digest(x_n8n_api_key, expected_key):
        # 보안 감사 로그: API 키 검증 실패 기록 (키 값은 기록하지 않음)
        client_ip = request.client.host if request.client else "unknown"
        logger.warning(
            f"n8n API 키 검증 실패: path={request.url.path}, "
            f"client_ip={client_ip}"
        )
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_n8n_api_key


async def verify_api_key(
    request: Request,
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> str | None:
    """일반 API 키 검증.

    Phase 7: ENV=production에서 API_DEBUG=true 차단.

    Args:
        request: FastAPI Request 객체 (보안 감사 로그용)
        x_api_key: 요청 헤더의 API 키 (선택)

    Returns:
        검증된 API 키 또는 None (디버그 모드 시)

    Raises:
        HTTPException: API 키가 유효하지 않거나 미설정된 경우
    """
    expected_key = os.getenv("API_KEY")
    api_debug = os.getenv("API_DEBUG", "false").lower() == "true"
    env = os.getenv("ENV", "development").lower()

    if not expected_key:
        if api_debug:
            # Phase 7: 프로덕션에서 디버그 모드 차단
            if env == "production":
                logger.critical(
                    "보안 위반: ENV=production에서 API_DEBUG=true 감지. 인증 우회 차단."
                )
                raise HTTPException(
                    status_code=500,
                    detail="API_DEBUG cannot be enabled in production",
                )
            logger.warning("API_DEBUG 모드 활성화 - 인증 건너뜀 (비프로덕션)")
            return None
        raise HTTPException(
            status_code=500,
            detail="API_KEY not configured"
        )

    if not x_api_key:
        raise HTTPException(status_code=401, detail="X-API-Key header required")

    # Timing Attack 방지: 상수 시간 비교
    if not hmac.compare_digest(x_api_key, expected_key):
        # 보안 감사 로그: API 키 검증 실패 기록 (키 값은 기록하지 않음)
        client_ip = request.client.host if request.client else "unknown"
        logger.warning(
            f"API 키 검증 실패: path={request.url.path}, "
            f"client_ip={client_ip}"
        )
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key



# =============================================================================
# Phase 7: 크리티컬 엔드포인트 레이트 리밋
# =============================================================================

_rate_limit_store: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_WINDOW = 60  # 1분
_RATE_LIMIT_CRITICAL = 5  # 크리티컬 엔드포인트: 분당 5회


async def check_critical_rate_limit(request: Request) -> None:
    """크리티컬 엔드포인트 레이트 리밋 (Phase 7).

    분당 5회로 제한. /api/n8n/command 등 거래 명령 경로에 적용.

    Args:
        request: FastAPI Request 객체

    Raises:
        HTTPException: 레이트 리밋 초과 시 429
    """
    client_ip = request.client.host if request.client else "unknown"
    key = f"critical:{client_ip}"
    now = time.time()

    # 만료된 요청 제거
    _rate_limit_store[key] = [
        t for t in _rate_limit_store[key]
        if now - t < _RATE_LIMIT_WINDOW
    ]

    if len(_rate_limit_store[key]) >= _RATE_LIMIT_CRITICAL:
        logger.warning(
            f"레이트 리밋 초과: {client_ip} "
            f"({len(_rate_limit_store[key])}/{_RATE_LIMIT_CRITICAL}/min)"
        )
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: {_RATE_LIMIT_CRITICAL} requests per minute",
        )

    _rate_limit_store[key].append(now)


# =============================================================================
# Phase 6.3: SignalTracker 의존성
# =============================================================================


def set_signal_tracker(tracker: Any) -> None:
    """SignalTracker 인스턴스 설정.

    Args:
        tracker: SignalTracker 인스턴스
    """
    global _signal_tracker  # noqa: PLW0603
    _signal_tracker = tracker


def get_signal_tracker() -> Any:
    """SignalTracker 인스턴스 반환.

    Returns:
        SignalTracker 인스턴스

    Raises:
        RuntimeError: SignalTracker가 설정되지 않은 경우
    """
    if _signal_tracker is None:
        raise RuntimeError("SignalTracker not configured")
    return _signal_tracker


def get_optional_signal_tracker() -> Any | None:
    """SignalTracker 인스턴스 반환 (Optional).

    Returns:
        SignalTracker 인스턴스 또는 None
    """
    return _signal_tracker

# =============================================================================
# Phase 3: 오케스트레이터 모드
# =============================================================================

_orchestration_service: Any | None = None


def is_orchestrator_mode() -> bool:
    """오케스트레이터 모드 여부 확인.

    ORCHESTRATOR_MODE=true 환경변수로 활성화.

    Returns:
        오케스트레이터 모드 활성화 여부
    """
    return os.getenv("ORCHESTRATOR_MODE", "false").lower() == "true"


def set_orchestration_service(service: Any) -> None:
    """OrchestrationService 인스턴스 설정.

    Args:
        service: OrchestrationService 인스턴스
    """
    global _orchestration_service  # noqa: PLW0603
    _orchestration_service = service


def get_orchestration_service() -> Any | None:
    """OrchestrationService 인스턴스 반환.

    Returns:
        OrchestrationService 인스턴스 또는 None
    """
    return _orchestration_service

