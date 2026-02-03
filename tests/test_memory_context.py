"""
AIMemoryContextBuilder 테스트

Phase 4: AI 메모리 시스템 - 메모리 컨텍스트 빌더 테스트
TDD 방식으로 작성
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from src.analytics.memory_context import (
    AIMemoryContextBuilder,
    MemoryContext,
)
from src.analytics.trade_analyzer import (
    TradeHistoryAnalyzer,
    TradingStats,
    RSIConditionStats,
    TimeBasedStats,
    PatternInsight,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_analyzer():
    """모의 TradeHistoryAnalyzer"""
    return MagicMock(spec=TradeHistoryAnalyzer)


@pytest.fixture
def context_builder(mock_analyzer):
    """AIMemoryContextBuilder 인스턴스"""
    return AIMemoryContextBuilder(mock_analyzer)


@pytest.fixture
def sample_stats():
    """샘플 거래 통계"""
    return TradingStats(
        total_trades=42,
        winning_trades=28,
        losing_trades=14,
        win_rate=66.67,
        total_pnl=125.50,
        avg_pnl=2.99,
        avg_win=7.50,
        avg_loss=-6.25,
        profit_factor=1.68,
        avg_duration_minutes=45.0,
        best_trade_pnl=35.00,
        worst_trade_pnl=-18.50,
        long_trades=25,
        short_trades=17,
        long_win_rate=72.0,
        short_win_rate=58.82,
    )


@pytest.fixture
def sample_rsi_stats():
    """샘플 RSI 조건별 통계"""
    return [
        RSIConditionStats(
            rsi_zone="oversold",
            side="LONG",
            total_trades=12,
            winning_trades=10,
            losing_trades=2,
            win_rate=83.33,
            avg_pnl=8.50,
            total_pnl=102.00,
            avg_duration_minutes=35.0,
        ),
        RSIConditionStats(
            rsi_zone="neutral",
            side="LONG",
            total_trades=15,
            winning_trades=6,
            losing_trades=9,
            win_rate=40.0,
            avg_pnl=-2.50,
            total_pnl=-37.50,
            avg_duration_minutes=55.0,
        ),
    ]


@pytest.fixture
def sample_hourly_stats():
    """샘플 시간대별 통계"""
    return [
        TimeBasedStats(
            hour_of_day=14,
            side="LONG",
            total_trades=8,
            winning_trades=7,
            losing_trades=1,
            win_rate=87.5,
            avg_pnl=12.00,
            total_pnl=96.00,
        ),
        TimeBasedStats(
            hour_of_day=3,
            side="LONG",
            total_trades=5,
            winning_trades=1,
            losing_trades=4,
            win_rate=20.0,
            avg_pnl=-8.00,
            total_pnl=-40.00,
        ),
    ]


@pytest.fixture
def sample_streak():
    """샘플 연승 데이터"""
    return {
        "streak_type": "WIN",
        "streak_count": 3,
        "last_trade_time": datetime.now(),
    }


@pytest.fixture
def sample_recent_summary():
    """샘플 최근 거래 요약"""
    return {
        "trades": [
            {"pnl": 10.0, "side": "LONG"},
            {"pnl": -5.0, "side": "LONG"},
            {"pnl": 8.0, "side": "SHORT"},
        ],
        "summary": {
            "count": 3,
            "winners": 2,
            "losers": 1,
            "total_pnl": 13.0,
        },
    }


# =============================================================================
# MemoryContext 데이터클래스 테스트
# =============================================================================


class TestMemoryContext:
    """MemoryContext 데이터클래스 테스트"""

    def test_memory_context_creation(self):
        """MemoryContext 생성 테스트"""
        context = MemoryContext(
            overall_summary="7일간: 42거래, 승률 68%, +$125",
            recent_performance="최근 10개: 7승 3패, 연속 3승 중",
            best_conditions="LONG 최적: RSI<35 (승률 85%)",
            worst_conditions="피해야 할: RSI 40-60에서 LONG",
            timing_insights="최적 시간: 14-16시",
            recommendations="추천 RSI: LONG < 35",
        )
        assert "42거래" in context.overall_summary
        assert "연속 3승" in context.recent_performance

    def test_memory_context_empty(self):
        """빈 MemoryContext 테스트"""
        context = MemoryContext.empty()
        assert context.overall_summary == ""
        assert context.recent_performance == ""

    def test_memory_context_to_prompt(self):
        """MemoryContext 프롬프트 변환 테스트"""
        context = MemoryContext(
            overall_summary="7일간: 42거래, 승률 68%, +$125",
            recent_performance="최근 10개: 7승 3패, 연속 3승 중",
            best_conditions="LONG 최적: RSI<35 (승률 85%)",
            worst_conditions="피해야 할: RSI 40-60에서 LONG",
            timing_insights="최적 시간: 14-16시",
            recommendations="추천 RSI: LONG < 35",
        )
        prompt = context.to_prompt()

        # 프롬프트에 모든 섹션 포함 확인
        assert "[과거 거래 기록 기반 학습 데이터]" in prompt
        assert "7일간: 42거래" in prompt
        assert "최근 10개: 7승 3패" in prompt
        assert "LONG 최적" in prompt
        assert "피해야 할" in prompt
        assert "최적 시간" in prompt

    def test_memory_context_to_dict(self):
        """MemoryContext dict 변환 테스트"""
        context = MemoryContext(
            overall_summary="요약",
            recent_performance="최근",
            best_conditions="최적",
            worst_conditions="피해야 할",
            timing_insights="타이밍",
            recommendations="추천",
        )
        result = context.to_dict()
        assert isinstance(result, dict)
        assert result["overall_summary"] == "요약"


# =============================================================================
# AIMemoryContextBuilder 테스트
# =============================================================================


class TestAIMemoryContextBuilder:
    """AIMemoryContextBuilder 테스트"""

    def test_builder_initialization(self, mock_analyzer):
        """빌더 초기화 테스트"""
        builder = AIMemoryContextBuilder(mock_analyzer)
        assert builder.analyzer == mock_analyzer

    @pytest.mark.asyncio
    async def test_build_context_with_data(
        self,
        context_builder,
        mock_analyzer,
        sample_stats,
        sample_rsi_stats,
        sample_hourly_stats,
        sample_streak,
        sample_recent_summary,
    ):
        """데이터가 있을 때 컨텍스트 생성 테스트"""
        # Mock 설정
        mock_analyzer.get_overall_stats = AsyncMock(return_value=sample_stats)
        mock_analyzer.get_rsi_condition_stats = AsyncMock(return_value=sample_rsi_stats)
        mock_analyzer.get_hourly_stats = AsyncMock(return_value=sample_hourly_stats)
        mock_analyzer.get_current_streak = AsyncMock(return_value=sample_streak)
        mock_analyzer.get_recent_trade_summary = AsyncMock(
            return_value=sample_recent_summary
        )
        mock_analyzer.get_pattern_insights = AsyncMock(return_value=[])
        mock_analyzer.get_worst_patterns = AsyncMock(return_value=[])

        context = await context_builder.build_context()

        # 전체 요약 확인
        assert "42" in context.overall_summary  # total_trades
        assert "66" in context.overall_summary or "67" in context.overall_summary  # win_rate
        assert "$125" in context.overall_summary or "125" in context.overall_summary  # pnl

        # 최근 성과 확인
        assert "2승" in context.recent_performance or "승" in context.recent_performance
        assert "3승" in context.recent_performance  # streak

    @pytest.mark.asyncio
    async def test_build_context_empty_data(self, context_builder, mock_analyzer):
        """데이터 없을 때 컨텍스트 생성 테스트"""
        # 빈 데이터 Mock
        mock_analyzer.get_overall_stats = AsyncMock(return_value=TradingStats.empty())
        mock_analyzer.get_rsi_condition_stats = AsyncMock(return_value=[])
        mock_analyzer.get_hourly_stats = AsyncMock(return_value=[])
        mock_analyzer.get_current_streak = AsyncMock(
            return_value={"streak_type": None, "streak_count": 0}
        )
        mock_analyzer.get_recent_trade_summary = AsyncMock(
            return_value={"trades": [], "summary": {"count": 0}}
        )
        mock_analyzer.get_pattern_insights = AsyncMock(return_value=[])
        mock_analyzer.get_worst_patterns = AsyncMock(return_value=[])

        context = await context_builder.build_context()

        # 빈 컨텍스트 또는 기본 메시지
        assert context is not None
        assert isinstance(context, MemoryContext)

    @pytest.mark.asyncio
    async def test_build_context_with_bot_id(
        self,
        context_builder,
        mock_analyzer,
        sample_stats,
    ):
        """특정 봇 ID로 컨텍스트 생성 테스트"""
        mock_analyzer.get_overall_stats = AsyncMock(return_value=sample_stats)
        mock_analyzer.get_rsi_condition_stats = AsyncMock(return_value=[])
        mock_analyzer.get_hourly_stats = AsyncMock(return_value=[])
        mock_analyzer.get_current_streak = AsyncMock(
            return_value={"streak_type": "WIN", "streak_count": 2}
        )
        mock_analyzer.get_recent_trade_summary = AsyncMock(
            return_value={"trades": [], "summary": {"count": 0}}
        )
        mock_analyzer.get_pattern_insights = AsyncMock(return_value=[])
        mock_analyzer.get_worst_patterns = AsyncMock(return_value=[])

        await context_builder.build_context(bot_id="test-bot-id")

        # bot_id가 분석기에 전달되었는지 확인
        mock_analyzer.get_overall_stats.assert_called_once()
        call_kwargs = mock_analyzer.get_overall_stats.call_args
        assert call_kwargs[1].get("bot_id") == "test-bot-id"

    @pytest.mark.asyncio
    async def test_build_overall_summary(
        self, context_builder, mock_analyzer, sample_stats
    ):
        """전체 요약 생성 테스트"""
        summary = context_builder._build_overall_summary(sample_stats, days=7)

        assert "7일간" in summary
        assert "42거래" in summary
        assert "$125" in summary or "125" in summary

    @pytest.mark.asyncio
    async def test_build_recent_performance(
        self, context_builder, sample_recent_summary, sample_streak
    ):
        """최근 성과 생성 테스트"""
        performance = context_builder._build_recent_performance(
            sample_recent_summary, sample_streak
        )

        assert "최근" in performance
        assert "2승" in performance
        assert "1패" in performance
        assert "연속 3승" in performance

    @pytest.mark.asyncio
    async def test_build_best_conditions(
        self, context_builder, sample_rsi_stats, sample_hourly_stats
    ):
        """최적 조건 생성 테스트"""
        best = context_builder._build_best_conditions(
            sample_rsi_stats, sample_hourly_stats
        )

        # RSI 과매도에서 LONG의 높은 승률
        assert "RSI" in best or "LONG" in best
        assert "83" in best or "87" in best  # win_rate

    @pytest.mark.asyncio
    async def test_build_worst_conditions(
        self, context_builder, sample_rsi_stats, sample_hourly_stats
    ):
        """피해야 할 조건 생성 테스트"""
        worst = context_builder._build_worst_conditions(
            sample_rsi_stats, sample_hourly_stats
        )

        # 낮은 승률 조건
        assert "RSI" in worst or "시" in worst
        assert "40" in worst or "20" in worst  # low win_rate

    @pytest.mark.asyncio
    async def test_build_timing_insights(
        self, context_builder, sample_hourly_stats
    ):
        """타이밍 인사이트 생성 테스트"""
        insights = context_builder._build_timing_insights(sample_hourly_stats)

        assert "시" in insights  # 시간대 언급
        assert "14" in insights or "3" in insights  # 특정 시간

    @pytest.mark.asyncio
    async def test_build_recommendations(
        self, context_builder, sample_rsi_stats, sample_hourly_stats
    ):
        """추천 생성 테스트"""
        recommendations = context_builder._build_recommendations(
            sample_rsi_stats, sample_hourly_stats
        )

        # 추천 내용 확인
        assert len(recommendations) > 0
        assert "RSI" in recommendations or "LONG" in recommendations or "시" in recommendations


# =============================================================================
# 에러 처리 테스트
# =============================================================================


class TestAIMemoryContextBuilderErrors:
    """AIMemoryContextBuilder 에러 처리 테스트"""

    @pytest.mark.asyncio
    async def test_build_context_analyzer_error(self, context_builder, mock_analyzer):
        """분석기 에러 시 처리 테스트"""
        mock_analyzer.get_overall_stats = AsyncMock(
            side_effect=Exception("DB connection failed")
        )

        # 에러가 발생해도 빈 컨텍스트 반환
        context = await context_builder.build_context()
        assert context is not None
        assert isinstance(context, MemoryContext)

    @pytest.mark.asyncio
    async def test_build_context_partial_data(self, context_builder, mock_analyzer):
        """일부 데이터만 있을 때 테스트"""
        mock_analyzer.get_overall_stats = AsyncMock(
            return_value=TradingStats(
                total_trades=5,
                winning_trades=3,
                losing_trades=2,
                win_rate=60.0,
                total_pnl=25.0,
                avg_pnl=5.0,
                avg_win=12.5,
                avg_loss=-7.5,
                profit_factor=1.5,
                avg_duration_minutes=30.0,
                best_trade_pnl=20.0,
                worst_trade_pnl=-10.0,
                long_trades=3,
                short_trades=2,
                long_win_rate=66.67,
                short_win_rate=50.0,
            )
        )
        mock_analyzer.get_rsi_condition_stats = AsyncMock(return_value=[])
        mock_analyzer.get_hourly_stats = AsyncMock(return_value=[])
        mock_analyzer.get_current_streak = AsyncMock(
            return_value={"streak_type": None, "streak_count": 0}
        )
        mock_analyzer.get_recent_trade_summary = AsyncMock(
            return_value={"trades": [], "summary": {"count": 0}}
        )
        mock_analyzer.get_pattern_insights = AsyncMock(return_value=[])
        mock_analyzer.get_worst_patterns = AsyncMock(return_value=[])

        context = await context_builder.build_context()

        # 전체 요약은 있어야 함
        assert "5" in context.overall_summary  # total_trades
        assert "60" in context.overall_summary  # win_rate


# =============================================================================
# 통합 테스트
# =============================================================================


class TestMemoryContextIntegration:
    """MemoryContext 통합 테스트"""

    @pytest.mark.asyncio
    async def test_full_context_flow(
        self,
        context_builder,
        mock_analyzer,
        sample_stats,
        sample_rsi_stats,
        sample_hourly_stats,
        sample_streak,
        sample_recent_summary,
    ):
        """전체 컨텍스트 생성 플로우 테스트"""
        # Mock 설정
        mock_analyzer.get_overall_stats = AsyncMock(return_value=sample_stats)
        mock_analyzer.get_rsi_condition_stats = AsyncMock(return_value=sample_rsi_stats)
        mock_analyzer.get_hourly_stats = AsyncMock(return_value=sample_hourly_stats)
        mock_analyzer.get_current_streak = AsyncMock(return_value=sample_streak)
        mock_analyzer.get_recent_trade_summary = AsyncMock(
            return_value=sample_recent_summary
        )
        mock_analyzer.get_pattern_insights = AsyncMock(return_value=[])
        mock_analyzer.get_worst_patterns = AsyncMock(return_value=[])

        # 컨텍스트 생성
        context = await context_builder.build_context()

        # 프롬프트 변환
        prompt = context.to_prompt()

        # 프롬프트 구조 확인
        assert "[과거 거래 기록 기반 학습 데이터]" in prompt
        assert len(prompt) > 100  # 충분한 내용

    @pytest.mark.asyncio
    async def test_context_with_patterns(
        self,
        context_builder,
        mock_analyzer,
        sample_stats,
        sample_rsi_stats,
    ):
        """패턴 인사이트 포함 컨텍스트 테스트"""
        patterns = [
            PatternInsight(
                pattern_type="rsi_zone",
                description="RSI 30 이하에서 LONG",
                side="LONG",
                condition="rsi_zone=oversold",
                sample_size=15,
                win_rate=85.0,
                avg_pnl=10.0,
                recommendation="RSI 30 이하에서 LONG 진입 권장",
            )
        ]

        mock_analyzer.get_overall_stats = AsyncMock(return_value=sample_stats)
        mock_analyzer.get_rsi_condition_stats = AsyncMock(return_value=sample_rsi_stats)
        mock_analyzer.get_hourly_stats = AsyncMock(return_value=[])
        mock_analyzer.get_current_streak = AsyncMock(
            return_value={"streak_type": "WIN", "streak_count": 2}
        )
        mock_analyzer.get_recent_trade_summary = AsyncMock(
            return_value={"trades": [], "summary": {"count": 0}}
        )
        mock_analyzer.get_pattern_insights = AsyncMock(return_value=patterns)
        mock_analyzer.get_worst_patterns = AsyncMock(return_value=[])

        context = await context_builder.build_context()
        prompt = context.to_prompt()

        # 최적 조건에 RSI 또는 LONG이 포함되어야 함 (rsi_stats에서 생성됨)
        assert "RSI" in prompt or "LONG" in prompt or "83" in prompt  # win_rate
