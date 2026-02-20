"""Event Bus.

비동기 이벤트 발행/구독 시스템.
트레이딩 이벤트를 느슨하게 결합된 핸들러에 전달.
"""
import asyncio
import contextlib
from collections.abc import Callable, Coroutine
from enum import Enum
from typing import Any

from loguru import logger


class EventType(Enum):
    """트레이딩 이벤트 유형."""
    TRADE_OPENED = "trade_opened"
    TRADE_CLOSED = "trade_closed"
    REGIME_CHANGED = "regime_changed"


class EventBus:
    """Fire-and-forget 이벤트 버스.

    구독자에게 비동기 이벤트를 발행. 핸들러 에러는 삼킴.

    Example:
        >>> bus = EventBus()
        >>> bus.subscribe(EventType.TRADE_OPENED, my_handler)
        >>> await bus.publish(EventType.TRADE_OPENED, {"signal": "LONG"})
    """

    def __init__(self) -> None:
        self._handlers: dict[
            EventType, list[Callable[..., Coroutine[Any, Any, Any]]]
        ] = {}

    def subscribe(
        self,
        event_type: EventType,
        handler: Callable[..., Coroutine[Any, Any, Any]],
    ) -> None:
        """이벤트 구독.

        Args:
            event_type: 구독할 이벤트 유형
            handler: 비동기 핸들러 (async def handler(data: dict))
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def unsubscribe(
        self,
        event_type: EventType,
        handler: Callable[..., Coroutine[Any, Any, Any]],
    ) -> None:
        """이벤트 구독 해제."""
        if event_type in self._handlers:
            with contextlib.suppress(ValueError):
                self._handlers[event_type].remove(handler)

    async def publish(
        self, event_type: EventType, data: dict[str, Any] | None = None,
    ) -> None:
        """이벤트 발행 (fire-and-forget).

        모든 핸들러를 병렬 실행. 개별 핸들러 에러는 로그 후 삼킴.

        Args:
            event_type: 발행할 이벤트 유형
            data: 이벤트 데이터 (선택)
        """
        handlers = self._handlers.get(event_type, [])
        if not handlers:
            return

        if data is None:
            data = {}

        tasks = [
            asyncio.create_task(self._safe_call(handler, event_type, data))
            for handler in handlers
        ]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    @staticmethod
    async def _safe_call(
        handler: Callable[..., Coroutine[Any, Any, Any]],
        event_type: EventType,
        data: dict[str, Any],
    ) -> None:
        """핸들러 안전 실행."""
        try:
            await handler(data)
        except Exception as e:
            logger.warning(
                f"EventBus 핸들러 에러 ({event_type.value}): {e}"
            )

    @property
    def handler_count(self) -> int:
        """등록된 핸들러 총 수."""
        return sum(len(h) for h in self._handlers.values())
