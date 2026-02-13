"""Tests for emergency close immediate execution."""
import asyncio
import time

import pytest

from src.bot_config import BotConfig
from src.bot_instance import BotInstance


def _make_bot(**kwargs) -> BotInstance:
    """테스트용 BotInstance 생성 헬퍼"""
    config = BotConfig(bot_name="test-bot", symbol="BTCUSDT")
    return BotInstance(
        config=config,
        binance_api_key="test",
        binance_secret_key="test",
        loop_interval_seconds=kwargs.get("loop_interval_seconds", 300),
    )


class TestEmergencyCloseImmediate:
    """긴급 청산 즉시 실행 테스트"""

    def test_emergency_event_exists(self):
        """BotInstance에 _emergency_event 속성이 있는지 확인"""
        bot = _make_bot()
        assert hasattr(bot, "_emergency_event")
        assert isinstance(bot._emergency_event, asyncio.Event)

    def test_request_emergency_close_sets_event(self):
        """request_emergency_close()가 이벤트를 설정하는지 확인"""
        bot = _make_bot()
        assert not bot._emergency_event.is_set()

        bot.request_emergency_close()

        assert bot._emergency_close is True
        assert bot._emergency_event.is_set()

    @pytest.mark.asyncio
    async def test_emergency_close_wakes_loop_immediately(self):
        """긴급 청산 요청 시 event.wait()가 즉시 깨어나는지 확인"""
        bot = _make_bot(loop_interval_seconds=60)

        # 이벤트 기반 대기를 직접 테스트
        start = time.monotonic()

        async def set_event_soon():
            await asyncio.sleep(0.1)
            bot.request_emergency_close()

        # wait_for와 동일한 패턴으로 대기
        bot._emergency_event.clear()
        task = asyncio.create_task(set_event_soon())
        try:
            await asyncio.wait_for(
                bot._emergency_event.wait(),
                timeout=60,
            )
        except asyncio.TimeoutError:
            pass

        elapsed = time.monotonic() - start
        await task

        # 이벤트가 설정되었으므로 즉시 깨어나야 함 (< 1초)
        assert elapsed < 2.0, f"Wait took {elapsed:.1f}s, should be < 2s"
        assert bot._emergency_event.is_set()
        assert bot._emergency_close is True


class TestEmergencyEventThreadSafety:
    """Event 기반 긴급 청산의 스레드 안전성 테스트"""

    @pytest.mark.asyncio
    async def test_multiple_emergency_requests_idempotent(self):
        """여러 번 긴급 청산 요청해도 Event는 한번만 설정됨"""
        bot = _make_bot()

        bot.request_emergency_close()
        bot.request_emergency_close()
        bot.request_emergency_close()

        # Event should be set (calling set() multiple times is idempotent)
        assert bot._emergency_event.is_set()

    @pytest.mark.asyncio
    async def test_event_clear_after_handling_allows_next_emergency(self):
        """핸들링 후 clear하면 다음 긴급 청산 요청을 받을 수 있음"""
        bot = _make_bot()

        bot.request_emergency_close()
        assert bot._emergency_event.is_set()

        # Simulate handling (clear)
        bot._emergency_event.clear()
        assert not bot._emergency_event.is_set()

        # Can request again
        bot.request_emergency_close()
        assert bot._emergency_event.is_set()
