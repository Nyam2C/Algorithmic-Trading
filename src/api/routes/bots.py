"""
봇 CRUD 라우트

봇 생성, 조회, 수정, 삭제 및 제어 엔드포인트입니다.
"""
from typing import Any

from fastapi import APIRouter, HTTPException, status, Depends

from src.api.dependencies import get_bot_manager
from src.api.schemas.bot import (
    BotCreateRequest,
    BotUpdateRequest,
    BotResponse,
    BotListResponse,
    BotStateResponse,
)
from src.api.schemas.common import SuccessResponse, APIResponse
from src.api.services.bot_service import BotService
from src.bot_manager import MultiBotManager

router = APIRouter(prefix="/bots", tags=["Bots"])


def get_bot_service(
    manager: MultiBotManager = Depends(get_bot_manager),
) -> BotService:
    """BotService 인스턴스 반환"""
    return BotService(manager)


# =============================================================================
# GET - 조회
# =============================================================================


@router.get("", response_model=APIResponse[BotListResponse])
async def list_bots(
    service: BotService = Depends(get_bot_service),
) -> dict[str, Any]:
    """봇 목록 조회

    등록된 모든 봇의 목록을 반환합니다.
    """
    result = service.list_bots()
    return {
        "success": True,
        "data": result,
    }


@router.get("/{bot_name}", response_model=APIResponse[BotStateResponse])
async def get_bot(
    bot_name: str,
    service: BotService = Depends(get_bot_service),
) -> dict[str, Any]:
    """봇 상세 조회

    특정 봇의 상세 정보 및 현재 상태를 반환합니다.

    Args:
        bot_name: 봇 이름
    """
    try:
        result = service.get_bot_state(bot_name)
        return {
            "success": True,
            "data": result,
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# =============================================================================
# POST - 생성
# =============================================================================


@router.post("", response_model=APIResponse[BotResponse], status_code=status.HTTP_201_CREATED)
async def create_bot(
    request: BotCreateRequest,
    service: BotService = Depends(get_bot_service),
) -> dict[str, Any]:
    """봇 생성

    새 봇을 생성합니다. 생성된 봇은 비활성 상태입니다.

    Args:
        request: 봇 생성 요청
    """
    try:
        result = service.create_bot(request)
        return {
            "success": True,
            "data": result,
            "message": f"Bot '{request.bot_name}' created successfully",
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


# =============================================================================
# PUT - 수정
# =============================================================================


@router.put("/{bot_name}", response_model=APIResponse[BotResponse])
async def update_bot(
    bot_name: str,
    request: BotUpdateRequest,
    service: BotService = Depends(get_bot_service),
) -> dict[str, Any]:
    """봇 설정 수정

    특정 봇의 설정을 수정합니다.
    실행 중인 봇의 설정은 일부만 변경 가능합니다.

    Args:
        bot_name: 봇 이름
        request: 수정 요청
    """
    try:
        result = service.update_bot(bot_name, request)
        return {
            "success": True,
            "data": result,
            "message": f"Bot '{bot_name}' updated successfully",
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# =============================================================================
# DELETE - 삭제
# =============================================================================


@router.delete("/{bot_name}", response_model=SuccessResponse)
async def delete_bot(
    bot_name: str,
    service: BotService = Depends(get_bot_service),
) -> SuccessResponse:
    """봇 삭제

    특정 봇을 삭제합니다.
    실행 중인 봇은 먼저 정지해야 합니다.

    Args:
        bot_name: 봇 이름
    """
    try:
        service.delete_bot(bot_name)
        return SuccessResponse(message=f"Bot '{bot_name}' deleted successfully")
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg,
            )
        elif "running" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error_msg,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg,
            )


# =============================================================================
# POST - 제어
# =============================================================================


@router.post("/{bot_name}/start", response_model=SuccessResponse)
async def start_bot(
    bot_name: str,
    service: BotService = Depends(get_bot_service),
) -> SuccessResponse:
    """봇 시작

    특정 봇을 시작합니다.

    Args:
        bot_name: 봇 이름
    """
    try:
        await service.start_bot(bot_name)
        return SuccessResponse(message=f"Bot '{bot_name}' started")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("/{bot_name}/stop", response_model=SuccessResponse)
async def stop_bot(
    bot_name: str,
    service: BotService = Depends(get_bot_service),
) -> SuccessResponse:
    """봇 정지

    특정 봇을 정지합니다.

    Args:
        bot_name: 봇 이름
    """
    try:
        await service.stop_bot(bot_name)
        return SuccessResponse(message=f"Bot '{bot_name}' stopped")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("/{bot_name}/pause", response_model=SuccessResponse)
async def pause_bot(
    bot_name: str,
    service: BotService = Depends(get_bot_service),
) -> SuccessResponse:
    """봇 일시정지

    특정 봇을 일시정지합니다.
    새 포지션 진입이 중지되지만, 기존 포지션은 계속 관리됩니다.

    Args:
        bot_name: 봇 이름
    """
    try:
        service.pause_bot(bot_name)
        return SuccessResponse(message=f"Bot '{bot_name}' paused")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("/{bot_name}/resume", response_model=SuccessResponse)
async def resume_bot(
    bot_name: str,
    service: BotService = Depends(get_bot_service),
) -> SuccessResponse:
    """봇 재개

    일시정지된 봇을 재개합니다.

    Args:
        bot_name: 봇 이름
    """
    try:
        service.resume_bot(bot_name)
        return SuccessResponse(message=f"Bot '{bot_name}' resumed")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("/{bot_name}/emergency-close", response_model=SuccessResponse)
async def emergency_close(
    bot_name: str,
    service: BotService = Depends(get_bot_service),
) -> SuccessResponse:
    """긴급 청산

    특정 봇의 포지션을 긴급 청산하고 봇을 일시정지합니다.

    Args:
        bot_name: 봇 이름
    """
    try:
        service.emergency_close(bot_name)
        return SuccessResponse(
            message=f"Emergency close requested for bot '{bot_name}'"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# =============================================================================
# POST - 전체 제어
# =============================================================================


@router.post("/start-all", response_model=APIResponse[dict[str, Any]])
async def start_all_bots(
    service: BotService = Depends(get_bot_service),
) -> dict[str, Any]:
    """전체 봇 시작

    등록된 모든 봇을 시작합니다.
    """
    started = await service.start_all()
    return {
        "success": True,
        "data": {"started": started},
        "message": f"{started} bots started",
    }


@router.post("/stop-all", response_model=APIResponse[dict[str, Any]])
async def stop_all_bots(
    service: BotService = Depends(get_bot_service),
) -> dict[str, Any]:
    """전체 봇 정지

    실행 중인 모든 봇을 정지합니다.
    """
    stopped = await service.stop_all()
    return {
        "success": True,
        "data": {"stopped": stopped},
        "message": f"{stopped} bots stopped",
    }
