"""
TradeHistoryAnalyzer 테스트

Phase 4: AI 메모리 시스템 - 거래 이력 분석기 테스트
TDD 방식으로 작성
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from src.analytics.trade_analyzer import (
    TradeHistoryAnalyzer,
    TradingStats,
    ExitReasonStats,
    RSIConditionStats,
    TimeBasedStats,
    PatternInsight,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_db():
    """모의 PostgreSQL 연결"""
    mock = MagicMock()
    mock.pool = MagicMock()
    return mock


@pytest.fixture
def analyzer(mock_db):
    """TradeHistoryAnalyzer 인스턴스"""
    return TradeHistoryAnalyzer(mock_db)


@pytest.fixture
def sample_trades():
    """샘플 거래 데이터"""
    return [
        {
            "id": "trade-1",
            "side": "LONG",
            "entry_price": Decimal("100000"),
            "exit_price": Decimal("100500"),
            "pnl": Decimal("50"),
            "pnl_pct": Decimal("0.5"),
            "exit_reason": "TP",
            "entry_time": datetime.now() - timedelta(hours=2),
            "exit_time": datetime.now() - timedelta(hours=1),
            "duration_minutes": 60,
        },
        {
            "id": "trade-2",
            "side": "LONG",
            "entry_price": Decimal("100500"),
            "exit_price": Decimal("100200"),
            "pnl": Decimal("-30"),
            "pnl_pct": Decimal("-0.3"),
            "exit_reason": "SL",
            "entry_time": datetime.now() - timedelta(hours=4),
            "exit_time": datetime.now() - timedelta(hours=3),
            "duration_minutes": 60,
        },
        {
            "id": "trade-3",
            "side": "SHORT",
            "entry_price": Decimal("100200"),
            "exit_price": Decimal("99800"),
            "pnl": Decimal("40"),
            "pnl_pct": Decimal("0.4"),
            "exit_reason": "TP",
            "entry_time": datetime.now() - timedelta(hours=6),
            "exit_time": datetime.now() - timedelta(hours=5),
            "duration_minutes": 60,
        },
    ]


# =============================================================================
# TradingStats 데이터클래스 테스트
# =============================================================================


class TestTradingStats:
    """TradingStats 데이터클래스 테스트"""

    def test_trading_stats_creation(self):
        """TradingStats 생성 테스트"""
        stats = TradingStats(
            total_trades=10,
            winning_trades=7,
            losing_trades=3,
            win_rate=70.0,
            total_pnl=150.0,
            avg_pnl=15.0,
            avg_win=30.0,
            avg_loss=-15.0,
            profit_factor=2.0,
            avg_duration_minutes=45.0,
            best_trade_pnl=100.0,
            worst_trade_pnl=-50.0,
            long_trades=6,
            short_trades=4,
            long_win_rate=66.67,
            short_win_rate=75.0,
        )
        assert stats.total_trades == 10
        assert stats.win_rate == 70.0
        assert stats.profit_factor == 2.0

    def test_trading_stats_empty(self):
        """빈 TradingStats 테스트"""
        stats = TradingStats.empty()
        assert stats.total_trades == 0
        assert stats.win_rate == 0.0
        assert stats.profit_factor == 0.0

    def test_trading_stats_to_dict(self):
        """TradingStats dict 변환 테스트"""
        stats = TradingStats(
            total_trades=5,
            winning_trades=3,
            losing_trades=2,
            win_rate=60.0,
            total_pnl=50.0,
            avg_pnl=10.0,
            avg_win=25.0,
            avg_loss=-12.5,
            profit_factor=1.6,
            avg_duration_minutes=30.0,
            best_trade_pnl=40.0,
            worst_trade_pnl=-20.0,
            long_trades=3,
            short_trades=2,
            long_win_rate=66.67,
            short_win_rate=50.0,
        )
        result = stats.to_dict()
        assert isinstance(result, dict)
        assert result["total_trades"] == 5
        assert result["win_rate"] == 60.0


# =============================================================================
# ExitReasonStats 데이터클래스 테스트
# =============================================================================


class TestExitReasonStats:
    """ExitReasonStats 데이터클래스 테스트"""

    def test_exit_reason_stats_creation(self):
        """ExitReasonStats 생성 테스트"""
        stats = ExitReasonStats(
            exit_reason="TP",
            side="LONG",
            total_trades=10,
            winning_trades=10,
            win_rate=100.0,
            avg_pnl=25.0,
            total_pnl=250.0,
            avg_duration_minutes=30.0,
        )
        assert stats.exit_reason == "TP"
        assert stats.win_rate == 100.0


# =============================================================================
# RSIConditionStats 데이터클래스 테스트
# =============================================================================


class TestRSIConditionStats:
    """RSIConditionStats 데이터클래스 테스트"""

    def test_rsi_condition_stats_creation(self):
        """RSIConditionStats 생성 테스트"""
        stats = RSIConditionStats(
            rsi_zone="oversold",
            side="LONG",
            total_trades=15,
            winning_trades=12,
            losing_trades=3,
            win_rate=80.0,
            avg_pnl=20.0,
            total_pnl=300.0,
            avg_duration_minutes=45.0,
        )
        assert stats.rsi_zone == "oversold"
        assert stats.win_rate == 80.0


# =============================================================================
# TimeBasedStats 데이터클래스 테스트
# =============================================================================


class TestTimeBasedStats:
    """TimeBasedStats 데이터클래스 테스트"""

    def test_time_based_stats_creation(self):
        """TimeBasedStats 생성 테스트"""
        stats = TimeBasedStats(
            hour_of_day=14,
            side="LONG",
            total_trades=8,
            winning_trades=6,
            losing_trades=2,
            win_rate=75.0,
            avg_pnl=15.0,
            total_pnl=120.0,
        )
        assert stats.hour_of_day == 14
        assert stats.win_rate == 75.0


# =============================================================================
# PatternInsight 데이터클래스 테스트
# =============================================================================


class TestPatternInsight:
    """PatternInsight 데이터클래스 테스트"""

    def test_pattern_insight_creation(self):
        """PatternInsight 생성 테스트"""
        insight = PatternInsight(
            pattern_type="rsi_zone",
            description="RSI < 30에서 LONG 진입",
            side="LONG",
            condition="rsi_zone=oversold",
            sample_size=20,
            win_rate=85.0,
            avg_pnl=25.0,
            recommendation="RSI 30 이하에서 LONG 진입 권장",
        )
        assert insight.pattern_type == "rsi_zone"
        assert insight.win_rate == 85.0

    def test_pattern_insight_to_dict(self):
        """PatternInsight dict 변환 테스트"""
        insight = PatternInsight(
            pattern_type="hourly",
            description="14시-16시 LONG 성과 우수",
            side="LONG",
            condition="hour=14-16",
            sample_size=15,
            win_rate=80.0,
            avg_pnl=20.0,
            recommendation="14-16시에 LONG 진입 권장",
        )
        result = insight.to_dict()
        assert isinstance(result, dict)
        assert result["win_rate"] == 80.0


# =============================================================================
# TradeHistoryAnalyzer 테스트
# =============================================================================


class TestTradeHistoryAnalyzer:
    """TradeHistoryAnalyzer 테스트"""

    def test_analyzer_initialization(self, mock_db):
        """분석기 초기화 테스트"""
        analyzer = TradeHistoryAnalyzer(mock_db)
        assert analyzer.db == mock_db

    @pytest.mark.asyncio
    async def test_get_overall_stats_empty(self, analyzer, mock_db):
        """거래 없을 때 전체 통계 테스트"""
        # Mock 설정
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_db.pool.acquire = MagicMock(return_value=AsyncMock())
        mock_db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await analyzer.get_overall_stats()
        assert result.total_trades == 0
        assert result.win_rate == 0.0

    @pytest.mark.asyncio
    async def test_get_overall_stats_with_data(self, analyzer, mock_db):
        """거래 있을 때 전체 통계 테스트"""
        # Mock 결과
        mock_result = {
            "total_trades": 10,
            "winning_trades": 7,
            "losing_trades": 3,
            "win_rate": Decimal("70.00"),
            "total_pnl": Decimal("150.00"),
            "avg_pnl": Decimal("15.00"),
            "avg_win": Decimal("30.00"),
            "avg_loss": Decimal("-15.00"),
            "profit_factor": Decimal("2.00"),
            "avg_duration_minutes": Decimal("45.00"),
            "best_trade_pnl": Decimal("100.00"),
            "worst_trade_pnl": Decimal("-50.00"),
            "long_trades": 6,
            "short_trades": 4,
            "long_win_rate": Decimal("66.67"),
            "short_win_rate": Decimal("75.00"),
        }

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=mock_result)
        mock_db.pool.acquire = MagicMock(return_value=AsyncMock())
        mock_db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await analyzer.get_overall_stats()
        assert result.total_trades == 10
        assert result.win_rate == 70.0
        assert result.profit_factor == 2.0

    @pytest.mark.asyncio
    async def test_get_overall_stats_with_bot_id(self, analyzer, mock_db):
        """특정 봇 ID로 전체 통계 조회 테스트"""
        mock_result = {
            "total_trades": 5,
            "winning_trades": 3,
            "losing_trades": 2,
            "win_rate": Decimal("60.00"),
            "total_pnl": Decimal("50.00"),
            "avg_pnl": Decimal("10.00"),
            "avg_win": Decimal("25.00"),
            "avg_loss": Decimal("-12.50"),
            "profit_factor": Decimal("1.60"),
            "avg_duration_minutes": Decimal("30.00"),
            "best_trade_pnl": Decimal("40.00"),
            "worst_trade_pnl": Decimal("-20.00"),
            "long_trades": 3,
            "short_trades": 2,
            "long_win_rate": Decimal("66.67"),
            "short_win_rate": Decimal("50.00"),
        }

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=mock_result)
        mock_db.pool.acquire = MagicMock(return_value=AsyncMock())
        mock_db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await analyzer.get_overall_stats(
            bot_id="test-bot-id",
            days=7,
        )
        assert result.total_trades == 5
        # fetchrow 호출 시 bot_id 파라미터 전달 확인
        mock_conn.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_exit_reason_stats(self, analyzer, mock_db):
        """청산 사유별 통계 테스트"""
        mock_results = [
            {
                "exit_reason": "TP",
                "side": "LONG",
                "total_trades": 10,
                "winning_trades": 10,
                "win_rate": Decimal("100.00"),
                "avg_pnl": Decimal("25.00"),
                "total_pnl": Decimal("250.00"),
                "avg_duration_minutes": Decimal("30.00"),
            },
            {
                "exit_reason": "SL",
                "side": "LONG",
                "total_trades": 5,
                "winning_trades": 0,
                "win_rate": Decimal("0.00"),
                "avg_pnl": Decimal("-20.00"),
                "total_pnl": Decimal("-100.00"),
                "avg_duration_minutes": Decimal("45.00"),
            },
        ]

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=mock_results)
        mock_db.pool.acquire = MagicMock(return_value=AsyncMock())
        mock_db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await analyzer.get_exit_reason_stats()
        assert len(result) == 2
        assert result[0].exit_reason == "TP"
        assert result[0].win_rate == 100.0

    @pytest.mark.asyncio
    async def test_get_rsi_condition_stats(self, analyzer, mock_db):
        """RSI 조건별 통계 테스트"""
        mock_results = [
            {
                "rsi_zone": "oversold",
                "side": "LONG",
                "total_trades": 15,
                "winning_trades": 12,
                "losing_trades": 3,
                "win_rate": Decimal("80.00"),
                "avg_pnl": Decimal("20.00"),
                "total_pnl": Decimal("300.00"),
                "avg_duration_minutes": Decimal("45.00"),
            },
            {
                "rsi_zone": "neutral",
                "side": "LONG",
                "total_trades": 10,
                "winning_trades": 4,
                "losing_trades": 6,
                "win_rate": Decimal("40.00"),
                "avg_pnl": Decimal("-5.00"),
                "total_pnl": Decimal("-50.00"),
                "avg_duration_minutes": Decimal("60.00"),
            },
        ]

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=mock_results)
        mock_db.pool.acquire = MagicMock(return_value=AsyncMock())
        mock_db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await analyzer.get_rsi_condition_stats()
        assert len(result) == 2
        assert result[0].rsi_zone == "oversold"
        assert result[0].win_rate == 80.0

    @pytest.mark.asyncio
    async def test_get_hourly_stats(self, analyzer, mock_db):
        """시간대별 통계 테스트"""
        mock_results = [
            {
                "hour_of_day": 14,
                "side": "LONG",
                "total_trades": 8,
                "winning_trades": 6,
                "losing_trades": 2,
                "win_rate": Decimal("75.00"),
                "avg_pnl": Decimal("15.00"),
                "total_pnl": Decimal("120.00"),
            },
            {
                "hour_of_day": 3,
                "side": "LONG",
                "total_trades": 5,
                "winning_trades": 1,
                "losing_trades": 4,
                "win_rate": Decimal("20.00"),
                "avg_pnl": Decimal("-10.00"),
                "total_pnl": Decimal("-50.00"),
            },
        ]

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=mock_results)
        mock_db.pool.acquire = MagicMock(return_value=AsyncMock())
        mock_db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await analyzer.get_hourly_stats()
        assert len(result) == 2
        assert result[0].hour_of_day == 14
        assert result[0].win_rate == 75.0

    @pytest.mark.asyncio
    async def test_get_recent_trade_summary(self, analyzer, mock_db, sample_trades):
        """최근 거래 요약 테스트"""
        # get_recent_trades는 TradeHistoryDB의 메서드이므로 직접 모킹
        mock_db.get_recent_trades = AsyncMock(return_value=sample_trades)

        result = await analyzer.get_recent_trade_summary(limit=10)
        assert "trades" in result
        assert "summary" in result
        assert len(result["trades"]) == 3

    @pytest.mark.asyncio
    async def test_get_current_streak_winning(self, analyzer, mock_db):
        """현재 연승 계산 테스트"""
        mock_result = {
            "streak_type": "WIN",
            "streak_count": 5,
            "last_trade_time": datetime.now(),
        }

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=mock_result)
        mock_db.pool.acquire = MagicMock(return_value=AsyncMock())
        mock_db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await analyzer.get_current_streak()
        assert result["streak_type"] == "WIN"
        assert result["streak_count"] == 5

    @pytest.mark.asyncio
    async def test_get_current_streak_losing(self, analyzer, mock_db):
        """현재 연패 계산 테스트"""
        mock_result = {
            "streak_type": "LOSS",
            "streak_count": 3,
            "last_trade_time": datetime.now(),
        }

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=mock_result)
        mock_db.pool.acquire = MagicMock(return_value=AsyncMock())
        mock_db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await analyzer.get_current_streak()
        assert result["streak_type"] == "LOSS"
        assert result["streak_count"] == 3

    @pytest.mark.asyncio
    async def test_get_pattern_insights(self, analyzer, mock_db):
        """패턴 인사이트 생성 테스트"""
        # RSI 조건 결과
        rsi_results = [
            {
                "rsi_zone": "oversold",
                "side": "LONG",
                "total_trades": 15,
                "winning_trades": 13,
                "losing_trades": 2,
                "win_rate": Decimal("86.67"),
                "avg_pnl": Decimal("25.00"),
                "total_pnl": Decimal("375.00"),
                "avg_duration_minutes": Decimal("40.00"),
            },
        ]

        # 시간대 결과
        hourly_results = [
            {
                "hour_of_day": 15,
                "side": "LONG",
                "total_trades": 10,
                "winning_trades": 8,
                "losing_trades": 2,
                "win_rate": Decimal("80.00"),
                "avg_pnl": Decimal("20.00"),
                "total_pnl": Decimal("200.00"),
            },
        ]

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(side_effect=[rsi_results, hourly_results])
        mock_db.pool.acquire = MagicMock(return_value=AsyncMock())
        mock_db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await analyzer.get_pattern_insights(min_sample_size=5)
        assert isinstance(result, list)
        # 높은 승률 패턴이 포함되어야 함
        for insight in result:
            assert insight.win_rate >= 70.0  # 기본 임계값

    @pytest.mark.asyncio
    async def test_get_pattern_insights_with_threshold(self, analyzer, mock_db):
        """커스텀 임계값으로 패턴 인사이트 생성 테스트"""
        rsi_results = []
        hourly_results = []

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(side_effect=[rsi_results, hourly_results])
        mock_db.pool.acquire = MagicMock(return_value=AsyncMock())
        mock_db.pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_db.pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await analyzer.get_pattern_insights(
            min_sample_size=10,
            min_win_rate=80.0,
        )
        assert isinstance(result, list)


# =============================================================================
# 에러 처리 테스트
# =============================================================================


class TestTradeHistoryAnalyzerErrors:
    """TradeHistoryAnalyzer 에러 처리 테스트"""

    @pytest.mark.asyncio
    async def test_get_overall_stats_db_error(self, analyzer, mock_db):
        """DB 에러 시 처리 테스트"""
        mock_db.pool = None

        with pytest.raises(RuntimeError, match="Database pool not initialized"):
            await analyzer.get_overall_stats()

    @pytest.mark.asyncio
    async def test_get_exit_reason_stats_db_error(self, analyzer, mock_db):
        """청산 사유 통계 DB 에러 테스트"""
        mock_db.pool = None

        with pytest.raises(RuntimeError, match="Database pool not initialized"):
            await analyzer.get_exit_reason_stats()
