"""
YAML 봇 설정 로더

멀티봇 YAML 설정 파일을 로드하고 BotConfig 리스트로 변환합니다.

Example:
    >>> from src.config_loader import load_bots_from_yaml_optional
    >>> bot_configs, global_config = load_bots_from_yaml_optional()
    >>> for config in bot_configs:
    ...     if config.is_active:
    ...         manager.add_bot(config)
"""
from pathlib import Path
from typing import Optional

import yaml
from loguru import logger
from pydantic import BaseModel, Field, field_validator

from src.bot_config import BotConfig


class GlobalConfig(BaseModel):
    """YAML 글로벌 설정 모델

    Attributes:
        is_testnet: 테스트넷 사용 여부
        loop_interval_seconds: 트레이딩 루프 간격 (초)
    """

    is_testnet: bool = Field(default=True)
    loop_interval_seconds: int = Field(default=300, gt=0)


class BotYamlEntry(BaseModel):
    """YAML 봇 항목 모델

    YAML 파일에서 파싱된 봇 설정을 나타냅니다.

    Attributes:
        name: 봇 이름 (고유)
        symbol: 거래 심볼 (예: BTCUSDT)
        risk_level: 위험도 (low, medium, high)
        is_active: 봇 활성화 여부
    """

    name: str = Field(..., min_length=1, max_length=50)
    symbol: str = Field(default="BTCUSDT")
    risk_level: str = Field(default="medium")
    is_active: bool = Field(default=True)

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """심볼 대문자 변환"""
        return v.upper()

    @field_validator("risk_level")
    @classmethod
    def validate_risk_level(cls, v: str) -> str:
        """위험도 검증"""
        valid_levels = ["low", "medium", "high"]
        if v not in valid_levels:
            raise ValueError(f"risk_level must be one of {valid_levels}")
        return v

    def to_bot_config(self, global_config: Optional[GlobalConfig] = None) -> BotConfig:
        """BotConfig로 변환

        Args:
            global_config: 글로벌 설정 (없으면 기본값 사용)

        Returns:
            BotConfig 인스턴스
        """
        if global_config is None:
            global_config = GlobalConfig()

        return BotConfig(
            bot_name=self.name,
            symbol=self.symbol,
            risk_level=self.risk_level,
            is_testnet=global_config.is_testnet,
            is_active=self.is_active,
        )


def load_bots_from_yaml(
    yaml_path: str,
) -> tuple[list[BotConfig], GlobalConfig]:
    """YAML 파일에서 봇 설정을 로드

    Args:
        yaml_path: YAML 파일 경로

    Returns:
        (BotConfig 리스트, GlobalConfig) 튜플

    Raises:
        FileNotFoundError: 파일이 존재하지 않을 때
        ValueError: YAML 파싱 오류 시
    """
    path = Path(yaml_path)
    if not path.exists():
        raise FileNotFoundError(f"YAML 설정 파일을 찾을 수 없습니다: {yaml_path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if data is None:
        data = {}

    # 글로벌 설정 파싱
    global_data = data.get("global", {})
    global_config = GlobalConfig(**global_data)

    # 봇 설정 파싱
    bots_data = data.get("bots", [])
    bot_configs: list[BotConfig] = []

    for bot_entry in bots_data:
        entry = BotYamlEntry(**bot_entry)
        bot_config = entry.to_bot_config(global_config)
        bot_configs.append(bot_config)

    logger.info(f"YAML에서 {len(bot_configs)}개 봇 설정 로드 완료: {yaml_path}")

    return bot_configs, global_config


def load_bots_from_yaml_optional(
    yaml_path: Optional[str] = None,
) -> tuple[list[BotConfig], Optional[GlobalConfig]]:
    """YAML 파일에서 봇 설정을 선택적으로 로드 (하위 호환성)

    파일이 없으면 빈 리스트를 반환합니다.

    Args:
        yaml_path: YAML 파일 경로 (기본값: configs/bots.yaml)

    Returns:
        (BotConfig 리스트, GlobalConfig 또는 None) 튜플
    """
    if yaml_path is None:
        yaml_path = "configs/bots.yaml"

    try:
        return load_bots_from_yaml(yaml_path)
    except FileNotFoundError:
        logger.debug(f"YAML 설정 파일 없음 (선택적): {yaml_path}")
        return [], None
