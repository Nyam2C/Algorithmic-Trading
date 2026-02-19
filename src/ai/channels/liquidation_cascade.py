"""Liquidation Cascade Hunter 채널.

강제청산 캐스케이드 감지 + 반전 트리거.
Mode A: IndividualSignal → Confluence 통합
Mode B: 독립 진입 (3조건 충족 시, 계좌 1% max)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from loguru import logger

from src.ai.ensemble import IndividualSignal, SignalSource


@dataclass
class CascadeTrigger:
    """Mode B 독립 진입 트리거 결과."""

    should_enter: bool
    direction: str
    confidence: float
    reason: str
    cascade_intensity: float


class LiquidationCascadeHunter:
    """청산 캐스케이드 감지 및 반전 시그널 생성기.

    3조건 동시 충족 시 반전 진입:
    1. 캐스케이드 감지 (일평균 대비 3배)
    2. 감속 확인 (10초 rate < 30초 rate)
    3. RSI 극단 (<15 or >85) + 반대편 depth 우위
    """

    CASCADE_MULTIPLIER = 3.0
    CASCADE_WINDOW_SEC = 30.0
    DECEL_SHORT_WINDOW = 10.0
    RSI_EXTREME_LOW = 15.0
    RSI_EXTREME_HIGH = 85.0
    OPPOSITE_DEPTH_RATIO = 1.5
    MAX_RISK_PCT = 0.01

    def _detect_cascade(
        self,
        liq_snapshot: dict[str, Any],
        daily_avg: float,
    ) -> tuple[bool, float]:
        """캐스케이드 감지.

        Returns:
            (is_cascade, ratio): 일평균 대비 배수
        """
        if daily_avg <= 0:
            return False, 0.0
        count_30s = liq_snapshot.get("count", 0)
        # 30초 윈도우를 일평균으로 정규화: count / (daily_avg / (86400/30))
        expected_30s = daily_avg / (86400 / self.CASCADE_WINDOW_SEC)
        if expected_30s <= 0:
            return False, 0.0
        ratio = count_30s / expected_30s
        return ratio >= self.CASCADE_MULTIPLIER, ratio

    def _check_deceleration(
        self, events: list[tuple[float, str, float, float]]
    ) -> bool:
        """10초 rate < 30초 rate → 감속 확인.

        Args:
            events: [(timestamp_mono, side, qty, price)]
        """
        _min_events = 2
        if len(events) < _min_events:
            return False
        last_ts = events[-1][0]
        cutoff_short = last_ts - self.DECEL_SHORT_WINDOW
        cutoff_long = last_ts - self.CASCADE_WINDOW_SEC

        short_count = sum(1 for ts, _, _, _ in events if ts >= cutoff_short)
        long_count = sum(1 for ts, _, _, _ in events if ts >= cutoff_long)

        # Rate per second
        short_rate = short_count / self.DECEL_SHORT_WINDOW
        long_rate = long_count / self.CASCADE_WINDOW_SEC

        return long_rate > 0 and short_rate < long_rate

    def _check_rsi_extreme(
        self, rsi_1m: float | None
    ) -> tuple[bool, str]:
        """RSI 극단 확인.

        Returns:
            (is_extreme, suggested_direction)
            RSI < 15 → LONG, RSI > 85 → SHORT
        """
        if rsi_1m is None:
            return False, "WAIT"
        if rsi_1m <= self.RSI_EXTREME_LOW:
            return True, "LONG"
        if rsi_1m >= self.RSI_EXTREME_HIGH:
            return True, "SHORT"
        return False, "WAIT"

    def _check_opposite_depth(
        self,
        depth: dict[str, float] | None,
        sell_dominant: bool,
    ) -> bool:
        """반대편 depth 우위 확인.

        sell_dominant=True (Short 캐스케이드) → bid depth > ask depth * ratio
        sell_dominant=False (Long 캐스케이드) → ask depth > bid depth * ratio
        """
        if depth is None:
            return False
        bid_depth = depth.get("bid_depth_total", 0.0)
        ask_depth = depth.get("ask_depth_total", 0.0)
        if bid_depth <= 0 or ask_depth <= 0:
            return False
        if sell_dominant:
            return bid_depth >= ask_depth * self.OPPOSITE_DEPTH_RATIO
        return ask_depth >= bid_depth * self.OPPOSITE_DEPTH_RATIO

    async def generate_signal(
        self,
        liq_snapshot: dict[str, Any] | None,
        daily_avg: float,
        rsi_1m: float | None = None,
        depth: dict[str, float] | None = None,  # noqa: ARG002
    ) -> IndividualSignal:
        """Mode A: IndividualSignal for Confluence 통합.

        캐스케이드 + 감속 감지 시 시그널 생성.
        RSI/depth는 confidence 보정에만 사용.
        """
        if liq_snapshot is None:
            return IndividualSignal(
                source=SignalSource.LIQUIDATION_CASCADE,
                signal="WAIT",
                confidence=0.0,
                reason="청산 데이터 없음",
                weight=0.10,
            )

        is_cascade, ratio = self._detect_cascade(liq_snapshot, daily_avg)
        if not is_cascade:
            return IndividualSignal(
                source=SignalSource.LIQUIDATION_CASCADE,
                signal="WAIT",
                confidence=0.0,
                reason=f"캐스케이드 미감지 (ratio={ratio:.1f}x)",
                weight=0.10,
            )

        events = liq_snapshot.get("events", [])
        is_decel = self._check_deceleration(events)

        # 매도 캐스케이드(sell_vol > buy_vol) → LONG
        sell_vol = liq_snapshot.get("sell_vol", 0.0)
        buy_vol = liq_snapshot.get("buy_vol", 0.0)
        sell_dominant = sell_vol > buy_vol

        direction = "LONG" if sell_dominant else "SHORT"

        # Confidence: 캐스케이드 강도 + 감속 + RSI
        confidence = min(1.0, ratio / (self.CASCADE_MULTIPLIER * 2))
        if is_decel:
            confidence = min(1.0, confidence + 0.2)

        rsi_extreme, rsi_dir = self._check_rsi_extreme(rsi_1m)
        if rsi_extreme and rsi_dir == direction:
            confidence = min(1.0, confidence + 0.15)

        reason = (
            f"캐스케이드 {ratio:.1f}x"
            f" ({'감속' if is_decel else '가속중'})"
            f" → {direction}"
        )

        return IndividualSignal(
            source=SignalSource.LIQUIDATION_CASCADE,
            signal=direction if is_decel else "WAIT",
            confidence=round(confidence, 3),
            reason=reason,
            weight=0.10,
        )

    async def evaluate_cascade_trigger(
        self,
        liq_snapshot: dict[str, Any] | None,
        daily_avg: float,
        rsi_1m: float | None = None,
        depth: dict[str, float] | None = None,
    ) -> CascadeTrigger:
        """Mode B: 독립 진입 평가.

        3조건 모두 충족 시 should_enter=True:
        1. 캐스케이드 감지 (3x daily avg)
        2. 감속 확인
        3. RSI 극단 + 반대편 depth 우위
        """
        if liq_snapshot is None:
            return CascadeTrigger(
                should_enter=False,
                direction="WAIT",
                confidence=0.0,
                reason="청산 데이터 없음",
                cascade_intensity=0.0,
            )

        # 조건 1: 캐스케이드 감지
        is_cascade, ratio = self._detect_cascade(liq_snapshot, daily_avg)
        if not is_cascade:
            return CascadeTrigger(
                should_enter=False,
                direction="WAIT",
                confidence=0.0,
                reason=f"캐스케이드 미감지 (ratio={ratio:.1f}x)",
                cascade_intensity=ratio,
            )

        # 조건 2: 감속 확인
        events = liq_snapshot.get("events", [])
        is_decel = self._check_deceleration(events)
        if not is_decel:
            return CascadeTrigger(
                should_enter=False,
                direction="WAIT",
                confidence=0.0,
                reason=f"캐스케이드 {ratio:.1f}x 감지, 감속 미확인",
                cascade_intensity=ratio,
            )

        # 방향: 매도 캐스케이드 → LONG, 매수 캐스케이드 → SHORT
        sell_vol = liq_snapshot.get("sell_vol", 0.0)
        buy_vol = liq_snapshot.get("buy_vol", 0.0)
        sell_dominant = sell_vol > buy_vol
        direction = "LONG" if sell_dominant else "SHORT"

        # 조건 3: RSI 극단 + depth 우위
        rsi_extreme, rsi_dir = self._check_rsi_extreme(rsi_1m)
        if not rsi_extreme or rsi_dir != direction:
            return CascadeTrigger(
                should_enter=False,
                direction=direction,
                confidence=0.0,
                reason=(
                    f"캐스케이드 {ratio:.1f}x + 감속 확인, "
                    f"RSI 조건 미충족 (rsi={rsi_1m})"
                ),
                cascade_intensity=ratio,
            )

        has_depth = self._check_opposite_depth(depth, sell_dominant)
        if not has_depth:
            return CascadeTrigger(
                should_enter=False,
                direction=direction,
                confidence=0.0,
                reason=(
                    f"캐스케이드 {ratio:.1f}x + 감속 + RSI 확인, "
                    f"depth 조건 미충족"
                ),
                cascade_intensity=ratio,
            )

        # 3조건 모두 충족
        confidence = min(1.0, ratio / (self.CASCADE_MULTIPLIER * 2) + 0.3)
        logger.info(
            f"Cascade Trigger 발동: {direction} "
            f"(ratio={ratio:.1f}x, rsi={rsi_1m})"
        )
        return CascadeTrigger(
            should_enter=True,
            direction=direction,
            confidence=round(confidence, 3),
            reason=(
                f"3조건 충족: 캐스케이드 {ratio:.1f}x + 감속 + "
                f"RSI={rsi_1m} + depth 우위"
            ),
            cascade_intensity=ratio,
        )
