"""앙상블 + 채널 통합 단위 테스트.

Phase B: 4채널 슬롯/setter/시그널 수집 검증.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.ai.ensemble import (
    EnsembleSignalGenerator,
    IndividualSignal,
    SignalSource,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ensemble() -> EnsembleSignalGenerator:
    """기본 앙상블 (소스 없음)."""
    return EnsembleSignalGenerator()


def _make_rule_based(signal: str = "LONG") -> MagicMock:
    mock = MagicMock()
    mock.get_signal.return_value = signal
    return mock


def _make_gemini(signal: str = "LONG") -> AsyncMock:
    mock = AsyncMock()
    mock.get_signal_with_reason = AsyncMock(return_value=(signal, "test reason"))
    mock.last_confidence = 0.8
    return mock


def _make_channel_signal(
    source: SignalSource, signal: str, confidence: float = 0.7
) -> IndividualSignal:
    return IndividualSignal(
        source=source,
        signal=signal,
        confidence=confidence,
        reason="test",
        weight=0.15,
    )


# ---------------------------------------------------------------------------
# 1. Setter 동작 확인
# ---------------------------------------------------------------------------


class TestChannelSetters:
    """채널 setter 메서드가 슬롯을 올바르게 설정하는지 확인."""

    def test_set_funding_channel(self, ensemble: EnsembleSignalGenerator) -> None:
        assert ensemble._funding_channel is None
        ch = MagicMock()
        ensemble.set_funding_channel(ch)
        assert ensemble._funding_channel is ch

    def test_set_leverage_channel(self, ensemble: EnsembleSignalGenerator) -> None:
        assert ensemble._leverage_channel is None
        ch = MagicMock()
        ensemble.set_leverage_channel(ch)
        assert ensemble._leverage_channel is ch

    def test_set_smart_money_channel(self, ensemble: EnsembleSignalGenerator) -> None:
        assert ensemble._smart_money_channel is None
        ch = MagicMock()
        ensemble.set_smart_money_channel(ch)
        assert ensemble._smart_money_channel is ch

    def test_set_tsmom_channel(self, ensemble: EnsembleSignalGenerator) -> None:
        assert ensemble._tsmom_channel is None
        ch = MagicMock()
        ensemble.set_tsmom_channel(ch)
        assert ensemble._tsmom_channel is ch


# ---------------------------------------------------------------------------
# 2. sentiment_data로 FundingBasis 시그널 생성
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_funding_channel_signal_via_sentiment_data() -> None:
    """sentiment_data 전달 시 FundingBasis 채널이 호출되어 시그널 수집."""
    ensemble = EnsembleSignalGenerator(
        rule_based_generator=_make_rule_based("WAIT"),
    )
    funding_ch = AsyncMock()
    funding_ch.generate_signal = AsyncMock(
        return_value=_make_channel_signal(SignalSource.FUNDING_BASIS, "SHORT")
    )
    ensemble.set_funding_channel(funding_ch)

    result = await ensemble.generate_ensemble_signal(
        {},
        sentiment_data={"funding_rate": 0.0005, "long_short_ratio": 2.0},
    )

    funding_ch.generate_signal.assert_called_once_with(0.0005, 2.0)
    sources = [s.source for s in result.individual_signals]
    assert SignalSource.FUNDING_BASIS in sources


# ---------------------------------------------------------------------------
# 3. klines_df로 TSMOM 시그널 생성
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tsmom_channel_signal_via_klines_df() -> None:
    """klines_df 전달 시 TSMOM 채널이 호출되어 시그널 수집."""
    ensemble = EnsembleSignalGenerator(
        rule_based_generator=_make_rule_based("WAIT"),
    )
    tsmom_ch = AsyncMock()
    tsmom_ch.generate_signal = AsyncMock(
        return_value=_make_channel_signal(SignalSource.TSMOM, "LONG")
    )
    ensemble.set_tsmom_channel(tsmom_ch)

    fake_df = MagicMock()
    result = await ensemble.generate_ensemble_signal(
        {},
        klines_df=fake_df,
    )

    tsmom_ch.generate_signal.assert_called_once_with(fake_df)
    sources = [s.source for s in result.individual_signals]
    assert SignalSource.TSMOM in sources


# ---------------------------------------------------------------------------
# 4. 7개 소스 동시 가중 투표
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_seven_sources_weighted_vote() -> None:
    """3기존 + 4채널 = 7개 소스 동시 가중 투표."""
    ensemble = EnsembleSignalGenerator(
        gemini_generator=_make_gemini("LONG"),
        rule_based_generator=_make_rule_based("LONG"),
    )

    # scoring mock
    scorer = MagicMock()
    scorer.calculate_score.return_value = MagicMock(
        signal="LONG", confidence=0.9, reasons=["test"]
    )
    ensemble.set_scoring_generator(scorer)

    # 4 channels - all LONG
    for setter, src in [
        (ensemble.set_tsmom_channel, SignalSource.TSMOM),
        (ensemble.set_funding_channel, SignalSource.FUNDING_BASIS),
        (ensemble.set_leverage_channel, SignalSource.LEVERAGE_TOPOLOGY),
        (ensemble.set_smart_money_channel, SignalSource.SMART_MONEY),
    ]:
        ch = AsyncMock()
        ch.generate_signal = AsyncMock(
            return_value=_make_channel_signal(src, "LONG")
        )
        setter(ch)

    result = await ensemble.generate_ensemble_signal(
        {},
        sentiment_data={
            "funding_rate": 0.0005,
            "long_short_ratio": 2.0,
            "open_interest": 1000.0,
            "current_price": 50000.0,
            "oi_history": [{"oi": 900, "price": 49000}],
            "ls_history": [{"ratio": 1.5, "price": 49500}],
        },
        klines_df=MagicMock(),
    )

    assert result.final_signal == "LONG"
    assert len(result.individual_signals) == 7
    assert result.metadata["sources_used"] == 7


# ---------------------------------------------------------------------------
# 5. 채널 실패 시 graceful fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_channel_failure_graceful_fallback() -> None:
    """채널 예외 발생 시 다른 소스 정상 작동."""
    ensemble = EnsembleSignalGenerator(
        rule_based_generator=_make_rule_based("LONG"),
    )

    # 실패하는 funding channel
    failing_ch = AsyncMock()
    failing_ch.generate_signal = AsyncMock(side_effect=RuntimeError("API error"))
    ensemble.set_funding_channel(failing_ch)

    result = await ensemble.generate_ensemble_signal(
        {},
        sentiment_data={"funding_rate": 0.001, "long_short_ratio": 2.0},
    )

    # rule_based만 수집됨 (funding 실패로 스킵)
    assert len(result.individual_signals) == 1
    assert result.individual_signals[0].source == SignalSource.RULE_BASED


# ---------------------------------------------------------------------------
# 6. sentiment_data=None → 채널 스킵
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_sentiment_skips_channels() -> None:
    """sentiment_data=None이면 funding/leverage/smart_money 채널 호출 안함."""
    ensemble = EnsembleSignalGenerator(
        rule_based_generator=_make_rule_based("LONG"),
    )

    funding_ch = AsyncMock()
    ensemble.set_funding_channel(funding_ch)

    result = await ensemble.generate_ensemble_signal(
        {},
        sentiment_data=None,
    )

    funding_ch.generate_signal.assert_not_called()
    assert len(result.individual_signals) == 1


# ---------------------------------------------------------------------------
# 7. 가중치 정규화 검증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_weight_normalization() -> None:
    """총 가중치가 정규화되어 비율이 유지되는지 확인."""
    ensemble = EnsembleSignalGenerator(
        rule_based_generator=_make_rule_based("LONG"),
    )

    # funding channel also LONG
    funding_ch = AsyncMock()
    funding_ch.generate_signal = AsyncMock(
        return_value=_make_channel_signal(SignalSource.FUNDING_BASIS, "LONG", 0.8)
    )
    ensemble.set_funding_channel(funding_ch)

    result = await ensemble.generate_ensemble_signal(
        {},
        sentiment_data={"funding_rate": 0.001, "long_short_ratio": 2.0},
    )

    # rule_based weight=0.3, funding weight=0.15 → total=0.45
    total_weight = sum(s.weight for s in result.individual_signals)
    assert abs(total_weight - 0.45) < 0.01
    # weighted_score is normalized by total_weight → should be positive
    assert result.weighted_score > 0


# ---------------------------------------------------------------------------
# 8. klines_df=None → TSMOM 스킵
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_klines_skips_tsmom() -> None:
    """klines_df=None이면 TSMOM 채널 호출 안함."""
    ensemble = EnsembleSignalGenerator(
        rule_based_generator=_make_rule_based("WAIT"),
    )

    tsmom_ch = AsyncMock()
    ensemble.set_tsmom_channel(tsmom_ch)

    await ensemble.generate_ensemble_signal({}, klines_df=None)

    tsmom_ch.generate_signal.assert_not_called()


# ---------------------------------------------------------------------------
# 9. SmartMoney price_change_pct 계산
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_smart_money_price_change_calculation() -> None:
    """SmartMoney 채널에 price_change_pct가 올바르게 계산되어 전달."""
    ensemble = EnsembleSignalGenerator(
        rule_based_generator=_make_rule_based("WAIT"),
    )

    sm_ch = AsyncMock()
    sm_ch.generate_signal = AsyncMock(
        return_value=_make_channel_signal(SignalSource.SMART_MONEY, "LONG")
    )
    ensemble.set_smart_money_channel(sm_ch)

    sentiment = {
        "long_short_ratio": 1.5,
        "current_price": 51000.0,
        "ls_history": [{"ratio": 1.3, "price": 50000.0}],
    }

    await ensemble.generate_ensemble_signal({}, sentiment_data=sentiment)

    call_args = sm_ch.generate_signal.call_args
    ls_ratio_arg = call_args[0][0]
    pcp_arg = call_args[0][1]
    ls_hist_arg = call_args[0][2]

    assert ls_ratio_arg == 1.5
    # price_change_pct = (51000 - 50000) / 50000 = 0.02
    assert abs(pcp_arg - 0.02) < 0.001
    assert ls_hist_arg == sentiment["ls_history"]


# ---------------------------------------------------------------------------
# 10. LeverageTopology 채널 호출
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_leverage_channel_called_with_correct_args() -> None:
    """LeverageTopology 채널에 OI, price, oi_history가 올바르게 전달."""
    ensemble = EnsembleSignalGenerator(
        rule_based_generator=_make_rule_based("WAIT"),
    )

    lev_ch = AsyncMock()
    lev_ch.generate_signal = AsyncMock(
        return_value=_make_channel_signal(SignalSource.LEVERAGE_TOPOLOGY, "WAIT")
    )
    ensemble.set_leverage_channel(lev_ch)

    oi_hist = [{"oi": 900, "price": 49000}, {"oi": 950, "price": 49500}]
    sentiment = {
        "open_interest": 1000.0,
        "current_price": 50000.0,
        "oi_history": oi_hist,
    }

    await ensemble.generate_ensemble_signal({}, sentiment_data=sentiment)

    lev_ch.generate_signal.assert_called_once_with(1000.0, 50000.0, oi_hist)
