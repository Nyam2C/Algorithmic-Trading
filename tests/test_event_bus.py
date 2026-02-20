"""Tests for Event Bus (WS-7)."""
import pytest

from src.utils.event_bus import EventBus, EventType


class TestEventType:
    """EventType enum 테스트."""

    def test_event_types(self):
        assert EventType.TRADE_OPENED.value == "trade_opened"
        assert EventType.TRADE_CLOSED.value == "trade_closed"
        assert EventType.REGIME_CHANGED.value == "regime_changed"


class TestEventBus:
    """EventBus 테스트."""

    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self):
        bus = EventBus()
        received = []

        async def handler(data):
            received.append(data)

        bus.subscribe(EventType.TRADE_OPENED, handler)
        await bus.publish(EventType.TRADE_OPENED, {"symbol": "BTCUSDT"})

        assert len(received) == 1
        assert received[0] == {"symbol": "BTCUSDT"}

    @pytest.mark.asyncio
    async def test_multiple_handlers(self):
        bus = EventBus()
        count = [0]

        async def handler1(data):
            count[0] += 1

        async def handler2(data):
            count[0] += 10

        bus.subscribe(EventType.TRADE_CLOSED, handler1)
        bus.subscribe(EventType.TRADE_CLOSED, handler2)
        await bus.publish(EventType.TRADE_CLOSED, {})

        assert count[0] == 11

    @pytest.mark.asyncio
    async def test_no_handler_no_error(self):
        bus = EventBus()
        # 핸들러 없이 publish — 에러 없음
        await bus.publish(EventType.REGIME_CHANGED, {"regime": "RANGING"})

    @pytest.mark.asyncio
    async def test_handler_error_swallowed(self):
        """핸들러 에러가 삼켜지는지 확인."""
        bus = EventBus()
        call_count = [0]

        async def bad_handler(data):
            raise ValueError("test error")

        async def good_handler(data):
            call_count[0] += 1

        bus.subscribe(EventType.TRADE_OPENED, bad_handler)
        bus.subscribe(EventType.TRADE_OPENED, good_handler)

        # 에러가 전파되지 않아야 함
        await bus.publish(EventType.TRADE_OPENED, {})
        assert call_count[0] == 1

    @pytest.mark.asyncio
    async def test_different_event_types_independent(self):
        bus = EventBus()
        opened_count = [0]
        closed_count = [0]

        async def on_open(data):
            opened_count[0] += 1

        async def on_close(data):
            closed_count[0] += 1

        bus.subscribe(EventType.TRADE_OPENED, on_open)
        bus.subscribe(EventType.TRADE_CLOSED, on_close)

        await bus.publish(EventType.TRADE_OPENED, {})
        assert opened_count[0] == 1
        assert closed_count[0] == 0

    @pytest.mark.asyncio
    async def test_publish_with_none_data(self):
        """data=None → {} 로 변환."""
        bus = EventBus()
        received = []

        async def handler(data):
            received.append(data)

        bus.subscribe(EventType.REGIME_CHANGED, handler)
        await bus.publish(EventType.REGIME_CHANGED)  # data=None → {}

        assert len(received) == 1
        assert received[0] == {}  # None은 {} 로 변환

    @pytest.mark.asyncio
    async def test_handler_count(self):
        bus = EventBus()

        async def h(data):
            pass

        assert bus.handler_count == 0
        bus.subscribe(EventType.TRADE_OPENED, h)
        assert bus.handler_count == 1
        bus.subscribe(EventType.TRADE_CLOSED, h)
        assert bus.handler_count == 2

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        bus = EventBus()
        count = [0]

        async def handler(data):
            count[0] += 1

        bus.subscribe(EventType.TRADE_OPENED, handler)
        bus.unsubscribe(EventType.TRADE_OPENED, handler)
        await bus.publish(EventType.TRADE_OPENED, {})
        assert count[0] == 0
