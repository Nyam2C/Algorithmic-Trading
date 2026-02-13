"""PnL 계산 유틸리티.

거래 손익 계산을 위한 공통 함수를 제공합니다.
"""


def calculate_pnl_pct(entry_price: float, current_price: float, side: str) -> float:
    """Calculate PnL percentage.

    Args:
        entry_price: 진입가
        current_price: 현재가
        side: 포지션 방향 ("LONG" or "SHORT")

    Returns:
        PnL 퍼센트
    """
    if side == "LONG":
        return ((current_price - entry_price) / entry_price) * 100
    # SHORT
    return ((entry_price - current_price) / entry_price) * 100


def calculate_pnl_usd(
    entry_price: float,
    current_price: float,
    side: str,
    quantity: float,
    leverage: int = 1,
) -> float:
    """Calculate PnL in USD.

    Args:
        entry_price: 진입가
        current_price: 현재가
        side: 포지션 방향 ("LONG" or "SHORT")
        quantity: 포지션 수량
        leverage: 레버리지 배수

    Returns:
        PnL (USD)
    """
    if side == "LONG":
        return (current_price - entry_price) * quantity * leverage
    # SHORT
    return (entry_price - current_price) * quantity * leverage
