"""
헬스체크 라우트

Kubernetes Liveness/Readiness probe를 위한 엔드포인트입니다.
"""
from typing import Any

from fastapi import APIRouter, Response, status

from src.api.dependencies import get_bot_manager_optional

router = APIRouter(tags=["Health"])

# 버전 정보 (실제 환경에서는 환경변수나 파일에서 읽음)
API_VERSION = "1.0.0"


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Liveness probe

    서버가 살아있는지 확인합니다.
    항상 200 OK를 반환합니다.

    Returns:
        상태 정보
    """
    return {
        "status": "healthy",
        "version": API_VERSION,
    }


@router.get("/ready")
async def readiness_check(response: Response) -> dict[str, Any]:
    """Readiness probe

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

    return {
        "status": "ready",
        "bots": {"total": total_bots, "running": running_bots},
    }
