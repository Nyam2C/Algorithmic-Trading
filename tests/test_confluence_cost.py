"""CostCalculator 테스트."""
import pytest

from src.ai.confluence.cost_calculator import CostCalculator


class TestCostCalculator:
    """CostCalculator 테스트."""

    def setup_method(self):
        self.calc = CostCalculator()

    def test_default_fee_rate(self):
        assert self.calc.fee_rate == 0.0008

    def test_default_slippage_factor(self):
        assert self.calc.slippage_factor == 0.1

    def test_cost_penalty_low_leverage(self):
        """낮은 레버리지에서 비용 패널티 계산."""
        penalty = self.calc.calculate_cost_penalty(atr_pct=1.0, leverage=3)
        # fee = 0.0008*2 = 0.0016
        # slippage = (1.0/100)*0.1 = 0.001
        # total = (0.0016 + 0.001) * 3 = 0.0078
        assert penalty == pytest.approx(0.0078)

    def test_cost_penalty_high_leverage(self):
        """높은 레버리지에서 비용 증가."""
        low = self.calc.calculate_cost_penalty(atr_pct=1.0, leverage=3)
        high = self.calc.calculate_cost_penalty(atr_pct=1.0, leverage=20)
        assert high > low

    def test_cost_penalty_capped_at_one(self):
        """패널티는 1.0을 초과하지 않음."""
        penalty = self.calc.calculate_cost_penalty(atr_pct=10.0, leverage=50)
        assert penalty <= 1.0

    def test_cost_penalty_zero_atr(self):
        """ATR=0이면 슬리피지 없음."""
        penalty = self.calc.calculate_cost_penalty(atr_pct=0.0, leverage=5)
        # fee only: 0.0016 * 5 = 0.008
        assert penalty == pytest.approx(0.008)

    def test_net_edge_positive(self):
        """confluence_score > cost → positive net_edge."""
        net_edge, cost = self.calc.calculate_net_edge(
            confluence_score=0.5, atr_pct=1.0, leverage=3
        )
        assert net_edge > 0
        assert net_edge == pytest.approx(0.5 - cost)

    def test_net_edge_negative(self):
        """높은 비용 → negative net_edge."""
        net_edge, cost = self.calc.calculate_net_edge(
            confluence_score=0.01, atr_pct=5.0, leverage=20
        )
        assert net_edge < 0

    def test_custom_parameters(self):
        """커스텀 수수료율/슬리피지 계수."""
        calc = CostCalculator(fee_rate=0.001, slippage_factor=0.2)
        penalty = calc.calculate_cost_penalty(atr_pct=1.0, leverage=5)
        # fee = 0.001*2 = 0.002
        # slippage = 0.01*0.2 = 0.002
        # total = (0.002 + 0.002) * 5 = 0.02
        assert penalty == pytest.approx(0.02)
