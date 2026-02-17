"""LeverageTopologyChannel 테스트.

OI + Price 패턴 기반 레버리지 구조 분석 채널 테스트.
"""
import pytest

from src.ai.channels.leverage_topology import LeverageTopologyChannel
from src.ai.ensemble import IndividualSignal, SignalSource


@pytest.fixture
def channel() -> LeverageTopologyChannel:
    return LeverageTopologyChannel()


def _make_history(pairs: list[tuple[float, float]]) -> list[dict]:
    """(oi, price) 쌍으로 히스토리 생성."""
    return [{"oi": oi, "price": price} for oi, price in pairs]


# ── 1. OI↑+Price↑ pattern → LONG ──


@pytest.mark.asyncio
async def test_oi_up_price_up_long(channel: LeverageTopologyChannel) -> None:
    """OI↑+Price↑ 패턴이 지속되면 LONG 시그널."""
    history = _make_history([
        (100, 50000),
        (110, 51000),
        (120, 52000),
        (130, 53000),
    ])
    sig = await channel.generate_signal(140, 54000, history)
    assert sig.signal == "LONG"


@pytest.mark.asyncio
async def test_oi_up_price_up_strong_trend(channel: LeverageTopologyChannel) -> None:
    """모든 구간 OI↑+P↑ → 강한 LONG."""
    history = _make_history([
        (100, 50000),
        (120, 51000),
        (140, 52000),
        (160, 53000),
        (180, 54000),
    ])
    sig = await channel.generate_signal(200, 55000, history)
    assert sig.signal == "LONG"
    assert sig.confidence > 0


# ── 2. OI↓+Price↓ pattern → SHORT (cascade) ──


@pytest.mark.asyncio
async def test_oi_down_price_down_short(channel: LeverageTopologyChannel) -> None:
    """OI↓+Price↓ 패턴 → 청산 캐스케이드 SHORT."""
    history = _make_history([
        (200, 55000),
        (180, 54000),
        (160, 53000),
        (140, 52000),
    ])
    sig = await channel.generate_signal(120, 51000, history)
    assert sig.signal == "SHORT"


@pytest.mark.asyncio
async def test_cascade_pattern_strong(channel: LeverageTopologyChannel) -> None:
    """강한 OI↓P↓ 캐스케이드 → SHORT."""
    history = _make_history([
        (300, 60000),
        (250, 58000),
        (200, 56000),
        (150, 54000),
        (100, 52000),
    ])
    sig = await channel.generate_signal(80, 50000, history)
    assert sig.signal == "SHORT"
    assert sig.confidence > 0


# ── 3. OI↑+Price↓ pattern → divergence (negative score → WAIT) ──


@pytest.mark.asyncio
async def test_oi_up_price_down_divergence(channel: LeverageTopologyChannel) -> None:
    """OI↑+Price↓ 패턴 → 디버전스 (WAIT)."""
    history = _make_history([
        (100, 55000),
        (120, 54000),
        (140, 53000),
        (160, 52000),
    ])
    sig = await channel.generate_signal(180, 51000, history)
    # OI↑P↓ each = -10, 4 intervals => -40 <= -15 => WAIT (divergence)
    assert sig.signal == "WAIT"
    assert "디버전스" in sig.reason


# ── 4. OI↓+Price↑ pattern → squeeze (negative score → WAIT) ──


@pytest.mark.asyncio
async def test_oi_down_price_up_squeeze(channel: LeverageTopologyChannel) -> None:
    """OI↓+Price↑ 패턴 → 숏 스퀴즈 (WAIT)."""
    history = _make_history([
        (200, 50000),
        (180, 51000),
        (160, 52000),
        (140, 53000),
    ])
    sig = await channel.generate_signal(120, 54000, history)
    # OI↓P↑ each = -15, 4 intervals => -60 <= -15 => WAIT (divergence)
    assert sig.signal == "WAIT"
    assert "디버전스" in sig.reason


# ── 5. Mixed patterns → score calculation ──


@pytest.mark.asyncio
async def test_mixed_patterns_score(channel: LeverageTopologyChannel) -> None:
    """혼합 패턴 → 점수 합산."""
    # OI↑P↑ (+15), OI↓P↓ (+20), OI↑P↑ (+15) = +50 >= 15 → signal
    history = _make_history([
        (100, 50000),
        (110, 51000),   # OI↑P↑
        (100, 50000),   # OI↓P↓
        (110, 51000),   # OI↑P↑
    ])
    sig = await channel.generate_signal(120, 52000, history)  # OI↑P↑
    assert sig.signal in ("LONG", "SHORT")


@pytest.mark.asyncio
async def test_mixed_patterns_cancel_out(channel: LeverageTopologyChannel) -> None:
    """상반된 패턴이 상쇄되면 WAIT."""
    # OI↑P↑ (+15), OI↓P↑ (-15) = 0 → WAIT
    history = _make_history([
        (100, 50000),
        (110, 51000),  # OI↑P↑ +15
        (100, 52000),  # OI↓P↑ -15
    ])
    # current: OI same, price same → no pattern
    sig = await channel.generate_signal(100, 52000, history)
    assert sig.signal == "WAIT"


# ── 6. current_oi=None → WAIT ──


@pytest.mark.asyncio
async def test_current_oi_none_wait(channel: LeverageTopologyChannel) -> None:
    """current_oi=None → WAIT."""
    history = _make_history([(100, 50000), (110, 51000), (120, 52000)])
    sig = await channel.generate_signal(None, 54000, history)
    assert sig.signal == "WAIT"
    assert sig.confidence == 0.0
    assert "데이터 없음" in sig.reason


# ── 7. current_price=None → WAIT ──


@pytest.mark.asyncio
async def test_current_price_none_wait(channel: LeverageTopologyChannel) -> None:
    """current_price=None → WAIT."""
    history = _make_history([(100, 50000), (110, 51000), (120, 52000)])
    sig = await channel.generate_signal(130, None, history)
    assert sig.signal == "WAIT"
    assert sig.confidence == 0.0
    assert "데이터 없음" in sig.reason


# ── 8. Empty history → WAIT ──


@pytest.mark.asyncio
async def test_empty_history_wait(channel: LeverageTopologyChannel) -> None:
    """빈 히스토리 → WAIT."""
    sig = await channel.generate_signal(130, 54000, [])
    assert sig.signal == "WAIT"
    assert "데이터 없음" in sig.reason


@pytest.mark.asyncio
async def test_none_history_wait(channel: LeverageTopologyChannel) -> None:
    """None 히스토리 → WAIT."""
    sig = await channel.generate_signal(130, 54000, None)
    assert sig.signal == "WAIT"
    assert "데이터 없음" in sig.reason


# ── 9. History < MIN_HISTORY → WAIT ──


@pytest.mark.asyncio
async def test_history_less_than_min_wait(channel: LeverageTopologyChannel) -> None:
    """히스토리 < MIN_HISTORY → WAIT."""
    history = _make_history([(100, 50000), (110, 51000)])
    sig = await channel.generate_signal(120, 52000, history)
    assert sig.signal == "WAIT"
    assert "히스토리 부족" in sig.reason


@pytest.mark.asyncio
async def test_history_exactly_min_ok(channel: LeverageTopologyChannel) -> None:
    """히스토리 == MIN_HISTORY → 정상 동작."""
    history = _make_history([
        (100, 50000),
        (110, 51000),
        (120, 52000),
    ])
    sig = await channel.generate_signal(130, 53000, history)
    # Should not return "히스토리 부족"
    assert "히스토리 부족" not in sig.reason


# ── 10. Score above SIGNAL_THRESHOLD → directional signal ──


@pytest.mark.asyncio
async def test_score_above_threshold_gives_signal(channel: LeverageTopologyChannel) -> None:
    """score >= SIGNAL_THRESHOLD → 방향성 시그널."""
    # All OI↑P↑: 15*4 = 60 >> 15
    history = _make_history([
        (100, 50000),
        (110, 51000),
        (120, 52000),
        (130, 53000),
    ])
    sig = await channel.generate_signal(140, 54000, history)
    assert sig.signal in ("LONG", "SHORT")


# ── 11. Score below -SIGNAL_THRESHOLD → WAIT (divergence) ──


@pytest.mark.asyncio
async def test_score_below_neg_threshold_wait(channel: LeverageTopologyChannel) -> None:
    """score <= -SIGNAL_THRESHOLD → WAIT (디버전스)."""
    # All OI↑P↓: -10*4 = -40 <= -15
    history = _make_history([
        (100, 55000),
        (120, 54000),
        (140, 53000),
        (160, 52000),
    ])
    sig = await channel.generate_signal(180, 51000, history)
    assert sig.signal == "WAIT"


# ── 12. Score between thresholds → WAIT ──


@pytest.mark.asyncio
async def test_score_between_thresholds_wait(channel: LeverageTopologyChannel) -> None:
    """score가 임계값 사이 → WAIT."""
    # OI↑P↑ (+15), OI↑P↓ (-10) = +5. Then current → depends.
    # Let's make score small: OI↑P↑ (+15), OI↓P↑ (-15) = 0
    history = _make_history([
        (100, 50000),
        (110, 51000),   # OI↑P↑ +15
        (100, 52000),   # OI↓P↑ -15
    ])
    sig = await channel.generate_signal(100, 52000, history)  # no change
    assert sig.signal == "WAIT"
    assert "중립" in sig.reason


# ── 13. Source is SignalSource.LEVERAGE_TOPOLOGY ──


@pytest.mark.asyncio
async def test_source_is_leverage_topology_long(channel: LeverageTopologyChannel) -> None:
    history = _make_history([
        (100, 50000), (110, 51000), (120, 52000), (130, 53000),
    ])
    sig = await channel.generate_signal(140, 54000, history)
    assert sig.source == SignalSource.LEVERAGE_TOPOLOGY


@pytest.mark.asyncio
async def test_source_is_leverage_topology_wait(channel: LeverageTopologyChannel) -> None:
    sig = await channel.generate_signal(None, None, None)
    assert sig.source == SignalSource.LEVERAGE_TOPOLOGY


@pytest.mark.asyncio
async def test_source_is_leverage_topology_short(channel: LeverageTopologyChannel) -> None:
    history = _make_history([
        (200, 55000), (180, 54000), (160, 53000), (140, 52000),
    ])
    sig = await channel.generate_signal(120, 51000, history)
    assert sig.source == SignalSource.LEVERAGE_TOPOLOGY


# ── 14. Weight is 0.15 ──


@pytest.mark.asyncio
async def test_weight_is_015_long(channel: LeverageTopologyChannel) -> None:
    history = _make_history([
        (100, 50000), (110, 51000), (120, 52000), (130, 53000),
    ])
    sig = await channel.generate_signal(140, 54000, history)
    assert sig.weight == 0.15


@pytest.mark.asyncio
async def test_weight_is_015_wait(channel: LeverageTopologyChannel) -> None:
    sig = await channel.generate_signal(None, None, None)
    assert sig.weight == 0.15


@pytest.mark.asyncio
async def test_weight_is_015_short(channel: LeverageTopologyChannel) -> None:
    history = _make_history([
        (200, 55000), (180, 54000), (160, 53000), (140, 52000),
    ])
    sig = await channel.generate_signal(120, 51000, history)
    assert sig.weight == 0.15


# ── 15. Consistent trend: all OI↑P↑ → strong LONG ──


@pytest.mark.asyncio
async def test_consistent_oi_up_price_up_strong_long(channel: LeverageTopologyChannel) -> None:
    """일관된 OI↑P↑ → 강한 LONG."""
    history = _make_history([
        (100, 50000),
        (150, 52000),
        (200, 54000),
        (250, 56000),
        (300, 58000),
        (350, 60000),
    ])
    sig = await channel.generate_signal(400, 62000, history)
    assert sig.signal == "LONG"
    assert sig.confidence > 0.5


# ── Additional edge cases ──


@pytest.mark.asyncio
async def test_returns_individual_signal_type(channel: LeverageTopologyChannel) -> None:
    """반환 타입이 IndividualSignal인지 확인."""
    sig = await channel.generate_signal(None, None, None)
    assert isinstance(sig, IndividualSignal)


@pytest.mark.asyncio
async def test_confidence_range(channel: LeverageTopologyChannel) -> None:
    """confidence는 0~1 범위."""
    history = _make_history([
        (100, 50000), (110, 51000), (120, 52000), (130, 53000),
    ])
    sig = await channel.generate_signal(140, 54000, history)
    assert 0 <= sig.confidence <= 1


@pytest.mark.asyncio
async def test_confidence_zero_for_none_data(channel: LeverageTopologyChannel) -> None:
    sig = await channel.generate_signal(None, 50000, None)
    assert sig.confidence == 0.0


@pytest.mark.asyncio
async def test_all_none_inputs(channel: LeverageTopologyChannel) -> None:
    sig = await channel.generate_signal(None, None, None)
    assert sig.signal == "WAIT"
    assert sig.confidence == 0.0


@pytest.mark.asyncio
async def test_reason_contains_score_info_long(channel: LeverageTopologyChannel) -> None:
    """LONG reason에 score 정보 포함."""
    history = _make_history([
        (100, 50000), (110, 51000), (120, 52000), (130, 53000),
    ])
    sig = await channel.generate_signal(140, 54000, history)
    assert "score=" in sig.reason


@pytest.mark.asyncio
async def test_reason_contains_score_info_short(channel: LeverageTopologyChannel) -> None:
    """SHORT reason에 score 정보 포함."""
    history = _make_history([
        (200, 55000), (180, 54000), (160, 53000), (140, 52000),
    ])
    sig = await channel.generate_signal(120, 51000, history)
    assert "score=" in sig.reason


@pytest.mark.asyncio
async def test_oi_no_change_no_pattern(channel: LeverageTopologyChannel) -> None:
    """OI 변화 없음 → 패턴 없음 → score=0 → WAIT."""
    history = _make_history([
        (100, 50000),
        (100, 50000),
        (100, 50000),
    ])
    sig = await channel.generate_signal(100, 50000, history)
    assert sig.signal == "WAIT"


@pytest.mark.asyncio
async def test_price_no_change_no_pattern(channel: LeverageTopologyChannel) -> None:
    """Price 변화 없음 → 패턴 없음 → WAIT."""
    history = _make_history([
        (100, 50000),
        (110, 50000),
        (120, 50000),
    ])
    sig = await channel.generate_signal(130, 50000, history)
    assert sig.signal == "WAIT"
