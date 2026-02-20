"""주간 AI 배치 분석 리포트 테스트.

WS3: generate_weekly_report + _maybe_generate_weekly_report 검증.
"""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.analytics.memory_context import MemoryContext

# =========================================================================
# EnhancedGeminiSignalGenerator.generate_weekly_report 테스트
# =========================================================================


class TestGenerateWeeklyReport:
    """generate_weekly_report 단위 테스트."""

    @pytest.fixture
    def mock_genai(self):
        """google.genai 모킹."""
        with patch("src.ai.gemini.genai") as mock:
            mock_client = MagicMock()
            mock.Client.return_value = mock_client
            yield mock

    @pytest.fixture
    def memory_context(self):
        """비어있지 않은 MemoryContext."""
        return MemoryContext(
            overall_summary="7일간: 20거래, 승률 65%, +$80",
            recent_performance="최근 10개: 7승 3패",
            best_conditions="LONG 최적: RSI<35",
            worst_conditions="피해야 할: RSI 40-60",
            timing_insights="최적 시간: 14-16시",
            recommendations="추천: LONG < 35",
        )

    @pytest.fixture
    def context_builder(self, memory_context):
        """Mock AIMemoryContextBuilder."""
        builder = AsyncMock()
        builder.build_context = AsyncMock(return_value=memory_context)
        return builder

    @pytest.fixture
    def enhanced_gemini(self, mock_genai, context_builder):
        """EnhancedGeminiSignalGenerator 인스턴스."""
        from src.ai.enhanced_gemini import EnhancedGeminiSignalGenerator

        gen = EnhancedGeminiSignalGenerator(
            api_key="test-key",
            context_builder=context_builder,
        )
        return gen

    @pytest.mark.asyncio
    async def test_generate_weekly_report_success(
        self, enhanced_gemini, context_builder
    ):
        """정상 리포트 생성."""
        mock_response = MagicMock()
        mock_response.text = (
            "요약\n"
            "지난 7일간 20거래 중 65% 승률 기록.\n\n"
            "분석\n"
            "- RSI 30 이하에서 LONG 진입 시 승률 85%\n"
            "- Asia 세션에서 손실 집중\n\n"
            "권장\n"
            "- Asia 세션 포지션 사이즈 50% 축소\n"
            "- SL을 0.3%로 타이트닝\n"
        )
        enhanced_gemini.client.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        result = await enhanced_gemini.generate_weekly_report("test-bot")

        assert result["summary"]
        assert len(result["insights"]) >= 1
        assert len(result["recommendations"]) >= 1
        assert result["raw_context"] is not None
        context_builder.build_context.assert_called_once_with(
            bot_id="test-bot", days=7
        )

    @pytest.mark.asyncio
    async def test_generate_weekly_report_empty_history(self, mock_genai):
        """거래 이력 없을 때."""
        from src.ai.enhanced_gemini import EnhancedGeminiSignalGenerator

        empty_ctx = MemoryContext(
            overall_summary="",
            recent_performance="",
            best_conditions="",
            worst_conditions="",
            timing_insights="",
            recommendations="",
        )
        builder = AsyncMock()
        builder.build_context = AsyncMock(return_value=empty_ctx)

        gen = EnhancedGeminiSignalGenerator(
            api_key="test-key",
            context_builder=builder,
        )

        result = await gen.generate_weekly_report("test-bot")

        assert result["summary"] == "거래 이력 없음"
        assert result["insights"] == []
        assert result["recommendations"] == []

    @pytest.mark.asyncio
    async def test_generate_weekly_report_no_context_builder(self, mock_genai):
        """context_builder 미설정."""
        from src.ai.enhanced_gemini import EnhancedGeminiSignalGenerator

        gen = EnhancedGeminiSignalGenerator(
            api_key="test-key",
            context_builder=None,
        )

        result = await gen.generate_weekly_report("test-bot")

        assert result["summary"] == "분석 불가"

    @pytest.mark.asyncio
    async def test_generate_weekly_report_gemini_failure(
        self, enhanced_gemini
    ):
        """Gemini API 호출 실패."""
        enhanced_gemini.client.aio.models.generate_content = AsyncMock(
            side_effect=Exception("API Error")
        )

        result = await enhanced_gemini.generate_weekly_report("test-bot")

        assert result["summary"] == "분석 불가"

    @pytest.mark.asyncio
    async def test_generate_weekly_report_custom_days(
        self, enhanced_gemini, context_builder
    ):
        """커스텀 분석 기간."""
        mock_response = MagicMock()
        mock_response.text = "요약\n14일 분석 완료."
        enhanced_gemini.client.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        await enhanced_gemini.generate_weekly_report("test-bot", days=14)

        context_builder.build_context.assert_called_once_with(
            bot_id="test-bot", days=14
        )


# =========================================================================
# BotInstance._maybe_generate_weekly_report 테스트
# =========================================================================


class TestMaybeGenerateWeeklyReport:
    """_maybe_generate_weekly_report 스케줄링 테스트."""

    @pytest.fixture
    def bot_config(self):
        """테스트용 BotConfig."""
        from src.bot_config import BotConfig

        return BotConfig(
            bot_name="test-bot",
            symbol="BTCUSDT",
            use_weekly_report=True,
        )

    @pytest.fixture
    def bot(self, bot_config):
        """테스트용 BotInstance."""
        from src.bot_instance import BotInstance

        return BotInstance(
            config=bot_config,
            binance_api_key="test",
            binance_secret_key="test",
            binance_client=MagicMock(),
            trade_db=None,
        )

    @pytest.mark.asyncio
    async def test_maybe_generate_sunday_only(self, bot):
        """일요일이 아니면 실행 안 함."""
        bot._enhanced_gemini = MagicMock()

        # 월요일
        with patch(
            "src.bot_instance.datetime"
        ) as mock_dt:
            mock_dt.utcnow.return_value = datetime(2026, 2, 16, 12, 0)  # Monday
            mock_dt.now.return_value = datetime(2026, 2, 16, 12, 0)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            await bot._maybe_generate_weekly_report()

        # enhanced_gemini.generate_weekly_report 호출 안 됨
        assert not hasattr(bot._enhanced_gemini, 'generate_weekly_report') or \
            not bot._enhanced_gemini.generate_weekly_report.called

    @pytest.mark.asyncio
    async def test_maybe_generate_24h_dedup(self, bot):
        """24시간 이내 중복 실행 방지."""
        bot._enhanced_gemini = AsyncMock()
        bot._enhanced_gemini.generate_weekly_report = AsyncMock(
            return_value={
                "summary": "test",
                "insights": [],
                "recommendations": [],
            }
        )

        # 이미 실행된 상태
        bot._last_weekly_report = datetime(2026, 2, 22, 10, 0)

        with patch(
            "src.bot_instance.datetime"
        ) as mock_dt:
            # 같은 일요일 20시 (10시간 후)
            mock_dt.utcnow.return_value = datetime(2026, 2, 22, 20, 0)  # Sunday
            mock_dt.now.return_value = datetime(2026, 2, 22, 20, 0)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            await bot._maybe_generate_weekly_report()

        bot._enhanced_gemini.generate_weekly_report.assert_not_called()

    @pytest.mark.asyncio
    async def test_maybe_generate_feature_flag_off(self, bot):
        """feature flag OFF → 실행 안 함."""
        bot.config.use_weekly_report = False
        bot._enhanced_gemini = AsyncMock()
        bot._enhanced_gemini.generate_weekly_report = AsyncMock()

        await bot._maybe_generate_weekly_report()

        bot._enhanced_gemini.generate_weekly_report.assert_not_called()

    @pytest.mark.asyncio
    async def test_maybe_generate_no_enhanced_gemini(self, bot):
        """enhanced_gemini 미설정 → 실행 안 함."""
        bot._enhanced_gemini = None

        # 에러 없이 종료
        await bot._maybe_generate_weekly_report()

    @pytest.mark.asyncio
    async def test_maybe_generate_success_on_sunday(self, bot):
        """일요일 정상 실행 + _last_weekly_report 갱신."""
        mock_gemini = AsyncMock()
        mock_gemini.generate_weekly_report = AsyncMock(
            return_value={
                "summary": "좋은 한 주",
                "insights": ["RSI 전략 효과적"],
                "recommendations": ["SL 타이트닝"],
            }
        )
        bot._enhanced_gemini = mock_gemini
        bot._on_signal_callback = None  # 콜백 없음

        with patch(
            "src.bot_instance.datetime"
        ) as mock_dt:
            mock_dt.utcnow.return_value = datetime(2026, 2, 22, 12, 0)  # Sunday
            mock_dt.now.return_value = datetime(2026, 2, 22, 12, 0)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

            await bot._maybe_generate_weekly_report()

        mock_gemini.generate_weekly_report.assert_called_once()
        call_kwargs = mock_gemini.generate_weekly_report.call_args
        assert call_kwargs.kwargs["days"] == 7
        assert bot._last_weekly_report is not None


# =========================================================================
# _parse_weekly_report 테스트
# =========================================================================


class TestParseWeeklyReport:
    """_parse_weekly_report 파싱 테스트."""

    def test_parse_structured_report(self):
        """구조화된 응답 파싱."""
        from src.ai.enhanced_gemini import EnhancedGeminiSignalGenerator

        raw = (
            "요약\n"
            "좋은 성과를 보였습니다.\n\n"
            "분석\n"
            "- RSI 전략이 효과적\n"
            "- Asia 세션 약세\n\n"
            "권장\n"
            "- SL 타이트닝\n"
            "- Asia 세션 축소\n"
        )
        ctx = MemoryContext(
            overall_summary="test",
            recent_performance="",
            best_conditions="",
            worst_conditions="",
            timing_insights="",
            recommendations="",
        )

        result = EnhancedGeminiSignalGenerator._parse_weekly_report(raw, ctx)

        assert "좋은 성과" in result["summary"]
        assert len(result["insights"]) == 2
        assert len(result["recommendations"]) == 2
        assert result["raw_context"] is ctx

    def test_parse_unstructured_report(self):
        """비구조화 응답 → summary에 전체 텍스트."""
        from src.ai.enhanced_gemini import EnhancedGeminiSignalGenerator

        raw = "This is just a plain text response without sections."
        ctx = MemoryContext(
            overall_summary="test",
            recent_performance="",
            best_conditions="",
            worst_conditions="",
            timing_insights="",
            recommendations="",
        )

        result = EnhancedGeminiSignalGenerator._parse_weekly_report(raw, ctx)

        assert "plain text" in result["summary"]
