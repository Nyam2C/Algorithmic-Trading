"""
JSON 구조화 로깅 모듈

CloudWatch, Loki 호환 JSON 포맷 로깅을 제공합니다.
민감정보 마스킹 기능을 포함합니다.
"""
import json
import re
import sys
from datetime import timezone
from pathlib import Path
from typing import Any

from loguru import logger


# 민감정보 패턴
SENSITIVE_PATTERNS = [
    (re.compile(r"(api[_-]?key)[\"']?\s*[:=]\s*[\"']?([a-zA-Z0-9]{8,})", re.I), r"\1=***MASKED***"),
    (re.compile(r"(secret[_-]?key)[\"']?\s*[:=]\s*[\"']?([a-zA-Z0-9]{8,})", re.I), r"\1=***MASKED***"),
    (re.compile(r"(password)[\"']?\s*[:=]\s*[\"']?([^\s\"']+)", re.I), r"\1=***MASKED***"),
    (re.compile(r"(token)[\"']?\s*[:=]\s*[\"']?([a-zA-Z0-9_\-.]{20,})", re.I), r"\1=***MASKED***"),
    (re.compile(r"(webhook[_-]?url)[\"']?\s*[:=]\s*[\"']?(https?://[^\s\"']+)", re.I), r"\1=***MASKED***"),
    # Binance API Key 패턴
    (re.compile(r"[A-Za-z0-9]{64}"), "***MASKED_KEY***"),
]


def mask_sensitive_data(text: str) -> str:
    """민감정보 마스킹

    API 키, 시크릿, 비밀번호 등을 마스킹합니다.

    Args:
        text: 마스킹할 텍스트

    Returns:
        마스킹된 텍스트
    """
    result = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def mask_dict_sensitive_data(data: dict[str, Any]) -> dict[str, Any]:
    """딕셔너리 내 민감정보 마스킹

    Args:
        data: 마스킹할 딕셔너리

    Returns:
        마스킹된 딕셔너리
    """
    sensitive_keys = {
        "api_key", "secret_key", "api_secret", "password", "token",
        "binance_api_key", "binance_secret_key", "gemini_api_key",
        "discord_webhook_url", "discord_bot_token", "webhook_url",
    }

    result: dict[str, Any] = {}
    for key, value in data.items():
        key_lower = key.lower()
        if key_lower in sensitive_keys:
            result[key] = "***MASKED***"
        elif isinstance(value, dict):
            result[key] = mask_dict_sensitive_data(value)
        elif isinstance(value, str):
            result[key] = mask_sensitive_data(value)
        else:
            result[key] = value
    return result


class JSONFormatter:
    """JSON 로그 포매터

    CloudWatch, Loki 호환 JSON 포맷으로 로그를 출력합니다.
    """

    def __init__(self, mask_sensitive: bool = True):
        """초기화

        Args:
            mask_sensitive: 민감정보 마스킹 여부
        """
        self.mask_sensitive = mask_sensitive

    def __call__(self, record: dict[str, Any]) -> str:
        """로그 레코드를 JSON 문자열로 변환

        Args:
            record: loguru 로그 레코드

        Returns:
            JSON 문자열
        """
        # 기본 필드
        log_entry = {
            "timestamp": record["time"].astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "level": record["level"].name,
            "logger": record["name"] or "root",
            "message": record["message"],
        }

        # 파일/라인 정보
        if record["file"]:
            log_entry["file"] = record["file"].name
            log_entry["line"] = record["line"]
            log_entry["function"] = record["function"]

        # 추가 컨텍스트 (bind로 추가된 데이터)
        extra = record.get("extra", {})
        if extra:
            for key, value in extra.items():
                if key not in log_entry:
                    log_entry[key] = value

        # 예외 정보
        if record["exception"]:
            exc = record["exception"]
            log_entry["exception"] = {
                "type": exc.type.__name__ if exc.type else None,
                "value": str(exc.value) if exc.value else None,
                "traceback": exc.traceback if exc.traceback else None,
            }

        # 민감정보 마스킹
        if self.mask_sensitive:
            log_entry["message"] = mask_sensitive_data(str(log_entry["message"]))
            log_entry = mask_dict_sensitive_data(log_entry)  # type: ignore[assignment]

        return json.dumps(log_entry, ensure_ascii=False, default=str) + "\n"


def setup_json_logging(
    log_level: str = "INFO",
    enable_file_logging: bool = True,
    enable_json_stdout: bool = True,
    mask_sensitive: bool = True,
    log_dir: str = "logs",
) -> None:
    """JSON 구조화 로깅 설정

    Args:
        log_level: 로그 레벨 (DEBUG, INFO, WARNING, ERROR)
        enable_file_logging: 파일 로깅 활성화 여부
        enable_json_stdout: stdout JSON 로깅 활성화 여부
        mask_sensitive: 민감정보 마스킹 여부
        log_dir: 로그 디렉토리 경로
    """
    # 기존 핸들러 제거
    logger.remove()

    json_formatter = JSONFormatter(mask_sensitive=mask_sensitive)

    if enable_json_stdout:
        # JSON stdout 로깅 (CloudWatch/Loki 호환)
        logger.add(
            sys.stdout,
            format=json_formatter,  # type: ignore[arg-type]
            level=log_level,
            serialize=False,
        )
    else:
        # Human-readable stdout 로깅 (개발용)
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level=log_level,
            colorize=True,
        )

    if enable_file_logging:
        # 로그 디렉토리 생성
        Path(log_dir).mkdir(exist_ok=True)

        # JSON 파일 로깅
        logger.add(
            f"{log_dir}/bot.json.log",
            format=json_formatter,  # type: ignore[arg-type]
            level="DEBUG",
            rotation="100 MB",
            retention="30 days",
            compression="zip",
            serialize=False,
        )

        # 에러 전용 파일 로깅
        logger.add(
            f"{log_dir}/error.json.log",
            format=json_formatter,  # type: ignore[arg-type]
            level="ERROR",
            rotation="10 MB",
            retention="30 days",
            compression="zip",
            serialize=False,
        )

    logger.info("JSON 구조화 로깅 설정 완료", log_level=log_level, json_stdout=enable_json_stdout)


def get_structured_logger(name: str, **context: Any) -> Any:
    """컨텍스트가 바인딩된 로거 반환

    Args:
        name: 로거 이름
        **context: 추가 컨텍스트 (bot_name, symbol 등)

    Returns:
        컨텍스트가 바인딩된 loguru 로거

    Example:
        >>> log = get_structured_logger("trading", bot_name="btc-bot", symbol="BTCUSDT")
        >>> log.info("Signal generated", signal="LONG", price=50000.0)
    """
    return logger.bind(logger_name=name, **context)


# Feature flag 지원
_json_logging_enabled = False


def is_json_logging_enabled() -> bool:
    """JSON 로깅 활성화 여부 반환"""
    return _json_logging_enabled


def enable_json_logging() -> None:
    """JSON 로깅 활성화"""
    global _json_logging_enabled
    _json_logging_enabled = True


def disable_json_logging() -> None:
    """JSON 로깅 비활성화"""
    global _json_logging_enabled
    _json_logging_enabled = False


def setup_logging_from_env() -> None:
    """환경변수 기반 로깅 설정

    환경변수:
        - LOG_LEVEL: 로그 레벨 (기본: INFO)
        - ENABLE_JSON_LOGGING: JSON 로깅 활성화 (기본: true)
        - ENABLE_FILE_LOGGING: 파일 로깅 활성화 (기본: true)
        - MASK_SENSITIVE: 민감정보 마스킹 (기본: true)
        - LOG_DIR: 로그 디렉토리 (기본: logs)
    """
    import os

    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    enable_json = os.getenv("ENABLE_JSON_LOGGING", "true").lower() == "true"
    enable_file = os.getenv("ENABLE_FILE_LOGGING", "true").lower() == "true"
    mask_sensitive = os.getenv("MASK_SENSITIVE", "true").lower() == "true"
    log_dir = os.getenv("LOG_DIR", "logs")

    if enable_json:
        enable_json_logging()

    setup_json_logging(
        log_level=log_level,
        enable_file_logging=enable_file,
        enable_json_stdout=enable_json,
        mask_sensitive=mask_sensitive,
        log_dir=log_dir,
    )
