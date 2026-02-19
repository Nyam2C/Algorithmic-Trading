"""Threshold Tuner.

매주 일요일 Regime x Session별 WR >= 57% 달성 최소 임계값 자동 계산.
"""
from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from src.ai.confluence.session_classifier import TradingSession

TARGET_WIN_RATE = 0.57
SMOOTHING_OLD = 0.7
SMOOTHING_NEW = 0.3

# 절대 최저 임계값 (안전장치)
FLOOR_THRESHOLDS: dict[str, dict[TradingSession, float]] = {
    "strong_trend": {
        TradingSession.US: 0.15,
        TradingSession.EU: 0.18,
        TradingSession.ASIA: 0.20,
        TradingSession.DEEP_NIGHT: 0.25,
    },
    "weak_trend": {
        TradingSession.US: 0.20,
        TradingSession.EU: 0.23,
        TradingSession.ASIA: 0.25,
        TradingSession.DEEP_NIGHT: 0.30,
    },
    "ranging": {
        TradingSession.US: 0.35,
        TradingSession.EU: 0.38,
        TradingSession.ASIA: 0.40,
        TradingSession.DEEP_NIGHT: 0.45,
    },
    "uncertainty": {
        TradingSession.US: 0.30,
        TradingSession.EU: 0.33,
        TradingSession.ASIA: 0.35,
        TradingSession.DEEP_NIGHT: 0.40,
    },
}


@dataclass
class TradeRecord:
    """튜닝용 거래 기록."""

    confluence_score: float
    regime: str
    session: TradingSession
    is_win: bool


@dataclass
class TuningResult:
    """튜닝 결과."""

    regime: str
    session: TradingSession
    old_threshold: float
    calc_threshold: float
    new_threshold: float
    sample_count: int
    achieved_win_rate: float


class ThresholdTuner:
    """Regime x Session별 임계값 자동 튜너.

    WR >= TARGET_WIN_RATE 달성하는 최소 임계값을 이진 탐색으로 찾고,
    기존 값과 smoothing 적용하여 급변 방지.
    """

    MIN_TRADES_PER_BUCKET = 10

    def tune(
        self,
        trade_records: list[TradeRecord],
        current_thresholds: dict[str, dict[TradingSession, float]],
    ) -> list[TuningResult]:
        """임계값 튜닝 실행.

        Args:
            trade_records: 거래 기록 리스트
            current_thresholds: 현재 임계값 테이블

        Returns:
            변경된 버킷의 TuningResult 리스트
        """
        results: list[TuningResult] = []

        # Regime x Session 버킷 분류
        buckets: dict[tuple[str, TradingSession], list[TradeRecord]] = {}
        for record in trade_records:
            key = (record.regime, record.session)
            if key not in buckets:
                buckets[key] = []
            buckets[key].append(record)

        for (regime, session), trades in buckets.items():
            if len(trades) < self.MIN_TRADES_PER_BUCKET:
                logger.debug(
                    f"ThresholdTuner: {regime}/{session.value} "
                    f"샘플 부족 ({len(trades)} < {self.MIN_TRADES_PER_BUCKET})"
                )
                continue

            old_threshold = (
                current_thresholds.get(regime, {}).get(session, 0.35)
            )

            calc_threshold = self._find_min_threshold_for_wr(
                trades, TARGET_WIN_RATE
            )

            if calc_threshold is None:
                # 어떤 임계값으로도 목표 WR 달성 불가
                logger.info(
                    f"ThresholdTuner: {regime}/{session.value} "
                    f"목표 WR {TARGET_WIN_RATE:.0%} 달성 불가"
                )
                continue

            # Smoothing
            new_threshold = (
                SMOOTHING_OLD * old_threshold
                + SMOOTHING_NEW * calc_threshold
            )

            # Floor 적용
            floor = FLOOR_THRESHOLDS.get(regime, {}).get(session, 0.15)
            new_threshold = max(new_threshold, floor)

            # 실제 달성 WR 계산
            above = [t for t in trades if t.confluence_score >= new_threshold]
            achieved_wr = (
                sum(1 for t in above if t.is_win) / len(above)
                if above else 0.0
            )

            results.append(TuningResult(
                regime=regime,
                session=session,
                old_threshold=old_threshold,
                calc_threshold=calc_threshold,
                new_threshold=round(new_threshold, 4),
                sample_count=len(trades),
                achieved_win_rate=round(achieved_wr, 4),
            ))

            logger.info(
                f"ThresholdTuner: {regime}/{session.value} "
                f"{old_threshold:.3f} → {new_threshold:.3f} "
                f"(calc={calc_threshold:.3f}, n={len(trades)}, "
                f"WR={achieved_wr:.1%})"
            )

        return results

    @staticmethod
    def _find_min_threshold_for_wr(
        trades: list[TradeRecord],
        target: float = TARGET_WIN_RATE,
    ) -> float | None:
        """이진 탐색으로 WR >= target 달성 최소 임계값 찾기.

        Args:
            trades: 해당 버킷의 거래 기록
            target: 목표 승률

        Returns:
            최소 임계값 or None (달성 불가)
        """
        scores = sorted({t.confluence_score for t in trades})
        if not scores:
            return None

        # 가장 높은 임계값에서도 달성 불가한 경우 체크
        best_threshold = None

        for threshold in scores:
            above = [t for t in trades if t.confluence_score >= threshold]
            if not above:
                continue
            wr = sum(1 for t in above if t.is_win) / len(above)
            if wr >= target:
                best_threshold = threshold
                break  # 최소 임계값 찾음 (scores는 정렬됨)

        return best_threshold

    @staticmethod
    def apply_to_engine(
        engine_thresholds: dict[str, dict[TradingSession, float]],
        results: list[TuningResult],
    ) -> dict[str, dict[TradingSession, float]]:
        """튜닝 결과를 엔진 임계값 테이블에 적용.

        Returns:
            업데이트된 새 임계값 테이블 (원본 불변)
        """
        new_table = {
            regime: dict(sessions)
            for regime, sessions in engine_thresholds.items()
        }

        for result in results:
            if result.regime not in new_table:
                new_table[result.regime] = {}
            new_table[result.regime][result.session] = result.new_threshold

        return new_table
