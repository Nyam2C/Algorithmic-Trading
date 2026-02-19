"""멀티봇 설정 모델.

각 봇 인스턴스의 개별 설정을 관리하는 Pydantic 모델.
risk_level에 따른 기본값 제공 및 기존 TradingConfig와의 호환성 지원.
"""
from typing import Any
from uuid import UUID, uuid4

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# =============================================================================
# 위험도별 기본값 상수
# =============================================================================

RISK_LEVEL_DEFAULTS: dict[str, dict[str, Any]] = {
    "low": {
        "leverage": 3,
        "position_size_pct": 0.03,
        "take_profit_pct": 0.006,
        "stop_loss_pct": 0.003,
    },
    "medium": {
        "leverage": 5,
        "position_size_pct": 0.05,
        "take_profit_pct": 0.008,
        "stop_loss_pct": 0.004,
    },
    "high": {
        "leverage": 10,
        "position_size_pct": 0.08,
        "take_profit_pct": 0.012,
        "stop_loss_pct": 0.004,
    },
}


class BotConfig(BaseModel):
    """멀티봇 설정 모델.

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
        >>> config = BotConfig(
        ...     bot_name="btc-bot", symbol="BTCUSDT",
        ...     risk_level="medium",
        ... )
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
    leverage: int | None = Field(default=None, ge=1, le=50)
    position_size_pct: float | None = Field(default=None, gt=0, le=1)
    take_profit_pct: float | None = Field(default=None, gt=0)
    stop_loss_pct: float | None = Field(default=None, gt=0)
    time_cut_minutes: int = Field(default=120, gt=0)

    # Phase 5.1: 실제 잔고 기반 포지션 사이징
    use_real_balance: bool = Field(default=False)

    # Phase 5.2: 일일 손실 한도
    max_daily_loss_pct: float = Field(default=0.05, gt=0, le=1)  # 5%

    # Phase 5.3: 연속 손실 관리
    max_consecutive_losses: int = Field(default=3, ge=1)
    cooldown_minutes: int = Field(default=30, ge=1)

    # Phase 5: 드로다운 관리
    max_drawdown_pct: float = Field(default=0.10, gt=0, le=1)  # 10%

    # Phase 7: 단일 거래 최대 손실률
    max_loss_per_trade_pct: float = Field(default=0.02, gt=0, le=1)  # 2%

    # Phase 9: 추정 수수료율 (PnL 계산 시 차감)
    estimated_fee_rate: float = Field(default=0.0008, ge=0, le=0.01)  # 0.08%

    # 시그널 쿨다운 & 중복 제거
    signal_cooldown_seconds: int = Field(default=300, ge=0)  # 5분
    post_loss_cooldown_seconds: int = Field(default=600, ge=0)  # 10분
    alert_dedup_seconds: int = Field(default=300, ge=0)  # 5분

    # Phase 7: 리스크 한도 시 포지션 청산
    close_on_risk_halt: bool = Field(default=True)

    # Phase 6.1: ATR 기반 동적 TP/SL
    use_atr_tp_sl: bool = Field(default=True)  # ATR 기반 TP/SL 사용 (기본 활성화)
    atr_tp_multiplier: float = Field(default=2.0, gt=0)  # TP = entry ± ATR x multiplier
    atr_sl_multiplier: float = Field(default=1.0, gt=0)  # SL = entry ± ATR x multiplier

    # APEX-V Phase A: 분할 TP
    use_split_tp: bool = Field(default=False)
    split_tp_ratios: list[float] = Field(default=[0.5, 0.3, 0.2])
    split_tp_atr_multipliers: list[float] = Field(default=[1.0, 1.5, 2.5])

    # APEX-V Phase A: ADX 기반 레짐 감지
    use_adx_regime: bool = Field(default=False)

    # APEX-V Phase B: 4채널 시그널 생성기
    use_tsmom_channel: bool = Field(default=False)
    use_funding_basis_channel: bool = Field(default=False)
    use_leverage_topology_channel: bool = Field(default=False)
    use_smart_money_channel: bool = Field(default=False)

    # APEX-V Fast Layer: WebSocket 채널
    use_ofi_channel: bool = Field(default=False)
    use_whale_flow_channel: bool = Field(default=False)
    use_websocket: bool = Field(default=False)

    # APEX-V Phase C: Confluence Engine
    use_confluence_engine: bool = Field(default=False)

    # APEX-V: Graceful Degradation Controller
    use_graceful_degradation: bool = Field(default=False)

    # APEX-V Phase D: Kelly + Risk Enhancement
    use_kelly_sizing: bool = Field(default=False)
    kelly_fraction: float = Field(default=0.25, gt=0, le=1.0)
    kelly_max_size_pct: float = Field(default=0.02, gt=0, le=0.1)
    kelly_min_size_pct: float = Field(default=0.003, gt=0)
    use_execution_feedback: bool = Field(default=False)
    use_drawdown_sizing: bool = Field(default=False)

    # Phase 6.2: 마켓 레짐 필터링
    use_regime_filter: bool = Field(default=False)  # True면 횡보장 진입 회피
    allow_weak_trend: bool = Field(default=True)  # 약한 추세에서 거래 허용

    # Phase 5 통합: 다중 타임프레임 필터
    use_mtf_filter: bool = Field(default=False)  # True면 상위 TF 추세 필터 적용

    # Phase 5 통합: 앙상블 시그널
    use_ensemble: bool = Field(default=False)  # True면 앙상블 시그널 사용

    # Phase 5 통합: 수동 승인
    manual_approval_enabled: bool = Field(default=False)
    manual_approval_trades: int = Field(default=5, ge=1)
    approval_timeout: int = Field(default=60, ge=1)

    # 신호 파라미터
    rsi_oversold: float = Field(default=30.0, ge=0, le=100)
    rsi_overbought: float = Field(default=70.0, ge=0, le=100)
    volume_threshold: float = Field(default=0.5, ge=0)  # 테스트넷 호환 (프로덕션: 1.2)

    # 신호 전략
    signal_strategy: str = Field(default="trend_following")

    # API 키 참조 (Secrets Manager 또는 환경변수 참조용)
    binance_api_key_ref: str | None = None
    binance_secret_key_ref: str | None = None

    # 설정
    is_testnet: bool = Field(default=True)
    is_active: bool = Field(default=False)

    # 메타데이터
    description: str | None = None

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """심볼 검증 및 대문자 변환."""
        v = v.upper()
        if not v.endswith("USDT"):
            raise ValueError("Symbol must end with USDT")
        return v

    @field_validator("risk_level")
    @classmethod
    def validate_risk_level(cls, v: str) -> str:
        """위험도 검증."""
        valid_levels = ["low", "medium", "high"]
        if v not in valid_levels:
            raise ValueError(f"risk_level must be one of {valid_levels}")
        return v

    @field_validator("split_tp_ratios")
    @classmethod
    def validate_split_tp_ratios(cls, v: list[float]) -> list[float]:
        """분할 TP 비율 합이 1.0이어야 함."""
        if abs(sum(v) - 1.0) > 0.01:  # noqa: PLR2004
            raise ValueError(f"split_tp_ratios sum must be 1.0, got {sum(v)}")
        return v

    @field_validator("position_size_pct")
    @classmethod
    def warn_high_position_size(cls, v: float | None) -> float | None:
        """포지션 크기가 10% 초과 시 경고."""
        max_position_size = 0.1
        if v is not None and v > max_position_size:
            logger.warning(f"Position size {v*100}%가 높습니다. 권장: <=10%")
        return v

    @model_validator(mode="after")
    def check_risk_consistency(self) -> "BotConfig":
        """SL x leverage가 일일 손실 한도를 초과하면 거부."""
        sl = self.get_effective_stop_loss_pct()
        leverage = self.get_effective_leverage()
        single_trade_loss = sl * leverage
        if single_trade_loss > self.max_daily_loss_pct:
            raise ValueError(
                f"리스크 불일치: SL({sl:.2%}) x 레버리지({leverage}x) = "
                f"{single_trade_loss:.2%} > 일일한도({self.max_daily_loss_pct:.2%}). "
                f"SL 또는 레버리지를 줄이세요."
            )
        return self

    def get_effective_leverage(self) -> int:
        """실제 적용될 레버리지 반환.

        명시적으로 지정된 값이 있으면 사용, 없으면 risk_level 기본값 사용.

        Returns:
            적용될 레버리지 값
        """
        if self.leverage is not None:
            return self.leverage
        return RISK_LEVEL_DEFAULTS[self.risk_level]["leverage"]

    def get_effective_position_size_pct(self) -> float:
        """실제 적용될 포지션 크기 비율 반환.

        Returns:
            적용될 포지션 크기 비율
        """
        if self.position_size_pct is not None:
            return self.position_size_pct
        return RISK_LEVEL_DEFAULTS[self.risk_level]["position_size_pct"]

    def get_effective_take_profit_pct(self) -> float:
        """실제 적용될 익절 비율 반환.

        Returns:
            적용될 익절 비율
        """
        if self.take_profit_pct is not None:
            return self.take_profit_pct
        return RISK_LEVEL_DEFAULTS[self.risk_level]["take_profit_pct"]

    def get_effective_stop_loss_pct(self) -> float:
        """실제 적용될 손절 비율 반환.

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
        discord_bot_token: str | None = None,
        database_url: str | None = None,
        loop_interval_seconds: int = 300,
    ):  # -> TradingConfig
        """기존 TradingConfig 형식으로 변환.

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
        from src.config import TradingConfig  # noqa: PLC0415

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
            use_real_balance=self.use_real_balance,  # Phase 5.1
            use_atr_tp_sl=self.use_atr_tp_sl,  # Phase 6.1
            atr_tp_multiplier=self.atr_tp_multiplier,  # Phase 6.1
            atr_sl_multiplier=self.atr_sl_multiplier,  # Phase 6.1
            use_split_tp=self.use_split_tp,  # APEX-V
            split_tp_ratios=self.split_tp_ratios,  # APEX-V
            split_tp_atr_multipliers=self.split_tp_atr_multipliers,  # APEX-V
            use_adx_regime=self.use_adx_regime,  # APEX-V
            use_regime_filter=self.use_regime_filter,  # Phase 6.2
            allow_weak_trend=self.allow_weak_trend,  # Phase 6.2
            use_mtf_filter=self.use_mtf_filter,  # Phase 5 통합
            use_ensemble=self.use_ensemble,  # Phase 5 통합
            manual_approval_enabled=self.manual_approval_enabled,  # Phase 5 통합
            manual_approval_trades=self.manual_approval_trades,  # Phase 5 통합
            approval_timeout=self.approval_timeout,  # Phase 5 통합
            gemini_api_key=gemini_api_key,
            discord_webhook_url=discord_webhook_url,
            discord_bot_token=discord_bot_token,
            database_url=database_url,
            loop_interval_seconds=loop_interval_seconds,
        )

    @classmethod
    def from_db_row(cls, row: dict[str, Any]) -> "BotConfig":
        """데이터베이스 row에서 BotConfig 생성.

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
            use_real_balance=row.get("use_real_balance", False),  # Phase 5.1
            max_daily_loss_pct=row.get("max_daily_loss_pct", 0.05),  # Phase 5.2
            max_consecutive_losses=row.get("max_consecutive_losses", 3),  # Phase 5.3
            cooldown_minutes=row.get("cooldown_minutes", 30),  # Phase 5.3
            max_drawdown_pct=row.get("max_drawdown_pct", 0.10),  # Phase 5
            use_atr_tp_sl=row.get("use_atr_tp_sl", False),  # Phase 6.1
            atr_tp_multiplier=row.get("atr_tp_multiplier", 2.0),  # Phase 6.1
            atr_sl_multiplier=row.get("atr_sl_multiplier", 1.0),  # Phase 6.1
            rsi_oversold=row.get("rsi_oversold", 30.0),
            rsi_overbought=row.get("rsi_overbought", 70.0),
            volume_threshold=row.get("volume_threshold", 0.5),
            signal_strategy=row.get("signal_strategy", "trend_pullback"),
            binance_api_key_ref=row.get("binance_api_key_ref"),
            binance_secret_key_ref=row.get("binance_secret_key_ref"),
            is_testnet=row.get("is_testnet", True),
            is_active=row.get("is_active", False),
            description=row.get("description"),
        )

    def to_db_dict(self) -> dict[str, Any]:
        """데이터베이스 저장용 dict로 변환.

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
            "use_real_balance": self.use_real_balance,  # Phase 5.1
            "max_daily_loss_pct": self.max_daily_loss_pct,  # Phase 5.2
            "max_consecutive_losses": self.max_consecutive_losses,  # Phase 5.3
            "cooldown_minutes": self.cooldown_minutes,  # Phase 5.3
            "max_drawdown_pct": self.max_drawdown_pct,  # Phase 5
            "use_atr_tp_sl": self.use_atr_tp_sl,  # Phase 6.1
            "atr_tp_multiplier": self.atr_tp_multiplier,  # Phase 6.1
            "atr_sl_multiplier": self.atr_sl_multiplier,  # Phase 6.1
            "rsi_oversold": self.rsi_oversold,
            "rsi_overbought": self.rsi_overbought,
            "volume_threshold": self.volume_threshold,
            "signal_strategy": self.signal_strategy,
            "binance_api_key_ref": self.binance_api_key_ref,
            "binance_secret_key_ref": self.binance_secret_key_ref,
            "is_testnet": self.is_testnet,
            "is_active": self.is_active,
            "description": self.description,
        }

    model_config = ConfigDict(validate_assignment=True)
