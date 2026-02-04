"""
Configuration management for High-Win Survival System
"""
import os
from typing import Optional
from pydantic import BaseModel, Field, validator
from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv()


class TradingConfig(BaseModel):
    """Trading configuration with validation"""

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
    redis_url: Optional[str] = Field(default=None)
    redis_password: Optional[str] = Field(default=None)
    redis_db: int = Field(default=0, ge=0, le=15)
    enable_redis_state: bool = Field(default=True)

    # Trading Parameters
    symbol: str = Field(default="BTCUSDT")
    leverage: int = Field(default=15, ge=1, le=125)
    position_size_pct: float = Field(default=0.05, gt=0, le=1)
    take_profit_pct: float = Field(default=0.004, gt=0)
    stop_loss_pct: float = Field(default=0.004, gt=0)
    time_cut_minutes: int = Field(default=120, gt=0)

    # Phase 5.1: 실제 잔고 기반 포지션 사이징
    use_real_balance: bool = Field(default=False)  # True면 실제 잔고 사용, False면 1000 USDT 기본값

    # Phase 6.1: ATR 기반 동적 TP/SL
    use_atr_tp_sl: bool = Field(default=False)
    atr_tp_multiplier: float = Field(default=2.0, gt=0)
    atr_sl_multiplier: float = Field(default=1.0, gt=0)

    # AI Configuration
    gemini_api_key: str
    gemini_model: str = Field(default="gemini-2.0-flash-exp")
    gemini_temperature: float = Field(default=0.1, ge=0, le=2)

    # Discord Configuration
    discord_webhook_url: str
    discord_bot_token: Optional[str] = None

    # Database Configuration
    database_url: Optional[str] = None

    # Trading Loop
    loop_interval_seconds: int = Field(default=300, gt=0)  # 5 minutes

    # Logging Configuration
    enable_json_logging: bool = Field(default=True)
    log_level: str = Field(default="INFO")

    # API Configuration
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000, ge=1, le=65535)
    api_debug: bool = Field(default=False)

    @validator("symbol")
    def validate_symbol(cls, v):
        """Validate symbol format"""
        # 먼저 대문자로 변환
        v = v.upper()
        # 그 다음 USDT로 끝나는지 확인
        if not v.endswith("USDT"):
            raise ValueError("Symbol must end with USDT")
        return v

    @validator("position_size_pct")
    def validate_position_size(cls, v):
        """Validate position size is reasonable"""
        if v > 0.1:  # Max 10% of capital
            logger.warning(f"Position size {v*100}% is high, recommended: <=10%")
        return v

    def validate_mainnet_switch(self) -> bool:
        """
        Phase 7.1: 메인넷 전환 시 안전 검증

        실거래(메인넷) 활성화 시 명시적 확인 문자열을 요구합니다.
        이는 실수로 실거래를 활성화하는 것을 방지합니다.

        Returns:
            True if validation passes

        Raises:
            ValueError: If mainnet is enabled without proper confirmation
        """
        REQUIRED_CONFIRMATION = "I_UNDERSTAND_THIS_IS_REAL_MONEY"

        if not self.binance_testnet:
            if self.mainnet_confirmation != REQUIRED_CONFIRMATION:
                raise ValueError(
                    f"메인넷(실거래) 전환을 위해 MAINNET_CONFIRMATION 환경변수를 "
                    f"'{REQUIRED_CONFIRMATION}'으로 설정하세요.\n"
                    f"주의: 실거래 모드에서는 실제 자금이 사용됩니다!"
                )
            logger.critical(
                "⚠️ 실거래 모드 활성화 - 실제 자금이 사용됩니다! ⚠️"
            )
        return True

    class Config:
        validate_assignment = True


def load_config() -> TradingConfig:
    """Load configuration from environment variables"""
    try:
        config = TradingConfig(
            bot_name=os.getenv("BOT_NAME", "trading-bot"),
            binance_testnet=os.getenv("BINANCE_TESTNET", "true").lower() == "true",
            binance_api_key=os.getenv("BINANCE_API_KEY", ""),
            binance_secret_key=os.getenv("BINANCE_SECRET_KEY", ""),
            mainnet_confirmation=os.getenv("MAINNET_CONFIRMATION", ""),
            symbol=os.getenv("SYMBOL", "BTCUSDT"),
            leverage=int(os.getenv("LEVERAGE", "15")),
            position_size_pct=float(os.getenv("POSITION_SIZE_PCT", "0.05")),
            take_profit_pct=float(os.getenv("TAKE_PROFIT_PCT", "0.004")),
            stop_loss_pct=float(os.getenv("STOP_LOSS_PCT", "0.004")),
            time_cut_minutes=int(os.getenv("TIME_CUT_MINUTES", "120")),
            use_real_balance=os.getenv("USE_REAL_BALANCE", "false").lower() == "true",
            gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp"),
            gemini_temperature=float(os.getenv("GEMINI_TEMPERATURE", "0.1")),
            discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL", ""),
            database_url=os.getenv("DATABASE_URL"),
            discord_bot_token=os.getenv("DISCORD_BOT_TOKEN"),
            loop_interval_seconds=int(os.getenv("LOOP_INTERVAL_SECONDS", "300")),
            # Redis Configuration
            redis_url=os.getenv("REDIS_URL"),
            redis_password=os.getenv("REDIS_PASSWORD"),
            redis_db=int(os.getenv("REDIS_DB", "0")),
            enable_redis_state=os.getenv("ENABLE_REDIS_STATE", "true").lower() == "true",
            # Logging Configuration
            enable_json_logging=os.getenv("ENABLE_JSON_LOGGING", "true").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            # API Configuration
            api_host=os.getenv("API_HOST", "0.0.0.0"),
            api_port=int(os.getenv("API_PORT", "8000")),
            api_debug=os.getenv("API_DEBUG", "false").lower() == "true",
        )

        # Phase 7.1: 메인넷 안전 검증
        config.validate_mainnet_switch()

        logger.info("Configuration loaded successfully")
        logger.info(f"Bot: {config.bot_name}")
        logger.info(f"Symbol: {config.symbol}")
        logger.info(f"Leverage: {config.leverage}x")
        logger.info(f"Position Size: {config.position_size_pct*100}%")
        logger.info(f"TP/SL: {config.take_profit_pct*100}% / {config.stop_loss_pct*100}%")
        logger.info(f"Testnet: {config.binance_testnet}")

        return config

    except Exception as e:
        logger.error(f"Configuration load failed: {e}")
        raise


# Singleton instance
_config: Optional[TradingConfig] = None


def get_config() -> TradingConfig:
    """Get singleton configuration instance"""
    global _config
    if _config is None:
        _config = load_config()
    return _config
