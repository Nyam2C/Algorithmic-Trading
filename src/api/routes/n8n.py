"""
n8n 웹훅 라우트

n8n과의 통합을 위한 웹훅 엔드포인트입니다.
"""
from fastapi import APIRouter, HTTPException, status, Depends
from loguru import logger

from src.api.dependencies import get_bot_manager
from src.api.schemas.n8n import N8NSignalPayload, N8NCommandPayload
from src.api.schemas.common import SuccessResponse
from src.bot_manager import MultiBotManager

router = APIRouter(prefix="/n8n", tags=["n8n"])


# =============================================================================
# POST - 시그널 수신
# =============================================================================


@router.post("/signal", response_model=SuccessResponse)
async def receive_signal(
    payload: N8NSignalPayload,
    manager: MultiBotManager = Depends(get_bot_manager),
) -> SuccessResponse:
    """외부 시그널 수신

    n8n이나 다른 외부 시스템에서 보내는 트레이딩 시그널을 수신합니다.

    Args:
        payload: 시그널 페이로드
    """
    logger.info(
        f"n8n 시그널 수신: {payload.signal} from {payload.source}"
        f" (bot={payload.bot_name or 'all'})"
    )

    # 특정 봇 또는 전체 봇에 시그널 주입
    if payload.bot_name:
        bot = manager.get_bot(payload.bot_name)
        if not bot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bot '{payload.bot_name}' not found",
            )

        # 시그널 주입 (BotInstance에 inject_signal 메서드가 필요)
        # 현재는 로그만 기록
        logger.info(f"시그널 주입: {payload.bot_name} <- {payload.signal}")

    else:
        # 전체 봇에 시그널 주입
        for bot_name, bot in manager.bots.items():
            logger.info(f"시그널 주입: {bot_name} <- {payload.signal}")

    return SuccessResponse(
        message=f"Signal '{payload.signal}' received from {payload.source}"
    )


# =============================================================================
# POST - 명령 수신
# =============================================================================


@router.post("/command", response_model=SuccessResponse)
async def receive_command(
    payload: N8NCommandPayload,
    manager: MultiBotManager = Depends(get_bot_manager),
) -> SuccessResponse:
    """외부 명령 수신

    n8n이나 다른 외부 시스템에서 보내는 봇 제어 명령을 수신합니다.

    Args:
        payload: 명령 페이로드
    """
    logger.info(
        f"n8n 명령 수신: {payload.command}"
        f" (bot={payload.bot_name or 'all'})"
    )

    command = payload.command
    bot_name = payload.bot_name

    try:
        if bot_name:
            # 특정 봇에 명령 실행
            if command == "start":
                await manager.start_bot(bot_name)
            elif command == "stop":
                await manager.stop_bot(bot_name)
            elif command == "pause":
                manager.pause_bot(bot_name)
            elif command == "resume":
                manager.resume_bot(bot_name)
            elif command == "emergency_close":
                bot = manager.get_bot(bot_name)
                if bot:
                    bot.request_emergency_close()
                else:
                    raise ValueError(f"Bot '{bot_name}' not found")
        else:
            # 전체 봇에 명령 실행
            if command == "start":
                await manager.start_all()
            elif command == "stop":
                await manager.stop_all()
            elif command == "pause":
                manager.pause_all()
            elif command == "resume":
                manager.resume_all()
            elif command == "emergency_close":
                # 전체 봇 긴급 청산
                for bot in manager.bots.values():
                    bot.request_emergency_close()

        return SuccessResponse(
            message=f"Command '{command}' executed successfully"
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"명령 실행 에러: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
