"""
Rule-based signal generator (temporary fallback for Gemini API)

Uses technical indicators (RSI, MA, volume) to generate trading signals.
This is a temporary solution until Gemini API becomes available.
"""
from typing import Dict, Any
from loguru import logger


class RuleBasedSignalGenerator:
    """
    Rule-based trading signal generator using technical indicators

    Strategy:
    - LONG: RSI < 35 (oversold) AND price > MA_7 (uptrend) AND volume > avg
    - SHORT: RSI > 65 (overbought) AND price < MA_7 (downtrend) AND volume > avg
    - WAIT: Otherwise
    """

    def __init__(
        self,
        rsi_oversold: float = 35.0,
        rsi_overbought: float = 65.0,
        volume_threshold: float = 1.2,
    ):
        """
        Initialize rule-based signal generator

        Args:
            rsi_oversold: RSI threshold for oversold condition
            rsi_overbought: RSI threshold for overbought condition
            volume_threshold: Volume ratio threshold (1.2 = 20% above average)
        """
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.volume_threshold = volume_threshold

        logger.info(
            f"Rule-based signal generator initialized "
            f"(RSI: {rsi_oversold}/{rsi_overbought}, "
            f"Volume: {volume_threshold}x)"
        )

    def get_signal(self, market_data: Dict[str, Any]) -> str:
        """
        Generate trading signal based on technical indicators

        Args:
            market_data: Dictionary containing:
                - current_price: float
                - rsi: float
                - ma_7: float
                - ma_25: float (optional)
                - volume_ratio: float
                - atr: float (optional)

        Returns:
            Signal: "LONG", "SHORT", or "WAIT"
        """
        try:
            # Extract indicators
            current_price = market_data.get("current_price", 0)
            rsi = market_data.get("rsi", 50)
            ma_7 = market_data.get("ma_7", current_price)
            volume_ratio = market_data.get("volume_ratio", 1.0)

            logger.debug(
                f"Analyzing indicators: "
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
                    f"LONG signal: RSI={rsi:.2f} < {self.rsi_oversold}, "
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
                    f"SHORT signal: RSI={rsi:.2f} > {self.rsi_overbought}, "
                    f"Price={current_price:.2f} < MA7={ma_7:.2f}, "
                    f"Volume={volume_ratio:.2f} > {self.volume_threshold}"
                )
                return "SHORT"

            # WAIT - no clear signal
            logger.debug(
                f"WAIT signal: No clear entry conditions "
                f"(RSI={rsi:.2f}, Price vs MA7={(current_price/ma_7-1)*100:.2f}%, "
                f"Volume={volume_ratio:.2f})"
            )
            return "WAIT"

        except Exception as e:
            logger.error(f"Error generating rule-based signal: {e}")
            # Safe fallback
            return "WAIT"
