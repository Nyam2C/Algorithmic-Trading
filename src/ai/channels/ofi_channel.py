"""Order Flow Imbalance (OFI) 채널.

APEX-V Fast Layer: WebSocket 오더북 데이터로 주문흐름 불균형 감지.
가중 OFI + CVD 교차검증으로 시그널 생성.
"""
from loguru import logger

from src.ai.ensemble import IndividualSignal, SignalSource


class OFIChannel:
    """Order Flow Imbalance 채널.

    오더북 bid/ask 변화량의 가중 평균(OFI)으로 수급 불균형 감지.
    CVD(Cumulative Volume Delta)와 교차검증하여 신뢰도 조정.
    """

    OFI_WEIGHTS = (0.50, 0.30, 0.20)  # 5/20/50 window 가중치
    SIGNAL_THRESHOLD = 30
    CVD_AGREE_MULT = 1.3
    CVD_DISAGREE_MULT = 0.6
    MIN_SAMPLE_COUNT = 10

    async def generate_signal(
        self, ofi_snapshot: dict | None
    ) -> IndividualSignal:
        """OFI 시그널 생성.

        Args:
            ofi_snapshot: OFI 스냅샷 dict
                - ofi_5: 5-window OFI
                - ofi_20: 20-window OFI
                - ofi_50: 50-window OFI
                - cvd: Cumulative Volume Delta
                - sample_count: 샘플 수

        Returns:
            IndividualSignal
        """
        try:
            if ofi_snapshot is None:
                return self._wait("데이터 없음")

            sample_count = ofi_snapshot.get("sample_count", 0)
            if sample_count < self.MIN_SAMPLE_COUNT:
                return self._wait(f"샘플 부족: {sample_count}<{self.MIN_SAMPLE_COUNT}")

            ofi_5 = ofi_snapshot.get("ofi_5", 0.0)
            ofi_20 = ofi_snapshot.get("ofi_20", 0.0)
            ofi_50 = ofi_snapshot.get("ofi_50", 0.0)
            cvd = ofi_snapshot.get("cvd", 0.0)

            # 가중 OFI
            w5, w20, w50 = self.OFI_WEIGHTS
            weighted_ofi = ofi_5 * w5 + ofi_20 * w20 + ofi_50 * w50

            # 스코어: [-100, 100] 범위로 클램프
            score = max(-100.0, min(100.0, weighted_ofi))

            if abs(score) <= self.SIGNAL_THRESHOLD:
                return self._wait(
                    f"임계값 미달: |{score:.1f}|<={self.SIGNAL_THRESHOLD}"
                )

            # 방향 결정
            direction = "LONG" if score > 0 else "SHORT"

            # 기본 confidence: |score| / 100
            confidence = min(1.0, abs(score) / 100.0)

            # CVD 교차검증
            if cvd != 0.0:
                cvd_agrees = (score > 0 and cvd > 0) or (score < 0 and cvd < 0)
                if cvd_agrees:
                    confidence = min(1.0, confidence * self.CVD_AGREE_MULT)
                else:
                    confidence *= self.CVD_DISAGREE_MULT

            reason = (
                f"OFI={weighted_ofi:.1f} "
                f"(5:{ofi_5:.1f}/20:{ofi_20:.1f}/50:{ofi_50:.1f}), "
                f"CVD={cvd:.1f}"
            )

            return IndividualSignal(
                source=SignalSource.OFI,
                signal=direction,
                confidence=round(confidence, 3),
                reason=reason,
                weight=0.15,
            )

        except Exception as e:
            logger.error(f"OFI 시그널 생성 실패: {e}")
            return self._wait(f"에러: {e}")

    @staticmethod
    def _wait(reason: str) -> IndividualSignal:
        """WAIT 시그널 반환."""
        return IndividualSignal(
            source=SignalSource.OFI,
            signal="WAIT",
            confidence=0.0,
            reason=reason,
            weight=0.15,
        )
