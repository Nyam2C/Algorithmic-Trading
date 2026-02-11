"""Discord 봇 유틸리티 함수

계산, 포맷팅 등의 헬퍼 함수를 제공합니다.
"""
from datetime import datetime
from typing import Tuple


def format_uptime(start_time: datetime | None) -> str:
    """가동 시간을 문자열로 포맷팅

    Args:
        start_time: 시작 시간

    Returns:
        포맷팅된 문자열 (예: "2시간 30분")
    """
    if not start_time:
        return "N/A"

    uptime_duration = datetime.now() - start_time
    hours = int(uptime_duration.total_seconds() / 3600)
    mins = int((uptime_duration.total_seconds() % 3600) / 60)
    return f"{hours}시간 {mins}분"


def format_time_ago(timestamp: datetime | None) -> str:
    """타임스탬프를 '~전' 형식으로 포맷팅

    Args:
        timestamp: 시간

    Returns:
        포맷팅된 문자열 (예: "30분 전", "2시간 전")
    """
    if not timestamp or not isinstance(timestamp, datetime):
        return "N/A"

    time_diff = datetime.now() - timestamp
    mins_ago = int(time_diff.total_seconds() / 60)

    if mins_ago < 60:
        return f"{mins_ago}분 전"
    hours_ago = mins_ago // 60
    return f"{hours_ago}시간 전"


def format_duration(start_time: datetime | None) -> str:
    """시작 시간부터 현재까지의 경과 시간을 포맷팅

    Args:
        start_time: 시작 시간

    Returns:
        포맷팅된 문자열 (예: "45분", "1시간 30분")
    """
    if not start_time or not isinstance(start_time, datetime):
        return "N/A"

    duration_delta = datetime.now() - start_time
    duration_mins = int(duration_delta.total_seconds() / 60)

    if duration_mins < 60:
        return f"{duration_mins}분"
    duration_hours = duration_mins // 60
    duration_mins_remain = duration_mins % 60
    return f"{duration_hours}시간 {duration_mins_remain}분"


def format_pause_duration(
    paused_at: datetime | None,
    paused_by: str | None = None
) -> str:
    """일시정지 정보를 포맷팅

    Args:
        paused_at: 일시정지 시간
        paused_by: 일시정지한 사용자

    Returns:
        포맷팅된 문자열
    """
    if not paused_at:
        return ""

    pause_duration = datetime.now() - paused_at
    hours = int(pause_duration.total_seconds() / 3600)
    mins = int((pause_duration.total_seconds() % 3600) / 60)

    result = f"\n일시정지 시간: {hours}시간 {mins}분"
    if paused_by:
        result += f" ({paused_by})"

    return result


def format_timecut_remaining(timecut_at: datetime | None) -> str:
    """타임컷까지 남은 시간을 포맷팅

    Args:
        timecut_at: 타임컷 시간

    Returns:
        포맷팅된 문자열 (예: "45분 남음", "만료됨")
    """
    if not timecut_at or not isinstance(timecut_at, datetime):
        return "N/A"

    timecut_remaining_delta = timecut_at - datetime.now()
    timecut_mins = int(timecut_remaining_delta.total_seconds() / 60)

    if timecut_mins > 0:
        return f"{timecut_mins}분 남음"
    return "만료됨"


def calculate_pnl(
    entry_price: float,
    current_price: float,
    side: str,
    leverage: int = 1,
    size: float = 0
) -> Tuple[float, float]:
    """PnL 계산

    Args:
        entry_price: 진입가
        current_price: 현재가
        side: 포지션 방향 ("LONG" or "SHORT")
        leverage: 레버리지
        size: 포지션 크기

    Returns:
        (pnl_pct, pnl_usd) 튜플
    """
    if side == "LONG":
        pnl_pct = ((current_price - entry_price) / entry_price) * 100 * leverage
        pnl_usd = (current_price - entry_price) * size
    else:  # SHORT
        pnl_pct = ((entry_price - current_price) / entry_price) * 100 * leverage
        pnl_usd = (entry_price - current_price) * size

    return pnl_pct, pnl_usd


def get_status_emoji(is_running: bool, is_paused: bool) -> str:
    """상태에 따른 이모지 반환

    Args:
        is_running: 실행 중 여부
        is_paused: 일시정지 여부

    Returns:
        상태 이모지
    """
    if is_running:
        if is_paused:
            return "🟡"  # 일시정지
        return "🟢"  # 실행 중
    return "🔴"  # 중지


def get_status_text(is_running: bool, is_paused: bool) -> str:
    """상태에 따른 텍스트 반환

    Args:
        is_running: 실행 중 여부
        is_paused: 일시정지 여부

    Returns:
        상태 텍스트
    """
    if is_running:
        if is_paused:
            return "⏸️ 일시정지"
        return "✅ 실행 중"
    return "🛑 중지됨"


def get_position_emoji(side: str) -> str:
    """포지션 방향에 따른 이모지 반환

    Args:
        side: 포지션 방향 ("LONG" or "SHORT")

    Returns:
        포지션 이모지
    """
    return "🟢" if side == "LONG" else "🔴"


def get_pnl_emoji(pnl: float) -> str:
    """손익에 따른 이모지 반환

    Args:
        pnl: 손익 값

    Returns:
        손익 이모지
    """
    return "💰" if pnl >= 0 else "📉"


def format_price(price: float, decimals: int = 2) -> str:
    """가격을 포맷팅

    Args:
        price: 가격
        decimals: 소수점 자릿수

    Returns:
        포맷팅된 가격 문자열
    """
    return f"${price:,.{decimals}f}"


def format_percentage(value: float, with_sign: bool = True) -> str:
    """퍼센트를 포맷팅

    Args:
        value: 퍼센트 값
        with_sign: 부호 표시 여부

    Returns:
        포맷팅된 퍼센트 문자열
    """
    if with_sign:
        return f"{value:+.2f}%"
    return f"{value:.2f}%"


def truncate_id(id_str: str, length: int = 8) -> str:
    """ID를 잘라서 반환

    Args:
        id_str: ID 문자열
        length: 최대 길이

    Returns:
        잘린 ID 문자열
    """
    return str(id_str)[:length] if id_str else "N/A"
