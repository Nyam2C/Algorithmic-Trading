"""REST Polling Scheduler.

시장 심리 데이터의 TTL 기반 캐싱 스케줄러.
각 API 엔드포인트별 독립적인 갱신 주기 관리.
"""
import time
from collections.abc import Callable, Coroutine
from typing import Any

from loguru import logger


class RESTPollingScheduler:
    """TTL 기반 REST 폴링 스케줄러.

    각 데이터 소스별 갱신 주기를 독립적으로 관리하여
    불필요한 API 호출을 줄이고 응답 시간을 단축.

    Example:
        >>> poller = RESTPollingScheduler()
        >>> data = await poller.get("funding_rate", client.get_funding_rate, symbol)
    """

    INTERVALS: dict[str, int] = {
        "funding_rate": 300,       # 5분
        "long_short_ratio": 300,   # 5분
        "open_interest": 120,      # 2분
        "premium_index": 60,       # 1분
        "global_ls_ratio": 300,    # 5분
        "taker_ls_ratio": 120,     # 2분
    }

    def __init__(self, intervals: dict[str, int] | None = None) -> None:
        self._cache: dict[str, tuple[float, Any]] = {}
        if intervals:
            self.INTERVALS = {**self.INTERVALS, **intervals}

    async def get(
        self,
        key: str,
        fetch_fn: Callable[..., Coroutine[Any, Any, Any]],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """TTL 체크 후 캐시 반환 또는 갱신.

        Args:
            key: 데이터 소스 키
            fetch_fn: 데이터 조회 코루틴
            *args: fetch_fn에 전달할 인자
            **kwargs: fetch_fn에 전달할 키워드 인자

        Returns:
            캐시된 또는 새로 조회한 데이터
        """
        now = time.monotonic()
        ttl = self.INTERVALS.get(key, 300)

        if key in self._cache:
            last_time, cached_data = self._cache[key]
            if now - last_time < ttl:
                return cached_data

        try:
            data = await fetch_fn(*args, **kwargs)
            self._cache[key] = (now, data)
            return data
        except Exception as e:
            logger.warning(f"REST 폴링 실패 ({key}): {e}")
            # 캐시에 있으면 만료된 데이터라도 반환
            if key in self._cache:
                return self._cache[key][1]
            raise

    async def get_all_sentiment(self, client: Any, symbol: str) -> dict[str, Any]:
        """모든 시장 심리 메트릭 일괄 조회.

        각 메트릭의 개별 TTL을 존중하여 만료된 것만 갱신.

        Args:
            client: BinanceTestnetClient 인스턴스
            symbol: 거래쌍 (예: "BTCUSDT")

        Returns:
            통합 시장 심리 데이터
        """
        funding = await self.get(
            "funding_rate", client.get_funding_rate, symbol
        )
        ls_ratio = await self.get(
            "long_short_ratio", client.get_long_short_ratio, symbol
        )
        oi = await self.get(
            "open_interest", client.get_open_interest, symbol
        )
        premium = await self.get(
            "premium_index", client.get_premium_index, symbol
        )
        global_ls = await self.get(
            "global_ls_ratio", client.get_global_long_short_ratio, symbol
        )
        taker_ls = await self.get(
            "taker_ls_ratio", client.get_taker_long_short_ratio, symbol
        )

        return {
            "funding_rate": funding.get("funding_rate", 0.0),
            "long_ratio": ls_ratio.get("long_ratio", 0.5),
            "short_ratio": ls_ratio.get("short_ratio", 0.5),
            "long_short_ratio": ls_ratio.get("long_short_ratio", 1.0),
            "open_interest": oi.get("open_interest", 0.0),
            "basis": premium.get("basis", 0.0),
            "global_long_ratio": global_ls.get("long_ratio", 0.5),
            "global_short_ratio": global_ls.get("short_ratio", 0.5),
            "taker_buy_sell_ratio": taker_ls.get("buy_sell_ratio", 1.0),
        }

    def invalidate(self, key: str) -> None:
        """특정 캐시 무효화."""
        self._cache.pop(key, None)

    def invalidate_all(self) -> None:
        """모든 캐시 무효화."""
        self._cache.clear()
