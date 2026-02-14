"""n8n 웹훅 스키마.

n8n과의 통합을 위한 페이로드 모델을 정의합니다.
"""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class N8NSignalPayload(BaseModel):
    """n8n 시그널 페이로드.

    외부 시스템에서 보내는 트레이딩 시그널입니다.

    Attributes:
        bot_name: 대상 봇 이름 (선택, 없으면 전체 봇에 적용)
        signal: 시그널 (LONG, SHORT, WAIT, CLOSE)
        source: 시그널 소스 (예: tradingview, custom)
        confidence: 신뢰도 (0-1)
        metadata: 추가 메타데이터 (선택)
    """

    bot_name: str | None = Field(default=None, description="대상 봇 이름")
    signal: Literal["LONG", "SHORT", "WAIT", "CLOSE"] = Field(
        ..., description="시그널"
    )
    source: str = Field(default="n8n", description="시그널 소스")
    confidence: float = Field(default=1.0, ge=0, le=1, description="신뢰도")
    metadata: dict[str, Any] | None = Field(
        default=None, description="추가 메타데이터"
    )


class N8NCallbackPayload(BaseModel):
    """n8n 콜백 페이로드.

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

class MarketContextPayload(BaseModel):
    """외부 시장 컨텍스트 데이터.

    n8n에서 수집한 Fear & Greed, 펀딩레이트 등 외부 데이터를 수신합니다.

    Attributes:
        fear_greed_index: Fear & Greed 지수 (0-100)
        funding_rate: 펀딩레이트
        whale_alerts: 고래 알림 목록
        custom_data: 사용자 정의 데이터
        source: 데이터 소스
        timestamp: 데이터 수집 시간
    """

    fear_greed_index: int | None = Field(default=None, ge=0, le=100)
    funding_rate: float | None = None
    whale_alerts: list[dict[str, Any]] | None = None
    custom_data: dict[str, Any] | None = None
    source: str = Field(default="n8n")
    timestamp: datetime | None = None
