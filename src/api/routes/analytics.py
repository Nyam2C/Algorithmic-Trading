"""
Analytics API 라우터

Phase 4: AI 메모리 시스템 - 분석 API 엔드포인트
거래 분석 결과 및 패턴 인사이트 제공
"""
from typing import Optional, List, Any
from fastapi import APIRouter, Query, HTTPException, status
from pydantic import BaseModel
from loguru import logger

from src.api.dependencies import get_trade_analyzer


router = APIRouter(prefix="/analytics", tags=["analytics"])


# =============================================================================
# Response Models
# =============================================================================


class TradingStatsResponse(BaseModel):
    """거래 통계 응답"""

    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    avg_pnl: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    avg_duration_minutes: float
    best_trade_pnl: float
    worst_trade_pnl: float
    long_trades: int
    short_trades: int
    long_win_rate: float
    short_win_rate: float


class PatternInsightResponse(BaseModel):
    """패턴 인사이트 응답"""

    pattern_type: str
    description: str
    side: str
    condition: str
    sample_size: int
    win_rate: float
    avg_pnl: float
    recommendation: str


class RSIConditionStatsResponse(BaseModel):
    """RSI 조건별 통계 응답"""

    rsi_zone: str
    side: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_pnl: float
    total_pnl: float
    avg_duration_minutes: float


class TimeBasedStatsResponse(BaseModel):
    """시간대별 통계 응답"""

    hour_of_day: int
    side: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_pnl: float
    total_pnl: float


class StreakResponse(BaseModel):
    """연승/연패 응답"""

    streak_type: Optional[str]
    streak_count: int
    last_trade_time: Optional[str]


class RecommendationsResponse(BaseModel):
    """추천 응답"""

    recommendations: List[str]
    best_long_condition: Optional[str]
    best_short_condition: Optional[str]
    best_hour: Optional[int]
    avoid_conditions: List[str]


# =============================================================================
# API Response Wrapper
# =============================================================================


class APIResponse(BaseModel):
    """표준 API 응답"""

    success: bool
    data: Any
    message: Optional[str] = None


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/summary", response_model=APIResponse)
async def get_analytics_summary(
    bot_id: Optional[str] = Query(None, description="봇 ID"),
    days: int = Query(7, ge=1, le=90, description="분석 기간 (일)"),
) -> APIResponse:
    """전체 성과 요약 조회

    Args:
        bot_id: 봇 ID (선택, 미지정 시 전체)
        days: 분석 기간 (1-90일)

    Returns:
        APIResponse: 거래 통계
    """
    analyzer = get_trade_analyzer()
    if analyzer is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Analytics service not available",
        )

    try:
        stats = await analyzer.get_overall_stats(bot_id=bot_id, days=days)
        return APIResponse(
            success=True,
            data=stats.to_dict(),
            message=f"{days}일간 거래 통계",
        )
    except Exception as e:
        logger.error(f"Analytics summary error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/patterns", response_model=APIResponse)
async def get_analytics_patterns(
    bot_id: Optional[str] = Query(None, description="봇 ID"),
    days: int = Query(7, ge=1, le=90, description="분석 기간 (일)"),
    min_sample_size: int = Query(5, ge=1, description="최소 샘플 수"),
    min_win_rate: float = Query(70.0, ge=0, le=100, description="최소 승률 (%)"),
) -> APIResponse:
    """발견된 패턴 조회

    높은 승률을 보이는 조건들과 피해야 할 조건들을 분석

    Args:
        bot_id: 봇 ID (선택)
        days: 분석 기간
        min_sample_size: 최소 샘플 수
        min_win_rate: 최소 승률

    Returns:
        APIResponse: 패턴 인사이트
    """
    analyzer = get_trade_analyzer()
    if analyzer is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Analytics service not available",
        )

    try:
        best_patterns = await analyzer.get_pattern_insights(
            bot_id=bot_id,
            days=days,
            min_sample_size=min_sample_size,
            min_win_rate=min_win_rate,
        )

        worst_patterns = await analyzer.get_worst_patterns(
            bot_id=bot_id,
            days=days,
            min_sample_size=min_sample_size,
            max_win_rate=100 - min_win_rate,  # 반대 기준
        )

        return APIResponse(
            success=True,
            data={
                "best_patterns": [p.to_dict() for p in best_patterns],
                "worst_patterns": [p.to_dict() for p in worst_patterns],
                "analysis_period_days": days,
                "min_sample_size": min_sample_size,
            },
            message=f"{days}일간 패턴 분석",
        )
    except Exception as e:
        logger.error(f"Analytics patterns error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/recommendations", response_model=APIResponse)
async def get_analytics_recommendations(
    bot_id: Optional[str] = Query(None, description="봇 ID"),
    days: int = Query(7, ge=1, le=90, description="분석 기간 (일)"),
) -> APIResponse:
    """AI 추천 파라미터 조회

    과거 성과를 기반으로 최적 조건 추천

    Args:
        bot_id: 봇 ID (선택)
        days: 분석 기간

    Returns:
        APIResponse: 추천 파라미터
    """
    analyzer = get_trade_analyzer()
    if analyzer is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Analytics service not available",
        )

    try:
        rsi_stats = await analyzer.get_rsi_condition_stats(bot_id=bot_id, days=days)
        hourly_stats = await analyzer.get_hourly_stats(bot_id=bot_id, days=days)

        # 최적 조건 추출
        recommendations = []
        best_long_condition = None
        best_short_condition = None
        best_hour = None
        avoid_conditions = []

        # LONG 최적 RSI
        long_rsi = [s for s in rsi_stats if s.side == "LONG" and s.win_rate >= 70 and s.total_trades >= 5]
        if long_rsi:
            best = max(long_rsi, key=lambda x: x.win_rate)
            best_long_condition = f"RSI {best.rsi_zone} (승률 {best.win_rate:.1f}%)"
            recommendations.append(f"LONG: {best_long_condition}")

        # SHORT 최적 RSI
        short_rsi = [s for s in rsi_stats if s.side == "SHORT" and s.win_rate >= 70 and s.total_trades >= 5]
        if short_rsi:
            best = max(short_rsi, key=lambda x: x.win_rate)
            best_short_condition = f"RSI {best.rsi_zone} (승률 {best.win_rate:.1f}%)"
            recommendations.append(f"SHORT: {best_short_condition}")

        # 최적 시간
        good_hours = [h for h in hourly_stats if h.win_rate >= 75 and h.total_trades >= 5]
        if good_hours:
            best_hourly = max(good_hours, key=lambda x: x.win_rate)
            best_hour = best_hourly.hour_of_day
            recommendations.append(f"최적 시간: {best_hour}시 (승률 {best_hourly.win_rate:.1f}%)")

        # 피해야 할 조건
        bad_conditions = [s for s in rsi_stats if s.win_rate <= 40 and s.total_trades >= 5]
        for cond in bad_conditions:
            avoid_conditions.append(f"{cond.side} RSI {cond.rsi_zone} (승률 {cond.win_rate:.1f}%)")

        return APIResponse(
            success=True,
            data={
                "recommendations": recommendations,
                "best_long_condition": best_long_condition,
                "best_short_condition": best_short_condition,
                "best_hour": best_hour,
                "avoid_conditions": avoid_conditions,
                "analysis_period_days": days,
            },
            message=f"{days}일간 데이터 기반 추천",
        )
    except Exception as e:
        logger.error(f"Analytics recommendations error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/rsi-stats", response_model=APIResponse)
async def get_rsi_stats(
    bot_id: Optional[str] = Query(None, description="봇 ID"),
    days: int = Query(7, ge=1, le=90, description="분석 기간 (일)"),
) -> APIResponse:
    """RSI 조건별 통계 조회

    Args:
        bot_id: 봇 ID (선택)
        days: 분석 기간

    Returns:
        APIResponse: RSI 조건별 통계
    """
    analyzer = get_trade_analyzer()
    if analyzer is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Analytics service not available",
        )

    try:
        stats = await analyzer.get_rsi_condition_stats(bot_id=bot_id, days=days)
        return APIResponse(
            success=True,
            data=[s.to_dict() for s in stats],
            message=f"RSI 조건별 통계 ({len(stats)}개 구간)",
        )
    except Exception as e:
        logger.error(f"RSI stats error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/hourly-stats", response_model=APIResponse)
async def get_hourly_stats(
    bot_id: Optional[str] = Query(None, description="봇 ID"),
    days: int = Query(7, ge=1, le=90, description="분석 기간 (일)"),
) -> APIResponse:
    """시간대별 통계 조회

    Args:
        bot_id: 봇 ID (선택)
        days: 분석 기간

    Returns:
        APIResponse: 시간대별 통계
    """
    analyzer = get_trade_analyzer()
    if analyzer is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Analytics service not available",
        )

    try:
        stats = await analyzer.get_hourly_stats(bot_id=bot_id, days=days)
        return APIResponse(
            success=True,
            data=[s.to_dict() for s in stats],
            message=f"시간대별 통계 ({len(stats)}개 시간대)",
        )
    except Exception as e:
        logger.error(f"Hourly stats error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/streak", response_model=APIResponse)
async def get_streak(
    bot_id: Optional[str] = Query(None, description="봇 ID"),
) -> APIResponse:
    """연승/연패 조회

    Args:
        bot_id: 봇 ID (선택)

    Returns:
        APIResponse: 연승/연패 정보
    """
    analyzer = get_trade_analyzer()
    if analyzer is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Analytics service not available",
        )

    try:
        streak = await analyzer.get_current_streak(bot_id=bot_id)

        # datetime을 문자열로 변환
        if streak.get("last_trade_time"):
            streak["last_trade_time"] = streak["last_trade_time"].isoformat()

        return APIResponse(
            success=True,
            data=streak,
            message="현재 연승/연패 정보",
        )
    except Exception as e:
        logger.error(f"Streak error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
