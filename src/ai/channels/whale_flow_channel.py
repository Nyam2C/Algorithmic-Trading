"""Whale Flow 채널.

APEX-V Fast Layer: WebSocket 체결 데이터로 고래 자금흐름 감지.
대형 주문의 순 방향 + Predatory 패턴 검출.
"""
from loguru import logger

from src.ai.ensemble import IndividualSignal, SignalSource


class WhaleFlowChannel:
    """Whale Flow 채널.

    체결 데이터에서 대형(whale) 주문의 순방향을 감지.
    고래와 개인(retail)의 방향이 반대인 Predatory 패턴 시 배수 적용.
    """

    SIGNAL_THRESHOLD = 25
    PREDATORY_MULTIPLIER = 1.5
    INTENSITY_SCALE = 250
    MIN_TOTAL_TRADES = 50

    async def generate_signal(
        self, whale_snapshot: dict | None
    ) -> IndividualSignal:
        """Whale Flow 시그널 생성.

        Args:
            whale_snapshot: 고래 스냅샷 dict
                - whale_buy_vol: 고래 매수량
                - whale_sell_vol: 고래 매도량
                - retail_buy_vol: 개인 매수량
                - retail_sell_vol: 개인 매도량
                - total_trades: 총 체결 수

        Returns:
            IndividualSignal
        """
        try:
            if whale_snapshot is None:
                return self._wait("데이터 없음")

            total_trades = whale_snapshot.get("total_trades", 0)
            if total_trades < self.MIN_TOTAL_TRADES:
                return self._wait(
                    f"거래 부족: {total_trades}<{self.MIN_TOTAL_TRADES}"
                )

            whale_buy = whale_snapshot.get("whale_buy_vol", 0.0)
            whale_sell = whale_snapshot.get("whale_sell_vol", 0.0)
            retail_buy = whale_snapshot.get("retail_buy_vol", 0.0)
            retail_sell = whale_snapshot.get("retail_sell_vol", 0.0)

            whale_net = whale_buy - whale_sell
            whale_total = whale_buy + whale_sell

            if whale_total <= 0:
                return self._wait("고래 거래량 없음")

            # 강도: |순방향| / 총고래볼륨
            intensity = abs(whale_net) / whale_total

            # Score range 제한
            raw_score = (1.0 if whale_net > 0 else -1.0) * min(
                100.0, intensity * self.INTENSITY_SCALE
            )
            if whale_net == 0:
                raw_score = 0.0

            score = raw_score

            # Predatory 감지: 고래/개인 반대 방향
            retail_net = retail_buy - retail_sell
            is_predatory = False
            if (
                whale_net != 0
                and retail_net != 0
                and (
                    (whale_net > 0 and retail_net < 0)
                    or (whale_net < 0 and retail_net > 0)
                )
            ):
                score = max(-100.0, min(100.0, score * self.PREDATORY_MULTIPLIER))
                is_predatory = True

            if abs(score) <= self.SIGNAL_THRESHOLD:
                return self._wait(
                    f"임계값 미달: |{score:.1f}|<={self.SIGNAL_THRESHOLD}"
                )

            direction = "LONG" if score > 0 else "SHORT"
            confidence = min(1.0, abs(score) / 100.0)

            pred_tag = " [Predatory]" if is_predatory else ""
            reason = (
                f"WhaleNet={whale_net:.2f} "
                f"(buy:{whale_buy:.2f}/sell:{whale_sell:.2f}), "
                f"intensity={intensity:.3f}{pred_tag}"
            )

            return IndividualSignal(
                source=SignalSource.WHALE_FLOW,
                signal=direction,
                confidence=round(confidence, 3),
                reason=reason,
                weight=0.15,
            )

        except Exception as e:
            logger.error(f"WhaleFlow 시그널 생성 실패: {e}")
            return self._wait(f"에러: {e}")

    @staticmethod
    def _wait(reason: str) -> IndividualSignal:
        """WAIT 시그널 반환."""
        return IndividualSignal(
            source=SignalSource.WHALE_FLOW,
            signal="WAIT",
            confidence=0.0,
            reason=reason,
            weight=0.15,
        )
