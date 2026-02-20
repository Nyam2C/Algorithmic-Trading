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

    # WS-2: Depth Absorption
    ABSORPTION_MULTIPLIER = 5.0
    ABSORPTION_LOOKBACK = 50
    ABSORPTION_RECENT = 5

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

        result = {
            "ofi_5": round(ofi_5, 4),
            "ofi_20": round(ofi_20, 4),
            "ofi_50": round(ofi_50, 4),
            "cvd": round(cvd, 4),
            "sample_count": n,
        }
        # Absorption 데이터 병합
        absorption = self._check_absorption()
        result.update(absorption)
        return result

    def _check_absorption(self) -> dict[str, bool]:
        """Depth Absorption 감지.

        최근 delta 중앙값 대비 5x 이상 큰 delta → absorption.
        bid_delta 흡수 → sell absorption (매도벽 흡수).
        ask_delta 흡수 → buy absorption (매수벽 흡수).

        Returns:
            {"absorption_buy": bool, "absorption_sell": bool}
        """
        n = len(self._buffer)
        if n < self.ABSORPTION_LOOKBACK:
            return {"absorption_buy": False, "absorption_sell": False}

        items = list(self._buffer)
        lookback = items[-self.ABSORPTION_LOOKBACK:]

        bid_deltas = [abs(b) for _, b, _ in lookback]
        ask_deltas = [abs(a) for _, _, a in lookback]

        bid_median = statistics.median(bid_deltas) if bid_deltas else 0.0
        ask_median = statistics.median(ask_deltas) if ask_deltas else 0.0

        recent = items[-self.ABSORPTION_RECENT:]

        # ask absorption → buy signal (large ask consumed)
        absorption_buy = False
        if ask_median > 0:
            for _, _, a in recent:
                if abs(a) > ask_median * self.ABSORPTION_MULTIPLIER:
                    absorption_buy = True
                    break

        # bid absorption → sell signal (large bid consumed)
        absorption_sell = False
        if bid_median > 0:
            for _, b, _ in recent:
                if abs(b) > bid_median * self.ABSORPTION_MULTIPLIER:
                    absorption_sell = True
                    break

        return {"absorption_buy": absorption_buy, "absorption_sell": absorption_sell}


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
        self._buffer: deque[tuple[float, float, bool, float]] = deque(
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
        price = float(msg.get("p", msg.get("price", 0)))

        self._buffer.append((now, qty, is_buyer_maker, price))
        self._last_update_time = now

        # 주기적 percentile 재계산
        if now - self._last_percentile_time > self.PERCENTILE_RECALC_INTERVAL:
            self._recalculate_percentiles()

    def _recalculate_percentiles(self) -> None:
        """분류 임계값 재계산."""
        if len(self._buffer) < self.MIN_TRADES_FOR_PERCENTILE:
            return
        quantities = [qty for _, qty, _, _ in self._buffer]
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

        for _, qty, is_buyer_maker, _ in self._buffer:
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

        result = {
            "whale_buy_vol": round(whale_buy, 4),
            "whale_sell_vol": round(whale_sell, 4),
            "retail_buy_vol": round(retail_buy, 4),
            "retail_sell_vol": round(retail_sell, 4),
            "total_trades": len(self._buffer),
        }
        # Iceberg 데이터 병합
        iceberg = self.iceberg_snapshot()
        result.update(iceberg)
        return result

    # Iceberg 감지 상수
    ICEBERG_REPEAT_THRESHOLD = 10

    def iceberg_snapshot(self) -> dict[str, Any]:
        """Iceberg 주문 감지 스냅샷.

        동일 가격/수량 그룹에서 반복 체결 패턴을 감지.
        10건+ 동일 그룹 → iceberg_detected=True.

        Returns:
            {"iceberg_detected": bool, "iceberg_direction": str,
             "iceberg_count": int}
        """
        if len(self._buffer) < self.ICEBERG_REPEAT_THRESHOLD:
            return {
                "iceberg_detected": False,
                "iceberg_direction": "none",
                "iceberg_count": 0,
            }

        groups: dict[tuple[float, float], list[bool]] = {}
        for _, qty, is_buyer_maker, price in self._buffer:
            key = (round(price, 1), round(qty, 4))
            if key not in groups:
                groups[key] = []
            groups[key].append(is_buyer_maker)

        best_count = 0
        best_direction = "none"
        for _key, makers in groups.items():
            if (
                len(makers) >= self.ICEBERG_REPEAT_THRESHOLD
                and len(makers) > best_count
            ):
                    best_count = len(makers)
                    buy_count = sum(1 for m in makers if not m)
                    sell_count = sum(1 for m in makers if m)
                    if buy_count > sell_count:
                        best_direction = "buy"
                    elif sell_count > buy_count:
                        best_direction = "sell"
                    else:
                        best_direction = "mixed"

        return {
            "iceberg_detected": best_count >= self.ICEBERG_REPEAT_THRESHOLD,
            "iceberg_direction": best_direction,
            "iceberg_count": best_count,
        }




class LiquidationAggregator:
    """강제청산 이벤트 집계기.

    forceOrder 메시지에서 청산 이벤트를 수집하여 캐스케이드 감지용 데이터 제공.
    """

    MAX_BUFFER_SIZE = 3000
    STALE_THRESHOLD_SEC = 60.0  # 청산은 덜 빈번

    def __init__(self) -> None:
        self._buffer: deque[tuple[float, str, float, float]] = deque(
            maxlen=self.MAX_BUFFER_SIZE
        )
        self._last_update_time: float = 0.0

    def update(self, msg: dict[str, Any]) -> None:
        """ForceOrder 메시지 처리.

        Args:
            msg: Binance forceOrder 메시지 {"o": {"S": side, "q": qty, "p": price}}
        """
        now = time.monotonic()
        order = msg.get("o", msg)
        side = str(order.get("S", "")).upper()
        if side not in ("BUY", "SELL"):
            return
        try:
            qty = float(order.get("q", 0))
            price = float(order.get("p", 0))
        except (ValueError, TypeError):
            return
        if qty <= 0 or price <= 0:
            return

        self._buffer.append((now, side, qty, price))
        self._last_update_time = now

    def snapshot(self, window: float = 30.0) -> dict[str, Any] | None:
        """청산 스냅샷 반환.

        Args:
            window: 윈도우 크기 (초)

        Returns:
            {"count": int, "buy_vol": float, "sell_vol": float,
             "total_vol": float, "events": list} or None if stale
        """
        now = time.monotonic()
        if not self._buffer:
            return None
        if now - self._last_update_time > self.STALE_THRESHOLD_SEC:
            return None

        cutoff = now - window
        events: list[tuple[float, str, float, float]] = []
        buy_vol = 0.0
        sell_vol = 0.0
        for ts, side, qty, price in self._buffer:
            if ts >= cutoff:
                events.append((ts, side, qty, price))
                if side == "BUY":
                    buy_vol += qty
                else:
                    sell_vol += qty

        return {
            "count": len(events),
            "buy_vol": round(buy_vol, 4),
            "sell_vol": round(sell_vol, 4),
            "total_vol": round(buy_vol + sell_vol, 4),
            "events": events,
        }

    def count_in_window(self, window: float = 30.0) -> int:
        """윈도우 내 청산 건수."""
        now = time.monotonic()
        cutoff = now - window
        return sum(1 for ts, _, _, _ in self._buffer if ts >= cutoff)

    def daily_average(self) -> float:
        """버퍼 기반 일평균 청산 건수 추정."""
        _min_for_avg = 2
        if len(self._buffer) < _min_for_avg:
            return 0.0
        first_ts = self._buffer[0][0]
        last_ts = self._buffer[-1][0]
        span = last_ts - first_ts
        if span <= 0:
            return 0.0
        rate_per_sec = len(self._buffer) / span
        return rate_per_sec * 86400  # 24h

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
        use_force_order: bool = False,
    ) -> None:
        self._symbol = symbol.lower()
        self._testnet = testnet
        self._api_key = api_key
        self._secret_key = secret_key
        self._use_force_order = use_force_order

        self.orderbook_aggregator = OrderBookAggregator()
        self.trade_aggregator = TradeAggregator()
        self.liquidation_aggregator = LiquidationAggregator()

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

            # forceOrder stream (optional)
            force_socket = None
            if self._use_force_order:
                force_socket = bsm.symbol_ticker_futures_socket(
                    self._symbol + "usdt"
                )

            async with depth_socket as ds, trade_socket as ts:
                # 두 스트림을 병렬로 수신
                depth_task = asyncio.create_task(
                    self._listen_depth(ds)
                )
                trade_task = asyncio.create_task(
                    self._listen_trades(ts)
                )

                tasks = [depth_task, trade_task]

                # forceOrder stream 추가
                if self._use_force_order and force_socket:
                    force_task = asyncio.create_task(
                        self._listen_force_orders_rest()
                    )
                    tasks.append(force_task)

                done, pending = await asyncio.wait(
                    tasks,
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
    async def _listen_force_orders_rest(self) -> None:
        """ForceOrder 이벤트 폴링 (REST fallback).

        Binance python-binance 라이브러리의 multiplex 지원 한계로
        REST polling 방식으로 청산 데이터를 수집.
        """
        while self._running:
            try:
                from binance import AsyncClient  # noqa: PLC0415
                client = await AsyncClient.create(
                    api_key=self._api_key or "",
                    api_secret=self._secret_key or "",
                    testnet=self._testnet,
                )
                try:
                    trades = await client.futures_liquidation_orders(
                        symbol=self._symbol.upper() + "USDT",
                        limit=50,
                    )
                    for trade in trades:
                        self.liquidation_aggregator.update({
                            "o": {
                                "S": trade.get("side", ""),
                                "q": trade.get("origQty", "0"),
                                "p": trade.get("price", "0"),
                            }
                        })
                        self._last_message_time = time.monotonic()
                finally:
                    await client.close_connection()
            except Exception as e:
                self._log.debug(f"forceOrder 폴링 실패: {e}")
            await asyncio.sleep(5.0)  # 5초 간격 폴링
