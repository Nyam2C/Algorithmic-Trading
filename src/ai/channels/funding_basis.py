"""Funding Rate + Long/Short Ratio 기반 군중 역행 채널.

Extreme funding rate + 포지션 편중 시 역방향 시그널 생성.
군중이 과도하게 몰릴 때 반대 방향으로 진입하는 역발상 전략.
"""
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

    async def generate_signal(
        self, funding_rate: float | None, long_short_ratio: float | None
    ) -> IndividualSignal:
        """Funding-Basis 시그널 생성.

        Args:
            funding_rate: 현재 펀딩레이트 (예: 0.0005 = 0.05%)
            long_short_ratio: Long/Short 비율 (예: 1.5 = long 60%, short 40%)
                Long% = ratio / (1 + ratio)

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
                return IndividualSignal(
                    source=SignalSource.FUNDING_BASIS,
                    signal="SHORT",
                    confidence=round(confidence, 3),
                    reason=f"역행: FR={funding_rate:.4%} + Long={long_pct:.1%} 과밀",
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
                return IndividualSignal(
                    source=SignalSource.FUNDING_BASIS,
                    signal="LONG",
                    confidence=round(confidence, 3),
                    reason=f"역행: FR={funding_rate:.4%} + Short={short_pct:.1%} 과밀",
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
