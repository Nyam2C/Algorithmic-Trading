"""Rule-based signal generator (temporary fallback for Gemini API).

Uses technical indicators (RSI, MA, volume) to generate trading signals.
Supports multiple strategies: trend_pullback (default) and classic.
"""
from typing import Any

from loguru import logger


class RuleBasedSignalGenerator:
    """Rule-based trading signal generator using technical indicators.

    Strategies:
    - trend_pullback (default): MA crossover + RSI pullback + volume confirmation
      - LONG: MA7 > MA25 > 0 AND RSI < oversold AND volume > threshold
      - SHORT: MA7 < MA25 AND MA25 > 0 AND RSI > overbought AND volume > threshold
    - classic: RSI + price vs MA7
      - LONG: RSI < oversold AND price > MA_7 AND volume > threshold
      - SHORT: RSI > overbought AND price < MA_7 AND volume > threshold
    - WAIT: Otherwise

    기본 RSI 설정: 30/70 (보수적, 생존 우선)

    Phase 6.3: BotConfig에서 rsi_oversold/rsi_overbought 설정 가능
    """

    # 프로덕션 권장 RSI 임계값
    PRODUCTION_RSI_OVERSOLD = 30.0
    PRODUCTION_RSI_OVERBOUGHT = 70.0

    def __init__(
        self,
        rsi_oversold: float = 30.0,
        rsi_overbought: float = 70.0,
        volume_threshold: float = 0.5,
        strategy: str = "trend_pullback",
    ):
        """Initialize rule-based signal generator.

        Args:
            rsi_oversold: RSI threshold for oversold condition (default: 30)
            rsi_overbought: RSI threshold for overbought condition (default: 70)
            volume_threshold: Volume ratio threshold (1.2 = 20% above average)
            strategy: Signal strategy - 'trend_pullback' or 'classic'
        """
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.volume_threshold = volume_threshold
        self.strategy = strategy

        logger.info(
            f"Rule-based signal generator initialized "
            f"(strategy={strategy}, RSI: {rsi_oversold}/{rsi_overbought}, "
            f"Volume: {volume_threshold}x)"
        )

    def get_signal(self, market_data: dict[str, Any]) -> str:
        """Generate trading signal based on technical indicators.

        Dispatches to the appropriate strategy method.

        Args:
            market_data: Dictionary containing:
                - current_price: float
                - rsi: float
                - ma_7: float
                - ma_25: float (optional)
                - volume_ratio: float
                - atr: float (optional)

        Returns:
            Signal: 'LONG', 'SHORT', or 'WAIT'
        """
        if self.strategy == "trend_pullback":
            return self._trend_pullback_signal(market_data)
        return self._classic_signal(market_data)

    def _trend_pullback_signal(self, market_data: dict[str, Any]) -> str:
        """Trend pullback strategy: MA crossover + RSI pullback + volume.

        LONG: MA7 > MA25 > 0 AND RSI < oversold AND volume > threshold
        SHORT: MA7 < MA25 AND MA25 > 0 AND RSI > overbought AND volume > threshold

        Args:
            market_data: Market data dictionary

        Returns:
            Signal: 'LONG', 'SHORT', or 'WAIT'
        """
        try:
            rsi = market_data.get("rsi", 50)
            ma_7 = market_data.get("ma_7", 0)
            ma_25 = market_data.get("ma_25", 0)
            volume_ratio = market_data.get("volume_ratio", 1.0)

            logger.debug(
                f"[trend_pullback] Analyzing: "
                f"RSI={rsi}, MA7={ma_7}, MA25={ma_25}, "
                f"Vol={volume_ratio}"
            )

            # Candle direction confirmation
            current_close = market_data.get("current_price", 0)
            prev_close = market_data.get("prev_close", current_close)

            # LONG: uptrend (MA7 > MA25) + oversold pullback + volume + bullish candle
            if (
                ma_7 > ma_25 > 0
                and rsi < self.rsi_oversold
                and volume_ratio > self.volume_threshold
                and current_close > prev_close
            ):
                logger.info(
                    f"LONG signal [trend_pullback]: "
                    f"MA7={ma_7:.2f} > MA25={ma_25:.2f} (uptrend), "
                    f"RSI={rsi:.2f} < {self.rsi_oversold} (pullback), "
                    f"Vol={volume_ratio:.2f} > {self.volume_threshold}, "
                    f"Bullish candle (close={current_close:.2f} "
                    f"> prev={prev_close:.2f})"
                )
                return "LONG"

            # SHORT: downtrend + overbought pullback + volume + bearish candle
            if (
                ma_7 < ma_25
                and ma_25 > 0
                and rsi > self.rsi_overbought
                and volume_ratio > self.volume_threshold
                and current_close < prev_close
            ):
                logger.info(
                    f"SHORT signal [trend_pullback]: "
                    f"MA7={ma_7:.2f} < MA25={ma_25:.2f} (downtrend), "
                    f"RSI={rsi:.2f} > {self.rsi_overbought} (overbought), "
                    f"Vol={volume_ratio:.2f} > {self.volume_threshold}, "
                    f"Bearish candle (close={current_close:.2f} "
                    f"< prev={prev_close:.2f})"
                )
                return "SHORT"

            logger.debug(
                f"WAIT signal [trend_pullback]: No clear entry "
                f"(RSI={rsi:.2f}, MA7={ma_7:.2f}, MA25={ma_25:.2f}, "
                f"Vol={volume_ratio:.2f})"
            )
            return "WAIT"

        except Exception as e:
            logger.error(f"Error in trend_pullback signal: {e}")
            return "WAIT"

    def _classic_signal(self, market_data: dict[str, Any]) -> str:
        """Classic strategy: RSI + price vs MA7 + volume.

        LONG: RSI < oversold AND price > MA_7 AND volume > threshold
        SHORT: RSI > overbought AND price < MA_7 AND volume > threshold

        Args:
            market_data: Market data dictionary

        Returns:
            Signal: 'LONG', 'SHORT', or 'WAIT'
        """
        try:
            current_price = market_data.get("current_price", 0)
            rsi = market_data.get("rsi", 50)
            ma_7 = market_data.get("ma_7", current_price)
            volume_ratio = market_data.get("volume_ratio", 1.0)

            logger.debug(
                f"[classic] Analyzing: "
                f"Price={current_price:.2f}, "
                f"RSI={rsi:.2f}, "
                f"MA7={ma_7:.2f}, "
                f"Vol={volume_ratio:.2f}"
            )

            # LONG signal conditions
            if (
                rsi < self.rsi_oversold
                and current_price > ma_7
                and volume_ratio > self.volume_threshold
            ):
                logger.info(
                    f"LONG signal [classic]: RSI={rsi:.2f} < {self.rsi_oversold}, "
                    f"Price={current_price:.2f} > MA7={ma_7:.2f}, "
                    f"Volume={volume_ratio:.2f} > {self.volume_threshold}"
                )
                return "LONG"

            # SHORT signal conditions
            if (
                rsi > self.rsi_overbought
                and current_price < ma_7
                and volume_ratio > self.volume_threshold
            ):
                logger.info(
                    f"SHORT signal [classic]: RSI={rsi:.2f} > {self.rsi_overbought}, "
                    f"Price={current_price:.2f} < MA7={ma_7:.2f}, "
                    f"Volume={volume_ratio:.2f} > {self.volume_threshold}"
                )
                return "SHORT"

            # WAIT - no clear signal
            logger.debug(
                f"WAIT signal [classic]: No clear entry conditions "
                f"(RSI={rsi:.2f}, Price vs MA7={(current_price/ma_7-1)*100:.2f}%, "
                f"Volume={volume_ratio:.2f})"
            )
            return "WAIT"

        except Exception as e:
            logger.error(f"Error generating classic signal: {e}")
            return "WAIT"

    def get_signal_diagnostic(self, market_data: dict[str, Any]) -> dict[str, Any]:
        """Return diagnostic info about each signal condition.

        Useful for debugging why a signal was generated or suppressed.

        Args:
            market_data: Market data dictionary

        Returns:
            Dict with condition details: current values, thresholds,
            and pass/fail status
        """
        rsi = market_data.get("rsi", 50)
        ma_7 = market_data.get("ma_7", 0)
        ma_25 = market_data.get("ma_25", 0)
        current_price = market_data.get("current_price", 0)
        volume_ratio = market_data.get("volume_ratio", 1.0)

        signal = self.get_signal(market_data)

        diagnostic: dict[str, Any] = {
            "strategy": self.strategy,
            "signal": signal,
            "rsi": {
                "value": rsi,
                "oversold_threshold": self.rsi_oversold,
                "overbought_threshold": self.rsi_overbought,
                "is_oversold": rsi < self.rsi_oversold,
                "is_overbought": rsi > self.rsi_overbought,
            },
            "volume": {
                "value": volume_ratio,
                "threshold": self.volume_threshold,
                "passes": volume_ratio > self.volume_threshold,
            },
        }

        if self.strategy == "trend_pullback":
            diagnostic["trend"] = {
                "ma_7": ma_7,
                "ma_25": ma_25,
                "is_uptrend": ma_7 > ma_25 > 0,
                "is_downtrend": ma_7 < ma_25 and ma_25 > 0,
            }
        else:
            diagnostic["price"] = {
                "current_price": current_price,
                "ma_7": ma_7,
                "above_ma7": current_price > ma_7,
                "below_ma7": current_price < ma_7,
            }

        return diagnostic
