"""
봇 API 스키마

봇 CRUD API의 요청/응답 모델을 정의합니다.
"""
from datetime import datetime
from typing import Any, Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator


# 허용된 거래 심볼 화이트리스트
ALLOWED_SYMBOLS = frozenset({
    # 메이저 코인
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "SOLUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "DOTUSDT", "MATICUSDT",
    # 추가 인기 코인
    "LINKUSDT", "ATOMUSDT", "LTCUSDT", "UNIUSDT", "NEARUSDT",
    "AAVEUSDT", "APTUSDT", "ARBUSDT", "OPUSDT", "SEIUSDT",
})


class BotCreateRequest(BaseModel):
    """봇 생성 요청

    Attributes:
        bot_name: 봇 이름 (고유)
        symbol: 거래 심볼 (예: BTCUSDT)
        risk_level: 위험도 (low, medium, high)
        leverage: 레버리지 (선택, 명시하지 않으면 risk_level 기본값)
        position_size_pct: 포지션 크기 비율 (선택)
        take_profit_pct: 익절 비율 (선택)
        stop_loss_pct: 손절 비율 (선택)
        time_cut_minutes: 타임컷 분 (선택)
        rsi_oversold: RSI 과매도 기준 (선택)
        rsi_overbought: RSI 과매수 기준 (선택)
        volume_threshold: 거래량 임계값 (선택)
        is_testnet: 테스트넷 사용 여부 (기본값: True)
        description: 봇 설명 (선택)
    """

    bot_name: str = Field(..., min_length=1, max_length=50, description="봇 이름")
    symbol: str = Field(default="BTCUSDT", description="거래 심볼")

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """거래 심볼 화이트리스트 검증"""
        v = v.upper()
        if v not in ALLOWED_SYMBOLS:
            raise ValueError(
                f"허용되지 않은 심볼: {v}. "
                f"허용 목록: {', '.join(sorted(ALLOWED_SYMBOLS))}"
            )
        return v
    risk_level: str = Field(default="medium", description="위험도 (low, medium, high)")
    leverage: Optional[int] = Field(default=None, ge=1, le=125, description="레버리지")
    position_size_pct: Optional[float] = Field(
        default=None, gt=0, le=1, description="포지션 크기 비율"
    )
    take_profit_pct: Optional[float] = Field(
        default=None, gt=0, description="익절 비율"
    )
    stop_loss_pct: Optional[float] = Field(default=None, gt=0, description="손절 비율")
    time_cut_minutes: Optional[int] = Field(
        default=None, gt=0, description="타임컷 분"
    )
    rsi_oversold: Optional[float] = Field(
        default=None, ge=0, le=100, description="RSI 과매도 기준"
    )
    rsi_overbought: Optional[float] = Field(
        default=None, ge=0, le=100, description="RSI 과매수 기준"
    )
    volume_threshold: Optional[float] = Field(
        default=None, ge=0, description="거래량 임계값"
    )
    is_testnet: bool = Field(default=True, description="테스트넷 사용 여부")
    description: Optional[str] = Field(default=None, description="봇 설명")


class BotUpdateRequest(BaseModel):
    """봇 설정 수정 요청

    모든 필드는 선택이며, 지정된 필드만 업데이트됩니다.
    """

    risk_level: Optional[str] = Field(default=None, description="위험도")
    leverage: Optional[int] = Field(default=None, ge=1, le=125, description="레버리지")
    position_size_pct: Optional[float] = Field(
        default=None, gt=0, le=1, description="포지션 크기 비율"
    )
    take_profit_pct: Optional[float] = Field(
        default=None, gt=0, description="익절 비율"
    )
    stop_loss_pct: Optional[float] = Field(default=None, gt=0, description="손절 비율")
    time_cut_minutes: Optional[int] = Field(
        default=None, gt=0, description="타임컷 분"
    )
    rsi_oversold: Optional[float] = Field(
        default=None, ge=0, le=100, description="RSI 과매도 기준"
    )
    rsi_overbought: Optional[float] = Field(
        default=None, ge=0, le=100, description="RSI 과매수 기준"
    )
    volume_threshold: Optional[float] = Field(
        default=None, ge=0, description="거래량 임계값"
    )
    is_testnet: Optional[bool] = Field(default=None, description="테스트넷 사용 여부")
    is_active: Optional[bool] = Field(default=None, description="봇 활성화 여부")
    description: Optional[str] = Field(default=None, description="봇 설명")


class BotResponse(BaseModel):
    """봇 정보 응답

    봇의 설정 및 현재 상태를 포함합니다.
    """

    bot_id: UUID = Field(..., description="봇 고유 ID")
    bot_name: str = Field(..., description="봇 이름")
    symbol: str = Field(..., description="거래 심볼")
    risk_level: str = Field(..., description="위험도")
    leverage: int = Field(..., description="적용 레버리지")
    position_size_pct: float = Field(..., description="적용 포지션 크기 비율")
    take_profit_pct: float = Field(..., description="적용 익절 비율")
    stop_loss_pct: float = Field(..., description="적용 손절 비율")
    time_cut_minutes: int = Field(..., description="타임컷 분")
    is_testnet: bool = Field(..., description="테스트넷 사용 여부")
    is_active: bool = Field(..., description="봇 활성화 여부")
    is_running: bool = Field(default=False, description="봇 실행 중 여부")
    is_paused: bool = Field(default=False, description="봇 일시정지 여부")
    description: Optional[str] = Field(default=None, description="봇 설명")


class BotStateResponse(BaseModel):
    """봇 상태 응답

    봇의 현재 실행 상태 및 포지션 정보를 포함합니다.
    """

    bot_id: str = Field(..., description="봇 고유 ID")
    bot_name: str = Field(..., description="봇 이름")
    symbol: str = Field(..., description="거래 심볼")
    risk_level: str = Field(..., description="위험도")
    is_running: bool = Field(..., description="봇 실행 중 여부")
    is_paused: bool = Field(..., description="봇 일시정지 여부")
    uptime_start: Optional[datetime] = Field(default=None, description="시작 시간")
    loop_count: int = Field(default=0, description="루프 횟수")
    current_price: float = Field(default=0.0, description="현재 가격")
    last_signal: str = Field(default="WAIT", description="마지막 시그널")
    last_signal_time: Optional[datetime] = Field(
        default=None, description="마지막 시그널 시간"
    )
    position: Optional[dict[str, Any]] = Field(default=None, description="현재 포지션")
    leverage: int = Field(..., description="적용 레버리지")


class BotListResponse(BaseModel):
    """봇 목록 응답"""

    total_bots: int = Field(..., description="전체 봇 수")
    running_bots: int = Field(..., description="실행 중인 봇 수")
    paused_bots: int = Field(..., description="일시정지된 봇 수")
    bots: list[BotResponse] = Field(default_factory=list, description="봇 목록")
