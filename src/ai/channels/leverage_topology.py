"""OI + Price 패턴 기반 레버리지 구조 분석 채널.

Open Interest와 가격 변화의 조합으로 시장 구조를 분석합니다.
OI 히스토리는 Redis 캐시에서 로드합니다.
"""
from loguru import logger

from src.ai.ensemble import IndividualSignal, SignalSource


class LeverageTopologyChannel:
    """OI + Price 패턴 기반 레버리지 구조 분석.

    OI↑+Price↑ → LONG 확인 (신규 롱 진입)
    OI↓+Price↓ → 청산 캐스케이드 → SHORT
    OI↑+Price↓ → Hidden accumulation (역발상 LONG 가능)
    OI↓+Price↑ → Short squeeze (약한 LONG)

    점수 기반: 각 패턴에 포인트 부여, 합산으로 방향 결정.
    """

    MIN_HISTORY = 3  # 최소 히스토리 개수

    # Pattern scores
    SCORE_OI_UP_PRICE_UP = 15     # 건강한 추세 확인
    SCORE_OI_DOWN_PRICE_DOWN = 20  # 청산 캐스케이드 (강한 SHORT)
    SCORE_OI_UP_PRICE_DOWN = -10   # 숨은 축적 (약한 반전 신호)
    SCORE_OI_DOWN_PRICE_UP = -15   # 숏 스퀴즈 (약한 반전 신호)

    # Threshold for signal generation
    SIGNAL_THRESHOLD = 15

    async def generate_signal(
        self,
        current_oi: float | None,
        current_price: float | None,
        oi_history: list[dict] | None,
    ) -> IndividualSignal:
        """레버리지 토폴로지 시그널 생성.

        Args:
            current_oi: 현재 OI
            current_price: 현재 가격
            oi_history: OI 히스토리 [{oi: float, price: float}, ...]
                        시간순 정렬 (oldest first)

        Returns:
            IndividualSignal
        """
        try:
            if not self._has_valid_data(
                current_oi, current_price, oi_history
            ):
                return self._wait_signal("데이터 없음")

            if len(oi_history) < self.MIN_HISTORY:  # type: ignore[arg-type]
                n = len(oi_history)  # type: ignore[arg-type]
                return self._wait_signal(
                    f"히스토리 부족 ({n}/{self.MIN_HISTORY})"
                )

            total_score, patterns = self._score_history(oi_history)  # type: ignore[arg-type]

            # Also factor in current vs last history
            oi_change, total_score = self._score_current(
                current_oi,  # type: ignore[arg-type]
                current_price,  # type: ignore[arg-type]
                oi_history[-1],  # type: ignore[index]
                total_score,
                patterns,
            )

            return self._build_signal(
                total_score, oi_change, patterns
            )

        except Exception as e:
            logger.error(f"LeverageTopology 시그널 생성 실패: {e}")
            return self._wait_signal(f"에러: {e}")

    @staticmethod
    def _has_valid_data(
        current_oi: float | None,
        current_price: float | None,
        oi_history: list[dict] | None,
    ) -> bool:
        """데이터 유효성 확인."""
        return (
            current_oi is not None
            and current_price is not None
            and bool(oi_history)
        )

    def _score_history(
        self, oi_history: list[dict]
    ) -> tuple[int, list[str]]:
        """히스토리에서 패턴 점수 계산."""
        total_score = 0
        patterns: list[str] = []

        prev_oi = oi_history[0].get("oi", 0)
        prev_price = oi_history[0].get("price", 0)

        for snapshot in oi_history[1:]:
            oi = snapshot.get("oi", 0)
            price = snapshot.get("price", 0)
            score, label = self._classify_change(
                oi - prev_oi, price - prev_price
            )
            total_score += score
            if label:
                patterns.append(label)
            prev_oi = oi
            prev_price = price

        return total_score, patterns

    def _score_current(
        self,
        current_oi: float,
        current_price: float,
        last: dict,
        total_score: int,
        patterns: list[str],
    ) -> tuple[float, int]:
        """현재 데이터 vs 마지막 히스토리 비교."""
        oi_change = current_oi - last.get("oi", 0)
        price_change = current_price - last.get("price", 0)

        score, label = self._classify_change(oi_change, price_change)
        total_score += score
        if label:
            patterns.append(label)

        return oi_change, total_score

    def _classify_change(
        self, oi_change: float, price_change: float
    ) -> tuple[int, str]:
        """OI/Price 변화 패턴 분류."""
        if oi_change > 0 and price_change > 0:
            return self.SCORE_OI_UP_PRICE_UP, "OI↑P↑"
        if oi_change < 0 and price_change < 0:
            return self.SCORE_OI_DOWN_PRICE_DOWN, "OI↓P↓"
        if oi_change > 0 and price_change < 0:
            return self.SCORE_OI_UP_PRICE_DOWN, "OI↑P↓"
        if oi_change < 0 and price_change > 0:
            return self.SCORE_OI_DOWN_PRICE_UP, "OI↓P↑"
        return 0, ""

    def _build_signal(
        self,
        total_score: int,
        oi_change: float,
        patterns: list[str],
    ) -> IndividualSignal:
        """점수 기반 시그널 생성."""
        max_possible = (
            abs(self.SCORE_OI_DOWN_PRICE_DOWN) * len(patterns)
            if patterns
            else 1
        )
        confidence = min(
            1.0, abs(total_score) / max(max_possible, 1)
        )
        pattern_summary = ",".join(patterns[-3:])

        if total_score >= self.SIGNAL_THRESHOLD:
            signal, reason = self._positive_score_signal(
                total_score, oi_change, pattern_summary
            )
        elif total_score <= -self.SIGNAL_THRESHOLD:
            signal = "WAIT"
            reason = (
                f"디버전스 감지: score={total_score},"
                f" {pattern_summary}"
            )
        else:
            signal = "WAIT"
            reason = f"중립: score={total_score}, {pattern_summary}"

        logger.debug(
            f"LeverageTopology 시그널: {signal} (score={total_score})"
        )
        return IndividualSignal(
            source=SignalSource.LEVERAGE_TOPOLOGY,
            signal=signal,
            confidence=round(confidence, 3),
            reason=reason,
            weight=0.15,
        )

    @staticmethod
    def _positive_score_signal(
        total_score: int,
        oi_change: float,
        pattern_summary: str,
    ) -> tuple[str, str]:
        """양수 점수 시그널 결정."""
        if oi_change >= 0:
            return (
                "LONG",
                f"레버리지 확인: score={total_score},"
                f" {pattern_summary}",
            )
        return (
            "SHORT",
            f"청산 캐스케이드: score={total_score},"
            f" {pattern_summary}",
        )

    def _wait_signal(self, reason: str) -> IndividualSignal:
        return IndividualSignal(
            source=SignalSource.LEVERAGE_TOPOLOGY,
            signal="WAIT",
            confidence=0.0,
            reason=reason,
            weight=0.15,
        )
