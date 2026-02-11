"""
Analytics 모듈 커버리지 개선 테스트

signal_tracker.py, trade_analyzer.py의 미커버 라인을 대상으로 합니다.
"""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.analytics.signal_tracker import (
    SignalRecord,
    SignalTracker,
)
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
# SignalTracker: DB 관련 추가 커버리지
# =============================================================================

class TestSignalTrackerDBEdgeCases:
    """SignalTracker DB 연동 엣지 케이스"""

    @pytest.fixture
    def mock_pool(self):
        pool = MagicMock()
        return pool

    @pytest.fixture
    def tracker_with_db(self, mock_pool):
        return SignalTracker(db_pool=mock_pool)

    @pytest.mark.asyncio
    async def test_update_signal_result_db_error_fallback_memory(self, tracker_with_db, mock_pool):
        """DB 업데이트 실패 시 인메모리 폴백"""
        mock_conn = AsyncMock()
        mock_conn.execute.side_effect = Exception("DB Error")
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # 인메모리에 기록 추가
        tracker_with_db._in_memory_signals["test-id"] = SignalRecord.create(
            bot_id="test", signal="LONG", source="gemini"
        )
        tracker_with_db._in_memory_signals["test-id"].signal_id = "test-id"

        # DB 실패 후 인메모리 업데이트 시도
        success = await tracker_with_db.update_signal_result("test-id", "win", 100.0)
        assert success is True

    @pytest.mark.asyncio
    async def test_update_signal_result_db_error_no_memory(self, tracker_with_db, mock_pool):
        """DB 업데이트 실패 + 인메모리에도 없는 경우"""
        mock_conn = AsyncMock()
        mock_conn.execute.side_effect = Exception("DB Error")
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        success = await tracker_with_db.update_signal_result("nonexistent", "win", 100.0)
        assert success is False

    @pytest.mark.asyncio
    async def test_get_signal_stats_db_error_fallback(self, tracker_with_db, mock_pool):
        """DB 통계 조회 실패 시 인메모리 폴백"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.side_effect = Exception("DB Error")
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        stats = await tracker_with_db.get_signal_stats(days=7)
        # 인메모리에 데이터 없으므로 빈 통계
        assert stats.total_signals == 0

    @pytest.mark.asyncio
    async def test_get_win_rate_by_source_db_error_fallback(self, tracker_with_db, mock_pool):
        """DB 소스별 승률 조회 실패 시 인메모리 폴백"""
        mock_conn = AsyncMock()
        mock_conn.fetch.side_effect = Exception("DB Error")
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await tracker_with_db.get_win_rate_by_source(days=7)
        assert result == {}

    @pytest.mark.asyncio
    async def test_get_recent_signals_db_error_fallback(self, tracker_with_db, mock_pool):
        """DB 신호 조회 실패 시 인메모리 폴백"""
        mock_conn = AsyncMock()
        mock_conn.fetch.side_effect = Exception("DB Error")
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        signals = await tracker_with_db.get_recent_signals()
        assert signals == []

    @pytest.mark.asyncio
    async def test_get_recent_signals_from_db_with_bot_id(self, tracker_with_db, mock_pool):
        """DB에서 bot_id 필터 조회"""
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = [
            {
                "id": "sig-1",
                "timestamp": datetime.now(),
                "bot_id": "test-bot",
                "signal": "LONG",
                "source": "gemini",
                "market_conditions": {"rsi": 30},
                "trade_result": "win",
                "pnl": 100.0,
                "reason": "RSI",
            }
        ]
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        signals = await tracker_with_db.get_recent_signals(bot_id="test-bot", limit=10)
        assert len(signals) == 1
        assert signals[0]["signal"] == "LONG"

    @pytest.mark.asyncio
    async def test_get_recent_signals_from_db_without_bot_id(self, tracker_with_db, mock_pool):
        """DB에서 bot_id 없이 조회"""
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = [
            {
                "id": "sig-1",
                "timestamp": datetime.now(),
                "bot_id": "test-bot",
                "signal": "SHORT",
                "source": "rule_based",
                "market_conditions": None,
                "trade_result": None,
                "pnl": None,
                "reason": None,
            }
        ]
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        signals = await tracker_with_db.get_recent_signals(limit=5)
        assert len(signals) == 1
        assert signals[0]["pnl"] is None

    @pytest.mark.asyncio
    async def test_get_stats_from_db_with_bot_id_and_source(self, tracker_with_db, mock_pool):
        """DB 통계: bot_id + source 필터"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = {
            "total_signals": 5,
            "traded_signals": 4,
            "wins": 3,
            "losses": 1,
            "total_pnl": 200.0,
            "best_pnl": 100.0,
            "worst_pnl": -30.0,
        }
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        stats = await tracker_with_db.get_signal_stats(
            bot_id="test-bot", source="gemini", days=7
        )
        assert stats.total_signals == 5
        assert stats.wins == 3

    @pytest.mark.asyncio
    async def test_get_win_rate_by_source_with_bot_id(self, tracker_with_db, mock_pool):
        """DB 소스별 승률: bot_id 필터"""
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = [
            {"source": "gemini", "traded": 10, "wins": 8},
            {"source": "scoring", "traded": 0, "wins": 0},
        ]
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await tracker_with_db.get_win_rate_by_source(
            days=7, bot_id="test-bot"
        )
        assert result["gemini"] == 80.0
        assert result["scoring"] == 0.0

    @pytest.mark.asyncio
    async def test_cleanup_old_signals_db(self, tracker_with_db, mock_pool):
        """DB 오래된 신호 정리"""
        mock_conn = AsyncMock()
        mock_conn.execute.return_value = "DELETE 5"
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        deleted = await tracker_with_db.cleanup_old_signals(days=30)
        assert deleted == 5

    @pytest.mark.asyncio
    async def test_cleanup_old_signals_db_error(self, tracker_with_db, mock_pool):
        """DB 정리 실패"""
        mock_conn = AsyncMock()
        mock_conn.execute.side_effect = Exception("DB Error")
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        deleted = await tracker_with_db.cleanup_old_signals(days=30)
        assert deleted == 0


class TestSignalTrackerInMemoryEdgeCases:
    """SignalTracker 인메모리 엣지 케이스"""

    @pytest.fixture
    def tracker(self):
        return SignalTracker()

    @pytest.mark.asyncio
    async def test_in_memory_stats_filter_by_bot_id(self, tracker):
        """봇 ID별 인메모리 필터링"""
        await tracker.record_signal("bot-a", "LONG", "gemini")
        await tracker.record_signal("bot-b", "SHORT", "gemini")

        stats = await tracker.get_signal_stats(bot_id="bot-a", days=7)
        assert stats.total_signals == 1

    @pytest.mark.asyncio
    async def test_in_memory_win_rate_by_source_filter_by_bot(self, tracker):
        """봇 ID별 소스 승률 필터링"""
        sid = await tracker.record_signal("bot-a", "LONG", "gemini")
        await tracker.update_signal_result(sid, "win", 100.0)

        sid = await tracker.record_signal("bot-b", "SHORT", "gemini")
        await tracker.update_signal_result(sid, "loss", -50.0)

        result = await tracker.get_win_rate_by_source(days=7, bot_id="bot-a")
        assert result["gemini"] == 100.0

    @pytest.mark.asyncio
    async def test_in_memory_win_rate_no_traded(self, tracker):
        """거래되지 않은 신호만 있는 경우"""
        await tracker.record_signal("bot-a", "LONG", "gemini")

        result = await tracker.get_win_rate_by_source(days=7)
        assert result == {}

    @pytest.mark.asyncio
    async def test_get_recent_signals_without_bot_id(self, tracker):
        """봇 ID 없이 최근 신호 조회"""
        await tracker.record_signal("bot-a", "LONG", "gemini")
        await tracker.record_signal("bot-b", "SHORT", "rule_based")

        signals = await tracker.get_recent_signals(limit=10)
        assert len(signals) == 2

    @pytest.mark.asyncio
    async def test_set_db_pool(self, tracker):
        """DB 풀 설정"""
        mock_pool = MagicMock()
        tracker.set_db_pool(mock_pool)
        assert tracker.db_pool is mock_pool


# =============================================================================
# TradeAnalyzer: 추가 커버리지
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


# =============================================================================
# TradeAnalyzer: PatternInsight, StatisticalInsight 테스트
# =============================================================================

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
