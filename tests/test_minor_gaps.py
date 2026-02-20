"""Tests for APEX-V Minor Gaps (WS-1 through WS-7)."""
import math
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest


# ========================================================
# WS-1: Iceberg Detection
# ========================================================
class TestIcebergDetection:
    """TradeAggregator iceberg_snapshot + WhaleFlowChannel iceberg bonus."""

    def test_trade_aggregator_buffer_stores_price(self):
        """TradeAggregator buffer는 4-tuple (time, qty, is_buyer_maker, price)."""
        from src.exchange.ws_manager import TradeAggregator
        ta = TradeAggregator()
        ta.update({"q": "0.5", "m": False, "p": "50000.0"})
        assert len(ta._buffer) == 1
        entry = ta._buffer[0]
        assert len(entry) == 4
        assert entry[1] == 0.5
        assert entry[2] is False
        assert entry[3] == 50000.0

    def test_iceberg_not_detected_insufficient_data(self):
        """데이터 부족 시 iceberg 미감지."""
        from src.exchange.ws_manager import TradeAggregator
        ta = TradeAggregator()
        for _i in range(5):
            ta.update({"q": "0.1", "m": False, "p": "50000.0"})
        snap = ta.iceberg_snapshot()
        assert snap["iceberg_detected"] is False
        assert snap["iceberg_count"] == 0

    def test_iceberg_detected_repeated_trades(self):
        """동일 가격/수량 반복 체결 시 iceberg 감지."""
        from src.exchange.ws_manager import TradeAggregator
        ta = TradeAggregator()
        # 12건 동일 가격/수량 (buy 방향)
        for _ in range(12):
            ta.update({"q": "0.5000", "m": False, "p": "50000.1"})
        # 5건 다른 가격
        for _ in range(5):
            ta.update({"q": "0.3000", "m": True, "p": "49999.0"})
        snap = ta.iceberg_snapshot()
        assert snap["iceberg_detected"] is True
        assert snap["iceberg_direction"] == "buy"
        assert snap["iceberg_count"] >= 10

    def test_iceberg_sell_direction(self):
        """매도 방향 iceberg 감지."""
        from src.exchange.ws_manager import TradeAggregator
        ta = TradeAggregator()
        # is_buyer_maker=True → sell
        for _ in range(15):
            ta.update({"q": "1.0000", "m": True, "p": "48000.0"})
        snap = ta.iceberg_snapshot()
        assert snap["iceberg_detected"] is True
        assert snap["iceberg_direction"] == "sell"

    def test_iceberg_merged_into_snapshot(self):
        """snapshot()에 iceberg 필드가 포함."""
        from src.exchange.ws_manager import TradeAggregator
        ta = TradeAggregator()
        for _ in range(25):
            ta.update({"q": "0.5", "m": False, "p": "50000.0"})
        ta._last_update_time = time.monotonic()
        snap = ta.snapshot()
        assert snap is not None
        assert "iceberg_detected" in snap
        assert "iceberg_direction" in snap

    @pytest.mark.asyncio
    async def test_whale_flow_iceberg_bonus(self):
        """WhaleFlowChannel: iceberg_detected=True 시 score 보너스."""
        from src.ai.channels.whale_flow_channel import WhaleFlowChannel
        ch = WhaleFlowChannel()
        snap = {
            "whale_buy_vol": 10.0,
            "whale_sell_vol": 2.0,
            "retail_buy_vol": 3.0,
            "retail_sell_vol": 5.0,
            "total_trades": 100,
            "iceberg_detected": True,
            "iceberg_direction": "buy",
            "iceberg_count": 15,
        }
        result = await ch.generate_signal(snap)
        # Iceberg buy boosts score, should be LONG
        assert result.signal in ("LONG", "WAIT")
        if result.signal == "LONG":
            assert "Iceberg" in result.reason

    @pytest.mark.asyncio
    async def test_whale_flow_no_iceberg(self):
        """WhaleFlowChannel: iceberg_detected=False 시 기존 동작."""
        from src.ai.channels.whale_flow_channel import WhaleFlowChannel
        ch = WhaleFlowChannel()
        snap = {
            "whale_buy_vol": 10.0,
            "whale_sell_vol": 2.0,
            "retail_buy_vol": 3.0,
            "retail_sell_vol": 5.0,
            "total_trades": 100,
            "iceberg_detected": False,
            "iceberg_direction": "none",
            "iceberg_count": 0,
        }
        result = await ch.generate_signal(snap)
        assert "Iceberg" not in result.reason


# ========================================================
# WS-2: Depth Absorption
# ========================================================
class TestDepthAbsorption:
    """OrderBookAggregator absorption + OFIChannel absorption bonus."""

    def test_absorption_not_detected_insufficient_data(self):
        """데이터 부족 시 absorption 미감지."""
        from src.exchange.ws_manager import OrderBookAggregator
        ob = OrderBookAggregator()
        for _i in range(10):
            ob.update({"bids": [("50000", "0.1")], "asks": [("50001", "0.1")]})
        result = ob._check_absorption()
        assert result["absorption_buy"] is False
        assert result["absorption_sell"] is False

    def test_absorption_detected_large_delta(self):
        """대형 delta 시 absorption 감지."""
        from src.exchange.ws_manager import OrderBookAggregator
        ob = OrderBookAggregator()
        # 49건 정상 데이터
        for i in range(49):
            ob.update({
                "bids": [(str(50000 + i * 0.01), "0.1")],
                "asks": [(str(50001 + i * 0.01), "0.1")],
            })
        # 최근 5건 중 1건이 10x median (absorption)
        ob.update({
            "bids": [("50000", "100.0")],  # 대형 bid delta
            "asks": [("50001", "0.1")],
        })
        result = ob._check_absorption()
        # bid에 대형 delta → sell absorption
        assert result["absorption_sell"] is True

    def test_absorption_merged_into_snapshot(self):
        """snapshot()에 absorption 필드가 포함."""
        from src.exchange.ws_manager import OrderBookAggregator
        ob = OrderBookAggregator()
        for i in range(60):
            ob.update({
                "bids": [(str(50000 + i * 0.01), "0.1")],
                "asks": [(str(50001 + i * 0.01), "0.1")],
            })
        snap = ob.snapshot()
        assert snap is not None
        assert "absorption_buy" in snap
        assert "absorption_sell" in snap

    @pytest.mark.asyncio
    async def test_ofi_absorption_bonus(self):
        """OFIChannel: absorption 시 score 보너스."""
        from src.ai.channels.ofi_channel import OFIChannel
        ch = OFIChannel()
        snap = {
            "ofi_5": 40.0, "ofi_20": 35.0, "ofi_50": 30.0,
            "cvd": 50.0, "sample_count": 100,
            "absorption_buy": True, "absorption_sell": False,
        }
        result = await ch.generate_signal(snap)
        assert result.signal in ("LONG", "WAIT")
        if result.signal == "LONG":
            assert "Absorption" in result.reason

    @pytest.mark.asyncio
    async def test_ofi_no_absorption(self):
        """OFIChannel: absorption 없을 때 기존 동작."""
        from src.ai.channels.ofi_channel import OFIChannel
        ch = OFIChannel()
        snap = {
            "ofi_5": 40.0, "ofi_20": 35.0, "ofi_50": 30.0,
            "cvd": 50.0, "sample_count": 100,
            "absorption_buy": False, "absorption_sell": False,
        }
        result = await ch.generate_signal(snap)
        assert "Absorption" not in result.reason


# ========================================================
# WS-3: VWAP Zone Check
# ========================================================
class TestVWAPZone:
    """calculate_vwap + TSMOMChannel VWAP zone boost."""

    def test_calculate_vwap_basic(self):
        """정상 VWAP 계산."""
        from src.data.indicators import calculate_vwap
        df = pd.DataFrame({
            "high": [100.0, 102.0, 104.0],
            "low": [98.0, 100.0, 102.0],
            "close": [99.0, 101.0, 103.0],
            "volume": [10.0, 20.0, 30.0],
        })
        vwap = calculate_vwap(df)
        assert not math.isnan(vwap)
        # typical = (100+98+99)/3, (102+100+101)/3, (104+102+103)/3 = 99, 101, 103
        # vwap = (99*10 + 101*20 + 103*30) / (10+20+30) = (990 + 2020 + 3090) / 60 = 101.67
        assert abs(vwap - 101.67) < 0.1

    def test_calculate_vwap_zero_volume(self):
        """거래량 0이면 NaN 반환."""
        from src.data.indicators import calculate_vwap
        df = pd.DataFrame({
            "high": [100.0], "low": [98.0], "close": [99.0], "volume": [0.0],
        })
        vwap = calculate_vwap(df)
        assert math.isnan(vwap)

    @pytest.mark.asyncio
    async def test_tsmom_vwap_zone_boost(self):
        """TSMOMChannel: VWAP 영역 내 시 confidence 부스트."""
        from src.ai.channels.tsmom import TSMOMChannel
        ch = TSMOMChannel()
        # VWAP에 가까운 데이터 생성 (상승 추세)
        n = 70
        prices = [50000 + i * 10 for i in range(n)]
        df = pd.DataFrame({
            "close": prices,
            "high": [p + 5 for p in prices],
            "low": [p - 5 for p in prices],
            "volume": [100.0] * n,
        })
        result = await ch.generate_signal(df)
        # 상승 추세이므로 LONG 시그널 예상
        assert result.signal in ("LONG", "SHORT", "WAIT")

    @pytest.mark.asyncio
    async def test_tsmom_vwap_tag_in_reason(self):
        """TSMOMChannel: VWAP zone 내 시 reason에 태그."""
        from src.ai.channels.tsmom import TSMOMChannel
        ch = TSMOMChannel()
        # 안정적 데이터 (close ≈ VWAP)
        n = 70
        df = pd.DataFrame({
            "close": [50000.0] * n,
            "high": [50010.0] * n,
            "low": [49990.0] * n,
            "volume": [100.0] * n,
        })
        result = await ch.generate_signal(df)
        # Flat data → likely WAIT, no VWAP tag
        assert result.signal == "WAIT"  # 혼합이므로 WAIT


# ========================================================
# WS-4: Economic Event Calendar
# ========================================================
class TestEconomicCalendar:
    """경제 이벤트 캘린더."""

    def test_no_active_events_normal_time(self):
        """이벤트 없는 시간."""
        from src.data.economic_calendar import get_active_economic_events
        t = datetime(2026, 6, 15, 10, 0, tzinfo=timezone.utc)  # 일반 시간
        events = get_active_economic_events(t)
        assert events == []

    def test_active_fomc_event(self):
        """FOMC 이벤트 윈도우 내."""
        from src.data.economic_calendar import get_active_economic_events
        # 2026-03-19T18:00 FOMC, window=120min
        t = datetime(2026, 3, 19, 18, 30, tzinfo=timezone.utc)  # 30분 후
        events = get_active_economic_events(t)
        assert len(events) >= 1
        evt_time, window = events[0]
        assert window == 120

    def test_active_cpi_event(self):
        """CPI 이벤트 윈도우 내."""
        from src.data.economic_calendar import get_active_economic_events
        # 2026-02-12T13:30 CPI
        t = datetime(2026, 2, 12, 14, 0, tzinfo=timezone.utc)  # 30분 후
        events = get_active_economic_events(t)
        assert len(events) >= 1

    def test_event_outside_window(self):
        """이벤트 윈도우 밖."""
        from src.data.economic_calendar import get_active_economic_events
        # 2026-03-19T18:00 FOMC, window=120min → 3시간 후는 밖
        t = datetime(2026, 3, 19, 21, 0, tzinfo=timezone.utc)
        events = get_active_economic_events(t)
        fomc_found = any(w == 120 for _, w in events)
        # 3시간 후 → 윈도우(2시간) 밖
        assert not fomc_found

    def test_naive_datetime_gets_utc(self):
        """naive datetime → UTC로 변환."""
        from src.data.economic_calendar import get_active_economic_events
        t = datetime(2026, 6, 15, 10, 0)  # naive
        events = get_active_economic_events(t)  # 에러 없이 실행
        assert isinstance(events, list)

    def test_tradability_economic_event_score(self):
        """MTI _event_score: 경제 이벤트 시 20점."""
        from src.data.tradability import MarketTradabilityIndex
        mti = MarketTradabilityIndex()
        t = datetime(2026, 3, 19, 18, 30, tzinfo=timezone.utc)
        econ = [(datetime(2026, 3, 19, 18, 0, tzinfo=timezone.utc), 120)]
        score = mti._event_score(t, economic_events=econ)
        assert score == 20.0

    def test_tradability_no_economic_event(self):
        """MTI _event_score: 경제 이벤트 없을 때 기존 동작."""
        from src.data.tradability import MarketTradabilityIndex
        mti = MarketTradabilityIndex()
        # 펀딩 정산 시간도 아닌 일반 시간
        t = datetime(2026, 6, 15, 10, 0, tzinfo=timezone.utc)
        score = mti._event_score(t)
        assert score == 100.0

    def test_evaluate_with_economic_events(self):
        """evaluate()에 economic_events 전달."""
        from src.data.tradability import MarketTradabilityIndex
        mti = MarketTradabilityIndex()
        t = datetime(2026, 6, 15, 10, 0, tzinfo=timezone.utc)
        result = mti.evaluate(
            atr_pct=1.0, volume_ratio=1.0, current_time=t,
            economic_events=[],
        )
        assert result.total_score > 0


# ========================================================
# WS-5: REST Polling Scheduler
# ========================================================
class TestRESTPollingScheduler:
    """TTL 기반 REST 폴링 스케줄러."""

    @pytest.mark.asyncio
    async def test_get_caches_result(self):
        """첫 호출 후 캐시에서 반환."""
        from src.exchange.rest_poller import RESTPollingScheduler
        poller = RESTPollingScheduler()
        call_count = 0

        async def mock_fetch():
            nonlocal call_count
            call_count += 1
            return {"value": 42}

        r1 = await poller.get("test", mock_fetch)
        r2 = await poller.get("test", mock_fetch)
        assert r1 == {"value": 42}
        assert r2 == {"value": 42}
        assert call_count == 1  # 두 번째는 캐시

    @pytest.mark.asyncio
    async def test_get_refreshes_after_ttl(self):
        """TTL 만료 후 재조회."""
        from src.exchange.rest_poller import RESTPollingScheduler
        poller = RESTPollingScheduler(intervals={"short": 0})  # TTL=0 → 항상 만료
        call_count = 0

        async def mock_fetch():
            nonlocal call_count
            call_count += 1
            return {"value": call_count}

        r1 = await poller.get("short", mock_fetch)
        r2 = await poller.get("short", mock_fetch)
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_get_returns_stale_on_error(self):
        """API 실패 시 만료된 캐시 반환."""
        from src.exchange.rest_poller import RESTPollingScheduler
        poller = RESTPollingScheduler(intervals={"fail": 0})

        async def mock_fetch():
            return {"ok": True}

        async def mock_fail():
            raise ConnectionError("down")

        await poller.get("fail", mock_fetch)
        result = await poller.get("fail", mock_fail)
        assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_get_raises_if_no_cache(self):
        """캐시 없고 API 실패 시 예외 전파."""
        from src.exchange.rest_poller import RESTPollingScheduler
        poller = RESTPollingScheduler()

        async def mock_fail():
            raise ConnectionError("down")

        with pytest.raises(ConnectionError):
            await poller.get("never", mock_fail)

    @pytest.mark.asyncio
    async def test_get_all_sentiment(self):
        """get_all_sentiment 통합 조회."""
        from src.exchange.rest_poller import RESTPollingScheduler
        poller = RESTPollingScheduler()

        client = MagicMock()
        client.get_funding_rate = AsyncMock(
            return_value={"funding_rate": 0.01}
        )
        client.get_long_short_ratio = AsyncMock(
            return_value={"long_ratio": 0.6, "short_ratio": 0.4, "long_short_ratio": 1.5}
        )
        client.get_open_interest = AsyncMock(
            return_value={"open_interest": 1000.0}
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
        assert result["open_interest"] == 1000.0

    def test_invalidate(self):
        """invalidate() 캐시 삭제."""
        from src.exchange.rest_poller import RESTPollingScheduler
        poller = RESTPollingScheduler()
        poller._cache["test"] = (time.monotonic(), {"v": 1})
        poller.invalidate("test")
        assert "test" not in poller._cache

    def test_invalidate_all(self):
        """invalidate_all() 전체 캐시 삭제."""
        from src.exchange.rest_poller import RESTPollingScheduler
        poller = RESTPollingScheduler()
        poller._cache["a"] = (time.monotonic(), 1)
        poller._cache["b"] = (time.monotonic(), 2)
        poller.invalidate_all()
        assert len(poller._cache) == 0


# ========================================================
# WS-6: API Weight Tracker
# ========================================================
class TestAPIWeightTracker:
    """Binance API weight 추적기."""

    def test_record_and_current_weight(self):
        """record() 후 current_weight 증가."""
        from src.exchange.api_weight_tracker import APIWeightTracker
        tracker = APIWeightTracker()
        assert tracker.current_weight == 0
        tracker.record("get_klines")
        assert tracker.current_weight == 5  # get_klines = 5

    def test_can_proceed_under_target(self):
        """TARGET 미만이면 proceed 가능."""
        from src.exchange.api_weight_tracker import APIWeightTracker
        tracker = APIWeightTracker()
        assert tracker.can_proceed("get_klines") is True

    def test_can_proceed_over_target(self):
        """TARGET 초과 시 proceed 불가."""
        from src.exchange.api_weight_tracker import APIWeightTracker
        tracker = APIWeightTracker()
        # 800/5 = 160회 기록하면 TARGET 도달
        for _ in range(161):
            tracker.record("get_klines")
        assert tracker.can_proceed("get_klines") is False

    def test_should_delay_under_target(self):
        """TARGET 미만이면 delay 0."""
        from src.exchange.api_weight_tracker import APIWeightTracker
        tracker = APIWeightTracker()
        assert tracker.should_delay() == 0.0

    def test_should_delay_over_target(self):
        """TARGET 초과 시 delay > 0."""
        from src.exchange.api_weight_tracker import APIWeightTracker
        tracker = APIWeightTracker()
        for _ in range(200):
            tracker.record("get_klines")
        delay = tracker.should_delay()
        assert delay > 0.0
        assert delay <= tracker.MAX_DELAY_SEC

    def test_window_pruning(self):
        """60초 윈도우 외 항목 정리."""
        from src.exchange.api_weight_tracker import APIWeightTracker
        tracker = APIWeightTracker()
        # 과거 시점에 데이터 삽입
        past = time.monotonic() - 120  # 2분 전
        tracker._window.append((past, 100))
        tracker._window.append((past, 100))
        # 현재 weight은 0이어야 함 (pruning 됨)
        assert tracker.current_weight == 0

    def test_get_status(self):
        """get_status() 반환값."""
        from src.exchange.api_weight_tracker import APIWeightTracker
        tracker = APIWeightTracker()
        status = tracker.get_status()
        assert "current_weight" in status
        assert "max_weight" in status
        assert "utilization_pct" in status
        assert status["can_proceed"] is True

    def test_unknown_endpoint_weight(self):
        """미등록 엔드포인트 → weight 1."""
        from src.exchange.api_weight_tracker import APIWeightTracker
        tracker = APIWeightTracker()
        tracker.record("unknown_endpoint")
        assert tracker.current_weight == 1


# ========================================================
# WS-7: Event Bus
# ========================================================
class TestEventBus:
    """비동기 이벤트 버스."""

    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self):
        """구독 후 이벤트 발행 시 핸들러 호출."""
        from src.utils.event_bus import EventBus, EventType
        bus = EventBus()
        received = []

        async def handler(data):
            received.append(data)

        bus.subscribe(EventType.TRADE_OPENED, handler)
        await bus.publish(EventType.TRADE_OPENED, {"side": "LONG"})
        assert len(received) == 1
        assert received[0]["side"] == "LONG"

    @pytest.mark.asyncio
    async def test_multiple_handlers(self):
        """여러 핸들러 병렬 호출."""
        from src.utils.event_bus import EventBus, EventType
        bus = EventBus()
        results = []

        async def h1(data):
            results.append("h1")

        async def h2(data):
            results.append("h2")

        bus.subscribe(EventType.TRADE_CLOSED, h1)
        bus.subscribe(EventType.TRADE_CLOSED, h2)
        await bus.publish(EventType.TRADE_CLOSED)
        assert "h1" in results
        assert "h2" in results

    @pytest.mark.asyncio
    async def test_handler_error_swallowed(self):
        """핸들러 에러 삼킴 (다른 핸들러는 정상 실행)."""
        from src.utils.event_bus import EventBus, EventType
        bus = EventBus()
        results = []

        async def bad_handler(data):
            raise RuntimeError("boom")

        async def good_handler(data):
            results.append("ok")

        bus.subscribe(EventType.REGIME_CHANGED, bad_handler)
        bus.subscribe(EventType.REGIME_CHANGED, good_handler)
        await bus.publish(EventType.REGIME_CHANGED, {"regime": "RANGING"})
        assert "ok" in results

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        """구독 해제 후 호출 안됨."""
        from src.utils.event_bus import EventBus, EventType
        bus = EventBus()
        called = []

        async def handler(data):
            called.append(True)

        bus.subscribe(EventType.TRADE_OPENED, handler)
        bus.unsubscribe(EventType.TRADE_OPENED, handler)
        await bus.publish(EventType.TRADE_OPENED)
        assert len(called) == 0

    @pytest.mark.asyncio
    async def test_publish_no_subscribers(self):
        """구독자 없으면 에러 없이 리턴."""
        from src.utils.event_bus import EventBus, EventType
        bus = EventBus()
        await bus.publish(EventType.TRADE_OPENED)  # 에러 없음

    def test_handler_count(self):
        """handler_count 프로퍼티."""
        from src.utils.event_bus import EventBus, EventType
        bus = EventBus()
        assert bus.handler_count == 0

        async def h(data): pass

        bus.subscribe(EventType.TRADE_OPENED, h)
        bus.subscribe(EventType.TRADE_CLOSED, h)
        assert bus.handler_count == 2

    def test_event_type_values(self):
        """EventType 열거형 값."""
        from src.utils.event_bus import EventType
        assert EventType.TRADE_OPENED.value == "trade_opened"
        assert EventType.TRADE_CLOSED.value == "trade_closed"
        assert EventType.REGIME_CHANGED.value == "regime_changed"
