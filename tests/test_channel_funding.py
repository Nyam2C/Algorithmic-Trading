"""FundingBasisChannel 테스트.

Funding Rate + Long/Short Ratio 기반 군중 역행 채널 테스트.
"""
import pytest

from src.ai.channels.funding_basis import FundingBasisChannel
from src.ai.ensemble import IndividualSignal, SignalSource


@pytest.fixture
def channel() -> FundingBasisChannel:
    return FundingBasisChannel()


# ── 1. Extreme positive FR + long crowded -> SHORT ──


@pytest.mark.asyncio
async def test_extreme_positive_fr_long_crowded_short(channel: FundingBasisChannel) -> None:
    """FR >= 0.05% 이고 Long >= 65% 이면 SHORT 시그널."""
    # ratio 2.0 -> long_pct = 2/3 = 66.7%
    sig = await channel.generate_signal(0.001, 2.0)
    assert sig.signal == "SHORT"


@pytest.mark.asyncio
async def test_short_signal_with_high_fr_and_crowded_longs(channel: FundingBasisChannel) -> None:
    """매우 높은 FR + 극단적 long 비율 -> SHORT."""
    sig = await channel.generate_signal(0.002, 5.0)  # long_pct = 83.3%
    assert sig.signal == "SHORT"
    assert sig.confidence > 0


# ── 2. Extreme negative FR + short crowded -> LONG ──


@pytest.mark.asyncio
async def test_extreme_negative_fr_short_crowded_long(channel: FundingBasisChannel) -> None:
    """FR <= -0.03% 이고 Short >= 60% 이면 LONG 시그널."""
    # ratio 0.5 -> long_pct = 0.5/1.5 = 33.3%, short_pct = 66.7%
    sig = await channel.generate_signal(-0.0005, 0.5)
    assert sig.signal == "LONG"


@pytest.mark.asyncio
async def test_long_signal_with_very_negative_fr(channel: FundingBasisChannel) -> None:
    """매우 낮은 FR + short 과밀 -> LONG."""
    sig = await channel.generate_signal(-0.001, 0.3)  # short_pct = 76.9%
    assert sig.signal == "LONG"
    assert sig.confidence > 0


# ── 3. Neutral FR -> WAIT ──


@pytest.mark.asyncio
async def test_neutral_fr_wait(channel: FundingBasisChannel) -> None:
    """중립적 FR -> WAIT."""
    sig = await channel.generate_signal(0.0001, 1.0)
    assert sig.signal == "WAIT"


@pytest.mark.asyncio
async def test_slightly_positive_fr_wait(channel: FundingBasisChannel) -> None:
    """약간 양수 FR -> WAIT."""
    sig = await channel.generate_signal(0.0002, 1.5)
    assert sig.signal == "WAIT"


# ── 4. Extreme FR but NOT crowded -> WAIT ──


@pytest.mark.asyncio
async def test_extreme_positive_fr_but_not_crowded_wait(channel: FundingBasisChannel) -> None:
    """FR 극단적이지만 Long 과밀 아님 -> WAIT."""
    # ratio 1.0 -> long_pct = 50%, not >= 65%
    sig = await channel.generate_signal(0.001, 1.0)
    assert sig.signal == "WAIT"


@pytest.mark.asyncio
async def test_extreme_negative_fr_but_not_short_crowded_wait(channel: FundingBasisChannel) -> None:
    """FR 극단적 음수이지만 Short 과밀 아님 -> WAIT."""
    # ratio 1.5 -> long_pct = 60%, short_pct = 40%, not >= 60%
    sig = await channel.generate_signal(-0.0005, 1.5)
    assert sig.signal == "WAIT"


# ── 5. Crowded but NOT extreme FR -> WAIT ──


@pytest.mark.asyncio
async def test_long_crowded_but_normal_fr_wait(channel: FundingBasisChannel) -> None:
    """Long 과밀이지만 FR 정상 -> WAIT."""
    sig = await channel.generate_signal(0.0002, 3.0)  # long_pct = 75%
    assert sig.signal == "WAIT"


@pytest.mark.asyncio
async def test_short_crowded_but_normal_fr_wait(channel: FundingBasisChannel) -> None:
    """Short 과밀이지만 FR 정상 -> WAIT."""
    sig = await channel.generate_signal(-0.0001, 0.4)  # short_pct = 71.4%
    assert sig.signal == "WAIT"


# ── 6-8. None 입력 처리 ──


@pytest.mark.asyncio
async def test_funding_rate_none_wait(channel: FundingBasisChannel) -> None:
    """funding_rate=None -> WAIT."""
    sig = await channel.generate_signal(None, 1.0)
    assert sig.signal == "WAIT"
    assert sig.confidence == 0.0
    assert "데이터 없음" in sig.reason


@pytest.mark.asyncio
async def test_long_short_ratio_none_wait(channel: FundingBasisChannel) -> None:
    """long_short_ratio=None -> WAIT."""
    sig = await channel.generate_signal(0.001, None)
    assert sig.signal == "WAIT"
    assert sig.confidence == 0.0
    assert "데이터 없음" in sig.reason


@pytest.mark.asyncio
async def test_both_none_wait(channel: FundingBasisChannel) -> None:
    """둘 다 None -> WAIT."""
    sig = await channel.generate_signal(None, None)
    assert sig.signal == "WAIT"
    assert sig.confidence == 0.0


# ── 9-12. Boundary tests ──


@pytest.mark.asyncio
async def test_boundary_fr_exactly_extreme_long_with_crowded(channel: FundingBasisChannel) -> None:
    """FR이 정확히 FR_EXTREME_LONG 경계 + 과밀 -> SHORT."""
    # ratio = 0.65/0.35 = 1.857... -> long_pct = exactly 65%
    ratio = 0.65 / 0.35
    sig = await channel.generate_signal(0.0005, ratio)
    assert sig.signal == "SHORT"


@pytest.mark.asyncio
async def test_boundary_fr_exactly_extreme_short_with_crowded(channel: FundingBasisChannel) -> None:
    """FR이 정확히 FR_EXTREME_SHORT 경계 + 과밀 -> LONG."""
    # ratio = 0.40/0.60 = 0.6667 -> short_pct = 60%
    ratio = 0.40 / 0.60
    sig = await channel.generate_signal(-0.0003, ratio)
    assert sig.signal == "LONG"


@pytest.mark.asyncio
async def test_boundary_long_pct_exactly_at_crowded(channel: FundingBasisChannel) -> None:
    """long_pct이 정확히 LS_LONG_CROWDED(65%) 경계."""
    ratio = 0.65 / 0.35  # long_pct = 65%
    sig = await channel.generate_signal(0.0005, ratio)
    assert sig.signal == "SHORT"


@pytest.mark.asyncio
async def test_boundary_short_pct_exactly_at_crowded(channel: FundingBasisChannel) -> None:
    """short_pct이 정확히 LS_SHORT_CROWDED(60%) 경계."""
    ratio = 0.40 / 0.60  # short_pct = 60%
    sig = await channel.generate_signal(-0.0003, ratio)
    assert sig.signal == "LONG"


@pytest.mark.asyncio
async def test_boundary_fr_just_below_extreme_long(channel: FundingBasisChannel) -> None:
    """FR이 FR_EXTREME_LONG 미만 -> WAIT (과밀이어도)."""
    sig = await channel.generate_signal(0.00049, 3.0)
    assert sig.signal == "WAIT"


@pytest.mark.asyncio
async def test_boundary_fr_just_above_extreme_short(channel: FundingBasisChannel) -> None:
    """FR이 FR_EXTREME_SHORT 초과 -> WAIT (과밀이어도)."""
    sig = await channel.generate_signal(-0.00029, 0.3)
    assert sig.signal == "WAIT"


# ── 13. Very extreme FR -> confidence capped at 1.0 ──


@pytest.mark.asyncio
async def test_very_extreme_fr_confidence_capped(channel: FundingBasisChannel) -> None:
    """매우 극단적 FR에서도 confidence는 1.0 이하."""
    sig = await channel.generate_signal(0.01, 10.0)  # long_pct = 90.9%
    assert sig.signal == "SHORT"
    assert sig.confidence <= 1.0


@pytest.mark.asyncio
async def test_very_extreme_negative_fr_confidence_capped(channel: FundingBasisChannel) -> None:
    """매우 극단적 음수 FR에서도 confidence는 1.0 이하."""
    sig = await channel.generate_signal(-0.01, 0.05)  # short_pct = 95.2%
    assert sig.signal == "LONG"
    assert sig.confidence <= 1.0


# ── 14. Signal source is FUNDING_BASIS ──


@pytest.mark.asyncio
async def test_signal_source_is_funding_basis_short(channel: FundingBasisChannel) -> None:
    """SHORT 시그널의 source는 FUNDING_BASIS."""
    sig = await channel.generate_signal(0.001, 3.0)
    assert sig.source == SignalSource.FUNDING_BASIS


@pytest.mark.asyncio
async def test_signal_source_is_funding_basis_long(channel: FundingBasisChannel) -> None:
    """LONG 시그널의 source는 FUNDING_BASIS."""
    sig = await channel.generate_signal(-0.001, 0.3)
    assert sig.source == SignalSource.FUNDING_BASIS


@pytest.mark.asyncio
async def test_signal_source_is_funding_basis_wait(channel: FundingBasisChannel) -> None:
    """WAIT 시그널의 source는 FUNDING_BASIS."""
    sig = await channel.generate_signal(0.0001, 1.0)
    assert sig.source == SignalSource.FUNDING_BASIS


@pytest.mark.asyncio
async def test_signal_source_is_funding_basis_none(channel: FundingBasisChannel) -> None:
    """None 입력 시에도 source는 FUNDING_BASIS."""
    sig = await channel.generate_signal(None, None)
    assert sig.source == SignalSource.FUNDING_BASIS


# ── 15. Weight is 0.15 ──


@pytest.mark.asyncio
async def test_weight_is_015_for_short(channel: FundingBasisChannel) -> None:
    sig = await channel.generate_signal(0.001, 3.0)
    assert sig.weight == 0.15


@pytest.mark.asyncio
async def test_weight_is_015_for_long(channel: FundingBasisChannel) -> None:
    sig = await channel.generate_signal(-0.001, 0.3)
    assert sig.weight == 0.15


@pytest.mark.asyncio
async def test_weight_is_015_for_wait(channel: FundingBasisChannel) -> None:
    sig = await channel.generate_signal(0.0001, 1.0)
    assert sig.weight == 0.15


# ── 16. Confidence is between 0 and 1 ──


@pytest.mark.asyncio
async def test_confidence_range_short(channel: FundingBasisChannel) -> None:
    sig = await channel.generate_signal(0.001, 2.0)
    assert 0 <= sig.confidence <= 1


@pytest.mark.asyncio
async def test_confidence_range_long(channel: FundingBasisChannel) -> None:
    sig = await channel.generate_signal(-0.001, 0.3)
    assert 0 <= sig.confidence <= 1


@pytest.mark.asyncio
async def test_confidence_zero_for_wait(channel: FundingBasisChannel) -> None:
    sig = await channel.generate_signal(0.0001, 1.0)
    assert sig.confidence == 0.0


# ── 17. Reason messages contain FR and ratio info ──


@pytest.mark.asyncio
async def test_reason_contains_fr_info_short(channel: FundingBasisChannel) -> None:
    sig = await channel.generate_signal(0.001, 3.0)
    assert "FR=" in sig.reason
    assert "Long=" in sig.reason


@pytest.mark.asyncio
async def test_reason_contains_fr_info_long(channel: FundingBasisChannel) -> None:
    sig = await channel.generate_signal(-0.001, 0.3)
    assert "FR=" in sig.reason
    assert "Short=" in sig.reason


@pytest.mark.asyncio
async def test_reason_contains_neutral_info(channel: FundingBasisChannel) -> None:
    sig = await channel.generate_signal(0.0001, 1.0)
    assert "중립" in sig.reason
    assert "FR=" in sig.reason


# ── 18. Zero funding rate -> WAIT ──


@pytest.mark.asyncio
async def test_zero_funding_rate_wait(channel: FundingBasisChannel) -> None:
    """FR=0 -> WAIT."""
    sig = await channel.generate_signal(0.0, 1.0)
    assert sig.signal == "WAIT"


# ── 19. Ratio = 1.0 (50/50) -> WAIT ──


@pytest.mark.asyncio
async def test_ratio_one_balanced_wait(channel: FundingBasisChannel) -> None:
    """ratio=1.0 (50/50) -> WAIT."""
    sig = await channel.generate_signal(0.0001, 1.0)
    assert sig.signal == "WAIT"


# ── 20. Very high ratio (e.g., 10.0) ──


@pytest.mark.asyncio
async def test_very_high_ratio_long_pct_calculation(channel: FundingBasisChannel) -> None:
    """ratio=10.0 -> long_pct = 90.9%, short_pct = 9.1%."""
    sig = await channel.generate_signal(0.001, 10.0)
    assert sig.signal == "SHORT"  # extreme FR + extremely crowded longs


# ── 21. Very low ratio (e.g., 0.1) ──


@pytest.mark.asyncio
async def test_very_low_ratio_short_pct_calculation(channel: FundingBasisChannel) -> None:
    """ratio=0.1 -> long_pct = 9.1%, short_pct = 90.9%."""
    sig = await channel.generate_signal(-0.001, 0.1)
    assert sig.signal == "LONG"  # extreme negative FR + extremely crowded shorts


# ── 22. Negative ratio handling ──


@pytest.mark.asyncio
async def test_negative_ratio_does_not_crash(channel: FundingBasisChannel) -> None:
    """음수 ratio -> 크래시 없이 처리 (에러 또는 WAIT)."""
    sig = await channel.generate_signal(0.001, -1.0)
    # ZeroDivisionError or weird math -> error handler catches
    assert isinstance(sig, IndividualSignal)
    assert sig.signal in ("WAIT", "SHORT", "LONG")


@pytest.mark.asyncio
async def test_zero_ratio_does_not_crash(channel: FundingBasisChannel) -> None:
    """ratio=0 -> 크래시 없이 처리."""
    sig = await channel.generate_signal(0.001, 0.0)
    assert isinstance(sig, IndividualSignal)


# ── Additional edge cases ──


@pytest.mark.asyncio
async def test_returns_individual_signal_type(channel: FundingBasisChannel) -> None:
    """반환 타입이 IndividualSignal인지 확인."""
    sig = await channel.generate_signal(0.001, 2.0)
    assert isinstance(sig, IndividualSignal)


@pytest.mark.asyncio
async def test_short_confidence_calculation(channel: FundingBasisChannel) -> None:
    """SHORT 시그널 confidence 계산 정확성."""
    # FR=0.0005, ratio=0.65/0.35 -> long_pct=0.65
    # confidence = min(1.0, (0.0005/0.0005)*0.5 + (0.65-0.5)*2*0.5)
    #            = min(1.0, 0.5 + 0.15) = 0.65
    ratio = 0.65 / 0.35
    sig = await channel.generate_signal(0.0005, ratio)
    assert sig.signal == "SHORT"
    assert sig.confidence == pytest.approx(0.65, abs=0.01)


@pytest.mark.asyncio
async def test_long_confidence_calculation(channel: FundingBasisChannel) -> None:
    """LONG 시그널 confidence 계산 정확성."""
    # FR=-0.0003, ratio=0.40/0.60 -> short_pct=0.60
    # confidence = min(1.0, (0.0003/0.0003)*0.5 + (0.60-0.5)*2*0.5)
    #            = min(1.0, 0.5 + 0.10) = 0.60
    ratio = 0.40 / 0.60
    sig = await channel.generate_signal(-0.0003, ratio)
    assert sig.signal == "LONG"
    assert sig.confidence == pytest.approx(0.60, abs=0.01)
