"""API 스키마 모듈.

요청/응답 모델을 정의합니다.
"""

from src.api.schemas.bot import (
    BotCreateRequest,
    BotListResponse,
    BotResponse,
    BotStateResponse,
    BotUpdateRequest,
)
from src.api.schemas.common import (
    APIResponse,
    ErrorResponse,
    SuccessResponse,
)
from src.api.schemas.n8n import (
    N8NCallbackPayload,
    N8NCommandPayload,
    N8NSignalPayload,
)

__all__ = [
    "APIResponse",
    "BotCreateRequest",
    "BotListResponse",
    "BotResponse",
    "BotStateResponse",
    "BotUpdateRequest",
    "ErrorResponse",
    "N8NCallbackPayload",
    "N8NCommandPayload",
    "N8NSignalPayload",
    "SuccessResponse",
]
