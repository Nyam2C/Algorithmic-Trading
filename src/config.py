"""Configuration management for High-Win Survival System."""
import os

from dotenv import load_dotenv
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

# Load environment variables
load_dotenv()


class TradingConfig(BaseModel):
    """Trading configuration with validation."""

    # Bot Info
    bot_name: str = Field(default="trading-bot")

    # Binance Configuration
    binance_testnet: bool = Field(default=True)
    binance_api_key: str
    binance_secret_key: str

    # Phase 7.1: 메인넷 안전장치
    # 실거래 활성화 시 명시적 확인 문자열 필요
    mainnet_confirmation: str = Field(default="")

    # Redis Configuration
    redis_url: str | None = Field(default=None)
    redis_password: str | None = Field(default=None)
    redis_db: int = Field(default=0, ge=0, le=15)
    enable_redis_state: bool = Field(default=True)

    # Trading Parameters
    symbol: str = Field(default="BTCUSDT")
    leverage: int = Field(default=15, ge=1, le=50)
    position_size_pct: float = Field(default=0.05, gt=0, le=1)
    take_profit_pct: float = Field(default=0.004, gt=0)
    stop_loss_pct: float = Field(default=0.004, gt=0)
    time_cut_minutes: int = Field(default=120, gt=0)

    # Phase 5.1: 실제 잔고 기반 포지션 사이징
    # True면 실제 잔고 사용, False면 1000 USDT 기본값
    use_real_balance: bool = Field(default=False)

    # Phase 6.1: ATR 기반 동적 TP/SL
    use_atr_tp_sl: bool = Field(default=False)
    atr_tp_multiplier: float = Field(default=2.0, gt=0)
    atr_sl_multiplier: float = Field(default=1.0, gt=0)

    # APEX-V: Split TP
    use_split_tp: bool = Field(default=False)
    split_tp_ratios: list[float] = Field(default=[0.5, 0.3, 0.2])
    split_tp_atr_multipliers: list[float] = Field(default=[1.0, 1.5, 2.5])

    # APEX-V: ADX regime
    use_adx_regime: bool = Field(default=False)

    # Slippage protection
    max_slippage_pct: float = Field(default=0.005)  # 0.5% default
    close_on_excessive_slippage: bool = Field(default=False)

    # Phase 6.2: 마켓 레짐 필터링
    use_regime_filter: bool = Field(default=False)
    allow_weak_trend: bool = Field(default=True)

    # Phase 5 통합: 다중 타임프레임 필터
    use_mtf_filter: bool = Field(default=False)

    # Phase 5 통합: 앙상블 시그널
    use_ensemble: bool = Field(default=False)

    # Phase 5 통합: 수동 승인
    manual_approval_enabled: bool = Field(default=False)
    manual_approval_trades: int = Field(default=5, ge=1)
    approval_timeout: int = Field(default=60, ge=1)

    # AI Configuration
    gemini_api_key: str
    gemini_model: str = Field(default="gemini-2.5-flash")
    gemini_temperature: float = Field(default=0.1, ge=0, le=2)

    # Discord Configuration
    discord_webhook_url: str
    discord_bot_token: str | None = None

    # Database Configuration
    database_url: str | None = None

    # Trading Loop
    loop_interval_seconds: int = Field(default=3600, gt=0)  # 1 hour

    # Logging Configuration
    enable_json_logging: bool = Field(default=True)
    log_level: str = Field(default="INFO")

    # API Configuration
    api_host: str = Field(default="0.0.0.0")  # noqa: S104
    api_port: int = Field(default=8000, ge=1, le=65535)
    api_debug: bool = Field(default=False)

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """Validate symbol format."""
        # 먼저 대문자로 변환
        v = v.upper()
        # 그 다음 USDT로 끝나는지 확인
        if not v.endswith("USDT"):
            raise ValueError("Symbol must end with USDT")
        return v

    @field_validator("position_size_pct")
    @classmethod
    def validate_position_size(cls, v: float) -> float:
        """Validate position size is reasonable."""
        max_position_pct = 0.1  # Max 10% of capital
        if v > max_position_pct:
            logger.warning(f"Position size {v*100}% is high, recommended: <=10%")
        return v

    @field_validator("binance_secret_key")
    @classmethod
    def validate_binance_keys(cls, v: str, info: ValidationInfo) -> str:
        """메인넷에서 빈 API 키 차단.

        테스트넷에서는 경고만 출력하고, 메인넷에서는 ValueError 발생.
        """
        is_testnet = info.data.get("binance_testnet", True)
        api_key = info.data.get("binance_api_key", "")

        if not api_key or not v:
            if not is_testnet:
                raise ValueError(
                    "Binance API key and secret key are required for mainnet. "
                    "Set BINANCE_API_KEY and BINANCE_SECRET_KEY environment variables."
                )
            if not api_key:
                logger.warning("BINANCE_API_KEY is empty (testnet mode)")
            if not v:
                logger.warning("BINANCE_SECRET_KEY is empty (testnet mode)")
        return v

    def validate_mainnet_switch(self) -> bool:
        """Phase 7.1: 메인넷 전환 시 안전 검증.

        실거래(메인넷) 활성화 시 명시적 확인 문자열을 요구합니다.
        이는 실수로 실거래를 활성화하는 것을 방지합니다.

        Returns:
            True if validation passes

        Raises:
            ValueError: If mainnet is enabled without proper confirmation
        """
        required_confirmation = "I_UNDERSTAND_THIS_IS_REAL_MONEY"

        if not self.binance_testnet:
            if self.mainnet_confirmation != required_confirmation:
                raise ValueError(
                    f"메인넷(실거래) 전환을 위해 MAINNET_CONFIRMATION 환경변수를 "
                    f"'{required_confirmation}'으로 설정하세요.\n"
                    f"주의: 실거래 모드에서는 실제 자금이 사용됩니다!"
                )
            logger.critical(
                "⚠️ 실거래 모드 활성화 - 실제 자금이 사용됩니다! ⚠️"
            )
        return True

    model_config = ConfigDict(validate_assignment=True)


def load_config() -> TradingConfig:
    """Load configuration from environment variables."""
    try:
        config = TradingConfig(
            binance_testnet=os.getenv("BINANCE_TESTNET", "true").lower() == "true",
            binance_api_key=os.getenv("BINANCE_API_KEY", ""),
            binance_secret_key=os.getenv("BINANCE_SECRET_KEY", ""),
            mainnet_confirmation=os.getenv("MAINNET_CONFIRMATION", ""),
            use_real_balance=os.getenv("USE_REAL_BALANCE", "false").lower() == "true",
            # Phase 6.1: ATR 기반 동적 TP/SL
            use_atr_tp_sl=os.getenv("USE_ATR_TP_SL", "false").lower() == "true",
            atr_tp_multiplier=float(os.getenv("ATR_TP_MULTIPLIER", "2.0")),
            atr_sl_multiplier=float(os.getenv("ATR_SL_MULTIPLIER", "1.0")),
            # Phase 6.2: 마켓 레짐 필터링
            use_regime_filter=os.getenv("USE_REGIME_FILTER", "false").lower() == "true",
            allow_weak_trend=os.getenv("ALLOW_WEAK_TREND", "true").lower() == "true",
            # Phase 5 통합: 다중 타임프레임 필터
            use_mtf_filter=os.getenv("USE_MTF_FILTER", "false").lower() == "true",
            # Phase 5 통합: 앙상블 시그널
            use_ensemble=os.getenv("USE_ENSEMBLE", "false").lower() == "true",
            # Phase 5 통합: 수동 승인
            manual_approval_enabled=(
                os.getenv("MANUAL_APPROVAL_ENABLED", "false").lower()
                == "true"
            ),
            manual_approval_trades=int(os.getenv("MANUAL_APPROVAL_TRADES", "5")),
            approval_timeout=int(os.getenv("APPROVAL_TIMEOUT", "60")),
            gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            gemini_temperature=float(os.getenv("GEMINI_TEMPERATURE", "0.1")),
            discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL", ""),
            database_url=os.getenv("DATABASE_URL"),
            discord_bot_token=os.getenv("DISCORD_BOT_TOKEN"),
            loop_interval_seconds=int(os.getenv("LOOP_INTERVAL_SECONDS", "3600")),
            # Redis Configuration
            redis_url=os.getenv("REDIS_URL"),
            redis_password=os.getenv("REDIS_PASSWORD"),
            redis_db=int(os.getenv("REDIS_DB", "0")),
            enable_redis_state=(
                os.getenv("ENABLE_REDIS_STATE", "true").lower() == "true"
            ),
            # Logging Configuration
            enable_json_logging=(
                os.getenv("ENABLE_JSON_LOGGING", "true").lower() == "true"
            ),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            # API Configuration
            api_host=os.getenv("API_HOST", "0.0.0.0"),  # noqa: S104
            api_port=int(os.getenv("API_PORT", "8000")),
            api_debug=os.getenv("API_DEBUG", "false").lower() == "true",
        )

        # Phase 7.1: 메인넷 안전 검증
        config.validate_mainnet_switch()

        logger.info("Configuration loaded successfully")
        logger.info("Mode: MultiBotManager (YAML config)")
        logger.info(f"Testnet: {config.binance_testnet}")

        return config

    except Exception as e:
        logger.error(f"Configuration load failed: {e}")
        raise


# Singleton instance
_config: TradingConfig | None = None


def get_config() -> TradingConfig:
    """Get singleton configuration instance."""
    global _config  # noqa: PLW0603
    if _config is None:
        _config = load_config()
    return _config
