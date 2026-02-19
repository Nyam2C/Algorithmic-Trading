"""8-Step Causal Confluence Engine.

APEX-V Phase C: 시장 상황 적응형 시그널 합류 엔진.
MI 기반 중복 제거, 계층적 게이트, Regime x Session 가중합,
Net Edge 필터, Gemini Dead Zone 검증.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from src.ai.confluence.cost_calculator import CostCalculator
from src.ai.confluence.session_classifier import SessionClassifier, TradingSession
from src.ai.confluence.signal_dedup import SignalDeduplicator
from src.ai.confluence.vitality_tracker import VitalitySnapshot, VitalityTracker
from src.ai.ensemble import IndividualSignal, SignalSource
from src.data.regime_detector import MarketRegime


@dataclass
class ConfluenceResult:
    """Confluence Engine 결과.

    Attributes:
        final_signal: 최종 시그널 ("LONG", "SHORT", "WAIT")
        confluence_score: 합류 점수 (0.0 ~ 1.0)
        net_edge: 순 기대값 (score - cost)
        threshold_used: 사용된 임계값
        vitality: 전략 생존력 스냅샷
        step_details: 각 step 중간 결과
    """

    final_signal: str
    confluence_score: float
    net_edge: float
    threshold_used: float
    vitality: VitalitySnapshot | None = None
    step_details: dict[str, Any] = field(default_factory=dict)


class ConfluenceEngine:
    """8-Step Causal Confluence Engine.

    Step 1: MI 기반 중복 제거
    Step 2: 계층적 게이트 (Slow -> Medium -> Base)
    Step 3: Regime x Session 가중합
    Step 4: 카테고리 보너스/충돌
    Step 5: Net Edge (비용 차감)
    Step 6: 적응형 임계값
    Step 7: Vitality (로깅만)
    Step 8: Gemini Dead Zone 검증
    """

    # Step 3: Regime별 소스 가중치
    REGIME_WEIGHTS: dict[str, dict[str, float]] = {
        "strong_trend": {
            "tsmom": 0.20, "smart_money": 0.10, "leverage_topology": 0.15,
            "funding_basis": 0.15, "gemini": 0.15, "rule_based": 0.10,
            "scoring": 0.05, "ofi": 0.05, "whale_flow": 0.05,
        },
        "weak_trend": {
            "tsmom": 0.15, "smart_money": 0.15, "leverage_topology": 0.15,
            "funding_basis": 0.15, "gemini": 0.15, "rule_based": 0.10,
            "scoring": 0.05, "ofi": 0.05, "whale_flow": 0.05,
        },
        "ranging": {
            "tsmom": 0.10, "smart_money": 0.20, "leverage_topology": 0.15,
            "funding_basis": 0.15, "gemini": 0.15, "rule_based": 0.10,
            "scoring": 0.05, "ofi": 0.05, "whale_flow": 0.05,
        },
        "uncertainty": {
            "tsmom": 0.15, "smart_money": 0.15, "leverage_topology": 0.15,
            "funding_basis": 0.15, "gemini": 0.15, "rule_based": 0.10,
            "scoring": 0.05, "ofi": 0.05, "whale_flow": 0.05,
        },
    }

    # Step 3: Session 보정 계수
    SESSION_MULTIPLIERS: dict[TradingSession, float] = {
        TradingSession.US: 1.0,
        TradingSession.EU: 0.95,
        TradingSession.ASIA: 0.85,
        TradingSession.DEEP_NIGHT: 0.70,
    }

    # Step 4: 카테고리 분류
    CATEGORIES: dict[str, set[str]] = {
        "trend": {"tsmom", "rule_based"},
        "structure": {"leverage_topology", "funding_basis", "ofi"},
        "sentiment": {"smart_money", "gemini", "whale_flow"},
    }

    # Step 6: Regime x Session 임계값 테이블
    THRESHOLD_TABLE: dict[str, dict[TradingSession, float]] = {
        "strong_trend": {
            TradingSession.US: 0.25,
            TradingSession.EU: 0.28,
            TradingSession.ASIA: 0.30,
            TradingSession.DEEP_NIGHT: 0.35,
        },
        "weak_trend": {
            TradingSession.US: 0.30,
            TradingSession.EU: 0.33,
            TradingSession.ASIA: 0.35,
            TradingSession.DEEP_NIGHT: 0.40,
        },
        "ranging": {
            TradingSession.US: 0.50,
            TradingSession.EU: 0.53,
            TradingSession.ASIA: 0.55,
            TradingSession.DEEP_NIGHT: 0.60,
        },
        "uncertainty": {
            TradingSession.US: 0.45,
            TradingSession.EU: 0.48,
            TradingSession.ASIA: 0.50,
            TradingSession.DEEP_NIGHT: 0.55,
        },
    }

    # Step 8: Dead Zone 범위
    DEAD_ZONE_MARGIN = 0.10

    # 카테고리 보너스
    CATEGORY_BONUS = 0.05

    # Step 4 상수
    FULL_CATEGORY_COUNT = 3
    CONFLICT_CONFIDENCE_THRESHOLD = 0.6
    CONFLICT_MIN_OPPOSITE = 2

    # SignalSource.value -> 가중치 테이블 키 매핑
    _SOURCE_KEY_MAP: dict[str, str] = {
        SignalSource.TSMOM.value: "tsmom",
        SignalSource.SMART_MONEY.value: "smart_money",
        SignalSource.LEVERAGE_TOPOLOGY.value: "leverage_topology",
        SignalSource.FUNDING_BASIS.value: "funding_basis",
        SignalSource.GEMINI_AI.value: "gemini",
        SignalSource.RULE_BASED.value: "rule_based",
        SignalSource.SCORING.value: "scoring",
        SignalSource.MEMORY_GEMINI.value: "gemini",  # memory_gemini -> gemini
        SignalSource.OFI.value: "ofi",
        SignalSource.WHALE_FLOW.value: "whale_flow",
    }

    def __init__(
        self,
        deduplicator: SignalDeduplicator | None = None,
        cost_calculator: CostCalculator | None = None,
        vitality_tracker: VitalityTracker | None = None,
        session_classifier: SessionClassifier | None = None,
        gemini_verifier: Any | None = None,
    ) -> None:
        """Confluence Engine 초기화.

        Args:
            deduplicator: MI 기반 중복 제거기
            cost_calculator: 비용 계산기
            vitality_tracker: 전략 생존력 추적기
            session_classifier: 세션 분류기
            gemini_verifier: Gemini AI 검증기 (Dead Zone용)
        """
        self._dedup = deduplicator or SignalDeduplicator()
        self._cost = cost_calculator or CostCalculator()
        self._vitality = vitality_tracker
        self._session = session_classifier or SessionClassifier()
        self._gemini = gemini_verifier
        self._log = logger.bind(module="confluence")

    def _get_regime_key(self, regime: MarketRegime) -> str:
        """MarketRegime -> 가중치 테이블 키 변환."""
        if regime in (MarketRegime.STRONG_UPTREND, MarketRegime.STRONG_DOWNTREND):
            return "strong_trend"
        if regime in (MarketRegime.WEAK_UPTREND, MarketRegime.WEAK_DOWNTREND):
            return "weak_trend"
        if regime == MarketRegime.RANGING:
            return "ranging"
        if regime == MarketRegime.UNCERTAINTY:
            return "uncertainty"
        # UNKNOWN -> weak_trend (fallback)
        return "weak_trend"

    def _get_source_key(self, source: SignalSource) -> str:
        """SignalSource -> 가중치 테이블 키 변환."""
        return self._SOURCE_KEY_MAP.get(source.value, "scoring")

    async def evaluate(
        self,
        signals: list[IndividualSignal],
        regime: MarketRegime,
        market_data: dict[str, Any],
    ) -> ConfluenceResult:
        """8-Step 합류 평가.

        Args:
            signals: 개별 시그널 리스트
            regime: 현재 마켓 레짐
            market_data: 시장 데이터

        Returns:
            ConfluenceResult
        """
        step_details: dict[str, Any] = {}

        # 빈 시그널 → WAIT
        if not signals:
            return ConfluenceResult(
                final_signal="WAIT",
                confluence_score=0.0,
                net_edge=0.0,
                threshold_used=0.0,
                step_details={"reason": "no_signals"},
            )

        session = self._session.classify()

        # Step 1: MI 기반 중복 제거
        deduped = self._step1_dedup(signals)
        step_details["step1_dedup"] = {
            "original_count": len(signals),
            "adjusted_count": len(deduped),
        }

        # Step 2: 계층적 게이트
        direction, gate_details = self._step2_hierarchical_gate(deduped)
        step_details["step2_gate"] = gate_details

        if direction == "UNDECIDED":
            return ConfluenceResult(
                final_signal="WAIT",
                confluence_score=0.0,
                net_edge=0.0,
                threshold_used=0.0,
                step_details=step_details,
            )

        # Step 3: Regime x Session 가중합
        score = self._step3_regime_session_weighted_sum(
            deduped, direction, regime, session
        )
        step_details["step3_score"] = round(score, 4)

        # Step 4: 카테고리 보너스/충돌
        score, has_conflict = self._step4_category_bonus_conflict(
            deduped, direction, score
        )
        step_details["step4_adjusted_score"] = round(score, 4)
        step_details["step4_conflict"] = has_conflict

        if has_conflict:
            return ConfluenceResult(
                final_signal="WAIT",
                confluence_score=score,
                net_edge=0.0,
                threshold_used=0.0,
                step_details=step_details,
            )

        # Step 5: Net Edge
        indicators = market_data.get("indicators", {})
        atr_pct = indicators.get("atr_pct", 0.5)
        leverage = indicators.get("leverage", 5)
        net_edge, cost_penalty = self._step5_net_edge(score, atr_pct, leverage)
        step_details["step5_net_edge"] = round(net_edge, 4)
        step_details["step5_cost"] = round(cost_penalty, 4)

        # Step 6: 적응형 임계값
        threshold = self._step6_adaptive_threshold(regime, session)
        step_details["step6_threshold"] = round(threshold, 4)
        step_details["step6_session"] = session.value

        # Step 7: Vitality (로깅만)
        vitality_snap = self._step7_vitality()
        step_details["step7_vitality"] = (
            vitality_snap.level.value if vitality_snap else "no_data"
        )

        # Step 8: Gemini Dead Zone 검증
        final_signal = await self._step8_gemini_boundary(
            direction, net_edge, threshold, market_data
        )
        step_details["step8_final"] = final_signal

        self._log.info(
            f"Confluence 결과: {final_signal} "
            f"(score={score:.3f}, net_edge={net_edge:.3f}, "
            f"threshold={threshold:.3f}, regime={regime.value}, "
            f"session={session.value})"
        )

        return ConfluenceResult(
            final_signal=final_signal,
            confluence_score=score,
            net_edge=net_edge,
            threshold_used=threshold,
            vitality=vitality_snap,
            step_details=step_details,
        )

    # =====================================================================
    # Step 1: MI 기반 중복 제거
    # =====================================================================

    def _step1_dedup(
        self, signals: list[IndividualSignal]
    ) -> list[IndividualSignal]:
        """Step 1: MI 기반 시그널 중복 제거."""
        return self._dedup.adjust_weights(signals)

    # =====================================================================
    # Step 2: 계층적 게이트
    # =====================================================================

    def _step2_hierarchical_gate(
        self, signals: list[IndividualSignal]
    ) -> tuple[str, dict[str, Any]]:
        """Step 2: Slow -> Medium -> Base 계층적 방향 결정.

        Returns:
            (direction, gate_details)
            direction: "LONG", "SHORT", or "UNDECIDED"
        """
        _slow_sources = (
            SignalSource.TSMOM, SignalSource.SMART_MONEY,
            SignalSource.WHALE_FLOW,
        )
        _medium_sources = (
            SignalSource.LEVERAGE_TOPOLOGY,
            SignalSource.FUNDING_BASIS, SignalSource.OFI,
        )
        slow_signals = [
            s for s in signals if s.source in _slow_sources
        ]
        medium_signals = [
            s for s in signals if s.source in _medium_sources
        ]
        base_signals = [
            s for s in signals
            if s.source in (
                SignalSource.GEMINI_AI, SignalSource.RULE_BASED,
                SignalSource.SCORING, SignalSource.MEMORY_GEMINI,
            )
        ]

        details: dict[str, Any] = {
            "slow_count": len(slow_signals),
            "medium_count": len(medium_signals),
            "base_count": len(base_signals),
        }

        # Slow 레이어 합의 확인
        direction = self._layer_consensus(slow_signals)
        details["slow_direction"] = direction

        if direction != "UNDECIDED":
            # Medium 레이어로 확인/약화
            medium_dir = self._layer_consensus(medium_signals)
            details["medium_direction"] = medium_dir
            if medium_dir == direction:
                details["gate_path"] = "slow_confirmed_by_medium"
            elif medium_dir == "UNDECIDED":
                details["gate_path"] = "slow_only"
            else:
                # Medium이 반대 → 아직 Slow 따르되 약화 기록
                details["gate_path"] = "slow_weakened_by_medium"
            return direction, details

        # Slow 미결정 → Base fallback
        base_dir = self._layer_consensus(base_signals)
        details["base_direction"] = base_dir
        if base_dir != "UNDECIDED":
            details["gate_path"] = "base_fallback"
            return base_dir, details

        # 모든 계층 미결정
        details["gate_path"] = "all_undecided"
        return "UNDECIDED", details

    @staticmethod
    def _layer_consensus(signals: list[IndividualSignal]) -> str:
        """레이어 내 합의 방향 계산.

        Returns:
            "LONG", "SHORT", or "UNDECIDED"
        """
        if not signals:
            return "UNDECIDED"

        long_weight = sum(
            s.weight * s.confidence for s in signals if s.signal == "LONG"
        )
        short_weight = sum(
            s.weight * s.confidence for s in signals if s.signal == "SHORT"
        )

        if long_weight > 0 and short_weight == 0:
            return "LONG"
        if short_weight > 0 and long_weight == 0:
            return "SHORT"
        if long_weight > short_weight * 1.5:
            return "LONG"
        if short_weight > long_weight * 1.5:
            return "SHORT"
        return "UNDECIDED"

    # =====================================================================
    # Step 3: Regime x Session 가중합
    # =====================================================================

    def _step3_regime_session_weighted_sum(
        self,
        signals: list[IndividualSignal],
        direction: str,
        regime: MarketRegime,
        session: TradingSession,
    ) -> float:
        """Step 3: Regime x Session 적응형 가중합.

        Returns:
            confluence_score (0.0 ~ 1.0)
        """
        regime_key = self._get_regime_key(regime)
        weights = self.REGIME_WEIGHTS.get(regime_key, self.REGIME_WEIGHTS["weak_trend"])
        session_mult = self.SESSION_MULTIPLIERS.get(session, 1.0)

        weighted_sum = 0.0
        total_weight = 0.0

        for sig in signals:
            source_key = self._get_source_key(sig.source)
            regime_weight = weights.get(source_key, 0.05)

            # 방향 일치 시 양수, 반대 시 음수 기여
            if sig.signal == direction:
                contribution = sig.confidence * sig.weight
            elif sig.signal == "WAIT":
                contribution = 0.0
            else:
                contribution = (
                    -sig.confidence * sig.weight * 0.5
                )  # 반대 방향 50% 패널티

            weighted_sum += contribution * regime_weight
            total_weight += regime_weight

        raw_score = weighted_sum / total_weight if total_weight > 0 else 0.0

        # Session 보정
        return max(0.0, min(1.0, raw_score * session_mult))

    # =====================================================================
    # Step 4: 카테고리 보너스/충돌
    # =====================================================================

    def _step4_category_bonus_conflict(
        self,
        signals: list[IndividualSignal],
        direction: str,
        score: float,
    ) -> tuple[float, bool]:
        """Step 4: 카테고리 정렬 보너스 및 충돌 감지.

        Returns:
            (adjusted_score, has_conflict)
        """
        # 카테고리별 방향 집계
        category_directions: dict[str, str] = {}
        for cat_name, cat_sources in self.CATEGORIES.items():
            cat_signals = [
                s for s in signals
                if self._get_source_key(s.source) in cat_sources
                and s.signal != "WAIT"
            ]
            if not cat_signals:
                continue
            long_count = sum(1 for s in cat_signals if s.signal == "LONG")
            short_count = sum(1 for s in cat_signals if s.signal == "SHORT")
            if long_count > short_count:
                category_directions[cat_name] = "LONG"
            elif short_count > long_count:
                category_directions[cat_name] = "SHORT"

        # 3/3 카테고리 정렬 시 보너스
        aligned_count = sum(
            1 for d in category_directions.values() if d == direction
        )
        if aligned_count == self.FULL_CATEGORY_COUNT:
            score = min(1.0, score + self.CATEGORY_BONUS)

        # 충돌 감지: 강한 시그널(confidence >= 0.6) 2개 이상 반대 방향
        opposite = "SHORT" if direction == "LONG" else "LONG"
        strong_opposite = [
            s for s in signals
            if s.signal == opposite
            and s.confidence >= self.CONFLICT_CONFIDENCE_THRESHOLD
        ]
        has_conflict = len(strong_opposite) >= self.CONFLICT_MIN_OPPOSITE

        return score, has_conflict

    # =====================================================================
    # Step 5: Net Edge
    # =====================================================================

    def _step5_net_edge(
        self, score: float, atr_pct: float, leverage: int
    ) -> tuple[float, float]:
        """Step 5: Net Edge (비용 차감)."""
        return self._cost.calculate_net_edge(score, atr_pct, leverage)

    # =====================================================================
    # Step 6: 적응형 임계값
    # =====================================================================

    def _step6_adaptive_threshold(
        self, regime: MarketRegime, session: TradingSession
    ) -> float:
        """Step 6: Regime x Session 적응형 임계값."""
        regime_key = self._get_regime_key(regime)
        session_thresholds = self.THRESHOLD_TABLE.get(
            regime_key, self.THRESHOLD_TABLE["weak_trend"]
        )
        return session_thresholds.get(session, 0.35)

    # =====================================================================
    # Step 7: Vitality
    # =====================================================================

    def _step7_vitality(self) -> VitalitySnapshot | None:
        """Step 7: 전략 생존력 조회 (로깅만, 차단 안 함)."""
        if self._vitality is None:
            return None
        return self._vitality.get_vitality()

    # =====================================================================
    # Step 8: Gemini Dead Zone 검증
    # =====================================================================

    async def _step8_gemini_boundary(
        self,
        direction: str,
        net_edge: float,
        threshold: float,
        market_data: dict[str, Any],
    ) -> str:
        """Step 8: Dead Zone 경계 검증.

        threshold +/- DEAD_ZONE_MARGIN 범위에 net_edge가 있으면 Gemini 호출.
        Dead Zone 밖 위: 자동 PASS.
        Dead Zone 밖 아래: 자동 BLOCK.
        """
        upper = threshold + self.DEAD_ZONE_MARGIN
        lower = threshold - self.DEAD_ZONE_MARGIN

        if net_edge >= upper:
            return direction  # Dead Zone 위: 자동 PASS

        if net_edge < lower:
            return "WAIT"  # Dead Zone 아래: 자동 BLOCK

        # Dead Zone 내: Gemini 검증 시도
        if self._gemini is None:
            return direction if net_edge >= threshold else "WAIT"

        return await self._gemini_verify(
            direction, net_edge, threshold, market_data
        )

    async def _gemini_verify(
        self,
        direction: str,
        net_edge: float,
        threshold: float,
        market_data: dict[str, Any],
    ) -> str:
        """Dead Zone 내 Gemini 검증 호출."""
        assert self._gemini is not None  # noqa: S101
        try:
            if hasattr(self._gemini, "get_signal_with_reason"):
                gemini_signal, _reason = (
                    await self._gemini.get_signal_with_reason(
                        market_data
                    )
                )
            elif hasattr(self._gemini, "get_signal"):
                gemini_signal = await self._gemini.get_signal(
                    market_data
                )
            else:
                return (
                    direction if net_edge >= threshold else "WAIT"
                )

            if gemini_signal == direction:
                self._log.info(
                    f"Dead Zone Gemini 확인: {direction} "
                    f"(net_edge={net_edge:.3f})"
                )
                return direction
            self._log.info(
                f"Dead Zone Gemini 거부: "
                f"{gemini_signal} != {direction}"
            )
            return "WAIT"
        except Exception as e:
            self._log.warning(f"Dead Zone Gemini 호출 실패: {e}")
            return direction if net_edge >= threshold else "WAIT"
