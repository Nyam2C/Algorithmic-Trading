"""Top Trader vs 가격 디버전스 감지 채널.

Top trader 포지션 방향 vs 최근 가격 움직임 비교.
디버전스 발생 시 Top trader 방향 추종.
"""
from loguru import logger

from src.ai.ensemble import IndividualSignal, SignalSource


class SmartMoneyDivergenceChannel:
    """Smart Money Divergence 채널.

    Top trader 포지션 방향 vs 최근 가격 움직임 비교.
    디버전스 발생 시 Top trader 방향 추종.
    컨버전스 시 추세 확인.
    """

    # Top trader long ratio thresholds
    SMART_LONG_THRESHOLD = 0.55    # Top traders are net long
    SMART_SHORT_THRESHOLD = 0.45   # Top traders are net short

    # Price change thresholds
    PRICE_UP_THRESHOLD = 0.001     # 0.1% up
    PRICE_DOWN_THRESHOLD = -0.001  # 0.1% down

    MIN_HISTORY = 3  # 최소 히스토리 개수

    async def generate_signal(
        self,
        top_ls_ratio: float | None,
        price_change_pct: float | None,
        ls_history: list[dict] | None = None,
    ) -> IndividualSignal:
        """Smart Money Divergence 시그널 생성.

        Args:
            top_ls_ratio: Top trader L/S ratio (예: 1.2 = long 54.5%)
                Long% = ratio / (1 + ratio)
            price_change_pct: 최근 가격 변화율 (예: 0.005 = 0.5%)
            ls_history: L/S 히스토리 [{ratio: float, price: float}, ...]

        Returns:
            IndividualSignal
        """
        try:
            if top_ls_ratio is None or price_change_pct is None:
                return self._wait_signal("데이터 없음")

            top_long_pct = top_ls_ratio / (1.0 + top_ls_ratio)
            smart_dir = self._smart_direction(top_long_pct)
            price_dir = self._price_direction(price_change_pct)
            history_bias = (
                self._analyze_history(ls_history)
                if ls_history
                else 0.0
            )

            return self._decide(
                smart_dir, price_dir,
                top_long_pct, price_change_pct, history_bias,
            )

        except Exception as e:
            logger.error(f"SmartMoney 시그널 생성 실패: {e}")
            return self._wait_signal(f"에러: {e}")

    def _smart_direction(self, top_long_pct: float) -> str:
        """스마트머니 방향 결정."""
        if top_long_pct >= self.SMART_LONG_THRESHOLD:
            return "LONG"
        if top_long_pct <= self.SMART_SHORT_THRESHOLD:
            return "SHORT"
        return "NEUTRAL"

    def _price_direction(self, price_change_pct: float) -> str:
        """가격 방향 결정."""
        if price_change_pct > self.PRICE_UP_THRESHOLD:
            return "UP"
        if price_change_pct < self.PRICE_DOWN_THRESHOLD:
            return "DOWN"
        return "FLAT"

    def _decide(
        self,
        smart_dir: str,
        price_dir: str,
        top_long_pct: float,
        price_change_pct: float,
        history_bias: float,
    ) -> IndividualSignal:
        """방향/가격 조합으로 시그널 결정."""
        # Divergence: Smart LONG + Price DOWN
        if smart_dir == "LONG" and price_dir == "DOWN":
            conf = min(
                1.0,
                (top_long_pct - 0.5) * 4 + abs(history_bias) * 0.3,
            )
            return self._make_signal(
                "LONG", max(0.3, conf),
                f"SM 디버전스: Top Long={top_long_pct:.1%},"
                f" Price↓{price_change_pct:.2%}",
            )

        # Divergence: Smart SHORT + Price UP
        if smart_dir == "SHORT" and price_dir == "UP":
            conf = min(
                1.0,
                (0.5 - top_long_pct) * 4 + abs(history_bias) * 0.3,
            )
            return self._make_signal(
                "SHORT", max(0.3, conf),
                f"SM 디버전스: Top Long={top_long_pct:.1%},"
                f" Price↑{price_change_pct:.2%}",
            )

        # Convergence: Smart LONG + Price UP
        if smart_dir == "LONG" and price_dir == "UP":
            conf = min(0.6, (top_long_pct - 0.5) * 2)
            return self._make_signal(
                "LONG", max(0.2, conf),
                f"SM 컨버전스: Top Long={top_long_pct:.1%},"
                f" Price↑{price_change_pct:.2%}",
            )

        # Convergence: Smart SHORT + Price DOWN
        if smart_dir == "SHORT" and price_dir == "DOWN":
            conf = min(0.6, (0.5 - top_long_pct) * 2)
            return self._make_signal(
                "SHORT", max(0.2, conf),
                f"SM 컨버전스: Top Long={top_long_pct:.1%},"
                f" Price↓{price_change_pct:.2%}",
            )

        # Neutral
        return self._wait_signal(
            f"중립: Top Long={top_long_pct:.1%},"
            f" Price Δ={price_change_pct:.2%}"
        )

    def _analyze_history(self, ls_history: list[dict]) -> float:
        """히스토리에서 스마트머니 편향 분석.

        Returns:
            positive = long bias, negative = short bias, 0 = neutral
        """
        if not ls_history or len(ls_history) < self.MIN_HISTORY:
            return 0.0

        long_trend = 0
        for snapshot in ls_history:
            ratio = snapshot.get("ratio", 1.0)
            pct = ratio / (1.0 + ratio)
            if pct > self.SMART_LONG_THRESHOLD:
                long_trend += 1
            elif pct < self.SMART_SHORT_THRESHOLD:
                long_trend -= 1

        return long_trend / len(ls_history)

    def _make_signal(
        self, signal: str, confidence: float, reason: str
    ) -> IndividualSignal:
        return IndividualSignal(
            source=SignalSource.SMART_MONEY,
            signal=signal,
            confidence=round(confidence, 3),
            reason=reason,
            weight=0.15,
        )

    def _wait_signal(self, reason: str) -> IndividualSignal:
        return IndividualSignal(
            source=SignalSource.SMART_MONEY,
            signal="WAIT",
            confidence=0.0,
            reason=reason,
            weight=0.15,
        )
