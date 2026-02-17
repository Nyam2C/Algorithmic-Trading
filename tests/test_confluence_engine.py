"""ConfluenceEngine 통합 테스트."""
from unittest.mock import AsyncMock

import pytest

from src.ai.confluence.confluence_engine import ConfluenceEngine, ConfluenceResult
from src.ai.confluence.cost_calculator import CostCalculator
from src.ai.confluence.session_classifier import SessionClassifier, TradingSession
from src.ai.confluence.signal_dedup import SignalDeduplicator
from src.ai.confluence.vitality_tracker import VitalityTracker
from src.ai.ensemble import IndividualSignal, SignalSource
from src.data.regime_detector import MarketRegime


def _make_signal(
    source: SignalSource,
    signal: str,
    confidence: float = 0.8,
    weight: float = 1.0,
) -> IndividualSignal:
    return IndividualSignal(
        source=source, signal=signal, confidence=confidence, weight=weight,
    )


class TestConfluenceResult:

    def test_dataclass_fields(self):
        result = ConfluenceResult(
            final_signal="LONG",
            confluence_score=0.5,
            net_edge=0.45,
            threshold_used=0.3,
        )
        assert result.final_signal == "LONG"
        assert result.confluence_score == 0.5
        assert result.net_edge == 0.45
        assert result.threshold_used == 0.3
        assert result.vitality is None
        assert result.step_details == {}


class TestConfluenceEngineInit:

    def test_default_init(self):
        engine = ConfluenceEngine()
        assert engine._dedup is not None
        assert engine._cost is not None
        assert engine._session is not None
        assert engine._vitality is None
        assert engine._gemini is None

    def test_custom_init(self):
        dedup = SignalDeduplicator()
        cost = CostCalculator(fee_rate=0.001)
        vit = VitalityTracker(window_size=30)
        sess = SessionClassifier()
        engine = ConfluenceEngine(
            deduplicator=dedup,
            cost_calculator=cost,
            vitality_tracker=vit,
            session_classifier=sess,
        )
        assert engine._dedup is dedup
        assert engine._cost is cost
        assert engine._vitality is vit
        assert engine._session is sess


class TestStep1Dedup:

    def test_dedup_adjusts_weights(self):
        engine = ConfluenceEngine()
        signals = [
            _make_signal(SignalSource.TSMOM, "LONG", weight=1.0),
            _make_signal(SignalSource.SMART_MONEY, "LONG", weight=1.0),
        ]
        result = engine._step1_dedup(signals)
        assert len(result) == 2
        # Same slow layer → MI=0.3 → weight * 0.7
        assert result[0].weight == pytest.approx(0.7)


class TestStep2HierarchicalGate:

    def setup_method(self):
        self.engine = ConfluenceEngine()

    def test_slow_consensus_long(self):
        signals = [
            _make_signal(SignalSource.TSMOM, "LONG"),
            _make_signal(SignalSource.SMART_MONEY, "LONG"),
        ]
        direction, details = self.engine._step2_hierarchical_gate(signals)
        assert direction == "LONG"
        assert details["slow_direction"] == "LONG"

    def test_slow_consensus_short(self):
        signals = [
            _make_signal(SignalSource.TSMOM, "SHORT"),
            _make_signal(SignalSource.SMART_MONEY, "SHORT"),
        ]
        direction, _ = self.engine._step2_hierarchical_gate(signals)
        assert direction == "SHORT"

    def test_slow_undecided_base_fallback(self):
        signals = [
            _make_signal(SignalSource.TSMOM, "LONG"),
            _make_signal(SignalSource.SMART_MONEY, "SHORT"),
            _make_signal(SignalSource.RULE_BASED, "LONG"),
            _make_signal(SignalSource.GEMINI_AI, "LONG"),
        ]
        direction, details = self.engine._step2_hierarchical_gate(signals)
        assert direction == "LONG"
        assert details["gate_path"] == "base_fallback"

    def test_all_undecided(self):
        signals = [
            _make_signal(SignalSource.TSMOM, "LONG"),
            _make_signal(SignalSource.SMART_MONEY, "SHORT"),
        ]
        direction, details = self.engine._step2_hierarchical_gate(signals)
        assert direction == "UNDECIDED"
        assert details["gate_path"] == "all_undecided"

    def test_empty_signals(self):
        direction, details = self.engine._step2_hierarchical_gate([])
        assert direction == "UNDECIDED"

    def test_slow_confirmed_by_medium(self):
        signals = [
            _make_signal(SignalSource.TSMOM, "LONG"),
            _make_signal(SignalSource.SMART_MONEY, "LONG"),
            _make_signal(SignalSource.FUNDING_BASIS, "LONG"),
        ]
        direction, details = self.engine._step2_hierarchical_gate(signals)
        assert direction == "LONG"
        assert details["gate_path"] == "slow_confirmed_by_medium"


class TestStep3RegimeSessionWeight:

    def setup_method(self):
        self.engine = ConfluenceEngine()

    def test_strong_trend_us_session(self):
        signals = [
            _make_signal(SignalSource.TSMOM, "LONG", confidence=0.9, weight=1.0),
            _make_signal(SignalSource.SMART_MONEY, "LONG", confidence=0.8, weight=1.0),
        ]
        score = self.engine._step3_regime_session_weighted_sum(
            signals, "LONG", MarketRegime.STRONG_UPTREND, TradingSession.US,
        )
        assert 0 < score <= 1.0

    def test_deep_night_lower_score(self):
        signals = [
            _make_signal(SignalSource.TSMOM, "LONG", confidence=0.8),
        ]
        us_score = self.engine._step3_regime_session_weighted_sum(
            signals, "LONG", MarketRegime.STRONG_UPTREND, TradingSession.US,
        )
        night_score = self.engine._step3_regime_session_weighted_sum(
            signals, "LONG", MarketRegime.STRONG_UPTREND, TradingSession.DEEP_NIGHT,
        )
        assert night_score < us_score

    def test_opposite_direction_negative_contribution(self):
        signals = [
            _make_signal(SignalSource.TSMOM, "SHORT", confidence=0.9),
        ]
        score = self.engine._step3_regime_session_weighted_sum(
            signals, "LONG", MarketRegime.STRONG_UPTREND, TradingSession.US,
        )
        assert score == 0.0  # clamped to 0


class TestStep4CategoryBonus:

    def setup_method(self):
        self.engine = ConfluenceEngine()

    def test_all_categories_aligned_bonus(self):
        signals = [
            _make_signal(SignalSource.TSMOM, "LONG"),       # trend
            _make_signal(SignalSource.RULE_BASED, "LONG"),  # trend
            _make_signal(SignalSource.FUNDING_BASIS, "LONG"), # structure
            _make_signal(SignalSource.SMART_MONEY, "LONG"),  # sentiment
        ]
        adjusted, conflict = self.engine._step4_category_bonus_conflict(
            signals, "LONG", 0.5,
        )
        assert adjusted == pytest.approx(0.55)  # 0.5 + 0.05
        assert conflict is False

    def test_conflict_detection(self):
        signals = [
            _make_signal(SignalSource.TSMOM, "LONG"),
            _make_signal(SignalSource.FUNDING_BASIS, "SHORT", confidence=0.7),
            _make_signal(SignalSource.SMART_MONEY, "SHORT", confidence=0.8),
        ]
        _, conflict = self.engine._step4_category_bonus_conflict(
            signals, "LONG", 0.5,
        )
        assert conflict is True


class TestStep5NetEdge:

    def test_net_edge_calculation(self):
        engine = ConfluenceEngine()
        net_edge, cost = engine._step5_net_edge(0.5, 1.0, 5)
        assert net_edge == pytest.approx(0.5 - cost)
        assert cost > 0


class TestStep6AdaptiveThreshold:

    def setup_method(self):
        self.engine = ConfluenceEngine()

    def test_strong_trend_us(self):
        t = self.engine._step6_adaptive_threshold(
            MarketRegime.STRONG_UPTREND, TradingSession.US,
        )
        assert t == 0.25

    def test_ranging_higher_threshold(self):
        strong = self.engine._step6_adaptive_threshold(
            MarketRegime.STRONG_UPTREND, TradingSession.US,
        )
        ranging = self.engine._step6_adaptive_threshold(
            MarketRegime.RANGING, TradingSession.US,
        )
        assert ranging > strong

    def test_deep_night_higher_threshold(self):
        us = self.engine._step6_adaptive_threshold(
            MarketRegime.STRONG_UPTREND, TradingSession.US,
        )
        night = self.engine._step6_adaptive_threshold(
            MarketRegime.STRONG_UPTREND, TradingSession.DEEP_NIGHT,
        )
        assert night > us


class TestStep7Vitality:

    def test_no_vitality_tracker(self):
        engine = ConfluenceEngine()
        assert engine._step7_vitality() is None

    def test_with_vitality_tracker(self):
        vit = VitalityTracker(window_size=5)
        vit.record_trade(0.02)
        engine = ConfluenceEngine(vitality_tracker=vit)
        snap = engine._step7_vitality()
        assert snap is not None
        assert snap.trade_count == 1


class TestStep8GeminiBoundary:

    def setup_method(self):
        self.engine = ConfluenceEngine()

    @pytest.mark.asyncio
    async def test_above_dead_zone_auto_pass(self):
        # threshold=0.3, upper=0.4, net_edge=0.5 > upper → LONG
        result = await self.engine._step8_gemini_boundary(
            "LONG", 0.5, 0.3, {},
        )
        assert result == "LONG"

    @pytest.mark.asyncio
    async def test_below_dead_zone_auto_block(self):
        # threshold=0.3, lower=0.2, net_edge=0.1 < lower → WAIT
        result = await self.engine._step8_gemini_boundary(
            "LONG", 0.1, 0.3, {},
        )
        assert result == "WAIT"

    @pytest.mark.asyncio
    async def test_dead_zone_no_gemini_above_threshold(self):
        # In dead zone, no gemini, net_edge >= threshold → direction
        result = await self.engine._step8_gemini_boundary(
            "LONG", 0.32, 0.3, {},
        )
        assert result == "LONG"

    @pytest.mark.asyncio
    async def test_dead_zone_no_gemini_below_threshold(self):
        # In dead zone, no gemini, net_edge < threshold → WAIT
        result = await self.engine._step8_gemini_boundary(
            "LONG", 0.25, 0.3, {},
        )
        assert result == "WAIT"

    @pytest.mark.asyncio
    async def test_dead_zone_gemini_confirms(self):
        gemini = AsyncMock()
        gemini.get_signal_with_reason = AsyncMock(return_value=("LONG", "reason"))
        engine = ConfluenceEngine(gemini_verifier=gemini)
        result = await engine._step8_gemini_boundary(
            "LONG", 0.32, 0.3, {},
        )
        assert result == "LONG"

    @pytest.mark.asyncio
    async def test_dead_zone_gemini_rejects(self):
        gemini = AsyncMock()
        gemini.get_signal_with_reason = AsyncMock(return_value=("SHORT", "bearish"))
        engine = ConfluenceEngine(gemini_verifier=gemini)
        result = await engine._step8_gemini_boundary(
            "LONG", 0.32, 0.3, {},
        )
        assert result == "WAIT"


class TestEvaluateIntegration:

    @pytest.mark.asyncio
    async def test_empty_signals_wait(self):
        engine = ConfluenceEngine()
        result = await engine.evaluate([], MarketRegime.STRONG_UPTREND, {})
        assert result.final_signal == "WAIT"
        assert result.step_details["reason"] == "no_signals"

    @pytest.mark.asyncio
    async def test_strong_long_signal(self):
        engine = ConfluenceEngine(session_classifier=_fixed_session(TradingSession.US))
        signals = [
            _make_signal(SignalSource.TSMOM, "LONG", confidence=0.9),
            _make_signal(SignalSource.SMART_MONEY, "LONG", confidence=0.8),
            _make_signal(SignalSource.FUNDING_BASIS, "LONG", confidence=0.7),
            _make_signal(SignalSource.RULE_BASED, "LONG", confidence=0.8),
        ]
        market_data = {"indicators": {"atr_pct": 1.0, "leverage": 5}}
        result = await engine.evaluate(
            signals, MarketRegime.STRONG_UPTREND, market_data,
        )
        assert result.final_signal == "LONG"
        assert result.confluence_score > 0

    @pytest.mark.asyncio
    async def test_conflict_returns_wait(self):
        engine = ConfluenceEngine(session_classifier=_fixed_session(TradingSession.US))
        signals = [
            _make_signal(SignalSource.TSMOM, "LONG", confidence=0.9),
            _make_signal(SignalSource.SMART_MONEY, "LONG", confidence=0.8),
            _make_signal(SignalSource.FUNDING_BASIS, "SHORT", confidence=0.7),
            _make_signal(SignalSource.LEVERAGE_TOPOLOGY, "SHORT", confidence=0.8),
        ]
        market_data = {"indicators": {"atr_pct": 1.0, "leverage": 5}}
        result = await engine.evaluate(
            signals, MarketRegime.STRONG_UPTREND, market_data,
        )
        assert result.final_signal == "WAIT"

    @pytest.mark.asyncio
    async def test_undecided_returns_wait(self):
        engine = ConfluenceEngine()
        signals = [
            _make_signal(SignalSource.TSMOM, "LONG", confidence=0.8),
            _make_signal(SignalSource.SMART_MONEY, "SHORT", confidence=0.8),
        ]
        result = await engine.evaluate(
            signals, MarketRegime.RANGING, {},
        )
        assert result.final_signal == "WAIT"

    @pytest.mark.asyncio
    async def test_regime_key_mapping(self):
        engine = ConfluenceEngine()
        assert engine._get_regime_key(MarketRegime.STRONG_UPTREND) == "strong_trend"
        assert engine._get_regime_key(MarketRegime.STRONG_DOWNTREND) == "strong_trend"
        assert engine._get_regime_key(MarketRegime.WEAK_UPTREND) == "weak_trend"
        assert engine._get_regime_key(MarketRegime.RANGING) == "ranging"
        assert engine._get_regime_key(MarketRegime.UNCERTAINTY) == "uncertainty"
        assert engine._get_regime_key(MarketRegime.UNKNOWN) == "weak_trend"


def _fixed_session(session: TradingSession) -> SessionClassifier:
    """고정 세션을 반환하는 mock SessionClassifier."""
    classifier = SessionClassifier()
    classifier.classify = lambda *_args, **_kwargs: session  # type: ignore[assignment]
    return classifier
