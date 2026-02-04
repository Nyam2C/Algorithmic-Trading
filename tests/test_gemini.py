"""
Tests for GeminiSignalGenerator
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock

from src.ai.gemini import GeminiSignalGenerator


class TestGeminiSignalGeneratorInit:
    """GeminiSignalGenerator 초기화 테스트"""

    @pytest.fixture
    def mock_prompts(self, tmp_path):
        """임시 프롬프트 파일 생성"""
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()

        (prompts_dir / "system.txt").write_text("You are a trading AI.")
        (prompts_dir / "analysis.txt").write_text("Analyze: {{symbol}} at {{current_price}}")

        return prompts_dir

    def test_init_success(self, mock_prompts):
        """초기화 성공"""
        with patch("src.ai.gemini.genai.Client") as mock_client:
            with patch.object(GeminiSignalGenerator, "_load_prompt") as mock_load:
                # Phase 6.1: 3개 프롬프트 로드 (system, analysis, analysis_with_reason)
                mock_load.side_effect = ["system prompt", "analysis template", "analysis with reason"]

                generator = GeminiSignalGenerator(
                    api_key="test_key",
                    model="gemini-2.0-flash-exp",
                    temperature=0.1
                )

                assert generator.model == "gemini-2.0-flash-exp"
                assert generator.temperature == 0.1
                mock_client.assert_called_once_with(api_key="test_key")

    def test_init_default_params(self):
        """기본 파라미터로 초기화"""
        with patch("src.ai.gemini.genai.Client"):
            with patch.object(GeminiSignalGenerator, "_load_prompt") as mock_load:
                # Phase 6.1: 3개 프롬프트 로드
                mock_load.side_effect = ["system", "analysis", "analysis_with_reason"]

                generator = GeminiSignalGenerator(api_key="test_key")

                assert generator.model == "gemini-2.0-flash-exp"
                # Phase 6.1: 기본 온도 0.1 → 0.3
                assert generator.temperature == 0.3


class TestLoadPrompt:
    """_load_prompt 메서드 테스트"""

    def test_load_prompt_success(self, tmp_path):
        """프롬프트 파일 로드 성공"""
        # 실제 프롬프트 디렉토리 구조 모킹
        with patch("src.ai.gemini.genai.Client"):
            with patch("src.ai.gemini.Path") as mock_path:
                mock_file = MagicMock()
                mock_file.read.return_value = "Test prompt content"
                mock_path.return_value.__truediv__.return_value.__truediv__.return_value = tmp_path / "test.txt"

                # 실제 파일 생성
                (tmp_path / "test.txt").write_text("Test prompt content")

                with patch.object(GeminiSignalGenerator, "_load_prompt", return_value="Test prompt"):
                    generator = GeminiSignalGenerator(api_key="test_key")
                    assert generator.system_prompt == "Test prompt"


class TestBuildMarketPrompt:
    """_build_market_prompt 메서드 테스트"""

    @pytest.fixture
    def generator(self):
        """테스트용 Generator"""
        with patch("src.ai.gemini.genai.Client"):
            with patch.object(GeminiSignalGenerator, "_load_prompt") as mock_load:
                # Phase 6.1: 3개 프롬프트 로드
                mock_load.side_effect = [
                    "System prompt",
                    "Symbol: {{symbol}}, Price: {{current_price}}, RSI: {{rsi}}",
                    "Analysis with reason template"
                ]
                return GeminiSignalGenerator(api_key="test_key")

    @pytest.fixture
    def sample_market_data(self):
        """샘플 시장 데이터"""
        return {
            "current_price": 105000.0,
            "high_24h": 108000.0,
            "low_24h": 102000.0,
            "change_24h_pct": 2.5,
            "trend_2h_pct": 1.2,
            "trend_30min_pct": 0.5,
            "bullish_candles": 15,
            "bearish_candles": 9,
            "resistance": 108000.0,
            "support": 102000.0,
            "rsi": 55.0,
            "rsi_trend": "rising",
            "ma_7": 104500.0,
            "ma_25": 103000.0,
            "ma_99": 100000.0,
            "price_vs_ma7_pct": 0.48,
            "price_vs_ma7_pos": "above",
            "price_vs_ma25_pct": 1.94,
            "price_vs_ma25_pos": "above",
            "current_volume": 1500.0,
            "avg_volume": 1200.0,
            "volume_ratio": 1.25,
            "volume_trend": "increasing",
            "atr": 1500.0,
            "atr_pct": 1.43,
            "volatility_state": "normal",
            "dist_resistance_pct": 2.86,
            "dist_support_pct": -2.86,
        }

    def test_build_market_prompt_success(self, generator, sample_market_data):
        """시장 프롬프트 생성 성공"""
        prompt = generator._build_market_prompt(sample_market_data)

        assert "105000.00" in prompt or "105,000.00" in prompt
        assert "55.00" in prompt


class TestGetSignal:
    """get_signal 메서드 테스트"""

    @pytest.fixture
    def generator(self):
        """테스트용 Generator"""
        with patch("src.ai.gemini.genai.Client"):
            with patch.object(GeminiSignalGenerator, "_load_prompt") as mock_load:
                # Phase 6.1: 3개 프롬프트 로드
                mock_load.side_effect = ["System", "Analysis {{current_price}}", "Analysis with reason"]
                gen = GeminiSignalGenerator(api_key="test_key")
                return gen

    @pytest.fixture
    def sample_market_data(self):
        return {
            "current_price": 105000.0,
            "high_24h": 108000.0,
            "low_24h": 102000.0,
            "change_24h_pct": 2.5,
            "trend_2h_pct": 1.2,
            "trend_30min_pct": 0.5,
            "bullish_candles": 15,
            "bearish_candles": 9,
            "resistance": 108000.0,
            "support": 102000.0,
            "rsi": 55.0,
            "rsi_trend": "rising",
            "ma_7": 104500.0,
            "ma_25": 103000.0,
            "ma_99": 100000.0,
            "price_vs_ma7_pct": 0.48,
            "price_vs_ma7_pos": "above",
            "price_vs_ma25_pct": 1.94,
            "price_vs_ma25_pos": "above",
            "current_volume": 1500.0,
            "avg_volume": 1200.0,
            "volume_ratio": 1.25,
            "volume_trend": "increasing",
            "atr": 1500.0,
            "atr_pct": 1.43,
            "volatility_state": "normal",
            "dist_resistance_pct": 2.86,
            "dist_support_pct": -2.86,
        }

    @pytest.mark.asyncio
    async def test_get_signal_long(self, generator, sample_market_data):
        """LONG 신호 반환"""
        mock_response = Mock()
        mock_response.text = "LONG"
        generator.client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        signal = await generator.get_signal(sample_market_data)

        assert signal == "LONG"

    @pytest.mark.asyncio
    async def test_get_signal_short(self, generator, sample_market_data):
        """SHORT 신호 반환"""
        mock_response = Mock()
        mock_response.text = "SHORT"
        generator.client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        signal = await generator.get_signal(sample_market_data)

        assert signal == "SHORT"

    @pytest.mark.asyncio
    async def test_get_signal_wait(self, generator, sample_market_data):
        """WAIT 신호 반환"""
        mock_response = Mock()
        mock_response.text = "WAIT"
        generator.client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        signal = await generator.get_signal(sample_market_data)

        assert signal == "WAIT"

    @pytest.mark.asyncio
    async def test_get_signal_with_whitespace(self, generator, sample_market_data):
        """공백이 포함된 신호 처리"""
        mock_response = Mock()
        mock_response.text = "  long  \n"
        generator.client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        signal = await generator.get_signal(sample_market_data)

        assert signal == "LONG"

    @pytest.mark.asyncio
    async def test_get_signal_invalid_defaults_to_wait(self, generator, sample_market_data):
        """잘못된 신호는 WAIT로 기본값"""
        mock_response = Mock()
        mock_response.text = "INVALID_SIGNAL"
        generator.client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        signal = await generator.get_signal(sample_market_data)

        assert signal == "WAIT"

    @pytest.mark.asyncio
    async def test_get_signal_empty_response(self, generator, sample_market_data):
        """빈 응답은 WAIT 반환"""
        mock_response = Mock()
        mock_response.text = None
        generator.client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        signal = await generator.get_signal(sample_market_data)

        assert signal == "WAIT"

    @pytest.mark.asyncio
    async def test_get_signal_api_error(self, generator, sample_market_data):
        """API 에러 시 WAIT 반환"""
        generator.client.aio.models.generate_content = AsyncMock(
            side_effect=Exception("API Error")
        )

        signal = await generator.get_signal(sample_market_data)

        assert signal == "WAIT"


class TestGetSignalSync:
    """get_signal_sync 메서드 테스트"""

    @pytest.fixture
    def generator(self):
        with patch("src.ai.gemini.genai.Client"):
            with patch.object(GeminiSignalGenerator, "_load_prompt") as mock_load:
                # Phase 6.1: 3개 프롬프트 로드
                mock_load.side_effect = ["System", "Analysis {{current_price}}", "Analysis with reason"]
                gen = GeminiSignalGenerator(api_key="test_key")
                return gen

    @pytest.fixture
    def sample_market_data(self):
        return {
            "current_price": 105000.0,
            "high_24h": 108000.0,
            "low_24h": 102000.0,
            "change_24h_pct": 2.5,
            "trend_2h_pct": 1.2,
            "trend_30min_pct": 0.5,
            "bullish_candles": 15,
            "bearish_candles": 9,
            "resistance": 108000.0,
            "support": 102000.0,
            "rsi": 55.0,
            "rsi_trend": "rising",
            "ma_7": 104500.0,
            "ma_25": 103000.0,
            "ma_99": 100000.0,
            "price_vs_ma7_pct": 0.48,
            "price_vs_ma7_pos": "above",
            "price_vs_ma25_pct": 1.94,
            "price_vs_ma25_pos": "above",
            "current_volume": 1500.0,
            "avg_volume": 1200.0,
            "volume_ratio": 1.25,
            "volume_trend": "increasing",
            "atr": 1500.0,
            "atr_pct": 1.43,
            "volatility_state": "normal",
            "dist_resistance_pct": 2.86,
            "dist_support_pct": -2.86,
        }

    def test_get_signal_sync_long(self, generator, sample_market_data):
        """동기 LONG 신호"""
        mock_response = Mock()
        mock_response.text = "LONG"
        generator.client.models.generate_content = Mock(return_value=mock_response)

        signal = generator.get_signal_sync(sample_market_data)

        assert signal == "LONG"

    def test_get_signal_sync_error(self, generator, sample_market_data):
        """동기 API 에러"""
        generator.client.models.generate_content = Mock(side_effect=Exception("Error"))

        signal = generator.get_signal_sync(sample_market_data)

        assert signal == "WAIT"
