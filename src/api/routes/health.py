"""헬스체크 라우트.

Kubernetes Liveness/Readiness probe를 위한 엔드포인트입니다.
Phase 7.2: /metrics 엔드포인트 추가 (Prometheus)
"""
from typing import Any

from fastapi import APIRouter, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from src.api.dependencies import check_redis_health, get_bot_manager_optional
from src.metrics.prometheus import get_metrics_registry

router = APIRouter(tags=["Health"])

# 버전 정보 (실제 환경에서는 환경변수나 파일에서 읽음)
API_VERSION = "1.0.0"


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Liveness probe.

    서버가 살아있는지 확인합니다.
    PostgreSQL, Redis 연결 상태를 포함합니다.

    Returns:
        상태 정보
    """
    redis_healthy = await check_redis_health()

    return {
        "status": "healthy",
        "version": API_VERSION,
        "components": {
            "redis": redis_healthy,
        },
    }


@router.get("/ready")
async def readiness_check(response: Response) -> dict[str, Any]:
    """Readiness probe.

    서버가 요청을 처리할 준비가 되었는지 확인합니다.
    MultiBotManager가 설정되어 있고 봇이 실행 중이면 200 OK,
    그렇지 않으면 503 Service Unavailable을 반환합니다.

    Returns:
        상태 정보
    """
    manager = get_bot_manager_optional()

    if manager is None:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "not_ready",
            "reason": "MultiBotManager not configured",
            "bots": {"total": 0, "running": 0},
        }

    total_bots = manager.bot_count
    running_bots = manager.running_count

    if running_bots == 0 and total_bots > 0:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "not_ready",
            "reason": "No bots running",
            "bots": {"total": total_bots, "running": running_bots},
        }

    redis_healthy = await check_redis_health()

    return {
        "status": "ready",
        "bots": {"total": total_bots, "running": running_bots},
        "components": {
            "redis": redis_healthy,
        },
    }


@router.get("/health/bots")
async def bot_health() -> dict[str, Any]:
    """봇별 상세 상태 확인.

    각 봇의 실시간 상태를 반환합니다.
    루프 소요시간, 마켓 레짐, 포지션 유무 등을 포함합니다.

    Returns:
        봇별 상태 목록
    """
    manager = get_bot_manager_optional()

    if manager is None:
        return {"bots": []}

    bots_status: list[dict[str, Any]] = []
    for bot in manager.bots.values():
        state = bot.get_state()
        uptime_start = state.get("uptime_start")
        uptime_seconds = 0.0
        if uptime_start:
            from datetime import datetime  # noqa: PLC0415
            if isinstance(uptime_start, datetime):
                uptime_seconds = (datetime.now() - uptime_start).total_seconds()

        bots_status.append({
            "bot_name": state.get("bot_name", ""),
            "is_running": state.get("is_running", False),
            "is_paused": state.get("is_paused", False),
            "loop_count": state.get("loop_count", 0),
            "last_loop_duration_sec": state.get("last_loop_duration", 0.0),
            "last_signal": state.get("last_signal", "WAIT"),
            "current_price": state.get("current_price", 0.0),
            "market_regime": state.get("market_regime", "UNKNOWN"),
            "has_position": state.get("has_position", False),
            "uptime_seconds": round(uptime_seconds, 1),
        })

    return {"bots": bots_status}


@router.get("/metrics")
async def prometheus_metrics() -> Response:
    """Prometheus 메트릭 엔드포인트.

    Phase 7.2: Prometheus 서버가 스크래핑하는 메트릭 엔드포인트입니다.
    거래 메트릭, API 지연시간, 포지션 PnL 등을 노출합니다.

    Returns:
        Prometheus 형식의 메트릭 텍스트
    """
    registry = get_metrics_registry()
    metrics_output = generate_latest(registry)

    return Response(
        content=metrics_output,
        media_type=CONTENT_TYPE_LATEST,
    )
