"""Economic Event Calendar.

주요 경제 이벤트 (FOMC, CPI 등) 시간을 관리.
이벤트 근처에서 거래 적합성(MTI) 점수를 낮춰 리스크 회피.
"""
from datetime import datetime, timezone

# 2026년 주요 경제 이벤트 캘린더
# date: ISO 형식 (UTC), type: 이벤트 유형, window_min: 이벤트 전후 보호 시간(분)
ECONOMIC_EVENTS_2026: list[dict] = [
    # FOMC 회의 (연 8회)
    {"date": "2026-01-29T19:00", "type": "FOMC", "window_min": 120},
    {"date": "2026-03-19T18:00", "type": "FOMC", "window_min": 120},
    {"date": "2026-05-07T18:00", "type": "FOMC", "window_min": 120},
    {"date": "2026-06-18T18:00", "type": "FOMC", "window_min": 120},
    {"date": "2026-07-30T18:00", "type": "FOMC", "window_min": 120},
    {"date": "2026-09-17T18:00", "type": "FOMC", "window_min": 120},
    {"date": "2026-11-05T19:00", "type": "FOMC", "window_min": 120},
    {"date": "2026-12-17T19:00", "type": "FOMC", "window_min": 120},
    # CPI 발표 (매월)
    {"date": "2026-01-14T13:30", "type": "CPI", "window_min": 120},
    {"date": "2026-02-12T13:30", "type": "CPI", "window_min": 120},
    {"date": "2026-03-11T12:30", "type": "CPI", "window_min": 120},
    {"date": "2026-04-14T12:30", "type": "CPI", "window_min": 120},
    {"date": "2026-05-13T12:30", "type": "CPI", "window_min": 120},
    {"date": "2026-06-10T12:30", "type": "CPI", "window_min": 120},
    {"date": "2026-07-15T12:30", "type": "CPI", "window_min": 120},
    {"date": "2026-08-12T12:30", "type": "CPI", "window_min": 120},
    {"date": "2026-09-15T12:30", "type": "CPI", "window_min": 120},
    {"date": "2026-10-13T12:30", "type": "CPI", "window_min": 120},
    {"date": "2026-11-12T13:30", "type": "CPI", "window_min": 120},
    {"date": "2026-12-10T13:30", "type": "CPI", "window_min": 120},
    # NFP (Non-Farm Payrolls, 매월 첫 금요일)
    {"date": "2026-01-09T13:30", "type": "NFP", "window_min": 90},
    {"date": "2026-02-06T13:30", "type": "NFP", "window_min": 90},
    {"date": "2026-03-06T13:30", "type": "NFP", "window_min": 90},
    {"date": "2026-04-03T12:30", "type": "NFP", "window_min": 90},
    {"date": "2026-05-08T12:30", "type": "NFP", "window_min": 90},
    {"date": "2026-06-05T12:30", "type": "NFP", "window_min": 90},
    {"date": "2026-07-02T12:30", "type": "NFP", "window_min": 90},
    {"date": "2026-08-07T12:30", "type": "NFP", "window_min": 90},
    {"date": "2026-09-04T12:30", "type": "NFP", "window_min": 90},
    {"date": "2026-10-02T12:30", "type": "NFP", "window_min": 90},
    {"date": "2026-11-06T13:30", "type": "NFP", "window_min": 90},
    {"date": "2026-12-04T13:30", "type": "NFP", "window_min": 90},
]

# 미리 파싱된 datetime 리스트 (모듈 로드 시 1회)
_PARSED_EVENTS: list[tuple[datetime, int, str]] = []
for evt in ECONOMIC_EVENTS_2026:
    dt = datetime.fromisoformat(evt["date"]).replace(tzinfo=timezone.utc)
    _PARSED_EVENTS.append((dt, evt["window_min"], evt["type"]))


def get_active_economic_events(
    current_time: datetime,
) -> list[tuple[datetime, int]]:
    """현재 시점에서 윈도우 내인 경제 이벤트 반환.

    Args:
        current_time: 현재 UTC 시간

    Returns:
        [(event_time, window_minutes), ...] 윈도우 내 이벤트 목록
    """
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)

    active: list[tuple[datetime, int]] = []
    for evt_time, window_min, _ in _PARSED_EVENTS:
        diff_sec = abs((current_time - evt_time).total_seconds())
        if diff_sec <= window_min * 60:
            active.append((evt_time, window_min))
    return active
