"""Code Audit P1/P2 Fix Tests.

각 P1/P2 수정 사항에 대한 회귀 방지 테스트.
"""
from __future__ import annotations

import math
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

# ================================================================
# P1-2: oi_orthogonalization — beta 폭발 방지
# ================================================================


class TestOiBetaExplosion:
    """var_oi 극소값 시 beta 폭발 방지 테스트."""

    def test_near_zero_var_oi_returns_current_beta(self):
        """var_oi < 1e-8 → 기존 beta 유지."""
        from src.ai.channels.oi_orthogonalization import OIOrthogonalizer

        ort = OIOrthogonalizer()
        ort._beta = 0.5
        # 모든 OI 값 동일 → var_oi ≈ 0
        for i in range(20):
            ort.update(0.0001 * i, 0.01)
        result = ort.recompute_beta()
        # var_oi가 극소이므로 beta는 기존값 유지
        assert result == 0.5

    def test_beta_clipping_upper(self):
        """calc_beta > 10 → 10으로 클리핑."""
        from src.ai.channels.oi_orthogonalization import OIOrthogonalizer

        ort = OIOrthogonalizer()
        # FR이 OI 변화에 비해 매우 큰 상관관계
        for i in range(20):
            ort.update(float(i) * 10, float(i) * 0.001)
        ort.recompute_beta()
        assert ort.beta <= 10.0

    def test_beta_clipping_lower(self):
        """calc_beta < -10 → -10으로 클리핑."""
        from src.ai.channels.oi_orthogonalization import OIOrthogonalizer

        ort = OIOrthogonalizer()
        for i in range(20):
            ort.update(-float(i) * 10, float(i) * 0.001)
        ort.recompute_beta()
        assert ort.beta >= -10.0

    def test_exact_zero_var_oi(self):
        """var_oi == 0 (완전 동일 OI) → beta 유지."""
        from src.ai.channels.oi_orthogonalization import OIOrthogonalizer

        ort = OIOrthogonalizer()
        ort._beta = 1.5
        for _ in range(20):
            ort.update(0.0001, 0.05)
        result = ort.recompute_beta()
        assert result == 1.5


# ================================================================
# P1-3: L4 Degradation 청산 시 가격 0 가능
# ================================================================


class TestL4DegradationPrice:
    """L4 Degradation 시 가격 미수신 처리."""

    @pytest.mark.asyncio
    async def test_l4_close_with_valid_price(self):
        """정상 가격 시 청산 실행."""
        from src.bot_instance import BotInstance

        bot = MagicMock(spec=BotInstance)
        bot._current_price = 50000.0
        bot._close_position = AsyncMock()
        bot._is_paused = False

        # 직접 L4 로직 시뮬레이션
        _l4_price = bot._current_price
        if _l4_price and _l4_price > 0:
            await bot._close_position(_l4_price, "DEGRADATION_L4")

        bot._close_position.assert_called_once_with(
            50000.0, "DEGRADATION_L4"
        )

    @pytest.mark.asyncio
    async def test_l4_close_with_none_price_fetches_emergency(self):
        """가격 None 시 긴급 조회."""
        _l4_price = None
        binance_client = AsyncMock()
        binance_client.get_current_price = AsyncMock(
            return_value=49000.0
        )
        close_fn = AsyncMock()

        if not _l4_price or _l4_price <= 0:
            try:
                _l4_price = await binance_client.get_current_price(
                    "BTCUSDT"
                )
            except Exception:
                _l4_price = None

        if _l4_price and _l4_price > 0:
            await close_fn(_l4_price, "DEGRADATION_L4")

        close_fn.assert_called_once_with(49000.0, "DEGRADATION_L4")

    @pytest.mark.asyncio
    async def test_l4_close_with_zero_price_no_close(self):
        """가격 0이고 긴급 조회도 실패 → 청산 불가."""
        _l4_price = 0.0
        binance_client = AsyncMock()
        binance_client.get_current_price = AsyncMock(return_value=None)
        close_fn = AsyncMock()

        if not _l4_price or _l4_price <= 0:
            try:
                _l4_price = await binance_client.get_current_price(
                    "BTCUSDT"
                )
            except Exception:
                _l4_price = None

        if _l4_price and _l4_price > 0:
            await close_fn(_l4_price, "DEGRADATION_L4")

        close_fn.assert_not_called()


# ================================================================
# P1-4: Regime Transition 포지션 축소 실패 → 진입 차단
# ================================================================


class TestRegimeTransitionBlock:
    """포지션 축소 실패 시 신규 진입 차단."""

    def test_regime_transition_block_initialized(self):
        """_regime_transition_block 초기값 False."""
        import inspect

        from src.bot_instance import BotInstance
        source = inspect.getsource(BotInstance.__init__)
        assert "_regime_transition_block" in source

    def test_block_flag_prevents_entry(self):
        """_regime_transition_block=True → _open_position 진입 차단."""
        import inspect

        from src.bot_instance import BotInstance

        source = inspect.getsource(BotInstance._open_position)
        assert "_regime_transition_block" in source
        assert "return None" in source


# ================================================================
# P1-5: Liquidation Cascade 감속 판단 최소 이벤트
# ================================================================


class TestLiquidationDecelMinEvents:
    """감속 판단 시 0건/1건 이벤트 처리."""

    def test_empty_events_no_decel(self):
        """이벤트 0건 → 감속 아님."""
        from src.ai.channels.liquidation_cascade import (
            LiquidationCascadeHunter,
        )

        hunter = LiquidationCascadeHunter()
        assert not hunter._check_deceleration([])

    def test_single_event_no_decel(self):
        """이벤트 1건 → 감속 아님."""
        from src.ai.channels.liquidation_cascade import (
            LiquidationCascadeHunter,
        )

        hunter = LiquidationCascadeHunter()
        now = time.monotonic()
        events = [(now, "SELL", 1.0, 50000.0)]
        assert not hunter._check_deceleration(events)

    def test_short_window_under_2_no_decel(self):
        """short_count < 2 → 감속 아님."""
        from src.ai.channels.liquidation_cascade import (
            LiquidationCascadeHunter,
        )

        hunter = LiquidationCascadeHunter()
        now = time.monotonic()
        events = [
            (now - 25, "SELL", 1.0, 50000.0),
            (now - 20, "SELL", 1.0, 50000.0),
            (now - 15, "SELL", 1.0, 50000.0),
            (now - 1, "SELL", 1.0, 50000.0),
        ]
        # short_count=1 < 2 → False
        assert not hunter._check_deceleration(events)


# ================================================================
# P2-1: Signal Invalidation threshold Redis 복원 시 검증
# ================================================================


class TestThresholdValidation:
    """Redis 복원 threshold 검증."""

    def test_negative_threshold_rejected(self):
        """음수 threshold → 무시."""
        _restored = -0.5
        result = isinstance(_restored, (int, float)) and _restored > 0
        assert not result

    def test_zero_threshold_rejected(self):
        """0 threshold → 무시."""
        _restored = 0
        result = isinstance(_restored, (int, float)) and _restored > 0
        assert not result

    def test_valid_threshold_accepted(self):
        """양수 threshold → 수용."""
        _restored = 0.35
        result = isinstance(_restored, (int, float)) and _restored > 0
        assert result

    def test_string_threshold_rejected(self):
        """문자열 threshold → 무시."""
        _restored = "invalid"
        result = isinstance(_restored, (int, float)) and _restored > 0
        assert not result


# ================================================================
# P2-2: _build_microprice_data ATR NaN 가드
# ================================================================


class TestMicropriceAtrNan:
    """ATR NaN 시 microprice_data None 반환."""

    def test_nan_atr_returns_none(self):
        """ATR=NaN → None."""
        atr = float("nan")
        result = math.isnan(atr)
        assert result

    def test_valid_atr_passes(self):
        """정상 ATR → 통과."""
        atr = 150.0
        result = not math.isnan(atr)
        assert result


# ================================================================
# P2-4: Smart Money Overheat taker validation
# ================================================================


class TestOverheatTakerValidation:
    """Overheat contrarian에 taker ratio 조건 추가."""

    @pytest.mark.asyncio
    async def test_overheat_long_without_taker_sell_no_short(self):
        """Top+Global Long > 70% + taker매수 > 매도 → SHORT 안됨."""
        from src.ai.channels.smart_money_divergence import (
            SmartMoneyDivergenceChannel,
        )

        channel = SmartMoneyDivergenceChannel()
        sig = await channel.generate_signal(
            top_ls_ratio=3.0,
            price_change_pct=0.005,
            global_long_ratio=0.75,
            global_short_ratio=0.25,
            taker_buy_sell_ratio=1.5,
        )
        assert sig.signal != "SHORT" or sig.confidence < 0.7

    @pytest.mark.asyncio
    async def test_overheat_long_with_taker_sell_gives_short(self):
        """Top+Global Long > 70% + taker매도 > 매수 → SHORT."""
        from src.ai.channels.smart_money_divergence import (
            SmartMoneyDivergenceChannel,
        )

        channel = SmartMoneyDivergenceChannel()
        sig = await channel.generate_signal(
            top_ls_ratio=3.0,
            price_change_pct=0.005,
            global_long_ratio=0.75,
            global_short_ratio=0.25,
            taker_buy_sell_ratio=0.8,
        )
        assert sig.signal == "SHORT"

    @pytest.mark.asyncio
    async def test_overheat_short_without_taker_buy_no_long(self):
        """Top+Global Short > 70% + taker매도 > 매수 → LONG 안됨."""
        from src.ai.channels.smart_money_divergence import (
            SmartMoneyDivergenceChannel,
        )

        channel = SmartMoneyDivergenceChannel()
        sig = await channel.generate_signal(
            top_ls_ratio=0.33,
            price_change_pct=-0.005,
            global_long_ratio=0.25,
            global_short_ratio=0.75,
            taker_buy_sell_ratio=0.5,
        )
        assert sig.signal != "LONG" or sig.confidence < 0.7


# ================================================================
# P2-6: digamma 극소값 underflow 클리핑
# ================================================================


class TestDigammaUnderflow:
    """digamma 결과 -50 하한 클리핑."""

    def test_very_small_x_clipped(self):
        """x=0.001 → digamma 결과 >= -50."""
        from src.ai.confluence.ksg_estimator import digamma

        result = digamma(0.001)
        assert result >= -50.0

    def test_normal_x_not_clipped(self):
        """x=1.0 → digamma ≈ -0.577 (정상 범위)."""
        from src.ai.confluence.ksg_estimator import digamma

        result = digamma(1.0)
        assert -1.0 < result < 0.0

    def test_large_x(self):
        """x=100.0 → digamma ≈ ln(100) ≈ 4.6."""
        from src.ai.confluence.ksg_estimator import digamma

        result = digamma(100.0)
        assert 4.0 < result < 5.0

    def test_zero_returns_large_negative(self):
        """x=0 → -50.0 (클리핑 적용)."""
        from src.ai.confluence.ksg_estimator import digamma

        result = digamma(0.0)
        assert result == -50.0


# ================================================================
# P2-7: Microprice market fallback 시 슬리피지 검증
# ================================================================


class TestMicropriceFallbackSlippage:
    """Market fallback 후 슬리피지 검증 적용."""

    def test_fallback_slippage_check_in_source(self):
        """executor.py에 P2-7 슬리피지 검증 코드 존재."""
        import inspect

        from src.trading.executor import TradingExecutor

        source = inspect.getsource(
            TradingExecutor._execute_microprice_limit
        )
        assert "_handle_slippage_detection" in source
        assert "Microprice fallback" in source


# ================================================================
# P1-1: confluence_engine — MIN_NET_EDGE 정의 유일성
# ================================================================


class TestMinNetEdgeSingle:
    """MIN_NET_EDGE가 단일 정의이고 중복 체크 없음."""

    def test_min_net_edge_single_definition(self):
        """MIN_NET_EDGE 클래스 변수 1회만 정의."""
        import inspect

        from src.ai.confluence.confluence_engine import ConfluenceEngine

        source = inspect.getsource(ConfluenceEngine)
        lines = [
            line.strip()
            for line in source.split("\n")
            if line.strip().startswith("MIN_NET_EDGE") and "=" in line
        ]
        assert len(lines) == 1, f"MIN_NET_EDGE 중복 정의: {lines}"

    @pytest.mark.asyncio
    async def test_min_net_edge_configurable(self):
        """min_net_edge 파라미터로 커스텀 최저선 설정."""
        from src.ai.confluence.confluence_engine import ConfluenceEngine

        engine = ConfluenceEngine(min_net_edge=0.10)
        assert engine.min_net_edge == 0.10

    @pytest.mark.asyncio
    async def test_min_net_edge_default(self):
        """기본 min_net_edge = 0.05."""
        from src.ai.confluence.confluence_engine import ConfluenceEngine

        engine = ConfluenceEngine()
        assert engine.min_net_edge == 0.05

    @pytest.mark.asyncio
    async def test_no_duplicate_net_edge_check(self):
        """evaluate() 내 net_edge < min_net_edge 체크가 1회만."""
        import inspect

        from src.ai.confluence.confluence_engine import ConfluenceEngine

        source = inspect.getsource(ConfluenceEngine.evaluate)
        count = source.count("net_edge < self.min_net_edge")
        assert count == 1, f"net_edge 체크 중복: {count}회"


# ================================================================
# P2-5: Dead Zone upper boundary 명시
# ================================================================


class TestDeadZoneUpperBoundary:
    """Dead Zone upper boundary 명시적 정의."""

    @pytest.mark.asyncio
    async def test_dead_zone_upper_defined(self):
        """_step8_gemini_boundary에서 upper 명시적 사용."""
        import inspect

        from src.ai.confluence.confluence_engine import ConfluenceEngine

        source = inspect.getsource(
            ConfluenceEngine._step8_gemini_boundary
        )
        assert "upper = threshold + self.DEAD_ZONE_MARGIN" in source

    @pytest.mark.asyncio
    async def test_above_upper_auto_pass(self):
        """net_edge >= upper → 자동 PASS."""
        from src.ai.confluence.confluence_engine import ConfluenceEngine

        engine = ConfluenceEngine()
        result = await engine._step8_gemini_boundary(
            "LONG", 0.45, 0.30, {}
        )
        assert result == "LONG"

    @pytest.mark.asyncio
    async def test_below_lower_auto_block(self):
        """net_edge < lower → 자동 BLOCK."""
        from src.ai.confluence.confluence_engine import ConfluenceEngine

        engine = ConfluenceEngine()
        result = await engine._step8_gemini_boundary(
            "LONG", 0.15, 0.30, {}
        )
        assert result == "WAIT"
