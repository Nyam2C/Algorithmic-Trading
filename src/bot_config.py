"""
멀티봇 설정 모델

각 봇 인스턴스의 개별 설정을 관리하는 Pydantic 모델.
risk_level에 따른 기본값 제공 및 기존 TradingConfig와의 호환성 지원.
"""
from typing import Optional, Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, field_validator
from loguru import logger


# =============================================================================
# 위험도별 기본값 상수
# =============================================================================

RISK_LEVEL_DEFAULTS: dict[str, dict[str, Any]] = {
    "low": {
        "leverage": 10,
        "position_size_pct": 0.03,
        "take_profit_pct": 0.003,
        "stop_loss_pct": 0.003,
    },
    "medium": {
        "leverage": 15,
        "position_size_pct": 0.05,
        "take_profit_pct": 0.004,
        "stop_loss_pct": 0.004,
    },
    "high": {
        "leverage": 20,
        "position_size_pct": 0.08,
        "take_profit_pct": 0.006,
        "stop_loss_pct": 0.006,
    },
}


class BotConfig(BaseModel):
    """멀티봇 설정 모델

    각 봇 인스턴스의 개별 설정을 관리합니다.
    risk_level에 따라 기본값이 제공되며, 명시적으로 지정한 값이 우선합니다.

    Attributes:
        bot_id: 봇 고유 식별자 (UUID)
        bot_name: 봇 이름 (고유)
        symbol: 거래 심볼 (예: BTCUSDT)
        risk_level: 위험도 (low, medium, high)
        leverage: 레버리지 (1-125)
        position_size_pct: 포지션 크기 비율 (0-1)
        take_profit_pct: 익절 비율
        stop_loss_pct: 손절 비율
        time_cut_minutes: 타임컷 시간 (분)
        rsi_oversold: RSI 과매도 기준
        rsi_overbought: RSI 과매수 기준
        volume_threshold: 거래량 임계값
        is_testnet: 테스트넷 사용 여부
        is_active: 봇 활성화 여부
        description: 봇 설명

    Example:
        >>> config = BotConfig(bot_name="btc-bot", symbol="BTCUSDT", risk_level="medium")
        >>> config.get_effective_leverage()
        15
    """

    # 식별자
    bot_id: UUID = Field(default_factory=uuid4)
    bot_name: str = Field(..., min_length=1, max_length=50)

    # 거래 심볼
    symbol: str = Field(default="BTCUSDT")

    # 위험도 분류
    risk_level: str = Field(default="medium")

    # 트레이딩 파라미터 (None이면 risk_level 기본값 사용)
    leverage: Optional[int] = Field(default=None, ge=1, le=125)
    position_size_pct: Optional[float] = Field(default=None, gt=0, le=1)
    take_profit_pct: Optional[float] = Field(default=None, gt=0)
    stop_loss_pct: Optional[float] = Field(default=None, gt=0)
    time_cut_minutes: int = Field(default=120, gt=0)

    # 신호 파라미터
    rsi_oversold: float = Field(default=35.0, ge=0, le=100)
    rsi_overbought: float = Field(default=65.0, ge=0, le=100)
    volume_threshold: float = Field(default=1.2, ge=0)

    # API 키 참조 (Secrets Manager 또는 환경변수 참조용)
    binance_api_key_ref: Optional[str] = None
    binance_secret_key_ref: Optional[str] = None

    # 설정
    is_testnet: bool = Field(default=True)
    is_active: bool = Field(default=False)

    # 메타데이터
    description: Optional[str] = None

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """심볼 검증 및 대문자 변환"""
        v = v.upper()
        if not v.endswith("USDT"):
            raise ValueError("Symbol must end with USDT")
        return v

    @field_validator("risk_level")
    @classmethod
    def validate_risk_level(cls, v: str) -> str:
        """위험도 검증"""
        valid_levels = ["low", "medium", "high"]
        if v not in valid_levels:
            raise ValueError(f"risk_level must be one of {valid_levels}")
        return v

    @field_validator("position_size_pct")
    @classmethod
    def warn_high_position_size(cls, v: Optional[float]) -> Optional[float]:
        """포지션 크기가 10% 초과 시 경고"""
        if v is not None and v > 0.1:
            logger.warning(f"Position size {v*100}%가 높습니다. 권장: <=10%")
        return v

    def get_effective_leverage(self) -> int:
        """실제 적용될 레버리지 반환

        명시적으로 지정된 값이 있으면 사용, 없으면 risk_level 기본값 사용.

        Returns:
            적용될 레버리지 값
        """
        if self.leverage is not None:
            return self.leverage
        return RISK_LEVEL_DEFAULTS[self.risk_level]["leverage"]

    def get_effective_position_size_pct(self) -> float:
        """실제 적용될 포지션 크기 비율 반환

        Returns:
            적용될 포지션 크기 비율
        """
        if self.position_size_pct is not None:
            return self.position_size_pct
        return RISK_LEVEL_DEFAULTS[self.risk_level]["position_size_pct"]

    def get_effective_take_profit_pct(self) -> float:
        """실제 적용될 익절 비율 반환

        Returns:
            적용될 익절 비율
        """
        if self.take_profit_pct is not None:
            return self.take_profit_pct
        return RISK_LEVEL_DEFAULTS[self.risk_level]["take_profit_pct"]

    def get_effective_stop_loss_pct(self) -> float:
        """실제 적용될 손절 비율 반환

        Returns:
            적용될 손절 비율
        """
        if self.stop_loss_pct is not None:
            return self.stop_loss_pct
        return RISK_LEVEL_DEFAULTS[self.risk_level]["stop_loss_pct"]

    def to_trading_config(
        self,
        binance_api_key: str,
        binance_secret_key: str,
        gemini_api_key: str,
        discord_webhook_url: str,
        discord_bot_token: Optional[str] = None,
        database_url: Optional[str] = None,
        loop_interval_seconds: int = 300,
    ):  # -> TradingConfig
        """기존 TradingConfig 형식으로 변환

        기존 코드와의 호환성을 위해 BotConfig를 TradingConfig로 변환합니다.

        Args:
            binance_api_key: Binance API 키
            binance_secret_key: Binance Secret 키
            gemini_api_key: Gemini API 키
            discord_webhook_url: Discord 웹훅 URL
            discord_bot_token: Discord 봇 토큰 (선택)
            database_url: 데이터베이스 URL (선택)
            loop_interval_seconds: 루프 간격 (초)

        Returns:
            TradingConfig 인스턴스
        """
        from src.config import TradingConfig

        return TradingConfig(
            bot_name=self.bot_name,
            binance_testnet=self.is_testnet,
            binance_api_key=binance_api_key,
            binance_secret_key=binance_secret_key,
            symbol=self.symbol,
            leverage=self.get_effective_leverage(),
            position_size_pct=self.get_effective_position_size_pct(),
            take_profit_pct=self.get_effective_take_profit_pct(),
            stop_loss_pct=self.get_effective_stop_loss_pct(),
            time_cut_minutes=self.time_cut_minutes,
            gemini_api_key=gemini_api_key,
            discord_webhook_url=discord_webhook_url,
            discord_bot_token=discord_bot_token,
            database_url=database_url,
            loop_interval_seconds=loop_interval_seconds,
        )

    @classmethod
    def from_db_row(cls, row: dict[str, Any]) -> "BotConfig":
        """데이터베이스 row에서 BotConfig 생성

        Args:
            row: 데이터베이스 row (dict)

        Returns:
            BotConfig 인스턴스
        """
        return cls(
            bot_id=row.get("id") or uuid4(),
            bot_name=row["bot_name"],
            symbol=row.get("symbol", "BTCUSDT"),
            risk_level=row.get("risk_level", "medium"),
            leverage=row.get("leverage"),
            position_size_pct=row.get("position_size_pct"),
            take_profit_pct=row.get("take_profit_pct"),
            stop_loss_pct=row.get("stop_loss_pct"),
            time_cut_minutes=row.get("time_cut_minutes", 120),
            rsi_oversold=row.get("rsi_oversold", 35.0),
            rsi_overbought=row.get("rsi_overbought", 65.0),
            volume_threshold=row.get("volume_threshold", 1.2),
            binance_api_key_ref=row.get("binance_api_key_ref"),
            binance_secret_key_ref=row.get("binance_secret_key_ref"),
            is_testnet=row.get("is_testnet", True),
            is_active=row.get("is_active", False),
            description=row.get("description"),
        )

    def to_db_dict(self) -> dict[str, Any]:
        """데이터베이스 저장용 dict로 변환

        Returns:
            데이터베이스 저장용 dict
        """
        return {
            "id": self.bot_id,
            "bot_name": self.bot_name,
            "symbol": self.symbol,
            "risk_level": self.risk_level,
            "leverage": self.leverage,
            "position_size_pct": self.position_size_pct,
            "take_profit_pct": self.take_profit_pct,
            "stop_loss_pct": self.stop_loss_pct,
            "time_cut_minutes": self.time_cut_minutes,
            "rsi_oversold": self.rsi_oversold,
            "rsi_overbought": self.rsi_overbought,
            "volume_threshold": self.volume_threshold,
            "binance_api_key_ref": self.binance_api_key_ref,
            "binance_secret_key_ref": self.binance_secret_key_ref,
            "is_testnet": self.is_testnet,
            "is_active": self.is_active,
            "description": self.description,
        }

    class Config:
        """Pydantic 설정"""
        validate_assignment = True
