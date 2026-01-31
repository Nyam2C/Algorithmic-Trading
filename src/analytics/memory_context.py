"""
AI 메모리 컨텍스트 빌더 (AIMemoryContextBuilder)

Phase 4: AI 메모리 시스템 - 과거 거래 분석을 AI 프롬프트로 변환
과거 거래 통계와 패턴을 분석하여 AI에게 "기억"으로 제공
"""
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List
from loguru import logger

from src.analytics.trade_analyzer import (
    TradeHistoryAnalyzer,
    TradingStats,
    RSIConditionStats,
    TimeBasedStats,
)


@dataclass
class MemoryContext:
    """AI 메모리 컨텍스트

    AI 프롬프트에 주입할 과거 거래 분석 결과

    Attributes:
        overall_summary: 전체 성과 요약 (예: "7일간: 42거래, 승률 68%, +$125")
        recent_performance: 최근 성과 (예: "최근 10개: 7승 3패, 연속 3승 중")
        best_conditions: 최적 조건 (예: "LONG 최적: RSI<35 (승률 85%)")
        worst_conditions: 피해야 할 조건 (예: "피해야 할: RSI 40-60에서 LONG")
        timing_insights: 시간대 인사이트 (예: "최적 시간: 14-16시")
        recommendations: 추천 사항 (예: "추천 RSI: LONG < 35")
    """

    overall_summary: str
    recent_performance: str
    best_conditions: str
    worst_conditions: str
    timing_insights: str
    recommendations: str

    @classmethod
    def empty(cls) -> "MemoryContext":
        """빈 컨텍스트 반환"""
        return cls(
            overall_summary="",
            recent_performance="",
            best_conditions="",
            worst_conditions="",
            timing_insights="",
            recommendations="",
        )

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return asdict(self)

    def to_prompt(self) -> str:
        """AI 프롬프트 형식으로 변환

        Returns:
            AI에게 전달할 메모리 컨텍스트 프롬프트
        """
        sections = []

        sections.append("[과거 거래 기록 기반 학습 데이터]")

        if self.overall_summary:
            sections.append(f"전체 성과: {self.overall_summary}")

        if self.recent_performance:
            sections.append(f"최근 성과: {self.recent_performance}")

        if self.best_conditions:
            sections.append(f"최적 조건: {self.best_conditions}")

        if self.worst_conditions:
            sections.append(f"피해야 할 조건: {self.worst_conditions}")

        if self.timing_insights:
            sections.append(f"시간대 분석: {self.timing_insights}")

        if self.recommendations:
            sections.append(f"추천: {self.recommendations}")

        return "\n".join(sections)

    def is_empty(self) -> bool:
        """빈 컨텍스트인지 확인"""
        return not any([
            self.overall_summary,
            self.recent_performance,
            self.best_conditions,
            self.worst_conditions,
            self.timing_insights,
            self.recommendations,
        ])


class AIMemoryContextBuilder:
    """AI 메모리 컨텍스트 빌더

    TradeHistoryAnalyzer의 분석 결과를 기반으로
    AI 프롬프트에 주입할 메모리 컨텍스트를 생성합니다.

    Example:
        >>> builder = AIMemoryContextBuilder(analyzer)
        >>> context = await builder.build_context(bot_id="btc-bot")
        >>> prompt = context.to_prompt()
        >>> # 프롬프트에 메모리 컨텍스트 주입
    """

    def __init__(self, analyzer: TradeHistoryAnalyzer) -> None:
        """빌더 초기화

        Args:
            analyzer: TradeHistoryAnalyzer 인스턴스
        """
        self.analyzer = analyzer
        self._log = logger.bind(module="memory_context")

    async def build_context(
        self,
        bot_id: Optional[str] = None,
        days: int = 7,
    ) -> MemoryContext:
        """메모리 컨텍스트 생성

        과거 거래 데이터를 분석하여 AI에게 전달할 컨텍스트 생성

        Args:
            bot_id: 봇 ID (선택)
            days: 분석 기간 (일)

        Returns:
            MemoryContext: AI 메모리 컨텍스트
        """
        try:
            # 1. 전체 통계 수집
            stats = await self.analyzer.get_overall_stats(bot_id=bot_id, days=days)

            # 거래가 없으면 빈 컨텍스트 반환
            if stats.total_trades == 0:
                self._log.info("거래 데이터 없음 - 빈 컨텍스트 반환")
                return MemoryContext.empty()

            # 2. 조건별 통계 수집
            rsi_stats = await self.analyzer.get_rsi_condition_stats(
                bot_id=bot_id, days=days
            )
            hourly_stats = await self.analyzer.get_hourly_stats(
                bot_id=bot_id, days=days
            )

            # 3. 연승/연패 및 최근 거래
            streak = await self.analyzer.get_current_streak(bot_id=bot_id)
            recent = await self.analyzer.get_recent_trade_summary(
                limit=10, bot_id=bot_id
            )

            # 4. 컨텍스트 생성
            context = MemoryContext(
                overall_summary=self._build_overall_summary(stats, days),
                recent_performance=self._build_recent_performance(recent, streak),
                best_conditions=self._build_best_conditions(rsi_stats, hourly_stats),
                worst_conditions=self._build_worst_conditions(rsi_stats, hourly_stats),
                timing_insights=self._build_timing_insights(hourly_stats),
                recommendations=self._build_recommendations(rsi_stats, hourly_stats),
            )

            self._log.info(
                f"메모리 컨텍스트 생성 완료: {stats.total_trades}거래, "
                f"승률 {stats.win_rate:.1f}%"
            )
            return context

        except Exception as e:
            self._log.error(f"메모리 컨텍스트 생성 실패: {e}")
            return MemoryContext.empty()

    def _build_overall_summary(self, stats: TradingStats, days: int) -> str:
        """전체 요약 생성

        Args:
            stats: 거래 통계
            days: 분석 기간

        Returns:
            전체 요약 문자열
        """
        pnl_sign = "+" if stats.total_pnl >= 0 else ""
        return (
            f"{days}일간: {stats.total_trades}거래, "
            f"승률 {stats.win_rate:.1f}%, "
            f"{pnl_sign}${stats.total_pnl:.2f}"
        )

    def _build_recent_performance(
        self,
        recent: Dict[str, Any],
        streak: Dict[str, Any],
    ) -> str:
        """최근 성과 생성

        Args:
            recent: 최근 거래 요약
            streak: 연승/연패 정보

        Returns:
            최근 성과 문자열
        """
        summary = recent.get("summary", {})
        count = summary.get("count", 0)
        winners = summary.get("winners", 0)
        losers = summary.get("losers", 0)

        parts = [f"최근 {count}개: {winners}승 {losers}패"]

        streak_type = streak.get("streak_type")
        streak_count = streak.get("streak_count", 0)
        if streak_type and streak_count > 0:
            streak_text = "연속" if streak_count > 1 else ""
            if streak_type == "WIN":
                parts.append(f"{streak_text} {streak_count}승 중")
            else:
                parts.append(f"{streak_text} {streak_count}패 중")

        return ", ".join(parts)

    def _build_best_conditions(
        self,
        rsi_stats: List[RSIConditionStats],
        hourly_stats: List[TimeBasedStats],
    ) -> str:
        """최적 조건 생성

        Args:
            rsi_stats: RSI 조건별 통계
            hourly_stats: 시간대별 통계

        Returns:
            최적 조건 문자열
        """
        best_conditions = []

        # RSI 최적 조건 (승률 70% 이상, 샘플 5개 이상)
        for stat in rsi_stats:
            if stat.total_trades >= 5 and stat.win_rate >= 70:
                zone_desc = self._get_rsi_short_desc(stat.rsi_zone)
                best_conditions.append(
                    f"{stat.side} {zone_desc} (승률 {stat.win_rate:.1f}%)"
                )

        # 시간대 최적 조건 (승률 75% 이상, 샘플 5개 이상)
        for hourly_stat in hourly_stats:
            if hourly_stat.total_trades >= 5 and hourly_stat.win_rate >= 75:
                best_conditions.append(
                    f"{hourly_stat.side} {hourly_stat.hour_of_day}시 (승률 {hourly_stat.win_rate:.1f}%)"
                )

        if not best_conditions:
            return "충분한 데이터 없음"

        # 상위 3개만 반환
        return " | ".join(best_conditions[:3])

    def _build_worst_conditions(
        self,
        rsi_stats: List[RSIConditionStats],
        hourly_stats: List[TimeBasedStats],
    ) -> str:
        """피해야 할 조건 생성

        Args:
            rsi_stats: RSI 조건별 통계
            hourly_stats: 시간대별 통계

        Returns:
            피해야 할 조건 문자열
        """
        worst_conditions = []

        # RSI 최악 조건 (승률 40% 이하, 샘플 5개 이상)
        for stat in rsi_stats:
            if stat.total_trades >= 5 and stat.win_rate <= 40:
                zone_desc = self._get_rsi_short_desc(stat.rsi_zone)
                worst_conditions.append(
                    f"{stat.side} {zone_desc} (승률 {stat.win_rate:.1f}%)"
                )

        # 시간대 최악 조건 (승률 35% 이하, 샘플 5개 이상)
        for hourly_stat in hourly_stats:
            if hourly_stat.total_trades >= 5 and hourly_stat.win_rate <= 35:
                worst_conditions.append(
                    f"{hourly_stat.side} {hourly_stat.hour_of_day}시 (승률 {hourly_stat.win_rate:.1f}%)"
                )

        if not worst_conditions:
            return "특별히 피해야 할 조건 없음"

        # 상위 3개만 반환
        return " | ".join(worst_conditions[:3])

    def _build_timing_insights(
        self,
        hourly_stats: List[TimeBasedStats],
    ) -> str:
        """타이밍 인사이트 생성

        Args:
            hourly_stats: 시간대별 통계

        Returns:
            타이밍 인사이트 문자열
        """
        if not hourly_stats:
            return "시간대별 데이터 없음"

        # 승률 기준 정렬
        sorted_stats = sorted(hourly_stats, key=lambda x: x.win_rate, reverse=True)

        # 최적/최악 시간대
        best_hours = [s for s in sorted_stats if s.win_rate >= 70 and s.total_trades >= 3]
        worst_hours = [s for s in sorted_stats if s.win_rate <= 35 and s.total_trades >= 3]

        parts = []
        if best_hours:
            hours_str = ", ".join([f"{h.hour_of_day}시" for h in best_hours[:3]])
            parts.append(f"최적: {hours_str}")

        if worst_hours:
            hours_str = ", ".join([f"{h.hour_of_day}시" for h in worst_hours[:3]])
            parts.append(f"피해야 할: {hours_str}")

        return " | ".join(parts) if parts else "특별한 시간대 패턴 없음"

    def _build_recommendations(
        self,
        rsi_stats: List[RSIConditionStats],
        hourly_stats: List[TimeBasedStats],
    ) -> str:
        """추천 생성

        Args:
            rsi_stats: RSI 조건별 통계
            hourly_stats: 시간대별 통계

        Returns:
            추천 문자열
        """
        recommendations = []

        # LONG 최적 RSI 조건
        long_rsi = [
            s for s in rsi_stats
            if s.side == "LONG" and s.win_rate >= 70 and s.total_trades >= 5
        ]
        if long_rsi:
            best = max(long_rsi, key=lambda x: x.win_rate)
            zone_desc = self._get_rsi_short_desc(best.rsi_zone)
            recommendations.append(f"LONG 추천: {zone_desc}")

        # SHORT 최적 RSI 조건
        short_rsi = [
            s for s in rsi_stats
            if s.side == "SHORT" and s.win_rate >= 70 and s.total_trades >= 5
        ]
        if short_rsi:
            best = max(short_rsi, key=lambda x: x.win_rate)
            zone_desc = self._get_rsi_short_desc(best.rsi_zone)
            recommendations.append(f"SHORT 추천: {zone_desc}")

        # 최적 시간대
        best_hours = [
            h for h in hourly_stats
            if h.win_rate >= 75 and h.total_trades >= 5
        ]
        if best_hours:
            best_hour = max(best_hours, key=lambda x: x.win_rate)
            recommendations.append(f"최적 시간: {best_hour.hour_of_day}시")

        return " | ".join(recommendations) if recommendations else "충분한 패턴 데이터 없음"

    def _get_rsi_short_desc(self, zone: str) -> str:
        """RSI 구간 짧은 설명 반환"""
        zone_descriptions = {
            "oversold": "RSI<30",
            "low": "RSI 30-40",
            "neutral": "RSI 40-60",
            "high": "RSI 60-70",
            "overbought": "RSI>70",
            "unknown": "RSI 알 수 없음",
        }
        return zone_descriptions.get(zone, zone)
