"""
Gemini AI client for trading signal generation
"""
from typing import Dict
from pathlib import Path
from google import genai
from loguru import logger


class GeminiSignalGenerator:
    """Generate trading signals using Gemini AI"""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash-exp",
        temperature: float = 0.1,
    ):
        """
        Initialize Gemini client

        Args:
            api_key: Gemini API key
            model: Model name (default: gemini-2.0-flash-exp)
            temperature: Temperature for generation (default: 0.1)
        """
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.temperature = temperature

        # Load prompts
        self.system_prompt = self._load_prompt("system.txt")
        self.analysis_template = self._load_prompt("analysis.txt")

        logger.info(f"Gemini client initialized (model: {model})")

    def _load_prompt(self, filename: str) -> str:
        """
        Load prompt from file

        Args:
            filename: Prompt filename (system.txt or analysis.txt)

        Returns:
            Prompt content
        """
        try:
            prompt_dir = Path(__file__).parent / "prompts"
            prompt_path = prompt_dir / filename
            with open(prompt_path, "r", encoding="utf-8") as f:
                content = f.read()
            logger.debug(f"Loaded prompt: {filename}")
            return content
        except Exception as e:
            logger.error(f"Failed to load prompt {filename}: {e}")
            raise

    def _build_market_prompt(self, market_data: Dict) -> str:
        """
        Build market analysis prompt from data

        Args:
            market_data: Dictionary with market indicators

        Returns:
            Formatted prompt string
        """
        try:
            # Format all values for the template
            formatted_data = {
                "symbol": "BTCUSDT",
                # Price action
                "trend_2h_pct": f"{market_data['trend_2h_pct']:+.2f}",
                "trend_30min_pct": f"{market_data['trend_30min_pct']:+.2f}",
                "bullish_candles": market_data["bullish_candles"],
                "bearish_candles": market_data["bearish_candles"],
                "highest": f"{market_data['resistance']:,.0f}",
                "lowest": f"{market_data['support']:,.0f}",
                # Current state
                "current_price": f"{market_data['current_price']:,.2f}",
                "high_24h": f"{market_data['high_24h']:,.2f}",
                "low_24h": f"{market_data['low_24h']:,.2f}",
                "change_24h_pct": f"{market_data['change_24h_pct']:+.2f}",
                # Technical indicators
                "rsi": f"{market_data['rsi']:.2f}",
                "rsi_trend": market_data["rsi_trend"],
                "ma_7": f"{market_data['ma_7']:,.2f}",
                "ma_25": f"{market_data['ma_25']:,.2f}",
                "ma_99": f"{market_data['ma_99']:,.2f}",
                "price_vs_ma7_pct": f"{market_data['price_vs_ma7_pct']:+.2f}",
                "price_vs_ma7_pos": market_data["price_vs_ma7_pos"],
                "price_vs_ma25_pct": f"{market_data['price_vs_ma25_pct']:+.2f}",
                "price_vs_ma25_pos": market_data["price_vs_ma25_pos"],
                # Volume
                "current_volume": f"{market_data['current_volume']:.0f}",
                "avg_volume": f"{market_data['avg_volume']:.0f}",
                "volume_ratio": f"{market_data['volume_ratio']:.2f}",
                "volume_trend": market_data["volume_trend"],
                # Volatility
                "atr": f"{market_data['atr']:.2f}",
                "atr_pct": f"{market_data['atr_pct']:.2f}",
                "volatility_state": market_data["volatility_state"],
                # Support/Resistance
                "resistance": f"{market_data['resistance']:,.2f}",
                "support": f"{market_data['support']:,.2f}",
                "dist_resistance_pct": f"{market_data['dist_resistance_pct']:+.2f}",
                "dist_support_pct": f"{market_data['dist_support_pct']:+.2f}",
            }

            # Replace template variables
            prompt = self.analysis_template
            for key, value in formatted_data.items():
                prompt = prompt.replace(f"{{{{{key}}}}}", str(value))

            return prompt

        except Exception as e:
            logger.error(f"Failed to build market prompt: {e}")
            raise

    async def get_signal(self, market_data: Dict) -> str:
        """
        Generate trading signal from market data

        Args:
            market_data: Dictionary with market indicators

        Returns:
            Signal: "LONG", "SHORT", or "WAIT"
        """
        try:
            # Build prompts
            user_prompt = self._build_market_prompt(market_data)
            full_prompt = f"{self.system_prompt}\n\n{user_prompt}"

            logger.debug("Calling Gemini API...")

            # Call Gemini API
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=full_prompt,
                config={
                    "temperature": self.temperature,
                    "max_output_tokens": 10,
                },
            )

            # Parse response
            if response.text is None:
                logger.warning("Empty response from Gemini, defaulting to WAIT")
                return "WAIT"

            signal = response.text.strip().upper()

            # Validate signal
            if signal not in ["LONG", "SHORT", "WAIT"]:
                logger.warning(
                    f"Invalid signal '{signal}' from Gemini, defaulting to WAIT"
                )
                return "WAIT"

            logger.info(f"Signal generated: {signal}")
            return signal

        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            logger.warning("Defaulting to WAIT due to error")
            return "WAIT"

    def get_signal_sync(self, market_data: Dict) -> str:
        """
        Synchronous version of get_signal (for testing)

        Args:
            market_data: Dictionary with market indicators

        Returns:
            Signal: "LONG", "SHORT", or "WAIT"
        """
        try:
            # Build prompts
            user_prompt = self._build_market_prompt(market_data)
            full_prompt = f"{self.system_prompt}\n\n{user_prompt}"

            logger.debug("Calling Gemini API (sync)...")

            # Call Gemini API (synchronous)
            response = self.client.models.generate_content(
                model=self.model,
                contents=full_prompt,
                config={
                    "temperature": self.temperature,
                    "max_output_tokens": 10,
                },
            )

            # Parse response
            if response.text is None:
                logger.warning("Empty response from Gemini (sync), defaulting to WAIT")
                return "WAIT"

            signal = response.text.strip().upper()

            # Validate signal
            if signal not in ["LONG", "SHORT", "WAIT"]:
                logger.warning(
                    f"Invalid signal '{signal}' from Gemini, defaulting to WAIT"
                )
                return "WAIT"

            logger.info(f"Signal generated: {signal}")
            return signal

        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            logger.warning("Defaulting to WAIT due to error")
            return "WAIT"
