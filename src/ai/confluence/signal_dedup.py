"""MI 기반 시그널 중복 제거.

APEX-V Phase C Step 1: 정적 MI 매트릭스로 동일 정보 공유 시그널 가중치 감소.
"""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from src.ai.ensemble import IndividualSignal

from src.ai.ensemble import SignalSource

# Lazy import to avoid circular dependency
KSGMIMatrix_TYPE = None


class SignalDeduplicator:
    """MI(Mutual Information) 기반 시그널 가중치 조정기.

    동적 KSG MI 사용 가능 시 실측 MI로 조정,
    없으면 정적 계층 기반 MI로 조정.
    Transfer Entropy 활성 시 leading/lagging 가중치 추가 조정.
    """

    # 계층 분류
    SLOW_LAYER = {
        SignalSource.TSMOM, SignalSource.SMART_MONEY,
        SignalSource.WHALE_FLOW, SignalSource.LIQUIDATION_CASCADE,
    }
    MEDIUM_LAYER = {
        SignalSource.LEVERAGE_TOPOLOGY,
        SignalSource.FUNDING_BASIS, SignalSource.OFI,
    }
    BASE_LAYER = {SignalSource.GEMINI_AI, SignalSource.SCORING}

    # 정적 MI 계수 (높을수록 중복 → 가중치 더 깎음)
    SAME_LAYER_MI = 0.3      # 동일 계층 → weight x (1 - 0.3) = 0.7
    CROSS_LAYER_MI = 0.1     # 교차 계층 → weight x (1 - 0.1) = 0.9
    BASE_MI = 0.2            # Base 소스 간 → weight x (1 - 0.2) = 0.8

    # Transfer Entropy 조정 계수
    TE_LEADING_BOOST = 0.10   # leading indicator 가중치 증가
    TE_LAGGING_PENALTY = 0.15  # lagging indicator 가중치 감소
    TE_THRESHOLD = 0.05       # TE 유의성 임계값

    def __init__(
        self,
        ksg_matrix: Any | None = None,
        *,
        use_transfer_entropy: bool = False,
    ) -> None:
        """초기화.

        Args:
            ksg_matrix: KSGMIMatrix 인스턴스 (동적 MI용, None이면 정적 MI)
            use_transfer_entropy: Transfer Entropy 기반 조정 사용 여부
        """
        self._ksg_matrix = ksg_matrix
        self._use_transfer_entropy = use_transfer_entropy

    def _get_layer(self, source: SignalSource) -> str:
        """소스의 계층 반환."""
        if source in self.SLOW_LAYER:
            return "slow"
        if source in self.MEDIUM_LAYER:
            return "medium"
        return "base"

    def adjust_weights(self, signals: list[IndividualSignal]) -> list[IndividualSignal]:
        """MI 기반 가중치 조정. 원본 불변, 새 리스트 반환.

        KSG matrix가 있고 계산 완료 시 동적 MI 사용,
        없으면 정적 계층 기반 MI 사용.
        Transfer Entropy 활성 시 추가 leading/lagging 조정.

        Args:
            signals: 원본 시그널 리스트

        Returns:
            가중치가 조정된 새 시그널 리스트
        """
        if len(signals) <= 1:
            return [replace(s) for s in signals]

        if (self._ksg_matrix is not None
                and hasattr(self._ksg_matrix, "is_computed")
                and self._ksg_matrix.is_computed):
            adjusted = self._adjust_with_ksg(signals)
        else:
            adjusted = self._adjust_with_static(signals)

        # Transfer Entropy 추가 조정
        if (
            self._use_transfer_entropy
            and self._ksg_matrix is not None
            and hasattr(self._ksg_matrix, "te_computed")
            and self._ksg_matrix.te_computed
        ):
            adjusted = self._adjust_with_te(adjusted)

        return adjusted

    def _adjust_with_ksg(
        self, signals: list[IndividualSignal]
    ) -> list[IndividualSignal]:
        """KSG 동적 MI 기반 가중치 조정."""
        assert self._ksg_matrix is not None  # noqa: S101
        adjusted = []
        for i, sig in enumerate(signals):
            max_penalty = 0.0
            for j, other in enumerate(signals):
                if i == j:
                    continue
                penalty = self._ksg_matrix.get_penalty(
                    sig.source.value, other.source.value
                )
                max_penalty = max(max_penalty, penalty)

            new_weight = sig.weight * (1.0 - max_penalty)
            adjusted.append(replace(sig, weight=new_weight))

            if max_penalty > 0:
                logger.debug(
                    f"KSG 중복 조정: {sig.source.value} "
                    f"weight {sig.weight:.3f} → {new_weight:.3f} "
                    f"(KSG penalty={max_penalty:.3f})"
                )
        return adjusted

    def _adjust_with_static(
        self, signals: list[IndividualSignal]
    ) -> list[IndividualSignal]:
        """정적 계층 기반 MI 가중치 조정."""
        adjusted = []
        for i, sig in enumerate(signals):
            penalty = 0.0
            layer_i = self._get_layer(sig.source)

            for j, other in enumerate(signals):
                if i == j:
                    continue
                layer_j = self._get_layer(other.source)

                if layer_i == layer_j:
                    if layer_i == "base":
                        penalty = max(penalty, self.BASE_MI)
                    else:
                        penalty = max(penalty, self.SAME_LAYER_MI)
                else:
                    penalty = max(penalty, self.CROSS_LAYER_MI)

            # 가중치 조정: weight x (1 - penalty)
            new_weight = sig.weight * (1.0 - penalty)
            adjusted.append(replace(sig, weight=new_weight))

            if penalty > 0:
                logger.debug(
                    f"시그널 중복 조정: {sig.source.value} "
                    f"weight {sig.weight:.3f} → {new_weight:.3f} (MI penalty={penalty})"
                )

        return adjusted

    def _adjust_with_te(
        self, signals: list[IndividualSignal]
    ) -> list[IndividualSignal]:
        """Transfer Entropy 기반 leading/lagging 가중치 조정.

        - 높은 outgoing TE → leading indicator → 가중치 보존/증가
        - 높은 incoming TE → lagging indicator → 가중치 감소
        """
        assert self._ksg_matrix is not None  # noqa: S101
        adjusted = []

        for sig in signals:
            outgoing_te = 0.0
            incoming_te = 0.0

            for other in signals:
                if sig.source == other.source:
                    continue
                # TE(sig → other): sig가 other에 정보 전달
                out_te = self._ksg_matrix.get_te(
                    sig.source.value, other.source.value
                )
                outgoing_te = max(outgoing_te, out_te)
                # TE(other → sig): other가 sig에 정보 전달
                in_te = self._ksg_matrix.get_te(
                    other.source.value, sig.source.value
                )
                incoming_te = max(incoming_te, in_te)

            # 조정: leading boost, lagging penalty
            modifier = 0.0
            if outgoing_te > self.TE_THRESHOLD:
                modifier += self.TE_LEADING_BOOST
            if incoming_te > self.TE_THRESHOLD:
                modifier -= self.TE_LAGGING_PENALTY

            new_weight = sig.weight * (1.0 + modifier)
            new_weight = max(0.01, new_weight)  # 최소 가중치 보장
            adjusted.append(replace(sig, weight=new_weight))

            if abs(modifier) > 0:
                logger.debug(
                    f"TE 조정: {sig.source.value} "
                    f"weight {sig.weight:.3f} → {new_weight:.3f} "
                    f"(out_te={outgoing_te:.3f}, in_te={incoming_te:.3f})"
                )

        return adjusted
