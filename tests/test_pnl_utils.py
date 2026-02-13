"""Tests for PnL utility functions."""
import pytest

from src.utils.pnl import calculate_pnl_pct, calculate_pnl_usd


class TestCalculatePnlPct:
    """calculate_pnl_pct 테스트."""

    def test_long_profit(self):
        """LONG 수익 시 양수 PnL %."""
        result = calculate_pnl_pct(50000.0, 51000.0, "LONG")
        assert result == pytest.approx(2.0)

    def test_long_loss(self):
        """LONG 손실 시 음수 PnL %."""
        result = calculate_pnl_pct(50000.0, 49000.0, "LONG")
        assert result == pytest.approx(-2.0)

    def test_short_profit(self):
        """SHORT 수익 시 양수 PnL %."""
        result = calculate_pnl_pct(50000.0, 49000.0, "SHORT")
        assert result == pytest.approx(2.0)

    def test_short_loss(self):
        """SHORT 손실 시 음수 PnL %."""
        result = calculate_pnl_pct(50000.0, 51000.0, "SHORT")
        assert result == pytest.approx(-2.0)

    def test_no_change(self):
        """가격 변동 없을 때 0%."""
        assert calculate_pnl_pct(50000.0, 50000.0, "LONG") == 0.0
        assert calculate_pnl_pct(50000.0, 50000.0, "SHORT") == 0.0

    def test_large_gain(self):
        """큰 수익."""
        result = calculate_pnl_pct(100.0, 200.0, "LONG")
        assert result == pytest.approx(100.0)

    def test_small_movement(self):
        """소폭 변동."""
        result = calculate_pnl_pct(50000.0, 50005.0, "LONG")
        assert result == pytest.approx(0.01)


class TestCalculatePnlUsd:
    """calculate_pnl_usd 테스트."""

    def test_long_profit(self):
        """LONG 수익 (USD)."""
        result = calculate_pnl_usd(50000.0, 51000.0, "LONG", 0.1)
        assert result == pytest.approx(100.0)

    def test_long_loss(self):
        """LONG 손실 (USD)."""
        result = calculate_pnl_usd(50000.0, 49000.0, "LONG", 0.1)
        assert result == pytest.approx(-100.0)

    def test_short_profit(self):
        """SHORT 수익 (USD)."""
        result = calculate_pnl_usd(50000.0, 49000.0, "SHORT", 0.1)
        assert result == pytest.approx(100.0)

    def test_short_loss(self):
        """SHORT 손실 (USD)."""
        result = calculate_pnl_usd(50000.0, 51000.0, "SHORT", 0.1)
        assert result == pytest.approx(-100.0)

    def test_with_leverage(self):
        """레버리지 적용."""
        result = calculate_pnl_usd(50000.0, 51000.0, "LONG", 0.1, leverage=10)
        assert result == pytest.approx(1000.0)

    def test_default_leverage(self):
        """기본 레버리지는 1."""
        result = calculate_pnl_usd(50000.0, 51000.0, "LONG", 0.1)
        assert result == pytest.approx(100.0)

    def test_no_change(self):
        """가격 변동 없으면 PnL은 0."""
        assert calculate_pnl_usd(50000.0, 50000.0, "LONG", 1.0) == 0.0
        assert calculate_pnl_usd(50000.0, 50000.0, "SHORT", 1.0) == 0.0

    def test_zero_quantity(self):
        """수량이 0이면 PnL은 0."""
        assert calculate_pnl_usd(50000.0, 51000.0, "LONG", 0.0) == 0.0
