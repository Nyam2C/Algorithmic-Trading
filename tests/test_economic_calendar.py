"""Tests for Economic Event Calendar (WS-4)."""
from datetime import datetime, timedelta, timezone

from src.data.economic_calendar import ECONOMIC_EVENTS_2026, get_active_economic_events


class TestEconomicEvents:
    """ECONOMIC_EVENTS_2026 리스트 검증."""

    def test_events_not_empty(self):
        assert len(ECONOMIC_EVENTS_2026) > 0

    def test_all_events_have_required_fields(self):
        for event in ECONOMIC_EVENTS_2026:
            assert "date" in event
            assert "type" in event
            assert "window_min" in event

    def test_event_types(self):
        types = {e["type"] for e in ECONOMIC_EVENTS_2026}
        assert "FOMC" in types
        assert "CPI" in types
        assert "NFP" in types

    def test_event_dates_parseable(self):
        for event in ECONOMIC_EVENTS_2026:
            dt = datetime.strptime(event["date"], "%Y-%m-%dT%H:%M")
            assert dt.year == 2026


class TestGetActiveEconomicEvents:
    """get_active_economic_events 함수 테스트."""

    def test_during_fomc(self):
        """FOMC 이벤트 시간 내 → 활성 이벤트 반환."""
        # 2026-01-29T19:00 FOMC, window 120min
        fomc_time = datetime(2026, 1, 29, 19, 30, tzinfo=timezone.utc)
        active = get_active_economic_events(fomc_time)
        assert len(active) >= 1
        # 120분 윈도우 이내
        for evt_time, window in active:
            diff = abs((fomc_time - evt_time).total_seconds())
            assert diff <= window * 60

    def test_outside_any_event(self):
        """이벤트 시간대 밖 → 빈 리스트."""
        # 2026-06-15 12:00 UTC — 어떤 이벤트와도 2시간 이상 떨어짐
        normal_time = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
        active = get_active_economic_events(normal_time)
        assert len(active) == 0

    def test_at_window_boundary(self):
        """윈도우 경계 정확히 120분 → 활성."""
        fomc_time_exact = datetime(2026, 1, 29, 19, 0, tzinfo=timezone.utc)
        # 정확히 120분 전
        boundary = fomc_time_exact - timedelta(minutes=120)
        active = get_active_economic_events(boundary)
        assert len(active) >= 1

    def test_just_outside_window(self):
        """윈도우 바깥 (121분) → 비활성."""
        fomc_time_exact = datetime(2026, 1, 29, 19, 0, tzinfo=timezone.utc)
        outside = fomc_time_exact - timedelta(minutes=121)
        active = get_active_economic_events(outside)
        # FOMC는 포함되지 않아야 함
        fomc_found = any(
            abs((outside - evt).total_seconds()) <= w * 60
            for evt, w in active
        )
        # 다른 이벤트가 우연히 걸리지 않는 한 빈 리스트
        assert not fomc_found

    def test_multiple_events_same_day(self):
        """같은 날 여러 이벤트가 있을 수 있음."""
        # 특정 날짜에 CPI와 다른 이벤트가 겹칠 수 있음
        # 단순히 함수가 리스트를 반환하는지 확인
        result = get_active_economic_events(
            datetime(2026, 2, 12, 13, 30, tzinfo=timezone.utc)
        )
        assert isinstance(result, list)
        assert len(result) >= 1  # CPI 2026-02-12T13:30

    def test_returns_tuple_format(self):
        """반환 형식: (datetime, int) 튜플."""
        fomc_time = datetime(2026, 1, 29, 19, 0, tzinfo=timezone.utc)
        active = get_active_economic_events(fomc_time)
        for item in active:
            assert isinstance(item, tuple)
            assert len(item) == 2
            assert isinstance(item[0], datetime)
            assert isinstance(item[1], int)
