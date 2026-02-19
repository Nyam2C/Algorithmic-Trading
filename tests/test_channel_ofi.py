"""OFI Channel 테스트."""
import pytest

from src.ai.channels.ofi_channel import OFIChannel
from src.ai.ensemble import SignalSource


@pytest.fixture
def channel():
    return OFIChannel()


class TestOFIChannelBasic:
    """기본 동작 테스트."""

    @pytest.mark.asyncio
    async def test_none_snapshot_returns_wait(self, channel):
        sig = await channel.generate_signal(None)
        assert sig.signal == "WAIT"
        assert sig.confidence == 0.0
        assert sig.source == SignalSource.OFI

    @pytest.mark.asyncio
    async def test_insufficient_samples_returns_wait(self, channel):
        snapshot = {"ofi_5": 50.0, "ofi_20": 40.0, "ofi_50": 30.0, "cvd": 10.0, "sample_count": 5}
        sig = await channel.generate_signal(snapshot)
        assert sig.signal == "WAIT"
        assert "샘플 부족" in sig.reason

    @pytest.mark.asyncio
    async def test_exactly_min_samples_processes(self, channel):
        snapshot = {"ofi_5": 80.0, "ofi_20": 60.0, "ofi_50": 40.0, "cvd": 50.0, "sample_count": 10}
        sig = await channel.generate_signal(snapshot)
        # Should process (not WAIT due to sample count)
        assert sig.source == SignalSource.OFI

    @pytest.mark.asyncio
    async def test_weight_is_015(self, channel):
        snapshot = {"ofi_5": 80.0, "ofi_20": 60.0, "ofi_50": 40.0, "cvd": 50.0, "sample_count": 100}
        sig = await channel.generate_signal(snapshot)
        assert sig.weight == 0.15


class TestOFIChannelDirections:
    """방향 판단 테스트."""

    @pytest.mark.asyncio
    async def test_strong_positive_ofi_returns_long(self, channel):
        snapshot = {"ofi_5": 80.0, "ofi_20": 60.0, "ofi_50": 40.0, "cvd": 50.0, "sample_count": 100}
        sig = await channel.generate_signal(snapshot)
        # weighted = 80*0.5 + 60*0.3 + 40*0.2 = 40 + 18 + 8 = 66 > 30
        assert sig.signal == "LONG"
        assert sig.confidence > 0

    @pytest.mark.asyncio
    async def test_strong_negative_ofi_returns_short(self, channel):
        snapshot = {"ofi_5": -80.0, "ofi_20": -60.0, "ofi_50": -40.0, "cvd": -50.0, "sample_count": 100}
        sig = await channel.generate_signal(snapshot)
        assert sig.signal == "SHORT"
        assert sig.confidence > 0

    @pytest.mark.asyncio
    async def test_weak_ofi_returns_wait(self, channel):
        snapshot = {"ofi_5": 10.0, "ofi_20": 5.0, "ofi_50": 2.0, "cvd": 3.0, "sample_count": 100}
        sig = await channel.generate_signal(snapshot)
        # weighted = 10*0.5 + 5*0.3 + 2*0.2 = 5 + 1.5 + 0.4 = 6.9 < 30
        assert sig.signal == "WAIT"

    @pytest.mark.asyncio
    async def test_threshold_boundary_exact_returns_wait(self, channel):
        # ofi exactly at threshold (30): |30| <= 30 → WAIT
        snapshot = {"ofi_5": 60.0, "ofi_20": 0.0, "ofi_50": 0.0, "cvd": 0.0, "sample_count": 100}
        sig = await channel.generate_signal(snapshot)
        # weighted = 60*0.5 = 30.0 → |30| <= 30 → WAIT
        assert sig.signal == "WAIT"

    @pytest.mark.asyncio
    async def test_just_above_threshold_returns_signal(self, channel):
        snapshot = {"ofi_5": 62.0, "ofi_20": 0.0, "ofi_50": 0.0, "cvd": 0.0, "sample_count": 100}
        sig = await channel.generate_signal(snapshot)
        # weighted = 62*0.5 = 31.0 > 30
        assert sig.signal == "LONG"


class TestOFIChannelCVDCrossValidation:
    """CVD 교차검증 테스트."""

    @pytest.mark.asyncio
    async def test_cvd_agree_boosts_confidence(self, channel):
        # OFI 양수 + CVD 양수 → confidence x 1.3
        snapshot_agree = {"ofi_5": 80.0, "ofi_20": 60.0, "ofi_50": 40.0, "cvd": 50.0, "sample_count": 100}
        snapshot_no_cvd = {"ofi_5": 80.0, "ofi_20": 60.0, "ofi_50": 40.0, "cvd": 0.0, "sample_count": 100}
        sig_agree = await channel.generate_signal(snapshot_agree)
        sig_no_cvd = await channel.generate_signal(snapshot_no_cvd)
        assert sig_agree.confidence >= sig_no_cvd.confidence

    @pytest.mark.asyncio
    async def test_cvd_disagree_reduces_confidence(self, channel):
        # OFI 양수 + CVD 음수 → confidence x 0.6
        snapshot_disagree = {"ofi_5": 80.0, "ofi_20": 60.0, "ofi_50": 40.0, "cvd": -50.0, "sample_count": 100}
        snapshot_no_cvd = {"ofi_5": 80.0, "ofi_20": 60.0, "ofi_50": 40.0, "cvd": 0.0, "sample_count": 100}
        sig_disagree = await channel.generate_signal(snapshot_disagree)
        sig_no_cvd = await channel.generate_signal(snapshot_no_cvd)
        assert sig_disagree.confidence < sig_no_cvd.confidence

    @pytest.mark.asyncio
    async def test_cvd_zero_no_change(self, channel):
        snapshot = {"ofi_5": 80.0, "ofi_20": 60.0, "ofi_50": 40.0, "cvd": 0.0, "sample_count": 100}
        sig = await channel.generate_signal(snapshot)
        # CVD=0 → no multiplier
        # weighted = 66, confidence = 66/100 = 0.66
        assert sig.confidence == 0.66

    @pytest.mark.asyncio
    async def test_negative_ofi_negative_cvd_agree(self, channel):
        snapshot = {"ofi_5": -80.0, "ofi_20": -60.0, "ofi_50": -40.0, "cvd": -50.0, "sample_count": 100}
        sig = await channel.generate_signal(snapshot)
        assert sig.signal == "SHORT"
        # CVD agrees (both negative) → boosted
        # base conf = 66/100 = 0.66, x 1.3 = 0.858
        assert sig.confidence == 0.858


class TestOFIChannelEdgeCases:
    """엣지케이스 테스트."""

    @pytest.mark.asyncio
    async def test_extreme_ofi_clamped_to_100(self, channel):
        snapshot = {"ofi_5": 500.0, "ofi_20": 500.0, "ofi_50": 500.0, "cvd": 0.0, "sample_count": 100}
        sig = await channel.generate_signal(snapshot)
        assert sig.signal == "LONG"
        # Score clamped to 100, confidence = 100/100 = 1.0
        assert sig.confidence == 1.0

    @pytest.mark.asyncio
    async def test_confidence_capped_at_1(self, channel):
        # Even with CVD boost, confidence should not exceed 1.0
        snapshot = {"ofi_5": 200.0, "ofi_20": 200.0, "ofi_50": 200.0, "cvd": 100.0, "sample_count": 100}
        sig = await channel.generate_signal(snapshot)
        assert sig.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_missing_fields_default_to_zero(self, channel):
        snapshot = {"sample_count": 100}
        sig = await channel.generate_signal(snapshot)
        # All OFI = 0, weighted = 0, |0| <= 30 → WAIT
        assert sig.signal == "WAIT"

    @pytest.mark.asyncio
    async def test_reason_contains_ofi_values(self, channel):
        snapshot = {"ofi_5": 80.0, "ofi_20": 60.0, "ofi_50": 40.0, "cvd": 10.0, "sample_count": 100}
        sig = await channel.generate_signal(snapshot)
        assert "OFI=" in sig.reason
        assert "CVD=" in sig.reason
