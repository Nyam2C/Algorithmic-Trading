"""Tests for REST Polling Scheduler (WS-5)."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.exchange.rest_poller import RESTPollingScheduler


class TestRESTPollingScheduler:
    """RESTPollingScheduler 테스트."""

    def test_intervals_defined(self):
        """주요 메트릭 간격 정의 확인."""
        assert "funding_rate" in RESTPollingScheduler.INTERVALS
        assert "open_interest" in RESTPollingScheduler.INTERVALS
        assert "premium_index" in RESTPollingScheduler.INTERVALS
        assert RESTPollingScheduler.INTERVALS["funding_rate"] == 300
        assert RESTPollingScheduler.INTERVALS["premium_index"] == 60

    @pytest.mark.asyncio
    async def test_first_call_fetches(self):
        """첫 호출은 항상 fetch."""
        poller = RESTPollingScheduler()
        fetch_fn = AsyncMock(return_value={"value": 42})
        result = await poller.get("funding_rate", fetch_fn)
        assert result == {"value": 42}
        fetch_fn.assert_called_once()

    @pytest.mark.asyncio
    async def test_cached_within_ttl(self):
        """TTL 이내 → 캐시 반환, fetch 안 함."""
        poller = RESTPollingScheduler()
        fetch_fn = AsyncMock(return_value={"value": 42})
        await poller.get("funding_rate", fetch_fn)
        # 두 번째 호출 — 캐시 사용
        result2 = await poller.get("funding_rate", fetch_fn)
        assert result2 == {"value": 42}
        assert fetch_fn.call_count == 1  # 한 번만 fetch

    @pytest.mark.asyncio
    async def test_fetch_after_ttl_expired(self):
        """TTL 만료 후 → 재fetch."""
        poller = RESTPollingScheduler()
        fetch_fn = AsyncMock(return_value={"v": 1})
        await poller.get("premium_index", fetch_fn)  # TTL=60s

        # 수동으로 캐시 시간 조작
        key_data = poller._cache["premium_index"]
        poller._cache["premium_index"] = (key_data[0] - 61, key_data[1])

        fetch_fn.return_value = {"v": 2}
        result = await poller.get("premium_index", fetch_fn)
        assert result == {"v": 2}
        assert fetch_fn.call_count == 2

    @pytest.mark.asyncio
    async def test_stale_cache_on_error(self):
        """fetch 실패 시 stale 캐시 반환."""
        poller = RESTPollingScheduler()
        fetch_fn = AsyncMock(return_value={"v": 1})
        await poller.get("funding_rate", fetch_fn)

        # TTL 만료
        key_data = poller._cache["funding_rate"]
        poller._cache["funding_rate"] = (key_data[0] - 301, key_data[1])

        # fetch 실패
        fetch_fn.side_effect = ConnectionError("network error")
        result = await poller.get("funding_rate", fetch_fn)
        assert result == {"v": 1}  # stale cache

    @pytest.mark.asyncio
    async def test_error_no_cache_raises(self):
        """캐시 없이 fetch 실패 → 예외 전파."""
        poller = RESTPollingScheduler()
        fetch_fn = AsyncMock(side_effect=ConnectionError("fail"))
        with pytest.raises(ConnectionError):
            await poller.get("funding_rate", fetch_fn)

    @pytest.mark.asyncio
    async def test_get_all_sentiment(self):
        """통합 센티먼트 조회 테스트."""
        poller = RESTPollingScheduler()
        client = MagicMock()
        client.get_funding_rate = AsyncMock(
            return_value={"funding_rate": 0.01}
        )
        client.get_long_short_ratio = AsyncMock(
            return_value={"long_ratio": 0.6, "short_ratio": 0.4, "long_short_ratio": 1.5}
        )
        client.get_open_interest = AsyncMock(
            return_value={"open_interest": 50000.0}
        )
        client.get_premium_index = AsyncMock(
            return_value={"basis": 0.001}
        )
        client.get_global_long_short_ratio = AsyncMock(
            return_value={"long_ratio": 0.55, "short_ratio": 0.45}
        )
        client.get_taker_long_short_ratio = AsyncMock(
            return_value={"buy_sell_ratio": 1.1}
        )

        result = await poller.get_all_sentiment(client, "BTCUSDT")
        assert result["funding_rate"] == 0.01
        assert result["open_interest"] == 50000.0
        assert result["basis"] == 0.001
        assert result["taker_buy_sell_ratio"] == 1.1

    @pytest.mark.asyncio
    async def test_default_ttl_for_unknown_key(self):
        """INTERVALS에 없는 키 → 기본 300초 TTL."""
        poller = RESTPollingScheduler()
        fetch_fn = AsyncMock(return_value={"v": 1})
        await poller.get("custom_metric", fetch_fn)
        assert "custom_metric" in poller._cache
