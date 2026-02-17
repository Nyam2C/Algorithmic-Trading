"""TSMOM (Time-Series Momentum) 채널.

다중 lookback window의 volatility-adjusted returns로 모멘텀 방향 판정.
순수 계산 기반 — API 호출 없음, 백테스트 호환.
"""
import pandas as pd
from loguru import logger

from src.ai.ensemble import IndividualSignal, SignalSource
from src.data.indicators import calculate_returns


class TSMOMChannel:
    """Time-Series Momentum 채널.

    다중 lookback [5, 10, 20, 60] volatility-adjusted returns 계산.
    과반수 양수 → LONG, 과반수 음수 → SHORT, 혼합 → WAIT.
    """

    LOOKBACK_WINDOWS = [5, 10, 20, 60]

    async def generate_signal(self, df: pd.DataFrame) -> IndividualSignal:
        """TSMOM 시그널 생성.

        Args:
            df: OHLCV DataFrame ('close' column required)

        Returns:
            IndividualSignal with LONG/SHORT/WAIT
        """
        try:
            if len(df) < max(self.LOOKBACK_WINDOWS) + 5:
                logger.debug("TSMOM: 데이터 부족 → WAIT")
                return IndividualSignal(
                    source=SignalSource.TSMOM,
                    signal="WAIT",
                    confidence=0.0,
                    reason="데이터 부족",
                    weight=0.15,
                )

            returns = calculate_returns(df, self.LOOKBACK_WINDOWS)

            long_count = 0
            short_count = 0
            valid_count = 0

            for window in self.LOOKBACK_WINDOWS:
                key = f"returns_{window}"
                if key not in returns:
                    continue
                val = returns[key].iloc[-1]
                if pd.isna(val):
                    continue
                valid_count += 1
                if val > 0:
                    long_count += 1
                else:
                    short_count += 1

            if valid_count == 0:
                return IndividualSignal(
                    source=SignalSource.TSMOM,
                    signal="WAIT",
                    confidence=0.0,
                    reason="유효한 리턴 데이터 없음",
                    weight=0.15,
                )

            majority = valid_count / 2.0

            if long_count > majority:
                confidence = long_count / valid_count
                signal = "LONG"
                reason = f"TSMOM {long_count}/{valid_count} windows 양수"
            elif short_count > majority:
                confidence = short_count / valid_count
                signal = "SHORT"
                reason = f"TSMOM {short_count}/{valid_count} windows 음수"
            else:
                confidence = max(long_count, short_count) / valid_count
                signal = "WAIT"
                reason = f"TSMOM 혼합 (long={long_count}, short={short_count})"

            logger.debug(f"TSMOM 시그널: {signal} (confidence={confidence:.2f})")
            return IndividualSignal(
                source=SignalSource.TSMOM,
                signal=signal,
                confidence=confidence,
                reason=reason,
                weight=0.15,
            )

        except Exception as e:
            logger.error(f"TSMOM 시그널 생성 실패: {e}")
            return IndividualSignal(
                source=SignalSource.TSMOM,
                signal="WAIT",
                confidence=0.0,
                reason=f"에러: {e}",
                weight=0.15,
            )
