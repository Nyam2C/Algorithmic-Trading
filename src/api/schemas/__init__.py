"""
API 스키마 모듈

요청/응답 모델을 정의합니다.
"""

from src.api.schemas.common import (
    APIResponse,
    ErrorResponse,
    SuccessResponse,
)
from src.api.schemas.bot import (
    BotCreateRequest,
    BotUpdateRequest,
    BotResponse,
    BotListResponse,
    BotStateResponse,
)
from src.api.schemas.n8n import (
    N8NSignalPayload,
    N8NCommandPayload,
    N8NCallbackPayload,
)

__all__ = [
    "APIResponse",
    "ErrorResponse",
    "SuccessResponse",
    "BotCreateRequest",
    "BotUpdateRequest",
    "BotResponse",
    "BotListResponse",
    "BotStateResponse",
    "N8NSignalPayload",
    "N8NCommandPayload",
    "N8NCallbackPayload",
]
