"""SmartMoneyDivergenceChannel 테스트.

Top Trader vs 가격 디버전스 감지 채널 테스트.
"""
import pytest

from src.ai.channels.smart_money_divergence import SmartMoneyDivergenceChannel
from src.ai.ensemble import IndividualSignal, SignalSource


@pytest.fixture
def channel() -> SmartMoneyDivergenceChannel:
    return SmartMoneyDivergenceChannel()


# ── 1. Smart LONG + Price DOWN → divergence LONG ──


@pytest.mark.asyncio
async def test_smart_long_price_down_divergence_long(channel: SmartMoneyDivergenceChannel) -> None:
    """Top traders net long + 가격 하락 → 디버전스 LONG."""
    # ratio=1.5 -> long_pct = 1.5/2.5 = 60% > 55%
    sig = await channel.generate_signal(1.5, -0.005)
    assert sig.signal == "LONG"
    assert "디버전스" in sig.reason


@pytest.mark.asyncio
async def test_strong_smart_long_divergence(channel: SmartMoneyDivergenceChannel) -> None:
    """매우 강한 smart long + 가격 하락 → LONG."""
    # ratio=3.0 -> long_pct = 75%
    sig = await channel.generate_signal(3.0, -0.01)
    assert sig.signal == "LONG"
    assert sig.confidence > 0.3


# ── 2. Smart SHORT + Price UP → divergence SHORT ──


@pytest.mark.asyncio
async def test_smart_short_price_up_divergence_short(channel: SmartMoneyDivergenceChannel) -> None:
    """Top traders net short + 가격 상승 → 디버전스 SHORT."""
    # ratio=0.6 -> long_pct = 0.6/1.6 = 37.5% < 45%
    sig = await channel.generate_signal(0.6, 0.005)
    assert sig.signal == "SHORT"
    assert "디버전스" in sig.reason


@pytest.mark.asyncio
async def test_strong_smart_short_divergence(channel: SmartMoneyDivergenceChannel) -> None:
    """매우 강한 smart short + 가격 상승 → SHORT."""
    # ratio=0.3 -> long_pct = 0.3/1.3 = 23.1%
    sig = await channel.generate_signal(0.3, 0.01)
    assert sig.signal == "SHORT"
    assert sig.confidence > 0.3


# ── 3. Smart LONG + Price UP → convergence LONG (weak) ──


@pytest.mark.asyncio
async def test_smart_long_price_up_convergence_long(channel: SmartMoneyDivergenceChannel) -> None:
    """Top traders net long + 가격 상승 → 컨버전스 LONG (약한)."""
    sig = await channel.generate_signal(1.5, 0.005)
    assert sig.signal == "LONG"
    assert "컨버전스" in sig.reason


@pytest.mark.asyncio
async def test_convergence_long_confidence_is_weak(channel: SmartMoneyDivergenceChannel) -> None:
    """컨버전스 LONG은 약한 confidence (최대 0.6)."""
    sig = await channel.generate_signal(1.5, 0.005)
    assert sig.confidence <= 0.6


# ── 4. Smart SHORT + Price DOWN → convergence SHORT (weak) ──


@pytest.mark.asyncio
async def test_smart_short_price_down_convergence_short(channel: SmartMoneyDivergenceChannel) -> None:
    """Top traders net short + 가격 하락 → 컨버전스 SHORT (약한)."""
    sig = await channel.generate_signal(0.6, -0.005)
    assert sig.signal == "SHORT"
    assert "컨버전스" in sig.reason


@pytest.mark.asyncio
async def test_convergence_short_confidence_is_weak(channel: SmartMoneyDivergenceChannel) -> None:
    """컨버전스 SHORT은 약한 confidence (최대 0.6)."""
    sig = await channel.generate_signal(0.6, -0.005)
    assert sig.confidence <= 0.6


# ── 5. Neutral smart money → WAIT ──


@pytest.mark.asyncio
async def test_neutral_smart_money_wait(channel: SmartMoneyDivergenceChannel) -> None:
    """중립 smart money → WAIT."""
    # ratio=1.0 -> long_pct = 50%, between 45% and 55%
    sig = await channel.generate_signal(1.0, 0.005)
    assert sig.signal == "WAIT"
    assert "중립" in sig.reason


# ── 6. Flat price → WAIT ──


@pytest.mark.asyncio
async def test_flat_price_wait(channel: SmartMoneyDivergenceChannel) -> None:
    """가격 변화 없음 → WAIT."""
    sig = await channel.generate_signal(1.5, 0.0)
    assert sig.signal == "WAIT"


@pytest.mark.asyncio
async def test_flat_price_within_threshold_wait(channel: SmartMoneyDivergenceChannel) -> None:
    """가격 변화가 임계값 이내 → WAIT."""
    sig = await channel.generate_signal(1.5, 0.0005)  # < 0.001
    assert sig.signal == "WAIT"


# ── 7. top_ls_ratio=None → WAIT ──


@pytest.mark.asyncio
async def test_top_ls_ratio_none_wait(channel: SmartMoneyDivergenceChannel) -> None:
    sig = await channel.generate_signal(None, 0.005)
    assert sig.signal == "WAIT"
    assert sig.confidence == 0.0
    assert "데이터 없음" in sig.reason


# ── 8. price_change_pct=None → WAIT ──


@pytest.mark.asyncio
async def test_price_change_none_wait(channel: SmartMoneyDivergenceChannel) -> None:
    sig = await channel.generate_signal(1.5, None)
    assert sig.signal == "WAIT"
    assert sig.confidence == 0.0
    assert "데이터 없음" in sig.reason


@pytest.mark.asyncio
async def test_both_none_wait(channel: SmartMoneyDivergenceChannel) -> None:
    sig = await channel.generate_signal(None, None)
    assert sig.signal == "WAIT"
    assert sig.confidence == 0.0


# ── 9. History analysis impact ──


@pytest.mark.asyncio
async def test_history_strengthens_divergence(channel: SmartMoneyDivergenceChannel) -> None:
    """히스토리가 있으면 confidence가 변화 (positive bias)."""
    # All history ratios > 0.55 long → long bias
    history = [
        {"ratio": 2.0, "price": 50000},
        {"ratio": 2.5, "price": 49000},
        {"ratio": 3.0, "price": 48000},
    ]
    sig_with = await channel.generate_signal(1.5, -0.005, history)
    sig_without = await channel.generate_signal(1.5, -0.005, None)
    # Both should be LONG, but with history may have different confidence
    assert sig_with.signal == "LONG"
    assert sig_without.signal == "LONG"


@pytest.mark.asyncio
async def test_history_too_short_ignored(channel: SmartMoneyDivergenceChannel) -> None:
    """히스토리 < MIN_HISTORY → 히스토리 무시."""
    history = [{"ratio": 2.0, "price": 50000}]  # only 1, need 3
    sig = await channel.generate_signal(1.5, -0.005, history)
    assert sig.signal == "LONG"  # still works, just no history boost


# ── 10. Boundary: ratio exactly at SMART_LONG_THRESHOLD ──


@pytest.mark.asyncio
async def test_boundary_ratio_at_smart_long_threshold(channel: SmartMoneyDivergenceChannel) -> None:
    """ratio에서 long_pct = 정확히 55%."""
    # long_pct = ratio / (1 + ratio) = 0.55
    # ratio = 0.55 / 0.45 = 1.2222...
    ratio = 0.55 / 0.45
    sig = await channel.generate_signal(ratio, -0.005)
    assert sig.signal == "LONG"  # >= threshold


@pytest.mark.asyncio
async def test_boundary_ratio_just_below_smart_long(channel: SmartMoneyDivergenceChannel) -> None:
    """ratio에서 long_pct가 55% 미만 → NEUTRAL."""
    # long_pct < 0.55, > 0.45 → NEUTRAL
    ratio = 0.54 / 0.46  # long_pct = 54%
    sig = await channel.generate_signal(ratio, -0.005)
    assert sig.signal == "WAIT"


# ── 11. Boundary: price_change_pct exactly at threshold ──


@pytest.mark.asyncio
async def test_boundary_price_at_up_threshold(channel: SmartMoneyDivergenceChannel) -> None:
    """price_change_pct = 정확히 PRICE_UP_THRESHOLD (0.001) → FLAT (not >)."""
    sig = await channel.generate_signal(1.5, 0.001)
    # 0.001 is NOT > 0.001, it's ==, so FLAT → WAIT
    assert sig.signal == "WAIT"


@pytest.mark.asyncio
async def test_boundary_price_just_above_up_threshold(channel: SmartMoneyDivergenceChannel) -> None:
    """price_change_pct > 0.001 → UP."""
    sig = await channel.generate_signal(1.5, 0.0011)
    assert sig.signal == "LONG"  # smart LONG + price UP = convergence LONG


@pytest.mark.asyncio
async def test_boundary_price_at_down_threshold(channel: SmartMoneyDivergenceChannel) -> None:
    """price_change_pct = 정확히 PRICE_DOWN_THRESHOLD (-0.001) → FLAT."""
    sig = await channel.generate_signal(1.5, -0.001)
    # -0.001 is NOT < -0.001, it's ==, so FLAT → WAIT
    assert sig.signal == "WAIT"


# ── 12. Source is SignalSource.SMART_MONEY ──


@pytest.mark.asyncio
async def test_source_is_smart_money_long(channel: SmartMoneyDivergenceChannel) -> None:
    sig = await channel.generate_signal(1.5, -0.005)
    assert sig.source == SignalSource.SMART_MONEY


@pytest.mark.asyncio
async def test_source_is_smart_money_short(channel: SmartMoneyDivergenceChannel) -> None:
    sig = await channel.generate_signal(0.6, 0.005)
    assert sig.source == SignalSource.SMART_MONEY


@pytest.mark.asyncio
async def test_source_is_smart_money_wait(channel: SmartMoneyDivergenceChannel) -> None:
    sig = await channel.generate_signal(1.0, 0.0)
    assert sig.source == SignalSource.SMART_MONEY


@pytest.mark.asyncio
async def test_source_is_smart_money_none(channel: SmartMoneyDivergenceChannel) -> None:
    sig = await channel.generate_signal(None, None)
    assert sig.source == SignalSource.SMART_MONEY


# ── 13. Weight is 0.15 ──


@pytest.mark.asyncio
async def test_weight_015_long(channel: SmartMoneyDivergenceChannel) -> None:
    sig = await channel.generate_signal(1.5, -0.005)
    assert sig.weight == 0.15


@pytest.mark.asyncio
async def test_weight_015_short(channel: SmartMoneyDivergenceChannel) -> None:
    sig = await channel.generate_signal(0.6, 0.005)
    assert sig.weight == 0.15


@pytest.mark.asyncio
async def test_weight_015_wait(channel: SmartMoneyDivergenceChannel) -> None:
    sig = await channel.generate_signal(None, None)
    assert sig.weight == 0.15


# ── 14. Confidence ranges ──


@pytest.mark.asyncio
async def test_divergence_confidence_at_least_03(channel: SmartMoneyDivergenceChannel) -> None:
    """디버전스 confidence >= 0.3."""
    sig = await channel.generate_signal(1.5, -0.005)
    assert sig.confidence >= 0.3


@pytest.mark.asyncio
async def test_divergence_confidence_max_10(channel: SmartMoneyDivergenceChannel) -> None:
    """디버전스 confidence <= 1.0."""
    sig = await channel.generate_signal(10.0, -0.01)
    assert sig.confidence <= 1.0


@pytest.mark.asyncio
async def test_convergence_confidence_max_06(channel: SmartMoneyDivergenceChannel) -> None:
    """컨버전스 confidence <= 0.6."""
    sig = await channel.generate_signal(5.0, 0.01)
    assert sig.confidence <= 0.6


@pytest.mark.asyncio
async def test_convergence_confidence_at_least_02(channel: SmartMoneyDivergenceChannel) -> None:
    """컨버전스 confidence >= 0.2."""
    # ratio = 0.55/0.45 -> long_pct = 55%, barely above threshold
    ratio = 0.55 / 0.45
    sig = await channel.generate_signal(ratio, 0.005)
    assert sig.confidence >= 0.2


# ── 15. Reason messages ──


@pytest.mark.asyncio
async def test_reason_divergence_long(channel: SmartMoneyDivergenceChannel) -> None:
    sig = await channel.generate_signal(1.5, -0.005)
    assert "SM 디버전스" in sig.reason
    assert "Top Long=" in sig.reason


@pytest.mark.asyncio
async def test_reason_divergence_short(channel: SmartMoneyDivergenceChannel) -> None:
    sig = await channel.generate_signal(0.6, 0.005)
    assert "SM 디버전스" in sig.reason
    assert "Top Long=" in sig.reason


@pytest.mark.asyncio
async def test_reason_convergence_long(channel: SmartMoneyDivergenceChannel) -> None:
    sig = await channel.generate_signal(1.5, 0.005)
    assert "SM 컨버전스" in sig.reason


@pytest.mark.asyncio
async def test_reason_convergence_short(channel: SmartMoneyDivergenceChannel) -> None:
    sig = await channel.generate_signal(0.6, -0.005)
    assert "SM 컨버전스" in sig.reason


@pytest.mark.asyncio
async def test_reason_neutral(channel: SmartMoneyDivergenceChannel) -> None:
    sig = await channel.generate_signal(1.0, 0.0)
    assert "중립" in sig.reason


# ── Additional edge cases ──


@pytest.mark.asyncio
async def test_returns_individual_signal_type(channel: SmartMoneyDivergenceChannel) -> None:
    sig = await channel.generate_signal(1.5, -0.005)
    assert isinstance(sig, IndividualSignal)


@pytest.mark.asyncio
async def test_analyze_history_all_long_bias(channel: SmartMoneyDivergenceChannel) -> None:
    """히스토리 분석: 모든 항목이 long bias."""
    history = [
        {"ratio": 2.0, "price": 50000},
        {"ratio": 2.5, "price": 51000},
        {"ratio": 3.0, "price": 52000},
    ]
    bias = channel._analyze_history(history)
    assert bias > 0  # positive = long bias


@pytest.mark.asyncio
async def test_analyze_history_all_short_bias(channel: SmartMoneyDivergenceChannel) -> None:
    """히스토리 분석: 모든 항목이 short bias."""
    history = [
        {"ratio": 0.3, "price": 50000},
        {"ratio": 0.4, "price": 51000},
        {"ratio": 0.35, "price": 52000},
    ]
    bias = channel._analyze_history(history)
    assert bias < 0  # negative = short bias


@pytest.mark.asyncio
async def test_analyze_history_empty(channel: SmartMoneyDivergenceChannel) -> None:
    assert channel._analyze_history([]) == 0.0


@pytest.mark.asyncio
async def test_analyze_history_none(channel: SmartMoneyDivergenceChannel) -> None:
    assert channel._analyze_history(None) == 0.0



# ── 3D Analysis tests ──


@pytest.mark.asyncio
async def test_3d_strong_long(channel: SmartMoneyDivergenceChannel) -> None:
    """Top Long>60% + Global Short>60% + Taker>1.3 → STRONG LONG."""
    # ratio=2.0 -> top_long_pct = 66.7%
    sig = await channel.generate_signal(
        2.0, -0.005,
        global_long_ratio=0.35,
        global_short_ratio=0.65,
        taker_buy_sell_ratio=1.5,
    )
    assert sig.signal == "LONG"
    assert "3D STRONG LONG" in sig.reason


@pytest.mark.asyncio
async def test_3d_strong_short(channel: SmartMoneyDivergenceChannel) -> None:
    """Top Short>60% + Global Long>60% + Taker<0.77 → STRONG SHORT."""
    # ratio=0.4 -> top_long_pct=28.6%, top_short_pct=71.4%
    sig = await channel.generate_signal(
        0.4, 0.005,
        global_long_ratio=0.65,
        global_short_ratio=0.35,
        taker_buy_sell_ratio=0.5,
    )
    assert sig.signal == "SHORT"
    assert "3D STRONG SHORT" in sig.reason


@pytest.mark.asyncio
async def test_3d_overheat_long_side(channel: SmartMoneyDivergenceChannel) -> None:
    """Top Long>70% + Global Long>70% + Taker 매도 우세 → 과열 SHORT."""
    # ratio=3.0 -> top_long_pct=75%
    sig = await channel.generate_signal(
        3.0, 0.005,
        global_long_ratio=0.75,
        global_short_ratio=0.25,
        taker_buy_sell_ratio=0.8,  # P2-4: taker 매도 > 매수일 때만 과열 SHORT
    )
    assert sig.signal == "SHORT"
    assert "과열" in sig.reason


@pytest.mark.asyncio
async def test_3d_overheat_short_side(channel: SmartMoneyDivergenceChannel) -> None:
    """Top Short>70% + Global Short>70% + Taker 매수 우세 → 과열 LONG."""
    # ratio=0.2 -> top_long_pct=16.7%, top_short_pct=83.3%
    sig = await channel.generate_signal(
        0.2, -0.005,
        global_long_ratio=0.25,
        global_short_ratio=0.75,
        taker_buy_sell_ratio=1.2,  # P2-4: taker 매수 > 매도일 때만 과열 LONG
    )
    assert sig.signal == "LONG"
    assert "과열" in sig.reason


@pytest.mark.asyncio
async def test_3d_partial_none_fallback_to_2d(channel: SmartMoneyDivergenceChannel) -> None:
    """3D 파라미터 일부 None → 2D 폴백."""
    sig = await channel.generate_signal(
        1.5, -0.005,
        global_long_ratio=0.35,
        global_short_ratio=None,
        taker_buy_sell_ratio=1.5,
    )
    assert sig.signal == "LONG"  # 2D: smart LONG + price DOWN → divergence LONG
    assert "SM 디버전스" in sig.reason


@pytest.mark.asyncio
async def test_3d_neutral_falls_through_to_2d(channel: SmartMoneyDivergenceChannel) -> None:
    """3D 조건 미충족 → 2D 로직으로 폴백."""
    # All 3D params present but not extreme enough
    sig = await channel.generate_signal(
        1.5, -0.005,
        global_long_ratio=0.50,
        global_short_ratio=0.50,
        taker_buy_sell_ratio=1.0,
    )
    assert sig.signal == "LONG"  # 2D divergence: smart LONG + price DOWN
    assert "SM 디버전스" in sig.reason


@pytest.mark.asyncio
async def test_3d_strong_long_confidence_range(channel: SmartMoneyDivergenceChannel) -> None:
    """3D STRONG LONG confidence >= 0.5."""
    sig = await channel.generate_signal(
        2.0, -0.005,
        global_long_ratio=0.35,
        global_short_ratio=0.65,
        taker_buy_sell_ratio=1.5,
    )
    assert sig.confidence >= 0.5
    assert sig.confidence <= 1.0


@pytest.mark.asyncio
async def test_3d_all_none_uses_2d(channel: SmartMoneyDivergenceChannel) -> None:
    """3D 파라미터 모두 None → 2D 로직."""
    sig = await channel.generate_signal(1.5, -0.005)
    assert sig.signal == "LONG"
    assert "SM 디버전스" in sig.reason
