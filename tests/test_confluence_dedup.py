"""SignalDeduplicator 테스트."""

import pytest

from src.ai.confluence.signal_dedup import SignalDeduplicator
from src.ai.ensemble import IndividualSignal, SignalSource


class TestSignalDeduplicator:
    """SignalDeduplicator 테스트."""

    def setup_method(self):
        self.dedup = SignalDeduplicator()

    def test_empty_signals(self):
        result = self.dedup.adjust_weights([])
        assert result == []

    def test_single_signal_no_change(self):
        sig = IndividualSignal(
            source=SignalSource.TSMOM, signal="LONG",
            confidence=0.8, weight=1.0,
        )
        result = self.dedup.adjust_weights([sig])
        assert len(result) == 1
        assert result[0].weight == 1.0

    def test_original_not_mutated(self):
        sig = IndividualSignal(
            source=SignalSource.TSMOM, signal="LONG",
            confidence=0.8, weight=1.0,
        )
        original_weight = sig.weight
        self.dedup.adjust_weights([sig, IndividualSignal(
            source=SignalSource.SMART_MONEY, signal="LONG",
            confidence=0.7, weight=1.0,
        )])
        assert sig.weight == original_weight

    def test_same_slow_layer_penalty(self):
        """동일 Slow 계층 (TSMOM + SmartMoney) → MI=0.3 → weight x 0.7."""
        signals = [
            IndividualSignal(source=SignalSource.TSMOM, signal="LONG", weight=1.0),
            IndividualSignal(source=SignalSource.SMART_MONEY, signal="LONG", weight=1.0),
        ]
        result = self.dedup.adjust_weights(signals)
        assert result[0].weight == pytest.approx(0.7)
        assert result[1].weight == pytest.approx(0.7)

    def test_same_medium_layer_penalty(self):
        """동일 Medium 계층 → MI=0.3 → weight x 0.7."""
        signals = [
            IndividualSignal(source=SignalSource.LEVERAGE_TOPOLOGY, signal="LONG", weight=1.0),
            IndividualSignal(source=SignalSource.FUNDING_BASIS, signal="LONG", weight=1.0),
        ]
        result = self.dedup.adjust_weights(signals)
        assert result[0].weight == pytest.approx(0.7)
        assert result[1].weight == pytest.approx(0.7)

    def test_cross_layer_penalty(self):
        """교차 계층 (Slow + Medium) → MI=0.1 → weight x 0.9."""
        signals = [
            IndividualSignal(source=SignalSource.TSMOM, signal="LONG", weight=1.0),
            IndividualSignal(source=SignalSource.FUNDING_BASIS, signal="LONG", weight=1.0),
        ]
        result = self.dedup.adjust_weights(signals)
        assert result[0].weight == pytest.approx(0.9)
        assert result[1].weight == pytest.approx(0.9)

    def test_base_layer_penalty(self):
        """Base 소스 간 → MI=0.2 → weight x 0.8."""
        signals = [
            IndividualSignal(source=SignalSource.GEMINI_AI, signal="LONG", weight=0.4),
            IndividualSignal(source=SignalSource.RULE_BASED, signal="LONG", weight=0.3),
        ]
        result = self.dedup.adjust_weights(signals)
        assert result[0].weight == pytest.approx(0.4 * 0.8)
        assert result[1].weight == pytest.approx(0.3 * 0.8)

    def test_mixed_layers_max_penalty(self):
        """혼합 계층에서 max penalty 적용."""
        signals = [
            IndividualSignal(source=SignalSource.TSMOM, signal="LONG", weight=1.0),
            IndividualSignal(source=SignalSource.SMART_MONEY, signal="LONG", weight=1.0),
            IndividualSignal(source=SignalSource.FUNDING_BASIS, signal="SHORT", weight=1.0),
        ]
        result = self.dedup.adjust_weights(signals)
        # TSMOM: same layer with SmartMoney (MI=0.3) > cross with Funding (MI=0.1) → max 0.3
        assert result[0].weight == pytest.approx(0.7)
        # SmartMoney: same layer with TSMOM (MI=0.3) → max 0.3
        assert result[1].weight == pytest.approx(0.7)
        # FundingBasis: cross with Slow (MI=0.1) — only cross-layer peers → max 0.1
        assert result[2].weight == pytest.approx(0.9)

    def test_layer_classification(self):
        """계층 분류 확인."""
        assert self.dedup._get_layer(SignalSource.TSMOM) == "slow"
        assert self.dedup._get_layer(SignalSource.SMART_MONEY) == "slow"
        assert self.dedup._get_layer(SignalSource.LEVERAGE_TOPOLOGY) == "medium"
        assert self.dedup._get_layer(SignalSource.FUNDING_BASIS) == "medium"
        assert self.dedup._get_layer(SignalSource.GEMINI_AI) == "base"
        assert self.dedup._get_layer(SignalSource.RULE_BASED) == "base"
        assert self.dedup._get_layer(SignalSource.SCORING) == "base"

    def test_signal_direction_preserved(self):
        """가중치만 변경, 시그널 방향/confidence는 보존."""
        signals = [
            IndividualSignal(source=SignalSource.TSMOM, signal="SHORT", confidence=0.9, weight=1.0),
            IndividualSignal(source=SignalSource.SMART_MONEY, signal="LONG", confidence=0.7, weight=0.8),
        ]
        result = self.dedup.adjust_weights(signals)
        assert result[0].signal == "SHORT"
        assert result[0].confidence == 0.9
        assert result[1].signal == "LONG"
        assert result[1].confidence == 0.7
