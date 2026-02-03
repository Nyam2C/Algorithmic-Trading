"""
AI 앙상블 시스템

Phase 6.3: 다중 신호 소스 앙상블
- Gemini AI, 규칙 기반, 스코어링 신호 결합
- 가중 투표로 최종 신호 결정
- 2/3 합의 시 신호 발생
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

from loguru import logger


class SignalSource(Enum):
    """신호 소스 종류"""

    GEMINI_AI = "gemini"
    RULE_BASED = "rule_based"
    SCORING = "scoring"
    MEMORY_GEMINI = "memory_gemini"


@dataclass
class IndividualSignal:
    """개별 신호

    Attributes:
        source: 신호 소스
        signal: 신호 ("LONG", "SHORT", "WAIT")
        confidence: 신뢰도 (0 ~ 1)
        reason: 신호 생성 이유
        weight: 가중치
    """

    source: SignalSource
    signal: str
    confidence: float = 1.0
    reason: str = ""
    weight: float = 1.0

    def weighted_vote(self) -> float:
        """가중 투표 값 반환

        Returns:
            LONG: +weight, SHORT: -weight, WAIT: 0
        """
        if self.signal == "LONG":
            return self.weight * self.confidence
        elif self.signal == "SHORT":
            return -self.weight * self.confidence
        return 0.0


@dataclass
class EnsembleResult:
    """앙상블 결과

    Attributes:
        final_signal: 최종 신호
        individual_signals: 개별 신호 목록
        consensus_ratio: 합의 비율
        weighted_score: 가중 점수
        metadata: 추가 메타데이터
    """

    final_signal: str
    individual_signals: List[IndividualSignal]
    consensus_ratio: float = 0.0
    weighted_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "final_signal": self.final_signal,
            "individual_signals": [
                {
                    "source": s.source.value,
                    "signal": s.signal,
                    "confidence": round(s.confidence, 3),
                    "reason": s.reason,
                    "weight": s.weight,
                }
                for s in self.individual_signals
            ],
            "consensus_ratio": round(self.consensus_ratio, 3),
            "weighted_score": round(self.weighted_score, 3),
            "metadata": self.metadata,
        }


class EnsembleSignalGenerator:
    """앙상블 신호 생성기

    여러 신호 소스를 결합하여 최종 신호를 생성합니다.

    Example:
        >>> ensemble = EnsembleSignalGenerator()
        >>> result = await ensemble.generate_ensemble_signal(market_data, "btc-bot")
        >>> print(f"Signal: {result.final_signal}")
    """

    # 기본 가중치
    DEFAULT_WEIGHTS = {
        SignalSource.GEMINI_AI: 0.4,
        SignalSource.RULE_BASED: 0.3,
        SignalSource.SCORING: 0.3,
    }

    # 합의 임계값
    CONSENSUS_THRESHOLD = 2 / 3  # 2/3 합의 필요
    WEIGHTED_THRESHOLD = 0.3  # 가중 점수 임계값

    def __init__(
        self,
        weights: Optional[Dict[SignalSource, float]] = None,
        consensus_threshold: float = CONSENSUS_THRESHOLD,
        weighted_threshold: float = WEIGHTED_THRESHOLD,
        # 의존성 주입
        gemini_generator: Optional[Any] = None,
        rule_based_generator: Optional[Any] = None,
        scoring_generator: Optional[Any] = None,
    ) -> None:
        """앙상블 생성기 초기화

        Args:
            weights: 소스별 가중치
            consensus_threshold: 합의 임계값
            weighted_threshold: 가중 점수 임계값
            gemini_generator: Gemini AI 생성기
            rule_based_generator: 규칙 기반 생성기
            scoring_generator: 스코어링 생성기
        """
        self.weights = weights or self.DEFAULT_WEIGHTS
        self.consensus_threshold = consensus_threshold
        self.weighted_threshold = weighted_threshold

        self._gemini = gemini_generator
        self._rule_based = rule_based_generator
        self._scoring = scoring_generator

        self._log = logger.bind(module="ensemble")
        self._log.info(
            f"EnsembleSignalGenerator 초기화: weights={self.weights}"
        )

    def set_gemini_generator(self, generator: Any) -> None:
        """Gemini 생성기 설정"""
        self._gemini = generator

    def set_rule_based_generator(self, generator: Any) -> None:
        """규칙 기반 생성기 설정"""
        self._rule_based = generator

    def set_scoring_generator(self, generator: Any) -> None:
        """스코어링 생성기 설정"""
        self._scoring = generator

    async def generate_ensemble_signal(
        self,
        market_data: Dict[str, Any],
        bot_id: str = "",
    ) -> EnsembleResult:
        """앙상블 신호 생성

        Args:
            market_data: 시장 데이터
            bot_id: 봇 ID

        Returns:
            EnsembleResult
        """
        individual_signals: List[IndividualSignal] = []

        # 1. 각 소스에서 신호 수집
        # Gemini AI
        if self._gemini:
            try:
                gemini_signal = await self._get_gemini_signal(market_data)
                individual_signals.append(gemini_signal)
            except Exception as e:
                self._log.warning(f"Gemini 신호 생성 실패: {e}")

        # Rule-based
        if self._rule_based:
            try:
                rule_signal = self._get_rule_based_signal(market_data)
                individual_signals.append(rule_signal)
            except Exception as e:
                self._log.warning(f"규칙 기반 신호 생성 실패: {e}")

        # Scoring
        if self._scoring:
            try:
                scoring_signal = self._get_scoring_signal(market_data)
                individual_signals.append(scoring_signal)
            except Exception as e:
                self._log.warning(f"스코어링 신호 생성 실패: {e}")

        # 신호가 없으면 WAIT
        if not individual_signals:
            self._log.warning("신호 소스 없음 - WAIT 반환")
            return EnsembleResult(
                final_signal="WAIT",
                individual_signals=[],
                metadata={"error": "신호 소스 없음"},
            )

        # 2. 가중 투표
        final_signal, weighted_score, consensus_ratio = self._weighted_vote(
            individual_signals
        )

        result = EnsembleResult(
            final_signal=final_signal,
            individual_signals=individual_signals,
            consensus_ratio=consensus_ratio,
            weighted_score=weighted_score,
            metadata={
                "bot_id": bot_id,
                "sources_used": len(individual_signals),
            },
        )

        self._log.info(
            f"앙상블 신호: {final_signal} "
            f"(합의율={consensus_ratio:.1%}, 가중점수={weighted_score:.3f})"
        )

        return result

    async def _get_gemini_signal(
        self, market_data: Dict[str, Any]
    ) -> IndividualSignal:
        """Gemini 신호 가져오기"""
        assert self._gemini is not None, "Gemini generator is required"
        # get_signal_with_reason 사용 시도
        if hasattr(self._gemini, "get_signal_with_reason"):
            signal, reason = await self._gemini.get_signal_with_reason(market_data)
        else:
            signal = await self._gemini.get_signal(market_data)
            reason = "Gemini AI 분석"

        return IndividualSignal(
            source=SignalSource.GEMINI_AI,
            signal=signal,
            confidence=0.8,  # AI 신뢰도
            reason=reason,
            weight=self.weights.get(SignalSource.GEMINI_AI, 0.4),
        )

    def _get_rule_based_signal(
        self, market_data: Dict[str, Any]
    ) -> IndividualSignal:
        """규칙 기반 신호 가져오기"""
        assert self._rule_based is not None, "Rule-based generator is required"
        signal = self._rule_based.get_signal(market_data)

        return IndividualSignal(
            source=SignalSource.RULE_BASED,
            signal=signal,
            confidence=1.0,  # 규칙 기반은 명확
            reason="규칙 기반 분석",
            weight=self.weights.get(SignalSource.RULE_BASED, 0.3),
        )

    def _get_scoring_signal(
        self, market_data: Dict[str, Any]
    ) -> IndividualSignal:
        """스코어링 신호 가져오기"""
        assert self._scoring is not None, "Scoring generator is required"
        # calculate_score 사용 시도
        if hasattr(self._scoring, "calculate_score"):
            result = self._scoring.calculate_score(market_data)
            signal = result.signal
            confidence = result.confidence
            reason = ", ".join(result.reasons) if result.reasons else "점수 기반"
        else:
            signal = self._scoring.get_signal(market_data)
            confidence = 0.7
            reason = "점수 기반 분석"

        return IndividualSignal(
            source=SignalSource.SCORING,
            signal=signal,
            confidence=confidence,
            reason=reason,
            weight=self.weights.get(SignalSource.SCORING, 0.3),
        )

    def _weighted_vote(
        self,
        signals: List[IndividualSignal],
    ) -> Tuple[str, float, float]:
        """가중 투표

        Args:
            signals: 개별 신호 목록

        Returns:
            (final_signal, weighted_score, consensus_ratio)
        """
        if not signals:
            return "WAIT", 0.0, 0.0

        # 가중 점수 계산
        total_weight = sum(s.weight for s in signals)
        weighted_score = sum(s.weighted_vote() for s in signals)

        if total_weight > 0:
            weighted_score /= total_weight

        # 신호별 카운트
        long_count = sum(1 for s in signals if s.signal == "LONG")
        short_count = sum(1 for s in signals if s.signal == "SHORT")
        wait_count = sum(1 for s in signals if s.signal == "WAIT")

        total_count = len(signals)

        # 합의 비율 계산
        max_count = max(long_count, short_count, wait_count)
        consensus_ratio = max_count / total_count if total_count > 0 else 0

        # 최종 신호 결정
        # 1. 가중 점수 기준
        if abs(weighted_score) >= self.weighted_threshold:
            if weighted_score > 0:
                return "LONG", weighted_score, consensus_ratio
            else:
                return "SHORT", weighted_score, consensus_ratio

        # 2. 합의 기준 (2/3 이상)
        if long_count / total_count >= self.consensus_threshold:
            return "LONG", weighted_score, consensus_ratio
        elif short_count / total_count >= self.consensus_threshold:
            return "SHORT", weighted_score, consensus_ratio

        # 3. 합의 실패 -> WAIT
        return "WAIT", weighted_score, consensus_ratio

    def get_signal(self, market_data: Dict[str, Any]) -> str:
        """동기 신호 반환 (규칙 기반 + 스코어링만 사용)

        Args:
            market_data: 시장 데이터

        Returns:
            신호
        """
        signals: List[IndividualSignal] = []

        if self._rule_based:
            signals.append(self._get_rule_based_signal(market_data))

        if self._scoring:
            signals.append(self._get_scoring_signal(market_data))

        if not signals:
            return "WAIT"

        final_signal, _, _ = self._weighted_vote(signals)
        return final_signal

    async def get_signal_async(
        self,
        market_data: Dict[str, Any],
        bot_id: str = "",
    ) -> str:
        """비동기 신호 반환 (Gemini 포함)

        Args:
            market_data: 시장 데이터
            bot_id: 봇 ID

        Returns:
            신호
        """
        result = await self.generate_ensemble_signal(market_data, bot_id)
        return result.final_signal
