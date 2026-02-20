"""API Weight Tracker.

Binance API 사용량(weight)을 슬라이딩 윈도우로 추적.
분당 한도 초과 방지를 위한 속도 제어.
"""
import time
from collections import deque

from loguru import logger


class APIWeightTracker:
    """Binance API weight 추적기.

    60초 슬라이딩 윈도우로 API 사용량을 추적하고
    한도 근접 시 지연을 권장.

    Example:
        >>> tracker = APIWeightTracker()
        >>> if tracker.can_proceed("get_klines"):
        ...     result = await client.get_klines(symbol)
        ...     tracker.record("get_klines")
    """

    MAX_WEIGHT_PER_MIN = 1200
    TARGET_WEIGHT = 800
    WINDOW_SEC = 60.0
    MAX_DELAY_SEC = 5.0

    ENDPOINT_WEIGHTS: dict[str, int] = {
        "get_klines": 5,
        "get_position": 5,
        "get_balance": 5,
        "get_current_price": 1,
        "get_ticker_24h": 1,
        "get_funding_rate": 1,
        "get_open_interest": 1,
        "get_long_short_ratio": 5,
        "get_premium_index": 1,
        "get_global_long_short_ratio": 5,
        "get_taker_long_short_ratio": 5,
        "get_market_sentiment": 18,  # 6개 API 합산
        "create_order": 1,
        "create_market_order": 1,
        "create_limit_order": 1,
        "cancel_order": 1,
        "cancel_all_open_orders": 1,
        "get_order_status": 1,
        "get_all_positions": 5,
        "create_stop_market_order": 1,
        "create_take_profit_market_order": 1,
    }

    def __init__(self) -> None:
        self._window: deque[tuple[float, int]] = deque()

    def _prune(self, now: float) -> None:
        """만료된 항목 제거."""
        cutoff = now - self.WINDOW_SEC
        while self._window and self._window[0][0] < cutoff:
            self._window.popleft()

    def record(self, endpoint: str) -> None:
        """API 호출 기록.

        Args:
            endpoint: 엔드포인트 이름
        """
        now = time.monotonic()
        weight = self.ENDPOINT_WEIGHTS.get(endpoint, 1)
        self._window.append((now, weight))
        self._prune(now)

    @property
    def current_weight(self) -> int:
        """현재 60초 윈도우 내 사용량."""
        self._prune(time.monotonic())
        return sum(w for _, w in self._window)

    def can_proceed(self, endpoint: str) -> bool:
        """TARGET 미만인지 확인.

        Args:
            endpoint: 호출하려는 엔드포인트

        Returns:
            호출 가능 여부
        """
        weight = self.ENDPOINT_WEIGHTS.get(endpoint, 1)
        return self.current_weight + weight <= self.TARGET_WEIGHT

    def should_delay(self) -> float:
        """현재 사용량 기반 권장 지연 시간.

        Returns:
            지연 시간(초). 0이면 즉시 진행 가능.
        """
        current = self.current_weight
        if current <= self.TARGET_WEIGHT:
            return 0.0

        # TARGET 초과 시 비례 지연
        overshoot = (current - self.TARGET_WEIGHT) / (
            self.MAX_WEIGHT_PER_MIN - self.TARGET_WEIGHT
        )
        delay = min(self.MAX_DELAY_SEC, overshoot * self.MAX_DELAY_SEC)

        if delay > 0:
            logger.debug(
                f"API weight {current}/{self.MAX_WEIGHT_PER_MIN}, "
                f"지연 {delay:.1f}초 권장"
            )
        return delay

    def get_status(self) -> dict:
        """모니터링용 상태 반환."""
        current = self.current_weight
        return {
            "current_weight": current,
            "max_weight": self.MAX_WEIGHT_PER_MIN,
            "target_weight": self.TARGET_WEIGHT,
            "utilization_pct": round(current / self.MAX_WEIGHT_PER_MIN * 100, 1),
            "can_proceed": current < self.TARGET_WEIGHT,
        }
