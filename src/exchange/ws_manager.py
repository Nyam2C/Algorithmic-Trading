"""WebSocket Manager for real-time orderbook & trade data.

APEX-V Fast Layer: Binance WebSocket으로 depth/aggTrade 스트림 수집.
OrderBookAggregator: OFI 계산용 오더북 델타 집계.
TradeAggregator: Whale/Retail 분류용 체결 데이터 집계.
"""
from __future__ import annotations

import asyncio
import contextlib
import statistics
import time
from collections import deque
from typing import Any

from loguru import logger


class OrderBookAggregator:
    """오더북 델타 집계기.

    depth@100ms 메시지에서 bid/ask delta를 추출하여 OFI 계산.
    """

    MAX_BUFFER_SIZE = 3000  # ~5분 (100ms 간격)
    MIN_SAMPLES = 5
    STALE_THRESHOLD_SEC = 5.0
    SPOOF_MULTIPLIER = 5.0
    SPOOF_DECAY_SEC = 3.0
    SPOOF_DECAY_RATIO = 0.8

    def __init__(self) -> None:
        self._buffer: deque[tuple[float, float, float]] = deque(
            maxlen=self.MAX_BUFFER_SIZE
        )
        self._last_bids: dict[str, float] = {}  # price_str -> qty
        self._last_asks: dict[str, float] = {}
        self._last_update_time: float = 0.0
        # Spoof tracking: (timestamp, size)
        self._large_orders: deque[tuple[float, float]] = deque(maxlen=100)

    def update(self, msg: dict[str, Any]) -> None:
        """Depth 메시지 처리.

        Args:
            msg: Binance depth 메시지 (bids, asks 포함)
        """
        now = time.monotonic()
        bids = msg.get("bids", msg.get("b", []))
        asks = msg.get("asks", msg.get("a", []))

        bid_delta = 0.0
        new_bids: dict[str, float] = {}
        for price_str, qty_str in bids:
            qty = float(qty_str)
            new_bids[price_str] = qty
            old_qty = self._last_bids.get(price_str, 0.0)
            bid_delta += qty - old_qty

        ask_delta = 0.0
        new_asks: dict[str, float] = {}
        for price_str, qty_str in asks:
            qty = float(qty_str)
            new_asks[price_str] = qty
            old_qty = self._last_asks.get(price_str, 0.0)
            ask_delta += qty - old_qty

        # Spoof filter: 대형 주문 추적
        total_delta = abs(bid_delta) + abs(ask_delta)
        if self._buffer:
            recent_deltas = [
                abs(b) + abs(a) for _, b, a in self._buffer
            ]
            if recent_deltas:
                median_delta = statistics.median(
                    recent_deltas[-min(50, len(recent_deltas)):]
                )
                spoof_limit = median_delta * self.SPOOF_MULTIPLIER
                if median_delta > 0 and total_delta > spoof_limit:
                    self._large_orders.append((now, total_delta))

        # 3초 이내 80% 소멸한 주문 제외
        if not self._is_spoofed(now, total_delta):
            self._buffer.append((now, bid_delta, ask_delta))

        self._last_bids = new_bids
        self._last_asks = new_asks
        self._last_update_time = now

    def _is_spoofed(self, now: float, current_delta: float) -> bool:
        """스푸프 주문 감지."""
        expired = []
        for ts, size in self._large_orders:
            age = now - ts
            decay_limit = size * (1 - self.SPOOF_DECAY_RATIO)
            if age > self.SPOOF_DECAY_SEC and current_delta < decay_limit:
                expired.append((ts, size))
                return True
        # 만료된 항목 정리
        for item in expired:
            with contextlib.suppress(ValueError):
                self._large_orders.remove(item)
        return False

    def depth_spread_snapshot(self) -> dict[str, float] | None:
        """오더북 깊이/스프레드 스냅샷.

        Returns:
            {"best_bid": float, "best_ask": float, "spread_pct": float,
             "bid_depth_total": float, "ask_depth_total": float,
             "depth_ratio": float} or None if stale/empty
        """
        now = time.monotonic()
        if now - self._last_update_time > self.STALE_THRESHOLD_SEC:
            return None
        if not self._last_bids or not self._last_asks:
            return None

        best_bid = max(float(p) for p in self._last_bids)
        best_ask = min(float(p) for p in self._last_asks)
        if best_bid <= 0 or best_ask <= 0:
            return None

        mid = (best_bid + best_ask) / 2
        spread_pct = (best_ask - best_bid) / mid * 100

        bid_depth_total = sum(self._last_bids.values())
        ask_depth_total = sum(self._last_asks.values())
        depth_ratio = bid_depth_total / ask_depth_total if ask_depth_total > 0 else 0.0

        return {
            "best_bid": round(best_bid, 8),
            "best_ask": round(best_ask, 8),
            "spread_pct": round(spread_pct, 6),
            "bid_depth_total": round(bid_depth_total, 4),
            "ask_depth_total": round(ask_depth_total, 4),
            "depth_ratio": round(depth_ratio, 4),
        }

    def snapshot(self) -> dict[str, Any] | None:
        """OFI 스냅샷 반환.

        Returns:
            {"ofi_5": float, "ofi_20": float, "ofi_50": float, "cvd": float,
             "sample_count": int} or None if stale/insufficient
        """
        now = time.monotonic()
        if not self._buffer:
            return None

        if now - self._last_update_time > self.STALE_THRESHOLD_SEC:
            return None

        n = len(self._buffer)
        if n < self.MIN_SAMPLES:
            return None

        # OFI = sum(bid_delta - ask_delta) over window
        items = list(self._buffer)

        def _ofi(window: int) -> float:
            recent = items[-min(window, n):]
            return sum(b - a for _, b, a in recent)

        ofi_5 = _ofi(5)
        ofi_20 = _ofi(20)
        ofi_50 = _ofi(50)

        # CVD: cumulative (bid_delta - ask_delta) over all
        cvd = sum(b - a for _, b, a in items)

        return {
            "ofi_5": round(ofi_5, 4),
            "ofi_20": round(ofi_20, 4),
            "ofi_50": round(ofi_50, 4),
            "cvd": round(cvd, 4),
            "sample_count": n,
        }


class TradeAggregator:
    """체결 데이터 집계기.

    aggTrade 메시지에서 whale/algo/retail 분류.
    """

    MAX_BUFFER_SIZE = 6000  # ~10분
    STALE_THRESHOLD_SEC = 10.0
    PERCENTILE_RECALC_INTERVAL = 60.0  # 60초마다 재계산

    # 분류 임계값 (percentile)
    WHALE_PERCENTILE = 90
    ALGO_PERCENTILE = 25
    MIN_TRADES_FOR_PERCENTILE = 20

    def __init__(self) -> None:
        self._buffer: deque[tuple[float, float, bool]] = deque(
            maxlen=self.MAX_BUFFER_SIZE
        )
        self._last_update_time: float = 0.0
        self._whale_threshold: float = 0.0
        self._algo_threshold: float = 0.0
        self._last_percentile_time: float = 0.0

    def update(self, msg: dict[str, Any]) -> None:
        """AggTrade 메시지 처리.

        Args:
            msg: Binance aggTrade 메시지
        """
        now = time.monotonic()
        qty = float(msg.get("q", msg.get("quantity", 0)))
        is_buyer_maker = msg.get("m", msg.get("is_buyer_maker", False))

        self._buffer.append((now, qty, is_buyer_maker))
        self._last_update_time = now

        # 주기적 percentile 재계산
        if now - self._last_percentile_time > self.PERCENTILE_RECALC_INTERVAL:
            self._recalculate_percentiles()

    def _recalculate_percentiles(self) -> None:
        """분류 임계값 재계산."""
        if len(self._buffer) < self.MIN_TRADES_FOR_PERCENTILE:
            return
        quantities = [qty for _, qty, _ in self._buffer]
        quantities.sort()
        n = len(quantities)
        self._whale_threshold = quantities[
            min(n - 1, int(n * self.WHALE_PERCENTILE / 100))
        ]
        self._algo_threshold = quantities[
            min(n - 1, int(n * self.ALGO_PERCENTILE / 100))
        ]
        self._last_percentile_time = time.monotonic()

    def snapshot(self) -> dict[str, Any] | None:
        """Whale Flow 스냅샷 반환.

        Returns:
            {"whale_buy_vol": float, "whale_sell_vol": float,
             "retail_buy_vol": float, "retail_sell_vol": float,
             "total_trades": int} or None
        """
        now = time.monotonic()
        if not self._buffer:
            return None

        if now - self._last_update_time > self.STALE_THRESHOLD_SEC:
            return None

        # 임계값이 아직 계산되지 않은 경우
        has_enough = len(self._buffer) >= self.MIN_TRADES_FOR_PERCENTILE
        if self._whale_threshold == 0 and has_enough:
            self._recalculate_percentiles()

        whale_buy = 0.0
        whale_sell = 0.0
        retail_buy = 0.0
        retail_sell = 0.0

        for _, qty, is_buyer_maker in self._buffer:
            # is_buyer_maker=True → seller is taker (sell)
            # is_buyer_maker=False → buyer is taker (buy)
            is_buy = not is_buyer_maker

            if self._whale_threshold > 0 and qty >= self._whale_threshold:
                if is_buy:
                    whale_buy += qty
                else:
                    whale_sell += qty
            elif self._algo_threshold > 0 and qty < self._algo_threshold:
                if is_buy:
                    retail_buy += qty
                else:
                    retail_sell += qty
            # algo 범위는 whale_snapshot에 포함하지 않음

        return {
            "whale_buy_vol": round(whale_buy, 4),
            "whale_sell_vol": round(whale_sell, 4),
            "retail_buy_vol": round(retail_buy, 4),
            "retail_sell_vol": round(retail_sell, 4),
            "total_trades": len(self._buffer),
        }


class BinanceWSManager:
    """Binance WebSocket Manager.

    depth@100ms + aggTrade 스트림을 관리하고
    OrderBookAggregator/TradeAggregator에 데이터를 전달.
    """

    RECONNECT_BASE_DELAY = 1.0
    RECONNECT_MAX_DELAY = 30.0
    MAX_RECONNECT_FAILURES = 5
    HEALTH_TIMEOUT_SEC = 30.0

    def __init__(
        self,
        symbol: str,
        testnet: bool = True,
        api_key: str = "",
        secret_key: str = "",
    ) -> None:
        self._symbol = symbol.lower()
        self._testnet = testnet
        self._api_key = api_key
        self._secret_key = secret_key

        self.orderbook_aggregator = OrderBookAggregator()
        self.trade_aggregator = TradeAggregator()

        self._running = False
        self._last_message_time: float = 0.0
        self._reconnect_failures: int = 0
        self._tasks: list[asyncio.Task[Any]] = []
        self._bsm: Any = None  # BinanceSocketManager
        self._log = logger.bind(module="ws_manager", symbol=symbol)

    @property
    def is_connected(self) -> bool:
        """건강 체크: 30초 이상 메시지 없으면 False."""
        if not self._running:
            return False
        if self._last_message_time == 0:
            return False
        return (time.monotonic() - self._last_message_time) < self.HEALTH_TIMEOUT_SEC

    async def start(self) -> None:
        """WebSocket 스트림 시작."""
        if self._running:
            return

        self._running = True
        self._reconnect_failures = 0
        self._log.info("WebSocket 스트림 시작")

        task = asyncio.create_task(self._run_streams())
        self._tasks.append(task)

    async def stop(self) -> None:
        """WebSocket 스트림 정지."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()

        if self._bsm:
            with contextlib.suppress(Exception):
                await self._bsm.close()
            self._bsm = None

        self._log.info("WebSocket 스트림 정지")

    async def _run_streams(self) -> None:
        """스트림 연결 및 재연결 루프."""
        delay = self.RECONNECT_BASE_DELAY

        while self._running:
            try:
                await self._connect_and_listen()
                # 정상 종료 시 delay 리셋
                delay = self.RECONNECT_BASE_DELAY
                self._reconnect_failures = 0
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._reconnect_failures += 1
                self._log.warning(
                    f"WebSocket 연결 실패 ({self._reconnect_failures}/"
                    f"{self.MAX_RECONNECT_FAILURES}): {e}"
                )

                if self._reconnect_failures >= self.MAX_RECONNECT_FAILURES:
                    self._log.error(
                        "WebSocket 재연결 한도 초과, REST 폴백으로 전환"
                    )
                    self._running = False
                    break

                await asyncio.sleep(delay)
                delay = min(delay * 2, self.RECONNECT_MAX_DELAY)

    async def _connect_and_listen(self) -> None:
        """실제 WS 연결 및 메시지 수신."""
        try:
            from binance import AsyncClient, BinanceSocketManager  # noqa: PLC0415
        except ImportError:
            self._log.error("python-binance 패키지가 필요합니다")
            raise

        client = await AsyncClient.create(
            api_key=self._api_key or "",
            api_secret=self._secret_key or "",
            testnet=self._testnet,
        )

        try:
            bsm = BinanceSocketManager(client)
            self._bsm = bsm

            # depth stream
            depth_socket = bsm.depth_socket(
                self._symbol + "usdt", depth=20, interval=100
            )
            # aggTrade stream
            trade_socket = bsm.aggtrade_socket(self._symbol + "usdt")

            async with depth_socket as ds, trade_socket as ts:
                # 두 스트림을 병렬로 수신
                depth_task = asyncio.create_task(
                    self._listen_depth(ds)
                )
                trade_task = asyncio.create_task(
                    self._listen_trades(ts)
                )

                done, pending = await asyncio.wait(
                    [depth_task, trade_task],
                    return_when=asyncio.FIRST_EXCEPTION,
                )

                for task in pending:
                    task.cancel()

                # 예외 전파
                for task in done:
                    if task.exception():
                        raise task.exception()  # type: ignore[misc]
        finally:
            await client.close_connection()

    async def _listen_depth(self, socket: Any) -> None:
        """Depth 스트림 수신."""
        while self._running:
            msg = await socket.recv()
            if msg:
                self.orderbook_aggregator.update(msg)
                self._last_message_time = time.monotonic()

    async def _listen_trades(self, socket: Any) -> None:
        """AggTrade 스트림 수신."""
        while self._running:
            msg = await socket.recv()
            if msg:
                self.trade_aggregator.update(msg)
                self._last_message_time = time.monotonic()
