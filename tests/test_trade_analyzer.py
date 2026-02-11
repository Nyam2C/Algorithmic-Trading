"""
TradeHistoryAnalyzer 테스트

Phase 4: AI 메모리 시스템 - 거래 이력 분석기 테스트
TDD 방식으로 작성
"""
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.analytics.trade_analyzer import (
    ExitReasonStats,
    PatternInsight,
    RSIConditionStats,
    StatisticalInsight,
    TimeBasedStats,
    TradeHistoryAnalyzer,
    TradingStats,
    _normal_cdf,
    calculate_confidence_interval,
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


# =============================================================================
# Coverage tests merged from test_analytics_coverage.py
# =============================================================================


class TestTradeAnalyzerEdgeCases:
    """TradeHistoryAnalyzer 추가 테스트"""

    @pytest.fixture
    def mock_db(self):
        mock = MagicMock()
        mock.pool = MagicMock()
        return mock

    @pytest.fixture
    def analyzer(self, mock_db):
        return TradeHistoryAnalyzer(mock_db)

    @pytest.mark.asyncio
    async def test_get_overall_stats_no_pool(self, mock_db):
        """DB 풀 없을 때 에러"""
        mock_db.pool = None
        analyzer = TradeHistoryAnalyzer(mock_db)

        with pytest.raises(RuntimeError, match="Database pool not initialized"):
            await analyzer.get_overall_stats()

    @pytest.mark.asyncio
    async def test_get_overall_stats_no_bot_id(self, analyzer, mock_db):
        """bot_id 없이 전체 통계 조회"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = {
            "total_trades": 10,
            "winning_trades": 7,
            "losing_trades": 3,
            "win_rate": 70.0,
            "total_pnl": 500.0,
            "avg_pnl": 50.0,
            "avg_win": 100.0,
            "avg_loss": -66.67,
            "profit_factor": 3.33,
            "avg_duration_minutes": 45.0,
            "best_trade_pnl": 200.0,
            "worst_trade_pnl": -80.0,
            "long_trades": 6,
            "short_trades": 4,
            "long_win_rate": 66.7,
            "short_win_rate": 75.0,
        }
        mock_db.pool.acquire.return_value.__aenter__.return_value = mock_conn

        stats = await analyzer.get_overall_stats(days=7)
        assert stats.total_trades == 10
        assert stats.win_rate == 70.0

    @pytest.mark.asyncio
    async def test_get_overall_stats_empty(self, analyzer, mock_db):
        """거래 없을 때 빈 통계 반환"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = {"total_trades": 0, "winning_trades": None, "losing_trades": None,
                                           "win_rate": None, "total_pnl": None, "avg_pnl": None,
                                           "avg_win": None, "avg_loss": None, "profit_factor": None,
                                           "avg_duration_minutes": None, "best_trade_pnl": None,
                                           "worst_trade_pnl": None, "long_trades": None, "short_trades": None,
                                           "long_win_rate": None, "short_win_rate": None}
        mock_db.pool.acquire.return_value.__aenter__.return_value = mock_conn

        stats = await analyzer.get_overall_stats(bot_id="test-bot", days=7)
        assert stats.total_trades == 0

    @pytest.mark.asyncio
    async def test_get_overall_stats_none_row(self, analyzer, mock_db):
        """fetchrow가 None 반환"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = None
        mock_db.pool.acquire.return_value.__aenter__.return_value = mock_conn

        stats = await analyzer.get_overall_stats(bot_id="test-bot", days=7)
        assert stats.total_trades == 0

    @pytest.mark.asyncio
    async def test_get_exit_reason_stats_no_pool(self, mock_db):
        """DB 풀 없을 때 에러"""
        mock_db.pool = None
        analyzer = TradeHistoryAnalyzer(mock_db)

        with pytest.raises(RuntimeError):
            await analyzer.get_exit_reason_stats()

    @pytest.mark.asyncio
    async def test_get_exit_reason_stats_no_bot_id(self, analyzer, mock_db):
        """bot_id 없이 청산 사유 통계"""
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = [
            {
                "exit_reason": "TP",
                "side": "LONG",
                "total_trades": 10,
                "winning_trades": 10,
                "win_rate": 100.0,
                "avg_pnl": 50.0,
                "total_pnl": 500.0,
                "avg_duration_minutes": 30.0,
            }
        ]
        mock_db.pool.acquire.return_value.__aenter__.return_value = mock_conn

        results = await analyzer.get_exit_reason_stats(days=7)
        assert len(results) == 1
        assert results[0].exit_reason == "TP"

    @pytest.mark.asyncio
    async def test_get_rsi_condition_stats_no_pool(self, mock_db):
        """DB 풀 없을 때 에러"""
        mock_db.pool = None
        analyzer = TradeHistoryAnalyzer(mock_db)

        with pytest.raises(RuntimeError):
            await analyzer.get_rsi_condition_stats()

    @pytest.mark.asyncio
    async def test_get_rsi_condition_stats_no_bot_id(self, analyzer, mock_db):
        """bot_id 없이 RSI 조건 통계"""
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = [
            {
                "rsi_zone": "oversold",
                "side": "LONG",
                "total_trades": 30,
                "winning_trades": 24,
                "losing_trades": 6,
                "win_rate": 80.0,
                "avg_pnl": 30.0,
                "total_pnl": 900.0,
                "avg_duration_minutes": 45.0,
            }
        ]
        mock_db.pool.acquire.return_value.__aenter__.return_value = mock_conn

        results = await analyzer.get_rsi_condition_stats(days=7)
        assert len(results) == 1
        assert results[0].rsi_zone == "oversold"

    @pytest.mark.asyncio
    async def test_get_hourly_stats_no_pool(self, mock_db):
        """DB 풀 없을 때 에러"""
        mock_db.pool = None
        analyzer = TradeHistoryAnalyzer(mock_db)

        with pytest.raises(RuntimeError):
            await analyzer.get_hourly_stats()

    @pytest.mark.asyncio
    async def test_get_hourly_stats_no_bot_id(self, analyzer, mock_db):
        """bot_id 없이 시간대별 통계"""
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = [
            {
                "hour_of_day": 14,
                "side": "LONG",
                "total_trades": 30,
                "winning_trades": 22,
                "win_rate": 73.3,
                "avg_pnl": 20.0,
                "total_pnl": 600.0,
            }
        ]
        mock_db.pool.acquire.return_value.__aenter__.return_value = mock_conn

        results = await analyzer.get_hourly_stats(days=7)
        assert len(results) == 1
        assert results[0].hour_of_day == 14
        assert results[0].losing_trades == 8  # 30 - 22

    @pytest.mark.asyncio
    async def test_get_recent_trade_summary_empty(self, analyzer, mock_db):
        """최근 거래 없을 때"""
        mock_db.get_recent_trades = AsyncMock(return_value=[])

        summary = await analyzer.get_recent_trade_summary(limit=10)
        assert summary["trades"] == []
        assert summary["summary"]["count"] == 0

    @pytest.mark.asyncio
    async def test_get_recent_trade_summary_with_trades(self, analyzer, mock_db):
        """최근 거래 요약"""
        mock_db.get_recent_trades = AsyncMock(return_value=[
            {"pnl": 100.0, "side": "LONG"},
            {"pnl": -50.0, "side": "SHORT"},
            {"pnl": 30.0, "side": "LONG"},
        ])

        summary = await analyzer.get_recent_trade_summary(limit=10, bot_id="test-bot")
        assert summary["summary"]["count"] == 3
        assert summary["summary"]["winners"] == 2
        assert summary["summary"]["losers"] == 1
        assert summary["summary"]["total_pnl"] == 80.0

    @pytest.mark.asyncio
    async def test_get_current_streak_no_pool(self, mock_db):
        """DB 풀 없을 때 에러"""
        mock_db.pool = None
        analyzer = TradeHistoryAnalyzer(mock_db)

        with pytest.raises(RuntimeError):
            await analyzer.get_current_streak()

    @pytest.mark.asyncio
    async def test_get_current_streak_no_bot_id(self, analyzer, mock_db):
        """bot_id 없이 연승 조회"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = {
            "streak_type": "win",
            "streak_count": 3,
            "last_trade_time": datetime.now(),
        }
        mock_db.pool.acquire.return_value.__aenter__.return_value = mock_conn

        streak = await analyzer.get_current_streak()
        assert streak["streak_type"] == "win"
        assert streak["streak_count"] == 3

    @pytest.mark.asyncio
    async def test_get_current_streak_none(self, analyzer, mock_db):
        """연승 정보 없음"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = {
            "streak_type": None,
            "streak_count": None,
            "last_trade_time": None,
        }
        mock_db.pool.acquire.return_value.__aenter__.return_value = mock_conn

        streak = await analyzer.get_current_streak(bot_id="test-bot")
        assert streak["streak_type"] is None
        assert streak["streak_count"] == 0


class TestStatisticalInsight:
    """StatisticalInsight 테스트"""

    def test_from_win_rate_zero_total(self):
        """총 거래 0인 경우"""
        insight = StatisticalInsight.from_win_rate(wins=0, total=0)
        assert insight.value == 0.0
        assert insight.sample_size == 0
        assert insight.is_statistically_significant is False

    def test_from_win_rate_small_sample(self):
        """작은 샘플 (p_value 없음)"""
        insight = StatisticalInsight.from_win_rate(wins=3, total=5)
        assert insight.sample_size == 5
        assert insight.p_value is None  # 10 미만이면 p_value 없음

    def test_from_win_rate_medium_sample(self):
        """중간 샘플 (p_value 있음)"""
        insight = StatisticalInsight.from_win_rate(wins=8, total=15)
        assert insight.sample_size == 15
        assert insight.p_value is not None

    def test_from_win_rate_large_sample_significant(self):
        """큰 샘플, 통계적 유의"""
        insight = StatisticalInsight.from_win_rate(wins=28, total=30)
        assert insight.sample_size == 30
        assert insight.is_statistically_significant is True
        assert insight.value > 80.0

    def test_from_win_rate_large_sample_not_significant(self):
        """큰 샘플, 통계적 유의하지 않음 (50% 근처)"""
        insight = StatisticalInsight.from_win_rate(wins=15, total=30)
        assert insight.is_statistically_significant is False

    def test_to_dict(self):
        """딕셔너리 변환"""
        insight = StatisticalInsight.from_win_rate(wins=7, total=10)
        data = insight.to_dict()
        assert "metric" in data
        assert "value" in data
        assert "sample_size" in data


class TestCalculateConfidenceInterval:
    """calculate_confidence_interval 테스트"""

    def test_empty_values(self):
        """빈 리스트"""
        mean, lower, upper, se = calculate_confidence_interval([])
        assert mean == 0.0
        assert se == 0.0

    def test_single_value(self):
        """값 하나"""
        mean, lower, upper, se = calculate_confidence_interval([42.0])
        assert mean == 42.0
        assert lower == 42.0
        assert upper == 42.0
        assert se == 0.0

    def test_normal_values(self):
        """정상적인 값들"""
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        mean, lower, upper, se = calculate_confidence_interval(values)
        assert mean == 30.0
        assert lower < mean
        assert upper > mean
        assert se > 0

    def test_confidence_90(self):
        """90% 신뢰도"""
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        mean, lower, upper, se = calculate_confidence_interval(values, confidence=0.90)
        assert mean == 30.0
        # 90%는 95%보다 구간이 좁아야 함
        _, lower_95, upper_95, _ = calculate_confidence_interval(values, confidence=0.95)
        assert (upper - lower) < (upper_95 - lower_95)


class TestPatternInsightWithConfidence:
    """PatternInsight.with_confidence 테스트"""

    def test_high_confidence(self):
        """높은 신뢰도: 샘플 많고 통계적 유의"""
        insight = PatternInsight.with_confidence(
            pattern_type="rsi_zone",
            description="RSI 과매도에서 LONG",
            side="LONG",
            condition="rsi_zone=oversold",
            wins=28,
            total=30,
            avg_pnl=50.0,
            recommendation="RSI 과매도에서 LONG 추천",
        )
        assert insight.confidence_level == "HIGH"
        assert insight.is_statistically_significant is True

    def test_medium_confidence(self):
        """중간 신뢰도: 샘플 10-29"""
        insight = PatternInsight.with_confidence(
            pattern_type="hourly",
            description="14시에 LONG",
            side="LONG",
            condition="hour=14",
            wins=8,
            total=15,
            avg_pnl=30.0,
            recommendation="14시에 LONG 추천",
        )
        assert insight.confidence_level == "MEDIUM"

    def test_low_confidence(self):
        """낮은 신뢰도: 샘플 < 10"""
        insight = PatternInsight.with_confidence(
            pattern_type="rsi_zone",
            description="RSI 과매수에서 SHORT",
            side="SHORT",
            condition="rsi_zone=overbought",
            wins=3,
            total=5,
            avg_pnl=-10.0,
            recommendation="RSI 과매수에서 SHORT 권장",
        )
        assert insight.confidence_level == "LOW"


class TestNormalCDF:
    """_normal_cdf 테스트"""

    def test_cdf_zero(self):
        """x=0이면 0.5"""
        assert _normal_cdf(0) == pytest.approx(0.5, abs=0.001)

    def test_cdf_positive(self):
        """양수면 > 0.5"""
        assert _normal_cdf(1.96) > 0.97

    def test_cdf_negative(self):
        """음수면 < 0.5"""
        assert _normal_cdf(-1.96) < 0.03


class TestTradingStatsEmpty:
    """TradingStats.empty 테스트"""

    def test_empty_stats(self):
        """빈 통계"""
        stats = TradingStats.empty()
        assert stats.total_trades == 0
        assert stats.win_rate == 0.0
        assert stats.total_pnl == 0.0

    def test_to_dict(self):
        """딕셔너리 변환"""
        stats = TradingStats.empty()
        data = stats.to_dict()
        assert data["total_trades"] == 0


class TestDataclassToDict:
    """데이터클래스 to_dict 테스트"""

    def test_exit_reason_stats_to_dict(self):
        """ExitReasonStats.to_dict"""
        s = ExitReasonStats(
            exit_reason="TP", side="LONG",
            total_trades=10, winning_trades=8,
            win_rate=80.0, avg_pnl=50.0,
            total_pnl=500.0, avg_duration_minutes=30.0,
        )
        d = s.to_dict()
        assert d["exit_reason"] == "TP"
        assert d["total_trades"] == 10

    def test_rsi_condition_stats_to_dict(self):
        """RSIConditionStats.to_dict"""
        s = RSIConditionStats(
            rsi_zone="oversold", side="LONG",
            total_trades=20, winning_trades=16,
            losing_trades=4, win_rate=80.0,
            avg_pnl=40.0, total_pnl=800.0,
            avg_duration_minutes=35.0,
        )
        d = s.to_dict()
        assert d["rsi_zone"] == "oversold"

    def test_time_based_stats_to_dict(self):
        """TimeBasedStats.to_dict"""
        s = TimeBasedStats(
            hour_of_day=14, side="SHORT",
            total_trades=15, winning_trades=10,
            losing_trades=5, win_rate=66.7,
            avg_pnl=20.0, total_pnl=300.0,
        )
        d = s.to_dict()
        assert d["hour_of_day"] == 14

    def test_pattern_insight_to_dict(self):
        """PatternInsight.to_dict"""
        pi = PatternInsight(
            pattern_type="rsi_zone",
            description="test",
            side="LONG",
            condition="rsi_zone=oversold",
            sample_size=30,
            win_rate=80.0,
            avg_pnl=50.0,
            recommendation="추천",
        )
        d = pi.to_dict()
        assert d["pattern_type"] == "rsi_zone"


class TestRSIZoneDescription:
    """_get_rsi_zone_description 테스트"""

    @pytest.fixture
    def analyzer(self):
        mock_db = MagicMock()
        mock_db.pool = MagicMock()
        return TradeHistoryAnalyzer(mock_db)

    def test_known_zones(self, analyzer):
        """알려진 RSI 구간"""
        assert "과매도" in analyzer._get_rsi_zone_description("oversold")
        assert "저점" in analyzer._get_rsi_zone_description("low")
        assert "중립" in analyzer._get_rsi_zone_description("neutral")
        assert "고점" in analyzer._get_rsi_zone_description("high")
        assert "과매수" in analyzer._get_rsi_zone_description("overbought")
        assert "알 수 없음" in analyzer._get_rsi_zone_description("unknown")

    def test_unknown_zone(self, analyzer):
        """알 수 없는 구간"""
        result = analyzer._get_rsi_zone_description("custom_zone")
        assert result == "custom_zone"
