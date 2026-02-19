"""Funding Rate + Long/Short Ratio 기반 군중 역행 채널.

Extreme funding rate + 포지션 편중 시 역방향 시그널 생성.
군중이 과도하게 몰릴 때 반대 방향으로 진입하는 역발상 전략.
"""
from typing import Any

from loguru import logger

from src.ai.ensemble import IndividualSignal, SignalSource


class FundingBasisChannel:
    """Funding Rate + Long/Short Ratio 기반 군중 역행 채널.

    Extreme FR(>0.05%) + Long 과밀(>65%) -> SHORT
    Extreme FR(<-0.03%) + Short 과밀(>60%) -> LONG
    """

    FR_EXTREME_LONG = 0.0005    # 0.05%
    FR_EXTREME_SHORT = -0.0003  # -0.03%
    LS_LONG_CROWDED = 0.65      # 65%
    LS_SHORT_CROWDED = 0.60     # 60%

    def __init__(self, orthogonalizer: Any | None = None) -> None:
        self._orthogonalizer = orthogonalizer

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
