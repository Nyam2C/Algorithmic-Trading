"""
Backtest 모듈 커버리지 개선 테스트

slippage.py의 미커버 라인을 대상으로 합니다.
"""
import pytest

from src.backtest.slippage import (
    MarketImpactModel,
    SlippageModel,
    calculate_realistic_entry_price,
    calculate_realistic_exit_price,
)

# =============================================================================
# SlippageModel 추가 테스트
# =============================================================================

class TestSlippageModelEdgeCases:
    """SlippageModel 엣지 케이스"""

    def test_calculate_slippage_zero_volume(self):
        """평균 거래량 0인 경우"""
        model = SlippageModel()
        slippage = model.calculate_slippage(
            order_size=1000.0,
            avg_volume=0.0,
            volatility=0.0,
        )
        # 기본 슬리피지만 적용
        assert slippage == pytest.approx(0.01 / 100)

    def test_calculate_slippage_with_volatility(self):
        """변동성 포함 슬리피지"""
        model = SlippageModel()
        slippage = model.calculate_slippage(
            order_size=1000.0,
            avg_volume=10000.0,
            volatility=2.0,
        )
        assert slippage > 0.01 / 100  # 기본보다 높아야 함

    def test_calculate_slippage_max_cap(self):
        """최대 슬리피지 제한"""
        model = SlippageModel(max_slippage_pct=0.05)
        slippage = model.calculate_slippage(
            order_size=100000.0,  # 매우 큰 주문
            avg_volume=100.0,  # 매우 작은 거래량
            volatility=10.0,  # 매우 높은 변동성
        )
        assert slippage <= 0.05 / 100

    def test_apply_to_price_long(self):
        """LONG 슬리피지 적용: 가격 상승"""
        model = SlippageModel(base_slippage_pct=0.1)
        price = model.apply_to_price(
            price=100000.0,
            side="LONG",
            order_size=1000.0,
            avg_volume=10000.0,
        )
        assert price > 100000.0

    def test_apply_to_price_short(self):
        """SHORT 슬리피지 적용: 가격 하락"""
        model = SlippageModel(base_slippage_pct=0.1)
        price = model.apply_to_price(
            price=100000.0,
            side="SHORT",
            order_size=1000.0,
            avg_volume=10000.0,
        )
        assert price < 100000.0

    def test_apply_to_price_with_volatility(self):
        """변동성 포함 가격 적용"""
        model = SlippageModel()
        price = model.apply_to_price(
            price=100000.0,
            side="LONG",
            order_size=1000.0,
            avg_volume=10000.0,
            volatility=2.0,
        )
        assert price > 100000.0


# =============================================================================
# MarketImpactModel 테스트
# =============================================================================

class TestMarketImpactModel:
    """MarketImpactModel 테스트"""

    def test_calculate_impact_normal(self):
        """정상적인 시장 영향"""
        model = MarketImpactModel()
        impact = model.calculate_impact(
            order_size=1000.0,
            market_depth=10000.0,
        )
        assert impact > 0
        assert impact <= 0.05

    def test_calculate_impact_zero_depth(self):
        """시장 깊이 0"""
        model = MarketImpactModel()
        impact = model.calculate_impact(
            order_size=1000.0,
            market_depth=0.0,
        )
        assert impact == 0.0

    def test_calculate_impact_negative_depth(self):
        """시장 깊이 음수"""
        model = MarketImpactModel()
        impact = model.calculate_impact(
            order_size=1000.0,
            market_depth=-100.0,
        )
        assert impact == 0.0

    def test_calculate_impact_max_cap(self):
        """최대 영향 5% 제한"""
        model = MarketImpactModel(impact_coefficient=10.0)
        impact = model.calculate_impact(
            order_size=10000.0,
            market_depth=100.0,
        )
        assert impact == 0.05

    def test_calculate_impact_large_depth(self):
        """큰 시장 깊이 → 낮은 영향"""
        model = MarketImpactModel()
        impact = model.calculate_impact(
            order_size=100.0,
            market_depth=1000000.0,
        )
        assert impact < 0.001


# =============================================================================
# calculate_realistic_entry_price 테스트
# =============================================================================

class TestRealisticEntryPrice:
    """현실적 진입 가격 계산"""

    def test_long_entry_no_slippage(self):
        """LONG 진입: 슬리피지 없음"""
        candle = {
            "open": 99000.0,
            "high": 101000.0,
            "low": 98000.0,
            "close": 100000.0,
            "volume": 1000.0,
        }
        price = calculate_realistic_entry_price(candle, "LONG")
        # 종가 + (고가-종가)*0.3 = 100000 + 300 = 100300
        assert price == pytest.approx(100300.0)

    def test_short_entry_no_slippage(self):
        """SHORT 진입: 슬리피지 없음"""
        candle = {
            "open": 99000.0,
            "high": 101000.0,
            "low": 98000.0,
            "close": 100000.0,
            "volume": 1000.0,
        }
        price = calculate_realistic_entry_price(candle, "SHORT")
        # 종가 - (종가-저가)*0.3 = 100000 - 600 = 99400
        assert price == pytest.approx(99400.0)

    def test_long_entry_with_slippage(self):
        """LONG 진입: 슬리피지 적용"""
        candle = {
            "open": 99000.0,
            "high": 101000.0,
            "low": 98000.0,
            "close": 100000.0,
            "volume": 1000.0,
        }
        model = SlippageModel(base_slippage_pct=0.1)
        price = calculate_realistic_entry_price(
            candle, "LONG",
            slippage_model=model,
            order_size=1000.0,
            avg_volume=10000.0,
        )
        # 슬리피지가 적용되므로 기본보다 높아야 함
        assert price > 100300.0

    def test_short_entry_with_slippage(self):
        """SHORT 진입: 슬리피지 적용"""
        candle = {
            "open": 99000.0,
            "high": 101000.0,
            "low": 98000.0,
            "close": 100000.0,
            "volume": 1000.0,
        }
        model = SlippageModel(base_slippage_pct=0.1)
        price = calculate_realistic_entry_price(
            candle, "SHORT",
            slippage_model=model,
            order_size=1000.0,
            avg_volume=10000.0,
        )
        # 슬리피지가 적용되므로 기본보다 낮아야 함
        assert price < 99400.0


# =============================================================================
# calculate_realistic_exit_price 테스트
# =============================================================================

class TestRealisticExitPrice:
    """현실적 청산 가격 계산"""

    def test_long_tp_reached(self):
        """LONG TP 도달"""
        candle = {
            "open": 100000.0,
            "high": 101500.0,
            "low": 99500.0,
            "close": 101000.0,
        }
        price = calculate_realistic_exit_price(
            candle=candle,
            position_side="LONG",
            exit_reason="TP",
            entry_price=100000.0,
            tp_pct=0.01,  # 1%
        )
        # TP target = 100000 * 1.01 = 101000
        # high (101500) >= TP target → return TP target
        assert price == pytest.approx(101000.0)

    def test_long_tp_not_reached(self):
        """LONG TP 미도달 → 종가"""
        candle = {
            "open": 100000.0,
            "high": 100500.0,  # TP target보다 낮음
            "low": 99500.0,
            "close": 100200.0,
        }
        price = calculate_realistic_exit_price(
            candle=candle,
            position_side="LONG",
            exit_reason="TP",
            entry_price=100000.0,
            tp_pct=0.01,
        )
        assert price == 100200.0  # 종가

    def test_long_sl_reached(self):
        """LONG SL 도달"""
        candle = {
            "open": 100000.0,
            "high": 100200.0,
            "low": 99400.0,
            "close": 99800.0,
        }
        price = calculate_realistic_exit_price(
            candle=candle,
            position_side="LONG",
            exit_reason="SL",
            entry_price=100000.0,
            sl_pct=0.005,  # 0.5%
        )
        # SL target = 100000 * 0.995 = 99500
        # low (99400) <= SL target → return SL target
        assert price == pytest.approx(99500.0)

    def test_long_sl_not_reached(self):
        """LONG SL 미도달 → 종가"""
        candle = {
            "open": 100000.0,
            "high": 100200.0,
            "low": 99600.0,  # SL target보다 높음
            "close": 99800.0,
        }
        price = calculate_realistic_exit_price(
            candle=candle,
            position_side="LONG",
            exit_reason="SL",
            entry_price=100000.0,
            sl_pct=0.005,
        )
        assert price == 99800.0

    def test_long_timecut(self):
        """LONG TIMECUT → 종가"""
        candle = {
            "open": 100000.0,
            "high": 100500.0,
            "low": 99500.0,
            "close": 100200.0,
        }
        price = calculate_realistic_exit_price(
            candle=candle,
            position_side="LONG",
            exit_reason="TIMECUT",
            entry_price=100000.0,
        )
        assert price == 100200.0

    def test_short_tp_reached(self):
        """SHORT TP 도달"""
        candle = {
            "open": 100000.0,
            "high": 100500.0,
            "low": 98500.0,
            "close": 99000.0,
        }
        price = calculate_realistic_exit_price(
            candle=candle,
            position_side="SHORT",
            exit_reason="TP",
            entry_price=100000.0,
            tp_pct=0.01,
        )
        # TP target = 100000 * 0.99 = 99000
        # low (98500) <= TP target → return TP target
        assert price == pytest.approx(99000.0)

    def test_short_tp_not_reached(self):
        """SHORT TP 미도달 → 종가"""
        candle = {
            "open": 100000.0,
            "high": 100500.0,
            "low": 99500.0,  # TP target보다 높음
            "close": 99800.0,
        }
        price = calculate_realistic_exit_price(
            candle=candle,
            position_side="SHORT",
            exit_reason="TP",
            entry_price=100000.0,
            tp_pct=0.01,
        )
        assert price == 99800.0

    def test_short_sl_reached(self):
        """SHORT SL 도달"""
        candle = {
            "open": 100000.0,
            "high": 100600.0,
            "low": 99500.0,
            "close": 99800.0,
        }
        price = calculate_realistic_exit_price(
            candle=candle,
            position_side="SHORT",
            exit_reason="SL",
            entry_price=100000.0,
            sl_pct=0.005,
        )
        # SL target = 100000 * 1.005 = 100500
        # high (100600) >= SL target → return SL target
        assert price == pytest.approx(100500.0)

    def test_short_sl_not_reached(self):
        """SHORT SL 미도달 → 종가"""
        candle = {
            "open": 100000.0,
            "high": 100200.0,  # SL target보다 낮음
            "low": 99500.0,
            "close": 99800.0,
        }
        price = calculate_realistic_exit_price(
            candle=candle,
            position_side="SHORT",
            exit_reason="SL",
            entry_price=100000.0,
            sl_pct=0.005,
        )
        assert price == 99800.0

    def test_short_timecut(self):
        """SHORT TIMECUT → 종가"""
        candle = {
            "open": 100000.0,
            "high": 100500.0,
            "low": 99500.0,
            "close": 99800.0,
        }
        price = calculate_realistic_exit_price(
            candle=candle,
            position_side="SHORT",
            exit_reason="TIMECUT",
            entry_price=100000.0,
        )
        assert price == 99800.0
