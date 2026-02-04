"""
EnhancedGeminiSignalGenerator 테스트

Phase 4: AI 메모리 시스템 - 메모리 주입 Gemini 클라이언트 테스트
TDD 방식으로 작성
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.ai.enhanced_gemini import EnhancedGeminiSignalGenerator
from src.analytics.memory_context import MemoryContext, AIMemoryContextBuilder

# genai는 src.ai.gemini 모듈에서 임포트되므로 해당 위치에서 패치해야 함
GENAI_PATCH = "src.ai.gemini.genai"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_genai_client():
    """모의 Gemini 클라이언트"""
    mock_client = MagicMock()
    mock_client.aio = MagicMock()
    mock_client.aio.models = MagicMock()
    return mock_client


@pytest.fixture
def mock_context_builder():
    """모의 AIMemoryContextBuilder"""
    builder = MagicMock(spec=AIMemoryContextBuilder)
    return builder


@pytest.fixture
def sample_memory_context():
    """샘플 메모리 컨텍스트"""
    return MemoryContext(
        overall_summary="7일간: 42거래, 승률 68%, +$125",
        recent_performance="최근 10개: 7승 3패, 연속 3승 중",
        best_conditions="LONG RSI<30 (승률 85%)",
        worst_conditions="LONG RSI 40-60 (승률 35%)",
        timing_insights="최적: 14시, 15시 | 피해야 할: 3시, 4시",
        recommendations="LONG 추천: RSI<30 | 최적 시간: 14시",
    )


@pytest.fixture
def sample_market_data():
    """샘플 시장 데이터"""
    return {
        "current_price": 106500.00,
        "trend_2h_pct": 0.5,
        "trend_30min_pct": 0.2,
        "bullish_candles": 15,
        "bearish_candles": 9,
        "rsi": 32.5,
        "rsi_trend": "rising",
        "ma_7": 106200.00,
        "ma_25": 105800.00,
        "ma_99": 104500.00,
        "price_vs_ma7_pct": 0.28,
        "price_vs_ma7_pos": "above",
        "price_vs_ma25_pct": 0.66,
        "price_vs_ma25_pos": "above",
        "current_volume": 15000,
        "avg_volume": 12000,
        "volume_ratio": 1.25,
        "volume_trend": "increasing",
        "atr": 450.0,
        "atr_pct": 0.42,
        "volatility_state": "normal",
        "resistance": 107000.00,
        "support": 105500.00,
        "dist_resistance_pct": 0.47,
        "dist_support_pct": -0.94,
        "high_24h": 107500.00,
        "low_24h": 104800.00,
        "change_24h_pct": 1.2,
    }


# =============================================================================
# EnhancedGeminiSignalGenerator 생성 테스트
# =============================================================================


class TestEnhancedGeminiSignalGeneratorInit:
    """EnhancedGeminiSignalGenerator 초기화 테스트"""

    @patch(GENAI_PATCH)
    def test_initialization_with_context_builder(self, mock_genai, mock_context_builder):
        """컨텍스트 빌더로 초기화 테스트"""
        generator = EnhancedGeminiSignalGenerator(
            api_key="test-api-key",
            context_builder=mock_context_builder,
        )
        assert generator.context_builder == mock_context_builder
        assert generator.memory_enabled is True

    @patch(GENAI_PATCH)
    def test_initialization_without_context_builder(self, mock_genai):
        """컨텍스트 빌더 없이 초기화 테스트"""
        generator = EnhancedGeminiSignalGenerator(
            api_key="test-api-key",
        )
        assert generator.context_builder is None
        assert generator.memory_enabled is False

    @patch(GENAI_PATCH)
    def test_memory_system_prompt_loaded(self, mock_genai, mock_context_builder):
        """메모리 시스템 프롬프트 로딩 테스트"""
        generator = EnhancedGeminiSignalGenerator(
            api_key="test-api-key",
            context_builder=mock_context_builder,
        )
        # 메모리 시스템 프롬프트가 로드되어야 함
        assert generator.memory_system_prompt is not None
        assert len(generator.memory_system_prompt) > 0


# =============================================================================
# 메모리 통합 시그널 생성 테스트
# =============================================================================


class TestEnhancedGeminiSignalGeneration:
    """EnhancedGeminiSignalGenerator 시그널 생성 테스트"""

    @pytest.mark.asyncio
    @patch(GENAI_PATCH)
    async def test_get_signal_with_memory(
        self,
        mock_genai,
        mock_context_builder,
        sample_memory_context,
        sample_market_data,
    ):
        """메모리 포함 시그널 생성 테스트"""
        # Mock 설정
        mock_context_builder.build_context = AsyncMock(
            return_value=sample_memory_context
        )

        mock_response = MagicMock()
        mock_response.text = "LONG"
        mock_genai.Client.return_value.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        generator = EnhancedGeminiSignalGenerator(
            api_key="test-api-key",
            context_builder=mock_context_builder,
        )

        signal = await generator.get_signal_with_memory(
            market_data=sample_market_data,
            bot_id="test-bot-id",
        )

        assert signal in ["LONG", "SHORT", "WAIT"]
        # 컨텍스트 빌더 호출 확인
        mock_context_builder.build_context.assert_called_once()

    @pytest.mark.asyncio
    @patch(GENAI_PATCH)
    async def test_get_signal_with_memory_fallback(
        self,
        mock_genai,
        mock_context_builder,
        sample_market_data,
    ):
        """메모리 생성 실패 시 fallback 테스트"""
        # 메모리 컨텍스트 생성 실패
        mock_context_builder.build_context = AsyncMock(
            return_value=MemoryContext.empty()
        )

        mock_response = MagicMock()
        mock_response.text = "WAIT"
        mock_genai.Client.return_value.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        generator = EnhancedGeminiSignalGenerator(
            api_key="test-api-key",
            context_builder=mock_context_builder,
        )

        signal = await generator.get_signal_with_memory(
            market_data=sample_market_data,
            bot_id="test-bot-id",
        )

        # 메모리 없이도 시그널 생성
        assert signal in ["LONG", "SHORT", "WAIT"]

    @pytest.mark.asyncio
    @patch(GENAI_PATCH)
    async def test_get_signal_without_memory(
        self,
        mock_genai,
        sample_market_data,
    ):
        """메모리 없이 시그널 생성 테스트"""
        mock_response = MagicMock()
        mock_response.text = "SHORT"
        mock_genai.Client.return_value.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        generator = EnhancedGeminiSignalGenerator(
            api_key="test-api-key",
            context_builder=None,  # 메모리 비활성화
        )

        signal = await generator.get_signal_with_memory(
            market_data=sample_market_data,
            bot_id="test-bot-id",
        )

        assert signal in ["LONG", "SHORT", "WAIT"]

    @pytest.mark.asyncio
    @patch(GENAI_PATCH)
    async def test_get_signal_api_error_returns_wait(
        self,
        mock_genai,
        mock_context_builder,
        sample_memory_context,
        sample_market_data,
    ):
        """API 에러 시 WAIT 반환 테스트"""
        mock_context_builder.build_context = AsyncMock(
            return_value=sample_memory_context
        )
        mock_genai.Client.return_value.aio.models.generate_content = AsyncMock(
            side_effect=Exception("API Error")
        )

        generator = EnhancedGeminiSignalGenerator(
            api_key="test-api-key",
            context_builder=mock_context_builder,
        )

        signal = await generator.get_signal_with_memory(
            market_data=sample_market_data,
            bot_id="test-bot-id",
        )

        assert signal == "WAIT"


# =============================================================================
# 프롬프트 빌드 테스트
# =============================================================================


class TestEnhancedGeminiPromptBuilding:
    """EnhancedGeminiSignalGenerator 프롬프트 빌드 테스트"""

    @patch(GENAI_PATCH)
    def test_build_prompt_with_memory(
        self,
        mock_genai,
        mock_context_builder,
        sample_memory_context,
        sample_market_data,
    ):
        """메모리 포함 프롬프트 빌드 테스트"""
        generator = EnhancedGeminiSignalGenerator(
            api_key="test-api-key",
            context_builder=mock_context_builder,
        )

        prompt = generator._build_prompt_with_memory(
            market_data=sample_market_data,
            memory_context=sample_memory_context,
        )

        # 메모리 컨텍스트 포함 확인
        assert "[과거 거래 기록 기반 학습 데이터]" in prompt
        assert "7일간: 42거래" in prompt
        assert "승률 68%" in prompt

        # 시장 데이터 포함 확인
        assert "Current Price" in prompt or "current_price" in prompt.lower()

    @patch(GENAI_PATCH)
    def test_build_prompt_without_memory(
        self,
        mock_genai,
        sample_market_data,
    ):
        """메모리 없이 프롬프트 빌드 테스트"""
        generator = EnhancedGeminiSignalGenerator(
            api_key="test-api-key",
            context_builder=None,
        )

        prompt = generator._build_prompt_with_memory(
            market_data=sample_market_data,
            memory_context=None,
        )

        # 메모리 컨텍스트 미포함
        assert "[과거 거래 기록 기반 학습 데이터]" not in prompt

        # 시장 데이터는 포함
        assert len(prompt) > 0

    @patch(GENAI_PATCH)
    def test_build_prompt_empty_memory(
        self,
        mock_genai,
        sample_market_data,
    ):
        """빈 메모리로 프롬프트 빌드 테스트"""
        generator = EnhancedGeminiSignalGenerator(
            api_key="test-api-key",
            context_builder=None,
        )

        empty_context = MemoryContext.empty()
        prompt = generator._build_prompt_with_memory(
            market_data=sample_market_data,
            memory_context=empty_context,
        )

        # 빈 메모리는 포함하지 않음
        assert "[과거 거래 기록 기반 학습 데이터]" not in prompt


# =============================================================================
# 메모리 시스템 프롬프트 테스트
# =============================================================================


class TestMemorySystemPrompt:
    """메모리 시스템 프롬프트 테스트"""

    @patch(GENAI_PATCH)
    def test_memory_system_prompt_content(self, mock_genai, mock_context_builder):
        """메모리 시스템 프롬프트 내용 테스트"""
        generator = EnhancedGeminiSignalGenerator(
            api_key="test-api-key",
            context_builder=mock_context_builder,
        )

        prompt = generator.memory_system_prompt

        # 핵심 지시사항 포함 확인
        assert "memory" in prompt.lower() or "기억" in prompt
        assert "past" in prompt.lower() or "과거" in prompt


# =============================================================================
# 기존 GeminiSignalGenerator 호환성 테스트
# =============================================================================


class TestEnhancedGeminiBackwardsCompatibility:
    """기존 GeminiSignalGenerator와의 호환성 테스트"""

    @pytest.mark.asyncio
    @patch(GENAI_PATCH)
    async def test_get_signal_compatibility(
        self,
        mock_genai,
        sample_market_data,
    ):
        """기존 get_signal 메서드 호환성 테스트"""
        mock_response = MagicMock()
        mock_response.text = "LONG"
        mock_genai.Client.return_value.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        generator = EnhancedGeminiSignalGenerator(
            api_key="test-api-key",
        )

        # 기존 get_signal 메서드 사용 가능
        signal = await generator.get_signal(sample_market_data)
        assert signal in ["LONG", "SHORT", "WAIT"]

    @patch(GENAI_PATCH)
    def test_inherits_from_gemini_signal_generator(self, mock_genai):
        """GeminiSignalGenerator 상속 확인"""
        from src.ai.gemini import GeminiSignalGenerator

        generator = EnhancedGeminiSignalGenerator(
            api_key="test-api-key",
        )

        assert isinstance(generator, GeminiSignalGenerator)


# =============================================================================
# 설정 옵션 테스트
# =============================================================================


class TestEnhancedGeminiConfiguration:
    """EnhancedGeminiSignalGenerator 설정 테스트"""

    @patch(GENAI_PATCH)
    def test_disable_memory(self, mock_genai, mock_context_builder):
        """메모리 비활성화 테스트"""
        generator = EnhancedGeminiSignalGenerator(
            api_key="test-api-key",
            context_builder=mock_context_builder,
            memory_enabled=False,
        )

        assert generator.memory_enabled is False

    @patch(GENAI_PATCH)
    def test_custom_memory_days(self, mock_genai, mock_context_builder):
        """커스텀 메모리 분석 기간 테스트"""
        generator = EnhancedGeminiSignalGenerator(
            api_key="test-api-key",
            context_builder=mock_context_builder,
            memory_days=14,
        )

        assert generator.memory_days == 14

    @patch(GENAI_PATCH)
    def test_set_context_builder(self, mock_genai, mock_context_builder):
        """컨텍스트 빌더 동적 설정 테스트"""
        generator = EnhancedGeminiSignalGenerator(
            api_key="test-api-key",
        )

        assert generator.context_builder is None

        generator.set_context_builder(mock_context_builder)
        assert generator.context_builder == mock_context_builder
        assert generator.memory_enabled is True


# =============================================================================
# 에러 처리 테스트
# =============================================================================


class TestEnhancedGeminiErrorHandling:
    """EnhancedGeminiSignalGenerator 에러 처리 테스트"""

    @pytest.mark.asyncio
    @patch(GENAI_PATCH)
    async def test_context_builder_error_graceful_handling(
        self,
        mock_genai,
        mock_context_builder,
        sample_market_data,
    ):
        """컨텍스트 빌더 에러 시 graceful 처리 테스트"""
        mock_context_builder.build_context = AsyncMock(
            side_effect=Exception("Context builder error")
        )

        mock_response = MagicMock()
        mock_response.text = "WAIT"
        mock_genai.Client.return_value.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        generator = EnhancedGeminiSignalGenerator(
            api_key="test-api-key",
            context_builder=mock_context_builder,
        )

        # 에러가 발생해도 시그널 생성 (메모리 없이)
        signal = await generator.get_signal_with_memory(
            market_data=sample_market_data,
            bot_id="test-bot-id",
        )

        assert signal in ["LONG", "SHORT", "WAIT"]

    @pytest.mark.asyncio
    @patch(GENAI_PATCH)
    async def test_invalid_signal_returns_wait(
        self,
        mock_genai,
        sample_market_data,
    ):
        """유효하지 않은 시그널은 WAIT 반환 테스트"""
        mock_response = MagicMock()
        mock_response.text = "INVALID_SIGNAL"
        mock_genai.Client.return_value.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        generator = EnhancedGeminiSignalGenerator(
            api_key="test-api-key",
        )

        signal = await generator.get_signal_with_memory(
            market_data=sample_market_data,
            bot_id="test-bot-id",
        )

        assert signal == "WAIT"
