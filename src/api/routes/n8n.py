"""n8n 웹훅 라우트.

n8n과의 통합을 위한 웹훅 엔드포인트입니다.
Phase 4.1: API 키 인증 추가
"""
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger

from src.api.dependencies import (
    get_bot_manager,
    get_redis_state_manager,
    verify_n8n_api_key,
)
from src.api.schemas.common import SuccessResponse
from src.api.schemas.n8n import MarketContextPayload, N8NSignalPayload
from src.bot_manager import MultiBotManager

router = APIRouter(prefix="/n8n", tags=["n8n"])


# =============================================================================
# POST - 시그널 수신
# =============================================================================


@router.post("/signal", response_model=SuccessResponse)
async def receive_signal(
    payload: N8NSignalPayload,
    manager: MultiBotManager = Depends(get_bot_manager),
    _: str = Depends(verify_n8n_api_key),
) -> SuccessResponse:
    """외부 시그널 수신.

    n8n이나 다른 외부 시스템에서 보내는 트레이딩 시그널을 수신합니다.

    Args:
        payload: 시그널 페이로드
        manager: MultiBotManager 인스턴스 (DI)
    """
    logger.info(
        f"n8n 시그널 수신: {payload.signal} from {payload.source}"
        f" (bot={payload.bot_name or 'all'})"
    )

    # 시그널 데이터 구조 (Pydantic에서 이미 검증됨)
    _signal_data = {
        "signal": payload.signal,
        "source": payload.source,
        "confidence": payload.confidence,
        "metadata": payload.metadata,
    }

    # 특정 봇 또는 전체 봇에 시그널 주입
    injected_bots: list[str] = []
    if payload.bot_name:
        bot = manager.get_bot(payload.bot_name)
        if not bot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bot '{payload.bot_name}' not found",
            )

        bot.inject_signal(_signal_data)
        logger.info(
            f"시그널 주입: {payload.bot_name} <- {payload.signal} "
            f"(confidence={payload.confidence}, source={payload.source})"
        )
        injected_bots.append(payload.bot_name)

    else:
        # 전체 봇에 시그널 주입
        for bot_name, _bot in manager.bots.items():
            _bot.inject_signal(_signal_data)
            logger.info(
                f"시그널 주입: {bot_name} <- {payload.signal} "
                f"(confidence={payload.confidence}, source={payload.source})"
            )
            injected_bots.append(bot_name)

    return SuccessResponse(
        message=(
            f"Signal '{payload.signal}' received from {payload.source}"
            f" (injected to {len(injected_bots)} bot(s))"
        )
    )


# =============================================================================
# POST - 외부 시장 컨텍스트 수신
# =============================================================================


@router.post("/market-context", response_model=SuccessResponse)
async def receive_market_context(
    payload: MarketContextPayload,
    _: str = Depends(verify_n8n_api_key),
) -> SuccessResponse:
    """외부 시장 컨텍스트 수신.

    n8n에서 수집한 Fear & Greed, 펀딩레이트 등 외부 데이터를 수신하여
    Redis에 저장합니다. AI 시그널 생성 시 참고 데이터로 사용됩니다.

    Args:
        payload: 시장 컨텍스트 페이로드
    """
    redis_manager = get_redis_state_manager()

    context_data: dict[str, Any] = {
        "source": payload.source,
        "received_at": datetime.now().isoformat(),
    }

    if payload.fear_greed_index is not None:
        context_data["fear_greed_index"] = payload.fear_greed_index
    if payload.funding_rate is not None:
        context_data["funding_rate"] = payload.funding_rate
    if payload.whale_alerts is not None:
        context_data["whale_alerts"] = payload.whale_alerts
    if payload.custom_data is not None:
        context_data["custom_data"] = payload.custom_data
    if payload.timestamp is not None:
        context_data["data_timestamp"] = payload.timestamp.isoformat()

    if redis_manager:
        saved = await redis_manager.save_market_context(context_data)
        if saved:
            logger.info(
                f"시장 컨텍스트 저장: source={payload.source}, "
                f"fields={list(context_data.keys())}"
            )
            return SuccessResponse(message="Market context saved successfully")
        logger.warning("시장 컨텍스트 Redis 저장 실패")
        return SuccessResponse(message="Market context received but Redis save failed")

    logger.warning("Redis not available - 시장 컨텍스트 저장 불가")
    return SuccessResponse(message="Market context received but Redis not available")
