"""
n8n 웹훅 스키마

n8n과의 통합을 위한 페이로드 모델을 정의합니다.
"""
from datetime import datetime
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


class N8NSignalPayload(BaseModel):
    """n8n 시그널 페이로드

    외부 시스템에서 보내는 트레이딩 시그널입니다.

    Attributes:
        bot_name: 대상 봇 이름 (선택, 없으면 전체 봇에 적용)
        signal: 시그널 (LONG, SHORT, WAIT, CLOSE)
        source: 시그널 소스 (예: tradingview, custom)
        confidence: 신뢰도 (0-1)
        metadata: 추가 메타데이터 (선택)
    """

    bot_name: Optional[str] = Field(default=None, description="대상 봇 이름")
    signal: Literal["LONG", "SHORT", "WAIT", "CLOSE"] = Field(
        ..., description="시그널"
    )
    source: str = Field(default="n8n", description="시그널 소스")
    confidence: float = Field(default=1.0, ge=0, le=1, description="신뢰도")
    metadata: Optional[dict[str, Any]] = Field(
        default=None, description="추가 메타데이터"
    )


class N8NCommandPayload(BaseModel):
    """n8n 명령 페이로드

    외부 시스템에서 보내는 봇 제어 명령입니다.

    Attributes:
        bot_name: 대상 봇 이름 (선택, 없으면 전체 봇에 적용)
        command: 명령 (start, stop, pause, resume, emergency_close)
        parameters: 명령 파라미터 (선택)
    """

    bot_name: Optional[str] = Field(default=None, description="대상 봇 이름")
    command: Literal[
        "start", "stop", "pause", "resume", "emergency_close"
    ] = Field(..., description="명령")
    parameters: Optional[dict[str, Any]] = Field(
        default=None, description="명령 파라미터"
    )


class N8NCallbackPayload(BaseModel):
    """n8n 콜백 페이로드

    n8n으로 보내는 이벤트 콜백입니다.

    Attributes:
        event_type: 이벤트 타입 (signal, trade, error, status)
        bot_name: 봇 이름
        timestamp: 이벤트 발생 시간
        data: 이벤트 데이터
    """

    event_type: Literal["signal", "trade", "error", "status"] = Field(
        ..., description="이벤트 타입"
    )
    bot_name: str = Field(..., description="봇 이름")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="이벤트 발생 시간"
    )
    data: dict[str, Any] = Field(..., description="이벤트 데이터")
