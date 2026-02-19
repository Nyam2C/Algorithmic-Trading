"""Microprice Smart Limit — 호가창 불균형 기반 지정가 주문 계산.

Stoikov (2018) microprice 공식을 사용하여 유리한 진입가를 산출합니다.
순수 함수 모듈 — 클래스 없이 함수만 제공합니다.
"""
import math

# 유동성 티어별 대기 설정
WAIT_CONFIG: dict[str, dict] = {
    "high": {
        "wait_seconds": 30,
        "slide_wait_seconds": 15,
        "allow_market_fallback": True,
    },
    "medium": {
        "wait_seconds": 15,
        "slide_wait_seconds": 8,
        "allow_market_fallback": True,
    },
    "low": {
        "wait_seconds": 60,
        "slide_wait_seconds": 30,
        "allow_market_fallback": False,
    },
}

# MTI 점수 구간
_MTI_HIGH_THRESHOLD = 70
_MTI_MEDIUM_THRESHOLD = 40


def calculate_microprice(
    best_bid: float, best_ask: float, bid_vol: float, ask_vol: float
) -> float | None:
    """호가창 불균형 기반 microprice 계산.

    microprice = (bid x ask_vol + ask x bid_vol) / (bid_vol + ask_vol)

    Args:
        best_bid: 최우선 매수호가
        best_ask: 최우선 매도호가
        bid_vol: 매수 호가 수량
        ask_vol: 매도 호가 수량

    Returns:
        microprice 또는 None (입력 무효 시)
    """
    if best_bid <= 0 or best_ask <= 0:
        return None
    if best_bid >= best_ask:
        return None  # crossed book
    total_vol = bid_vol + ask_vol
    if total_vol <= 0 or math.isnan(total_vol):
        return None
    return (best_bid * ask_vol + best_ask * bid_vol) / total_vol


def calculate_limit_price(
    microprice: float, side: str, atr_1m: float, offset_factor: float = 0.1
) -> float:
    """Microprice 기반 지정가 계산.

    LONG:  limit = microprice - ATR(1m) * offset_factor
    SHORT: limit = microprice + ATR(1m) * offset_factor

    Args:
        microprice: 계산된 microprice
        side: "LONG" or "SHORT"
        atr_1m: 1분 ATR
        offset_factor: ATR 오프셋 비율 (기본 0.1)

    Returns:
        지정가 (소수점 2자리)
    """
    offset = atr_1m * offset_factor
    if side == "LONG":
        return round(microprice - offset, 2)
    return round(microprice + offset, 2)


def get_liquidity_tier(mti_score: float) -> str:
    """MTI 점수를 유동성 티어로 매핑.

    Args:
        mti_score: MTI 총점 (0~100)

    Returns:
        "high", "medium", or "low"
    """
    if mti_score >= _MTI_HIGH_THRESHOLD:
        return "high"
    if mti_score >= _MTI_MEDIUM_THRESHOLD:
        return "medium"
    return "low"
