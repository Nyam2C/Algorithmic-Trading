"""Whale Flow Channel 테스트."""
import pytest

from src.ai.channels.whale_flow_channel import WhaleFlowChannel
from src.ai.ensemble import SignalSource


@pytest.fixture
def channel():
    return WhaleFlowChannel()


class TestWhaleFlowBasic:
    """기본 동작 테스트."""

    @pytest.mark.asyncio
    async def test_none_snapshot_returns_wait(self, channel):
        sig = await channel.generate_signal(None)
        assert sig.signal == "WAIT"
        assert sig.confidence == 0.0
        assert sig.source == SignalSource.WHALE_FLOW

    @pytest.mark.asyncio
    async def test_insufficient_trades_returns_wait(self, channel):
        snapshot = {
            "whale_buy_vol": 100.0, "whale_sell_vol": 10.0,
            "retail_buy_vol": 50.0, "retail_sell_vol": 50.0,
            "total_trades": 30,
        }
        sig = await channel.generate_signal(snapshot)
        assert sig.signal == "WAIT"
        assert "거래 부족" in sig.reason

    @pytest.mark.asyncio
    async def test_exactly_min_trades_processes(self, channel):
        snapshot = {
            "whale_buy_vol": 100.0, "whale_sell_vol": 10.0,
            "retail_buy_vol": 50.0, "retail_sell_vol": 50.0,
            "total_trades": 50,
        }
        sig = await channel.generate_signal(snapshot)
        assert sig.source == SignalSource.WHALE_FLOW

    @pytest.mark.asyncio
    async def test_weight_is_015(self, channel):
        snapshot = {
            "whale_buy_vol": 100.0, "whale_sell_vol": 10.0,
            "retail_buy_vol": 50.0, "retail_sell_vol": 50.0,
            "total_trades": 100,
        }
        sig = await channel.generate_signal(snapshot)
        assert sig.weight == 0.15


class TestWhaleFlowDirections:
    """방향 판단 테스트."""

    @pytest.mark.asyncio
    async def test_whale_buy_dominant_returns_long(self, channel):
        snapshot = {
            "whale_buy_vol": 100.0, "whale_sell_vol": 10.0,
            "retail_buy_vol": 50.0, "retail_sell_vol": 50.0,
            "total_trades": 100,
        }
        sig = await channel.generate_signal(snapshot)
        # whale_net = 90, whale_total = 110, intensity = 90/110 ≈ 0.818
        # raw_score = 1 * min(100, 0.818*250) = min(100, 204.5) = 100
        # No predatory (both whale & retail net positive or same direction)
        # retail_net = 0, so no predatory
        assert sig.signal == "LONG"

    @pytest.mark.asyncio
    async def test_whale_sell_dominant_returns_short(self, channel):
        snapshot = {
            "whale_buy_vol": 10.0, "whale_sell_vol": 100.0,
            "retail_buy_vol": 50.0, "retail_sell_vol": 50.0,
            "total_trades": 100,
        }
        sig = await channel.generate_signal(snapshot)
        assert sig.signal == "SHORT"

    @pytest.mark.asyncio
    async def test_balanced_whale_returns_wait(self, channel):
        snapshot = {
            "whale_buy_vol": 50.0, "whale_sell_vol": 50.0,
            "retail_buy_vol": 50.0, "retail_sell_vol": 50.0,
            "total_trades": 100,
        }
        sig = await channel.generate_signal(snapshot)
        # whale_net = 0, score = 0, |0| <= 25 → WAIT
        assert sig.signal == "WAIT"

    @pytest.mark.asyncio
    async def test_weak_whale_signal_returns_wait(self, channel):
        # Small whale net relative to total
        snapshot = {
            "whale_buy_vol": 55.0, "whale_sell_vol": 50.0,
            "retail_buy_vol": 50.0, "retail_sell_vol": 50.0,
            "total_trades": 100,
        }
        sig = await channel.generate_signal(snapshot)
        # whale_net = 5, whale_total = 105, intensity = 5/105 ≈ 0.0476
        # raw_score = 1 * min(100, 0.0476*250) ≈ 11.9 < 25 → WAIT
        assert sig.signal == "WAIT"


class TestWhaleFlowPredatory:
    """Predatory 패턴 테스트."""

    @pytest.mark.asyncio
    async def test_predatory_long_boosts_score(self, channel):
        # Whale buying, retail selling → predatory
        snapshot_pred = {
            "whale_buy_vol": 80.0, "whale_sell_vol": 30.0,
            "retail_buy_vol": 20.0, "retail_sell_vol": 60.0,
            "total_trades": 100,
        }
        snapshot_normal = {
            "whale_buy_vol": 80.0, "whale_sell_vol": 30.0,
            "retail_buy_vol": 50.0, "retail_sell_vol": 50.0,
            "total_trades": 100,
        }
        sig_pred = await channel.generate_signal(snapshot_pred)
        sig_normal = await channel.generate_signal(snapshot_normal)

        assert sig_pred.signal == "LONG"
        assert sig_normal.signal == "LONG"
        # Predatory should have higher confidence
        assert sig_pred.confidence >= sig_normal.confidence

    @pytest.mark.asyncio
    async def test_predatory_short_detected(self, channel):
        # Whale selling, retail buying → predatory short
        snapshot = {
            "whale_buy_vol": 20.0, "whale_sell_vol": 80.0,
            "retail_buy_vol": 60.0, "retail_sell_vol": 20.0,
            "total_trades": 100,
        }
        sig = await channel.generate_signal(snapshot)
        assert sig.signal == "SHORT"
        assert "[Predatory]" in sig.reason

    @pytest.mark.asyncio
    async def test_non_predatory_no_tag(self, channel):
        # Whale and retail same direction
        snapshot = {
            "whale_buy_vol": 80.0, "whale_sell_vol": 20.0,
            "retail_buy_vol": 60.0, "retail_sell_vol": 20.0,
            "total_trades": 100,
        }
        sig = await channel.generate_signal(snapshot)
        assert "[Predatory]" not in sig.reason


class TestWhaleFlowEdgeCases:
    """엣지케이스 테스트."""

    @pytest.mark.asyncio
    async def test_zero_whale_total_returns_wait(self, channel):
        snapshot = {
            "whale_buy_vol": 0.0, "whale_sell_vol": 0.0,
            "retail_buy_vol": 50.0, "retail_sell_vol": 50.0,
            "total_trades": 100,
        }
        sig = await channel.generate_signal(snapshot)
        assert sig.signal == "WAIT"
        assert "고래 거래량 없음" in sig.reason

    @pytest.mark.asyncio
    async def test_confidence_capped_at_1(self, channel):
        # Even with predatory multiplier, confidence should cap at 1.0
        snapshot = {
            "whale_buy_vol": 1000.0, "whale_sell_vol": 1.0,
            "retail_buy_vol": 1.0, "retail_sell_vol": 1000.0,
            "total_trades": 100,
        }
        sig = await channel.generate_signal(snapshot)
        assert sig.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_missing_fields_default_to_zero(self, channel):
        snapshot = {"total_trades": 100}
        sig = await channel.generate_signal(snapshot)
        # All volumes = 0, whale_total = 0 → WAIT
        assert sig.signal == "WAIT"

    @pytest.mark.asyncio
    async def test_reason_contains_whale_info(self, channel):
        snapshot = {
            "whale_buy_vol": 80.0, "whale_sell_vol": 20.0,
            "retail_buy_vol": 50.0, "retail_sell_vol": 50.0,
            "total_trades": 100,
        }
        sig = await channel.generate_signal(snapshot)
        assert "WhaleNet=" in sig.reason
        assert "intensity=" in sig.reason
