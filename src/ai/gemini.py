"""
Gemini AI client for trading signal generation

Phase 6.1: 신호 생성 이유 로깅 추가
- Temperature 0.1 → 0.3 (더 다양한 응답)
- get_signal_with_reason() 메서드 추가
- JSON 형식 응답 지원
"""
import json
from typing import Dict, Tuple
from pathlib import Path
from google import genai
from google.genai.errors import ClientError, ServerError
from loguru import logger

from src.utils.retry import async_retry


class GeminiSignalGenerator:
    """Generate trading signals using Gemini AI

    Phase 6.1: 신호 생성 이유 포함 응답 지원
    """

    # 기본 온도 설정 (Phase 6.1: 0.1 → 0.3)
    DEFAULT_TEMPERATURE = 0.3

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash-exp",
        temperature: float = DEFAULT_TEMPERATURE,
    ):
        """
        Initialize Gemini client

        Args:
            api_key: Gemini API key
            model: Model name (default: gemini-2.0-flash-exp)
            temperature: Temperature for generation (default: 0.3)
        """
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.temperature = temperature

        # Load prompts
        self.system_prompt = self._load_prompt("system.txt")
        self.analysis_template = self._load_prompt("analysis.txt")
        self.analysis_with_reason_template = self._load_prompt("analysis_with_reason.txt")

        logger.info(f"Gemini client initialized (model: {model}, temp: {temperature})")

    def _load_prompt(self, filename: str) -> str:
        """
        Load prompt from file

        Args:
            filename: Prompt filename (system.txt, analysis.txt, etc.)

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
        except FileNotFoundError:
            # analysis_with_reason.txt가 없으면 기본 템플릿 사용
            if filename == "analysis_with_reason.txt":
                logger.warning(f"Prompt {filename} not found, using default analysis.txt")
                return self._load_prompt("analysis.txt")
            raise
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

    @async_retry(
        max_attempts=3,
        delay=2.0,
        backoff=2.0,
        exceptions=(ClientError, ServerError, ConnectionError, TimeoutError),
    )
    async def get_signal(self, market_data: Dict) -> str:
        """
        Generate trading signal from market data (with retry)

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

    # =========================================================================
    # Phase 6.1: 신호 생성 이유 포함 메서드
    # =========================================================================

    def _build_market_prompt_with_reason(self, market_data: Dict) -> str:
        """
        Build market analysis prompt with reason format

        Args:
            market_data: Dictionary with market indicators

        Returns:
            Formatted prompt string for JSON response
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
            prompt = self.analysis_with_reason_template
            for key, value in formatted_data.items():
                prompt = prompt.replace(f"{{{{{key}}}}}", str(value))

            return prompt

        except Exception as e:
            logger.error(f"Failed to build market prompt with reason: {e}")
            raise

    def _parse_signal_with_reason(self, response_text: str) -> Tuple[str, str]:
        """
        Parse JSON response to extract signal and reason

        Args:
            response_text: Raw response from Gemini

        Returns:
            Tuple of (signal, reason)
        """
        if not response_text:
            return "WAIT", "응답 없음"

        # JSON 블록 추출 시도
        text = response_text.strip()

        # ```json 블록 제거
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end != -1:
                text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end != -1:
                text = text[start:end].strip()

        try:
            data = json.loads(text)
            signal = data.get("signal", "WAIT").upper()
            reason = data.get("reason", "이유 없음")

            # 신호 검증
            if signal not in ["LONG", "SHORT", "WAIT"]:
                logger.warning(f"Invalid signal in JSON: {signal}")
                signal = "WAIT"

            return signal, reason

        except json.JSONDecodeError:
            # JSON 파싱 실패 시 텍스트에서 신호 추출 시도
            logger.warning(f"Failed to parse JSON response: {text[:100]}...")

            upper_text = text.upper()
            if "LONG" in upper_text:
                return "LONG", "JSON 파싱 실패, 텍스트에서 추출"
            elif "SHORT" in upper_text:
                return "SHORT", "JSON 파싱 실패, 텍스트에서 추출"
            else:
                return "WAIT", "JSON 파싱 실패"

    @async_retry(
        max_attempts=3,
        delay=2.0,
        backoff=2.0,
        exceptions=(ClientError, ServerError, ConnectionError, TimeoutError),
    )
    async def get_signal_with_reason(self, market_data: Dict) -> Tuple[str, str]:
        """
        Generate trading signal with reasoning (with retry)

        Phase 6.1: 신호와 함께 이유도 반환

        Args:
            market_data: Dictionary with market indicators

        Returns:
            Tuple of (signal, reason) where:
                - signal: "LONG", "SHORT", or "WAIT"
                - reason: Korean explanation string
        """
        try:
            # Build prompts with reason format
            user_prompt = self._build_market_prompt_with_reason(market_data)
            full_prompt = f"{self.system_prompt}\n\n{user_prompt}"

            logger.debug("Calling Gemini API for signal with reason...")

            # Call Gemini API with higher max_output_tokens for JSON
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=full_prompt,
                config={
                    "temperature": self.temperature,
                    "max_output_tokens": 200,  # JSON 응답을 위해 증가
                },
            )

            # Parse response
            if response.text is None:
                logger.warning("Empty response from Gemini, defaulting to WAIT")
                return "WAIT", "응답 없음"

            signal, reason = self._parse_signal_with_reason(response.text)

            logger.info(f"Signal with reason: {signal} - {reason}")
            return signal, reason

        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            logger.warning("Defaulting to WAIT due to error")
            return "WAIT", f"API 오류: {str(e)[:50]}"

    def get_signal_with_reason_sync(self, market_data: Dict) -> Tuple[str, str]:
        """
        Synchronous version of get_signal_with_reason (for testing)

        Args:
            market_data: Dictionary with market indicators

        Returns:
            Tuple of (signal, reason)
        """
        try:
            # Build prompts with reason format
            user_prompt = self._build_market_prompt_with_reason(market_data)
            full_prompt = f"{self.system_prompt}\n\n{user_prompt}"

            logger.debug("Calling Gemini API (sync) for signal with reason...")

            # Call Gemini API (synchronous)
            response = self.client.models.generate_content(
                model=self.model,
                contents=full_prompt,
                config={
                    "temperature": self.temperature,
                    "max_output_tokens": 200,
                },
            )

            # Parse response
            if response.text is None:
                logger.warning("Empty response from Gemini (sync), defaulting to WAIT")
                return "WAIT", "응답 없음"

            signal, reason = self._parse_signal_with_reason(response.text)

            logger.info(f"Signal with reason (sync): {signal} - {reason}")
            return signal, reason

        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            logger.warning("Defaulting to WAIT due to error")
            return "WAIT", f"API 오류: {str(e)[:50]}"
