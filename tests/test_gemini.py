"""
Tests for GeminiSignalGenerator
"""
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

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
                    model="gemini-2.5-flash",
                    temperature=0.1
                )

                assert generator.model == "gemini-2.5-flash"
                assert generator.temperature == 0.1
                mock_client.assert_called_once_with(api_key="test_key")

    def test_init_default_params(self):
        """기본 파라미터로 초기화"""
        with patch("src.ai.gemini.genai.Client"):
            with patch.object(GeminiSignalGenerator, "_load_prompt") as mock_load:
                # Phase 6.1: 3개 프롬프트 로드
                mock_load.side_effect = ["system", "analysis", "analysis_with_reason"]

                generator = GeminiSignalGenerator(api_key="test_key")

                assert generator.model == "gemini-2.5-flash"
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


# =============================================================================
# Coverage tests merged from test_ai_coverage.py
# =============================================================================


def _make_generator(
    system_prompt="System",
    analysis_template="Analysis {{current_price}}",
    analysis_with_reason_template="AnalysisWithReason {{current_price}}",
):
    """Gemini generator 생성 헬퍼"""
    with patch("src.ai.gemini.genai.Client"):
        with patch.object(GeminiSignalGenerator, "_load_prompt") as mock_load:
            mock_load.side_effect = [
                system_prompt,
                analysis_template,
                analysis_with_reason_template,
            ]
            return GeminiSignalGenerator(api_key="test_key")


def _sample_market_data():
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


class TestGeminiLoadPromptErrors:
    """_load_prompt 에러 처리 테스트 (lines 70-78)"""

    def test_load_prompt_file_not_found_analysis_with_reason(self, tmp_path):
        """analysis_with_reason.txt 없을 때 analysis.txt로 폴백 (lines 72-74)"""
        # 프롬프트 디렉토리 생성 (analysis_with_reason.txt 제외)
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "system.txt").write_text("system prompt")
        (prompts_dir / "analysis.txt").write_text("analysis prompt")
        # analysis_with_reason.txt는 생성하지 않음

        with patch("src.ai.gemini.genai.Client"):
            with patch("src.ai.gemini.Path") as mock_path_cls:
                # Path(__file__).parent가 tmp_path를 가리키도록 설정
                mock_parent = MagicMock()
                mock_parent.__truediv__ = Mock(return_value=prompts_dir)
                mock_path_cls.return_value.parent = mock_parent

                generator = GeminiSignalGenerator.__new__(GeminiSignalGenerator)
                generator.client = MagicMock()
                generator.model = "test"
                generator.temperature = 0.3

                # system.txt 로드
                generator.system_prompt = generator._load_prompt("system.txt")
                assert generator.system_prompt == "system prompt"

                # analysis.txt 로드
                generator.analysis_template = generator._load_prompt("analysis.txt")
                assert generator.analysis_template == "analysis prompt"

                # analysis_with_reason.txt → FileNotFoundError → analysis.txt 폴백
                generator.analysis_with_reason_template = generator._load_prompt("analysis_with_reason.txt")
                assert generator.analysis_with_reason_template == "analysis prompt"

    def test_load_prompt_file_not_found_other_file_raises(self, tmp_path):
        """system.txt 등 다른 파일이 없으면 예외 발생 (line 75: raise)"""
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        # 파일 생성하지 않음

        with patch("src.ai.gemini.genai.Client"):
            with patch("src.ai.gemini.Path") as mock_path_cls:
                mock_parent = MagicMock()
                mock_parent.__truediv__ = Mock(return_value=prompts_dir)
                mock_path_cls.return_value.parent = mock_parent

                generator = GeminiSignalGenerator.__new__(GeminiSignalGenerator)
                generator.client = MagicMock()
                generator.model = "test"
                generator.temperature = 0.3

                with pytest.raises(FileNotFoundError):
                    generator._load_prompt("system.txt")

    def test_load_prompt_generic_exception(self):
        """일반 예외 발생 시 re-raise (lines 76-78)"""
        with patch("src.ai.gemini.genai.Client"):

            def smart_open(path, *args, **kwargs):
                raise PermissionError("Permission denied")

            with patch("builtins.open", side_effect=smart_open):
                generator = GeminiSignalGenerator.__new__(GeminiSignalGenerator)
                generator.client = MagicMock()
                generator.model = "test"
                generator.temperature = 0.3

                with pytest.raises(PermissionError):
                    generator._load_prompt("system.txt")


class TestGeminiBuildMarketPromptError:
    """_build_market_prompt 에러 처리 (lines 139-141)"""

    def test_build_market_prompt_missing_key(self):
        """필수 데이터 누락 시 예외 (lines 139-141)"""
        generator = _make_generator()
        # 불완전한 데이터
        bad_data = {"current_price": 100000.0}  # 나머지 필드 없음

        with pytest.raises(KeyError):
            generator._build_market_prompt(bad_data)


class TestGeminiGetSignalSyncEdgeCases:
    """get_signal_sync 엣지 케이스 (lines 227-228, 234-237)"""

    def test_get_signal_sync_null_response(self):
        """동기 호출 시 null 응답 → WAIT (lines 227-228)"""
        generator = _make_generator()
        mock_response = Mock()
        mock_response.text = None
        generator.client.models.generate_content = Mock(return_value=mock_response)

        signal = generator.get_signal_sync(_sample_market_data())
        assert signal == "WAIT"

    def test_get_signal_sync_invalid_signal(self):
        """동기 호출 시 잘못된 신호 → WAIT (lines 234-237)"""
        generator = _make_generator()
        mock_response = Mock()
        mock_response.text = "INVALID_RESPONSE"
        generator.client.models.generate_content = Mock(return_value=mock_response)

        signal = generator.get_signal_sync(_sample_market_data())
        assert signal == "WAIT"


class TestGeminiBuildMarketPromptWithReasonError:
    """_build_market_prompt_with_reason 에러 처리 (lines 310-312)"""

    def test_build_market_prompt_with_reason_error(self):
        """_build_market_prompt_with_reason 데이터 누락 시 예외"""
        generator = _make_generator()
        bad_data = {"current_price": 100000.0}  # 불완전

        with pytest.raises(KeyError):
            generator._build_market_prompt_with_reason(bad_data)


class TestGeminiGetSignalWithReasonSync:
    """get_signal_with_reason_sync 테스트 (lines 428-458)"""

    def test_sync_with_reason_success(self):
        """동기 신호+이유 정상 반환 (lines 428-453)"""
        generator = _make_generator()
        mock_response = Mock()
        mock_response.text = '{"signal": "LONG", "reason": "RSI 과매도"}'
        generator.client.models.generate_content = Mock(return_value=mock_response)

        signal, reason = generator.get_signal_with_reason_sync(_sample_market_data())
        assert signal == "LONG"
        assert "RSI" in reason or "과매도" in reason

    def test_sync_with_reason_null_response(self):
        """동기 null 응답 → WAIT + 응답 없음 (lines 446-448)"""
        generator = _make_generator()
        mock_response = Mock()
        mock_response.text = None
        generator.client.models.generate_content = Mock(return_value=mock_response)

        signal, reason = generator.get_signal_with_reason_sync(_sample_market_data())
        assert signal == "WAIT"
        assert "응답 없음" in reason

    def test_sync_with_reason_api_error(self):
        """동기 API 에러 → WAIT + 오류 메시지 (lines 455-458)"""
        generator = _make_generator()
        generator.client.models.generate_content = Mock(
            side_effect=Exception("Connection error")
        )

        signal, reason = generator.get_signal_with_reason_sync(_sample_market_data())
        assert signal == "WAIT"
        assert "API 오류" in reason
