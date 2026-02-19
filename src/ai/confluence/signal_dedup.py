"""MI 기반 시그널 중복 제거.

APEX-V Phase C Step 1: 정적 MI 매트릭스로 동일 정보 공유 시그널 가중치 감소.
"""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from src.ai.ensemble import IndividualSignal

from src.ai.ensemble import SignalSource


class SignalDeduplicator:
    """정적 MI(Mutual Information) 기반 시그널 가중치 조정기.

    동일 계층 채널 쌍은 높은 MI → 가중치 감소,
    교차 계층은 낮은 MI → 가중치 약간 감소.
    """

    # 계층 분류
    SLOW_LAYER = {
        SignalSource.TSMOM, SignalSource.SMART_MONEY,
        SignalSource.WHALE_FLOW,
    }
    MEDIUM_LAYER = {
        SignalSource.LEVERAGE_TOPOLOGY,
        SignalSource.FUNDING_BASIS, SignalSource.OFI,
    }
    BASE_LAYER = {SignalSource.GEMINI_AI, SignalSource.RULE_BASED, SignalSource.SCORING}

    # 정적 MI 계수 (높을수록 중복 → 가중치 더 깎음)
    SAME_LAYER_MI = 0.3      # 동일 계층 → weight x (1 - 0.3) = 0.7
    CROSS_LAYER_MI = 0.1     # 교차 계층 → weight x (1 - 0.1) = 0.9
    BASE_MI = 0.2            # Base 소스 간 → weight x (1 - 0.2) = 0.8

    def _get_layer(self, source: SignalSource) -> str:
        """소스의 계층 반환."""
        if source in self.SLOW_LAYER:
            return "slow"
        if source in self.MEDIUM_LAYER:
            return "medium"
        return "base"

    def adjust_weights(self, signals: list[IndividualSignal]) -> list[IndividualSignal]:
        """MI 기반 가중치 조정. 원본 불변, 새 리스트 반환.

        Args:
            signals: 원본 시그널 리스트

        Returns:
            가중치가 조정된 새 시그널 리스트
        """
        if len(signals) <= 1:
            return [replace(s) for s in signals]

        adjusted = []
        for i, sig in enumerate(signals):
            penalty = 0.0
            layer_i = self._get_layer(sig.source)
            peer_count = 0

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
                peer_count += 1

            # 가중치 조정: weight x (1 - penalty)
            new_weight = sig.weight * (1.0 - penalty)
            adjusted.append(replace(sig, weight=new_weight))

            if penalty > 0:
                logger.debug(
                    f"시그널 중복 조정: {sig.source.value} "
                    f"weight {sig.weight:.3f} → {new_weight:.3f} (MI penalty={penalty})"
                )

        return adjusted
