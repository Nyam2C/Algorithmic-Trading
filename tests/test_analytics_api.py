"""
Analytics API 엔드포인트 테스트

Phase 4: AI 메모리 시스템 - 분석 API 테스트
TDD 방식으로 작성
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from datetime import datetime

from src.api.main import create_app
from src.analytics.trade_analyzer import (
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
def mock_analyzer():
    """모의 TradeHistoryAnalyzer"""
    from src.analytics.trade_analyzer import TradeHistoryAnalyzer

    analyzer = MagicMock(spec=TradeHistoryAnalyzer)
    return analyzer


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
def sample_patterns():
    """샘플 패턴 인사이트"""
    return [
        PatternInsight(
            pattern_type="rsi_zone",
            description="RSI 30 이하에서 LONG",
            side="LONG",
            condition="rsi_zone=oversold",
            sample_size=15,
            win_rate=85.0,
            avg_pnl=10.0,
            recommendation="RSI 30 이하에서 LONG 진입 권장",
        ),
        PatternInsight(
            pattern_type="hourly",
            description="14시에 LONG",
            side="LONG",
            condition="hour=14",
            sample_size=10,
            win_rate=80.0,
            avg_pnl=8.0,
            recommendation="14시에 LONG 진입 권장",
        ),
    ]


@pytest.fixture
def sample_rsi_stats():
    """샘플 RSI 조건별 통계"""
    return [
        RSIConditionStats(
            rsi_zone="oversold",
            side="LONG",
            total_trades=15,
            winning_trades=12,
            losing_trades=3,
            win_rate=80.0,
            avg_pnl=10.0,
            total_pnl=150.0,
            avg_duration_minutes=40.0,
        ),
    ]


@pytest.fixture
def sample_hourly_stats():
    """샘플 시간대별 통계"""
    return [
        TimeBasedStats(
            hour_of_day=14,
            side="LONG",
            total_trades=10,
            winning_trades=8,
            losing_trades=2,
            win_rate=80.0,
            avg_pnl=8.0,
            total_pnl=80.0,
        ),
    ]


@pytest.fixture
def app_with_analytics(mock_analyzer, sample_stats, sample_patterns, sample_rsi_stats, sample_hourly_stats):
    """분석기가 주입된 앱"""
    # Mock 설정
    mock_analyzer.get_overall_stats = AsyncMock(return_value=sample_stats)
    mock_analyzer.get_pattern_insights = AsyncMock(return_value=sample_patterns)
    mock_analyzer.get_worst_patterns = AsyncMock(return_value=[])
    mock_analyzer.get_rsi_condition_stats = AsyncMock(return_value=sample_rsi_stats)
    mock_analyzer.get_hourly_stats = AsyncMock(return_value=sample_hourly_stats)
    mock_analyzer.get_current_streak = AsyncMock(
        return_value={"streak_type": "WIN", "streak_count": 3}
    )
    mock_analyzer.get_recent_trade_summary = AsyncMock(
        return_value={"trades": [], "summary": {"count": 0}}
    )

    with patch("src.api.routes.analytics.get_trade_analyzer", return_value=mock_analyzer):
        app = create_app()
        yield app, mock_analyzer


# =============================================================================
# GET /api/analytics/summary 테스트
# =============================================================================


class TestAnalyticsSummaryEndpoint:
    """GET /api/analytics/summary 테스트"""

    def test_get_summary_success(self, app_with_analytics, sample_stats):
        """성과 요약 조회 성공 테스트"""
        app, mock_analyzer = app_with_analytics
        client = TestClient(app)

        response = client.get("/api/analytics/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert data["data"]["total_trades"] == 42
        assert data["data"]["win_rate"] == 66.67

    def test_get_summary_with_bot_id(self, app_with_analytics):
        """특정 봇 ID로 성과 요약 조회 테스트"""
        app, mock_analyzer = app_with_analytics
        client = TestClient(app)

        response = client.get("/api/analytics/summary?bot_id=test-bot-id")

        assert response.status_code == 200
        mock_analyzer.get_overall_stats.assert_called()

    def test_get_summary_with_days(self, app_with_analytics):
        """기간 지정 성과 요약 조회 테스트"""
        app, mock_analyzer = app_with_analytics
        client = TestClient(app)

        response = client.get("/api/analytics/summary?days=14")

        assert response.status_code == 200

    def test_get_summary_empty_data(self, mock_analyzer):
        """데이터 없을 때 성과 요약 테스트"""
        mock_analyzer.get_overall_stats = AsyncMock(return_value=TradingStats.empty())

        with patch("src.api.routes.analytics.get_trade_analyzer", return_value=mock_analyzer):
            app = create_app()
            client = TestClient(app)

            response = client.get("/api/analytics/summary")

            assert response.status_code == 200
            data = response.json()
            assert data["data"]["total_trades"] == 0


# =============================================================================
# GET /api/analytics/patterns 테스트
# =============================================================================


class TestAnalyticsPatternsEndpoint:
    """GET /api/analytics/patterns 테스트"""

    def test_get_patterns_success(self, app_with_analytics, sample_patterns):
        """패턴 조회 성공 테스트"""
        app, mock_analyzer = app_with_analytics
        client = TestClient(app)

        response = client.get("/api/analytics/patterns")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "best_patterns" in data["data"]
        assert len(data["data"]["best_patterns"]) == 2

    def test_get_patterns_with_filters(self, app_with_analytics):
        """필터 적용 패턴 조회 테스트"""
        app, mock_analyzer = app_with_analytics
        client = TestClient(app)

        response = client.get(
            "/api/analytics/patterns?min_sample_size=10&min_win_rate=75"
        )

        assert response.status_code == 200

    def test_get_patterns_empty(self, mock_analyzer):
        """패턴 없을 때 테스트"""
        mock_analyzer.get_pattern_insights = AsyncMock(return_value=[])
        mock_analyzer.get_worst_patterns = AsyncMock(return_value=[])

        with patch("src.api.routes.analytics.get_trade_analyzer", return_value=mock_analyzer):
            app = create_app()
            client = TestClient(app)

            response = client.get("/api/analytics/patterns")

            assert response.status_code == 200
            data = response.json()
            assert data["data"]["best_patterns"] == []


# =============================================================================
# GET /api/analytics/recommendations 테스트
# =============================================================================


class TestAnalyticsRecommendationsEndpoint:
    """GET /api/analytics/recommendations 테스트"""

    def test_get_recommendations_success(self, app_with_analytics):
        """추천 조회 성공 테스트"""
        app, mock_analyzer = app_with_analytics
        client = TestClient(app)

        response = client.get("/api/analytics/recommendations")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "recommendations" in data["data"]

    def test_get_recommendations_with_bot_id(self, app_with_analytics):
        """특정 봇 ID로 추천 조회 테스트"""
        app, mock_analyzer = app_with_analytics
        client = TestClient(app)

        response = client.get("/api/analytics/recommendations?bot_id=test-bot-id")

        assert response.status_code == 200


# =============================================================================
# GET /api/analytics/rsi-stats 테스트
# =============================================================================


class TestAnalyticsRSIStatsEndpoint:
    """GET /api/analytics/rsi-stats 테스트"""

    def test_get_rsi_stats_success(self, app_with_analytics):
        """RSI 조건별 통계 조회 성공 테스트"""
        app, mock_analyzer = app_with_analytics
        client = TestClient(app)

        response = client.get("/api/analytics/rsi-stats")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert len(data["data"]) >= 1


# =============================================================================
# GET /api/analytics/hourly-stats 테스트
# =============================================================================


class TestAnalyticsHourlyStatsEndpoint:
    """GET /api/analytics/hourly-stats 테스트"""

    def test_get_hourly_stats_success(self, app_with_analytics):
        """시간대별 통계 조회 성공 테스트"""
        app, mock_analyzer = app_with_analytics
        client = TestClient(app)

        response = client.get("/api/analytics/hourly-stats")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data


# =============================================================================
# GET /api/analytics/streak 테스트
# =============================================================================


class TestAnalyticsStreakEndpoint:
    """GET /api/analytics/streak 테스트"""

    def test_get_streak_success(self, app_with_analytics):
        """연승/연패 조회 성공 테스트"""
        app, mock_analyzer = app_with_analytics
        client = TestClient(app)

        response = client.get("/api/analytics/streak")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["streak_type"] == "WIN"
        assert data["data"]["streak_count"] == 3


# =============================================================================
# 에러 처리 테스트
# =============================================================================


class TestAnalyticsAPIErrors:
    """Analytics API 에러 처리 테스트"""

    def test_analyzer_not_configured(self):
        """분석기 미설정 시 에러 테스트"""
        with patch("src.api.routes.analytics.get_trade_analyzer", return_value=None):
            app = create_app()
            client = TestClient(app)

            response = client.get("/api/analytics/summary")

            # 503 Service Unavailable 또는 에러 응답
            assert response.status_code in [503, 500]

    def test_invalid_days_parameter(self, app_with_analytics):
        """잘못된 days 파라미터 테스트"""
        app, mock_analyzer = app_with_analytics
        client = TestClient(app)

        response = client.get("/api/analytics/summary?days=-1")

        # 400 Bad Request 또는 유효성 검사 에러
        assert response.status_code in [400, 422]

    def test_database_error(self, mock_analyzer):
        """데이터베이스 에러 시 처리 테스트"""
        mock_analyzer.get_overall_stats = AsyncMock(
            side_effect=Exception("Database connection failed")
        )

        with patch("src.api.routes.analytics.get_trade_analyzer", return_value=mock_analyzer):
            app = create_app()
            client = TestClient(app)

            response = client.get("/api/analytics/summary")

            assert response.status_code == 500
