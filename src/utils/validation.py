"""데이터 검증 유틸리티 모듈.

OHLCV 데이터 검증 및 NaN 값 처리를 위한 헬퍼 함수들.
"""
import math

import pandas as pd
from loguru import logger


def validate_ohlcv_dataframe(
    df: pd.DataFrame, min_rows: int = 10
) -> pd.DataFrame:
    """OHLCV DataFrame 검증 및 정제.

    - NaN이 있는 OHLCV 열을 forward-fill로 채움
    - NaN 존재 시 경고 로그
    - 전체 행이 NaN인 경우 제거 후 min_rows 확인
    - 타임스탬프 단조 증가 확인

    Args:
        df: OHLCV DataFrame (timestamp, open, high, low, close, volume 열 필수)
        min_rows: 최소 행 수 (미달 시 ValueError)

    Returns:
        정제된 DataFrame

    Raises:
        ValueError: 열 누락 또는 행 수 부족
    """
    ohlcv_cols = ["open", "high", "low", "close", "volume"]
    required_cols = ["timestamp", *ohlcv_cols]

    # 필수 열 확인
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"OHLCV 필수 열 누락: {missing}")

    result = df.copy()

    # OHLCV NaN forward-fill
    nan_count = result[ohlcv_cols].isna().sum().sum()
    if nan_count > 0:
        logger.warning(f"OHLCV NaN {nan_count}개 발견, forward-fill 적용")
        result[ohlcv_cols] = result[ohlcv_cols].ffill()

    # 전체 행 NaN 제거
    result = result.dropna(subset=ohlcv_cols, how="all")

    if len(result) < min_rows:
        raise ValueError(
            f"OHLCV 행 수 부족: {len(result)} < {min_rows}"
        )

    # 타임스탬프 단조 증가 확인
    if "timestamp" in result.columns and len(result) > 1:
        ts = result["timestamp"]
        if not ts.is_monotonic_increasing:
            logger.warning("타임스탬프가 단조 증가하지 않음 - 정렬 수행")
            result = result.sort_values("timestamp").reset_index(drop=True)

    return result


def sanitize_nan_values(
    data: dict, default: float = 0.0
) -> dict:
    """딕셔너리 내 NaN/None 값을 기본값으로 교체.

    Args:
        data: 입력 딕셔너리
        default: NaN/None 대체 기본값

    Returns:
        정제된 딕셔너리
    """
    result = {}
    replaced_keys: list[str] = []

    for key, value in data.items():
        if value is None or (isinstance(value, float) and math.isnan(value)):
            result[key] = default
            replaced_keys.append(key)
        else:
            result[key] = value

    if replaced_keys:
        logger.warning(f"NaN/None 값 교체: {replaced_keys} -> {default}")

    return result
