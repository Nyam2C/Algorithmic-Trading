"""Funding Rate + Long/Short Ratio 기반 군중 역행 채널.

Extreme funding rate + 포지션 편중 시 역방향 시그널 생성.
군중이 과도하게 몰릴 때 반대 방향으로 진입하는 역발상 전략.
"""
from enum import Enum
from typing import Any

from loguru import logger

from src.ai.ensemble import IndividualSignal, SignalSource


class FundingState(Enum):
    """Funding Rate 5-State 상태 머신."""
    EUPHORIA = "euphoria"          # FR >= 0.05% → 군중 극단 롱
    GREED = "greed"                # 0.03% ~ 0.05% → 군중 롱
    NEUTRAL = "neutral"            # -0.02% ~ 0.03% → 중립
    FEAR = "fear"                  # -0.05% ~ -0.02% → 군중 숏
    CAPITULATION = "capitulation"  # FR < -0.05% → 군중 극단 숏


# FR 범위 → (state, contrarian score)
FUNDING_STATE_CONFIG: dict[str, dict[str, float | int]] = {
    "euphoria":      {"fr_min": 0.0005,  "fr_max": float("inf"), "score": -90},
    "greed":         {"fr_min": 0.0003,  "fr_max": 0.0005,      "score": -60},
    "neutral":       {"fr_min": -0.0002, "fr_max": 0.0003,      "score": 0},
    "fear":          {"fr_min": -0.0005, "fr_max": -0.0002,     "score": 60},
    "capitulation":  {"fr_min": float("-inf"), "fr_max": -0.0005, "score": 90},
}


class FundingBasisChannel:
    """Funding Rate + Long/Short Ratio 기반 군중 역행 채널.

    Extreme FR(>0.05%) + Long 과밀(>65%) -> SHORT
    Extreme FR(<-0.03%) + Short 과밀(>60%) -> LONG
    """

    FR_EXTREME_LONG = 0.0005    # 0.05%
    FR_GREED_FLOOR = 0.0003     # 0.03%
    FR_FEAR_CEIL = -0.0002      # -0.02%
    FR_EXTREME_SHORT = -0.0003  # -0.03%
    FR_CAPITULATION = -0.0005   # -0.05%
    LS_LONG_CROWDED = 0.65      # 65%
    LS_SHORT_CROWDED = 0.60     # 60%

    def __init__(
        self,
        orthogonalizer: Any | None = None,
        use_5state: bool = False,
    ) -> None:
        self._orthogonalizer = orthogonalizer
        self._use_5state = use_5state

    async def generate_signal(
        self,
        funding_rate: float | None,
        long_short_ratio: float | None,
        basis: float | None = None,
        oi_change_pct: float | None = None,
    ) -> IndividualSignal:
        """Funding-Basis 시그널 생성.

        Args:
            funding_rate: 현재 펀딩레이트 (예: 0.0005 = 0.05%)
            long_short_ratio: Long/Short 비율 (예: 1.5 = long 60%, short 40%)
                Long% = ratio / (1 + ratio)
            basis: Mark-Index 스프레드 비율 (예: 0.001 = 0.1%)
            oi_change_pct: OI 변화율 (직교화용)

        Returns:
            IndividualSignal
        """
        try:
            if funding_rate is None or long_short_ratio is None:
                return IndividualSignal(
                    source=SignalSource.FUNDING_BASIS,
                    signal="WAIT",
                    confidence=0.0,
                    reason="데이터 없음",
                    weight=0.15,
                )

            # OI 직교화 적용
            if (self._orthogonalizer is not None
                    and oi_change_pct is not None):
                self._orthogonalizer.update(funding_rate, oi_change_pct)
                self._orthogonalizer.recompute_beta()
                funding_rate = self._orthogonalizer.orthogonalize(
                    funding_rate, oi_change_pct
                )

            # Long/Short ratio -> percentage
            long_pct = long_short_ratio / (1.0 + long_short_ratio)
            short_pct = 1.0 - long_pct

            # 5-State 모드: 상태 머신 기반 시그널
            if self._use_5state:
                # 기존 로직으로 base signal 계산
                base_signal = "WAIT"
                base_confidence = 0.0
                if (funding_rate >= self.FR_EXTREME_LONG
                        and long_pct >= self.LS_LONG_CROWDED):
                    base_signal = "SHORT"
                    base_confidence = min(
                        1.0,
                        (funding_rate / self.FR_EXTREME_LONG) * 0.5
                        + (long_pct - 0.5) * 2 * 0.5,
                    )
                elif (funding_rate <= self.FR_EXTREME_SHORT
                        and short_pct >= self.LS_SHORT_CROWDED):
                    base_signal = "LONG"
                    base_confidence = min(
                        1.0,
                        (abs(funding_rate) / abs(self.FR_EXTREME_SHORT)) * 0.5
                        + (short_pct - 0.5) * 2 * 0.5,
                    )
                adj_signal, adj_conf, suffix = self._modulate_with_5state(
                    base_signal, base_confidence, funding_rate,
                )
                adj_conf = self._apply_basis_cross_validation(
                    adj_conf, funding_rate, basis,
                )
                reason = (
                    f"FR={funding_rate:.4%}, L/S={long_pct:.1%}/{short_pct:.1%}"
                    f"{suffix}"
                )
                return IndividualSignal(
                    source=SignalSource.FUNDING_BASIS,
                    signal=adj_signal,
                    confidence=round(adj_conf, 3),
                    reason=reason,
                    weight=0.15,
                )

            # === Legacy 경로 (use_5state=False) ===
            # Extreme long funding + long crowded -> SHORT (contrarian)
            if (funding_rate >= self.FR_EXTREME_LONG
                    and long_pct >= self.LS_LONG_CROWDED):
                confidence = min(
                    1.0,
                    (funding_rate / self.FR_EXTREME_LONG) * 0.5
                    + (long_pct - 0.5) * 2 * 0.5,
                )
                confidence = self._apply_basis_cross_validation(
                    confidence, funding_rate, basis
                )
                basis_info = f", basis={basis:.6f}" if basis else ""
                reason = (
                    f"역행: FR={funding_rate:.4%}"
                    f" + Long={long_pct:.1%} 과밀{basis_info}"
                )
                return IndividualSignal(
                    source=SignalSource.FUNDING_BASIS,
                    signal="SHORT",
                    confidence=round(confidence, 3),
                    reason=reason,
                    weight=0.15,
                )

            # Extreme short funding + short crowded -> LONG (contrarian)
            if (funding_rate <= self.FR_EXTREME_SHORT
                    and short_pct >= self.LS_SHORT_CROWDED):
                confidence = min(
                    1.0,
                    (abs(funding_rate) / abs(self.FR_EXTREME_SHORT)) * 0.5
                    + (short_pct - 0.5) * 2 * 0.5,
                )
                confidence = self._apply_basis_cross_validation(
                    confidence, funding_rate, basis
                )
                basis_info = f", basis={basis:.6f}" if basis else ""
                reason = (
                    f"역행: FR={funding_rate:.4%}"
                    f" + Short={short_pct:.1%} 과밀{basis_info}"
                )
                return IndividualSignal(
                    source=SignalSource.FUNDING_BASIS,
                    signal="LONG",
                    confidence=round(confidence, 3),
                    reason=reason,
                    weight=0.15,
                )

            # Neutral
            return IndividualSignal(
                source=SignalSource.FUNDING_BASIS,
                signal="WAIT",
                confidence=0.0,
                reason=f"중립: FR={funding_rate:.4%}, Long={long_pct:.1%}",
                weight=0.15,
            )

        except Exception as e:
            logger.error(f"FundingBasis 시그널 생성 실패: {e}")
            return IndividualSignal(
                source=SignalSource.FUNDING_BASIS,
                signal="WAIT",
                confidence=0.0,
                reason=f"에러: {e}",
                weight=0.15,
            )

    @staticmethod
    def _classify_funding_state(funding_rate: float) -> tuple[FundingState, int]:
        """Funding rate를 5-State로 분류.

        Args:
            funding_rate: 현재 펀딩레이트

        Returns:
            (FundingState, contrarian score)
        """
        if funding_rate >= FundingBasisChannel.FR_EXTREME_LONG:
            return FundingState.EUPHORIA, -90
        if funding_rate >= FundingBasisChannel.FR_GREED_FLOOR:
            return FundingState.GREED, -60
        if funding_rate > FundingBasisChannel.FR_FEAR_CEIL:
            return FundingState.NEUTRAL, 0
        if funding_rate >= FundingBasisChannel.FR_CAPITULATION:
            return FundingState.FEAR, 60
        return FundingState.CAPITULATION, 90

    def _modulate_with_5state(
        self,
        signal: str,
        confidence: float,
        funding_rate: float,
    ) -> tuple[str, float, str]:
        """5-State에 따라 signal/confidence 조정.

        극단 상태(EUPHORIA/CAPITULATION)는 역발상 시그널 강화,
        중립(NEUTRAL)은 WAIT 유도.

        Returns:
            (adjusted_signal, adjusted_confidence, reason_suffix)
        """
        state, score = self._classify_funding_state(funding_rate)

        if state == FundingState.NEUTRAL:
            return "WAIT", 0.0, f" [5S:{state.value}]"

        # score > 0 → LONG 유리, score < 0 → SHORT 유리
        direction = "LONG" if score > 0 else "SHORT"

        # 기존 시그널과 5-State 방향 일치 시 confidence 부스트
        state_confidence = abs(score) / 100.0  # 0.6 or 0.9

        if signal == direction:
            # 일치: confidence 부스트 (기존의 30% + state 기여 70%)
            boosted = confidence * 0.3 + state_confidence * 0.7
            return signal, min(1.0, round(boosted, 3)), f" [5S:{state.value}]"
        if signal == "WAIT":
            # WAIT에서 5-State가 방향 제시
            return direction, round(state_confidence * 0.5, 3), f" [5S:{state.value}]"
        # 불일치: confidence 감쇠
        return signal, round(confidence * 0.4, 3), f" [5S:{state.value}\u2194]"

    @staticmethod
    def _apply_basis_cross_validation(
        confidence: float, funding_rate: float, basis: float | None
    ) -> float:
        """Basis 교차검증으로 confidence 조정.

        FR 방향 == basis 방향 → confidence x 1.3 (상한 1.0)
        FR 방향 != basis 방향 → confidence x 0.7
        basis가 None이거나 0이면 → 무변경
        """
        if basis is None or basis == 0.0:
            return confidence
        fr_positive = funding_rate > 0
        basis_positive = basis > 0
        if fr_positive == basis_positive:
            return min(1.0, confidence * 1.3)
        return confidence * 0.7
