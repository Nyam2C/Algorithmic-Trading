"""
Gemini AI 신호 이유 로깅 테스트

Phase 6.1: get_signal_with_reason() 테스트
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.ai.gemini import GeminiSignalGenerator


class TestGeminiSignalGenerator:
    """GeminiSignalGenerator 테스트"""

    @pytest.fixture
    def sample_market_data(self):
        """테스트용 시장 데이터"""
        return {
            "current_price": 50000.0,
            "high_24h": 51000.0,
            "low_24h": 49000.0,
            "change_24h_pct": 2.5,
            "trend_2h_pct": 1.2,
            "trend_30min_pct": 0.5,
            "bullish_candles": 15,
            "bearish_candles": 9,
            "rsi": 35.5,
            "rsi_trend": "falling",
            "ma_7": 49800.0,
            "ma_25": 49500.0,
            "ma_99": 48000.0,
            "price_vs_ma7_pct": 0.4,
            "price_vs_ma7_pos": "above",
            "price_vs_ma25_pct": 1.0,
            "price_vs_ma25_pos": "above",
            "current_volume": 1500.0,
            "avg_volume": 1200.0,
            "volume_ratio": 1.25,
            "volume_trend": "increasing",
            "atr": 500.0,
            "atr_pct": 1.0,
            "volatility_state": "normal",
            "resistance": 51500.0,
            "support": 48500.0,
            "dist_resistance_pct": 3.0,
            "dist_support_pct": -3.0,
        }


class TestParseSignalWithReason:
    """_parse_signal_with_reason 테스트"""

    @pytest.fixture
    def generator(self):
        """Mock generator (API 키 없이)"""
        with patch.object(GeminiSignalGenerator, "__init__", lambda x, y: None):
            gen = GeminiSignalGenerator("dummy")
            return gen

    def test_parse_valid_json(self, generator):
        """유효한 JSON 파싱 테스트"""
        response = '{"signal": "LONG", "reason": "RSI 과매도 구간"}'

        signal, reason = generator._parse_signal_with_reason(response)

        assert signal == "LONG"
        assert reason == "RSI 과매도 구간"

    def test_parse_json_with_code_block(self, generator):
        """코드 블록 포함 JSON 파싱 테스트"""
        response = '''```json
{"signal": "SHORT", "reason": "RSI 70 이상 과매수"}
```'''

        signal, reason = generator._parse_signal_with_reason(response)

        assert signal == "SHORT"
        assert reason == "RSI 70 이상 과매수"

    def test_parse_json_with_plain_code_block(self, generator):
        """일반 코드 블록 포함 JSON 파싱 테스트"""
        response = '''```
{"signal": "WAIT", "reason": "명확한 방향성 부재"}
```'''

        signal, reason = generator._parse_signal_with_reason(response)

        assert signal == "WAIT"
        assert reason == "명확한 방향성 부재"

    def test_parse_invalid_signal_in_json(self, generator):
        """유효하지 않은 신호 처리 테스트"""
        response = '{"signal": "BUY", "reason": "테스트"}'

        signal, reason = generator._parse_signal_with_reason(response)

        assert signal == "WAIT"  # 유효하지 않은 신호는 WAIT로 변환
        assert reason == "테스트"

    def test_parse_fallback_to_text_long(self, generator):
        """JSON 파싱 실패 시 텍스트에서 LONG 추출 테스트"""
        response = "I recommend LONG position because RSI is low"

        signal, reason = generator._parse_signal_with_reason(response)

        assert signal == "LONG"
        assert "파싱 실패" in reason

    def test_parse_fallback_to_text_short(self, generator):
        """JSON 파싱 실패 시 텍스트에서 SHORT 추출 테스트"""
        response = "The market is overbought, SHORT is recommended"

        signal, reason = generator._parse_signal_with_reason(response)

        assert signal == "SHORT"

    def test_parse_fallback_to_wait(self, generator):
        """JSON 파싱 실패 시 WAIT 반환 테스트"""
        response = "The market is unclear"

        signal, reason = generator._parse_signal_with_reason(response)

        assert signal == "WAIT"
        assert "파싱 실패" in reason

    def test_parse_empty_response(self, generator):
        """빈 응답 처리 테스트"""
        signal, reason = generator._parse_signal_with_reason("")

        assert signal == "WAIT"
        assert reason == "응답 없음"

    def test_parse_none_response(self, generator):
        """None 응답 처리 테스트"""
        signal, reason = generator._parse_signal_with_reason(None)

        assert signal == "WAIT"
        assert reason == "응답 없음"


class TestGetSignalWithReason:
    """get_signal_with_reason 테스트"""

    @pytest.fixture
    def mock_generator(self, sample_market_data):
        """Mock API를 사용하는 generator"""
        with patch("src.ai.gemini.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client

            # Mock async response
            mock_response = MagicMock()
            mock_response.text = '{"signal": "LONG", "reason": "RSI 과매도"}'

            mock_client.aio.models.generate_content = AsyncMock(
                return_value=mock_response
            )

            generator = GeminiSignalGenerator("test-api-key")
            return generator

    @pytest.fixture
    def sample_market_data(self):
        """테스트용 시장 데이터"""
        return {
            "current_price": 50000.0,
            "high_24h": 51000.0,
            "low_24h": 49000.0,
            "change_24h_pct": 2.5,
            "trend_2h_pct": 1.2,
            "trend_30min_pct": 0.5,
            "bullish_candles": 15,
            "bearish_candles": 9,
            "rsi": 35.5,
            "rsi_trend": "falling",
            "ma_7": 49800.0,
            "ma_25": 49500.0,
            "ma_99": 48000.0,
            "price_vs_ma7_pct": 0.4,
            "price_vs_ma7_pos": "above",
            "price_vs_ma25_pct": 1.0,
            "price_vs_ma25_pos": "above",
            "current_volume": 1500.0,
            "avg_volume": 1200.0,
            "volume_ratio": 1.25,
            "volume_trend": "increasing",
            "atr": 500.0,
            "atr_pct": 1.0,
            "volatility_state": "normal",
            "resistance": 51500.0,
            "support": 48500.0,
            "dist_resistance_pct": 3.0,
            "dist_support_pct": -3.0,
        }

    @pytest.mark.asyncio
    async def test_get_signal_with_reason_success(
        self, mock_generator, sample_market_data
    ):
        """성공적인 신호 및 이유 반환 테스트"""
        signal, reason = await mock_generator.get_signal_with_reason(sample_market_data)

        assert signal == "LONG"
        assert reason == "RSI 과매도"

    @pytest.mark.asyncio
    async def test_get_signal_with_reason_empty_response(self, sample_market_data):
        """빈 응답 처리 테스트"""
        with patch("src.ai.gemini.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client

            mock_response = MagicMock()
            mock_response.text = None

            mock_client.aio.models.generate_content = AsyncMock(
                return_value=mock_response
            )

            generator = GeminiSignalGenerator("test-api-key")
            signal, reason = await generator.get_signal_with_reason(sample_market_data)

            assert signal == "WAIT"
            assert reason == "응답 없음"

    @pytest.mark.asyncio
    async def test_get_signal_with_reason_api_error(self, sample_market_data):
        """API 오류 처리 테스트"""
        with patch("src.ai.gemini.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client

            # API 오류 발생
            mock_client.aio.models.generate_content = AsyncMock(
                side_effect=Exception("API Error")
            )

            generator = GeminiSignalGenerator("test-api-key")

            # retry 데코레이터가 적용되어 있으므로 최종적으로 WAIT 반환
            signal, reason = await generator.get_signal_with_reason(sample_market_data)

            assert signal == "WAIT"
            assert "오류" in reason


class TestBuildMarketPromptWithReason:
    """_build_market_prompt_with_reason 테스트"""

    @pytest.fixture
    def generator(self):
        """Generator with mocked prompts"""
        with patch("src.ai.gemini.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client

            generator = GeminiSignalGenerator("test-api-key")
            return generator

    @pytest.fixture
    def sample_market_data(self):
        """테스트용 시장 데이터"""
        return {
            "current_price": 50000.0,
            "high_24h": 51000.0,
            "low_24h": 49000.0,
            "change_24h_pct": 2.5,
            "trend_2h_pct": 1.2,
            "trend_30min_pct": 0.5,
            "bullish_candles": 15,
            "bearish_candles": 9,
            "rsi": 35.5,
            "rsi_trend": "falling",
            "ma_7": 49800.0,
            "ma_25": 49500.0,
            "ma_99": 48000.0,
            "price_vs_ma7_pct": 0.4,
            "price_vs_ma7_pos": "above",
            "price_vs_ma25_pct": 1.0,
            "price_vs_ma25_pos": "above",
            "current_volume": 1500.0,
            "avg_volume": 1200.0,
            "volume_ratio": 1.25,
            "volume_trend": "increasing",
            "atr": 500.0,
            "atr_pct": 1.0,
            "volatility_state": "normal",
            "resistance": 51500.0,
            "support": 48500.0,
            "dist_resistance_pct": 3.0,
            "dist_support_pct": -3.0,
        }

    def test_build_prompt_contains_json_format(self, generator, sample_market_data):
        """프롬프트에 JSON 형식 지시가 포함되는지 테스트"""
        prompt = generator._build_market_prompt_with_reason(sample_market_data)

        assert "JSON" in prompt or "json" in prompt
        assert "signal" in prompt
        assert "reason" in prompt

    def test_build_prompt_contains_market_data(self, generator, sample_market_data):
        """프롬프트에 시장 데이터가 포함되는지 테스트"""
        prompt = generator._build_market_prompt_with_reason(sample_market_data)

        assert "50,000" in prompt  # current_price
        assert "35.5" in prompt  # RSI
        assert "49,800" in prompt  # MA7


class TestDefaultTemperature:
    """기본 Temperature 설정 테스트"""

    def test_default_temperature_is_0_3(self):
        """기본 온도가 0.3인지 테스트"""
        assert GeminiSignalGenerator.DEFAULT_TEMPERATURE == 0.3

    def test_generator_uses_default_temperature(self):
        """Generator가 기본 온도를 사용하는지 테스트"""
        with patch("src.ai.gemini.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client

            generator = GeminiSignalGenerator("test-api-key")

            assert generator.temperature == 0.3

    def test_generator_accepts_custom_temperature(self):
        """사용자 정의 온도 설정 테스트"""
        with patch("src.ai.gemini.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client

            generator = GeminiSignalGenerator("test-api-key", temperature=0.5)

            assert generator.temperature == 0.5
