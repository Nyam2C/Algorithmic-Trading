"""
거래 이력 분석기 (TradeHistoryAnalyzer)

Phase 4: AI 메모리 시스템 - 과거 거래 성과 분석
거래 이력을 분석하여 AI에게 "기억"으로 제공할 통계와 패턴을 생성

Phase 6.2: 통계적 신뢰도 개선
- 최소 샘플 수 5 → 30
- 95% 신뢰구간 계산
- p-value 통계적 유의성 검정
"""
import math
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
from loguru import logger

from src.storage.trade_history import TradeHistoryDB


# ============================================================================
# Phase 6.2: 통계적 신뢰도 관련 상수 및 클래스
# ============================================================================

# 최소 샘플 수 (Phase 6.2: 5 → 30)
MIN_SAMPLE_SIZE = 30
MIN_SAMPLE_SIZE_RELAXED = 10  # 완화된 최소 샘플 (참고용)

# Z-score for 95% confidence
Z_95 = 1.96


@dataclass
class StatisticalInsight:
    """통계적 인사이트

    Phase 6.2: 신뢰도 정보가 포함된 인사이트

    Attributes:
        metric: 메트릭 이름 (예: "win_rate")
        value: 측정 값
        sample_size: 샘플 수
        confidence_level: 신뢰 수준 (0.95 = 95%)
        lower_bound: 신뢰 구간 하한
        upper_bound: 신뢰 구간 상한
        is_statistically_significant: 통계적 유의성 여부
        p_value: p-value (선택)
    """

    metric: str
    value: float
    sample_size: int
    confidence_level: float = 0.95
    lower_bound: float = 0.0
    upper_bound: float = 0.0
    is_statistically_significant: bool = False
    p_value: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return asdict(self)

    @classmethod
    def from_win_rate(
        cls,
        wins: int,
        total: int,
        baseline: float = 0.5,
    ) -> "StatisticalInsight":
        """승률에서 통계적 인사이트 생성

        Args:
            wins: 승리 수
            total: 총 거래 수
            baseline: 기준 승률 (기본 50%)

        Returns:
            StatisticalInsight
        """
        if total == 0:
            return cls(
                metric="win_rate",
                value=0.0,
                sample_size=0,
                is_statistically_significant=False,
            )

        # 승률 계산
        win_rate = wins / total

        # 95% 신뢰 구간 (Wilson score interval)
        z = Z_95
        denominator = 1 + z * z / total
        center = (win_rate + z * z / (2 * total)) / denominator
        spread = z * math.sqrt(
            (win_rate * (1 - win_rate) + z * z / (4 * total)) / total
        ) / denominator

        lower = max(0, center - spread)
        upper = min(1, center + spread)

        # p-value 계산 (z-test for proportion)
        if total >= MIN_SAMPLE_SIZE_RELAXED:
            se = math.sqrt(baseline * (1 - baseline) / total)
            if se > 0:
                z_stat = (win_rate - baseline) / se
                # 양측 검정 p-value (근사값)
                p_value = 2 * (1 - _normal_cdf(abs(z_stat)))
            else:
                p_value = 1.0
        else:
            p_value = None

        # 통계적 유의성: 샘플 충분하고 신뢰구간이 baseline과 겹치지 않음
        is_significant = (
            total >= MIN_SAMPLE_SIZE and
            (upper < baseline or lower > baseline)
        )

        return cls(
            metric="win_rate",
            value=win_rate * 100,  # 퍼센트로 변환
            sample_size=total,
            confidence_level=0.95,
            lower_bound=lower * 100,
            upper_bound=upper * 100,
            is_statistically_significant=is_significant,
            p_value=p_value,
        )


def _normal_cdf(x: float) -> float:
    """표준 정규 분포 CDF (근사값)"""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def calculate_confidence_interval(
    values: List[float],
    confidence: float = 0.95,
) -> tuple:
    """평균의 신뢰 구간 계산

    Args:
        values: 값 리스트
        confidence: 신뢰 수준 (기본 95%)

    Returns:
        (mean, lower_bound, upper_bound, std_error)
    """
    n = len(values)
    if n == 0:
        return 0.0, 0.0, 0.0, 0.0

    mean = sum(values) / n

    if n == 1:
        return mean, mean, mean, 0.0

    # 표준 편차
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    std_dev = math.sqrt(variance)

    # 표준 오차
    std_error = std_dev / math.sqrt(n)

    # t-분포 대신 z-score 사용 (n >= 30 가정)
    z = Z_95 if confidence == 0.95 else 1.645  # 90%

    margin = z * std_error
    lower = mean - margin
    upper = mean + margin

    return mean, lower, upper, std_error


@dataclass
class TradingStats:
    """종합 거래 통계

    전체 거래 성과를 요약하는 데이터 클래스
    """

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

    @classmethod
    def empty(cls) -> "TradingStats":
        """빈 통계 반환"""
        return cls(
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            total_pnl=0.0,
            avg_pnl=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            profit_factor=0.0,
            avg_duration_minutes=0.0,
            best_trade_pnl=0.0,
            worst_trade_pnl=0.0,
            long_trades=0,
            short_trades=0,
            long_win_rate=0.0,
            short_win_rate=0.0,
        )

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return asdict(self)


@dataclass
class ExitReasonStats:
    """청산 사유별 통계"""

    exit_reason: str
    side: str
    total_trades: int
    winning_trades: int
    win_rate: float
    avg_pnl: float
    total_pnl: float
    avg_duration_minutes: float

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return asdict(self)


@dataclass
class RSIConditionStats:
    """RSI 조건별 통계"""

    rsi_zone: str  # oversold, low, neutral, high, overbought
    side: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_pnl: float
    total_pnl: float
    avg_duration_minutes: float

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return asdict(self)


@dataclass
class TimeBasedStats:
    """시간대별 통계"""

    hour_of_day: int
    side: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_pnl: float
    total_pnl: float

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return asdict(self)


@dataclass
class PatternInsight:
    """패턴 인사이트

    분석된 성공/실패 패턴 정보

    Phase 6.2: 신뢰도 정보 추가
    """

    pattern_type: str  # rsi_zone, hourly, exit_reason
    description: str  # 한글 설명
    side: str
    condition: str  # 조건 (예: rsi_zone=oversold)
    sample_size: int
    win_rate: float
    avg_pnl: float
    recommendation: str  # AI에게 전달할 추천 메시지
    # Phase 6.2: 신뢰도 정보
    confidence_level: str = "LOW"  # LOW, MEDIUM, HIGH
    win_rate_lower: float = 0.0  # 95% CI 하한
    win_rate_upper: float = 0.0  # 95% CI 상한
    is_statistically_significant: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return asdict(self)

    @classmethod
    def with_confidence(
        cls,
        pattern_type: str,
        description: str,
        side: str,
        condition: str,
        wins: int,
        total: int,
        avg_pnl: float,
        recommendation: str,
    ) -> "PatternInsight":
        """신뢰도 정보가 포함된 인사이트 생성

        Args:
            pattern_type: 패턴 타입
            description: 설명
            side: 방향
            condition: 조건
            wins: 승리 수
            total: 총 거래 수
            avg_pnl: 평균 손익
            recommendation: 추천 메시지

        Returns:
            PatternInsight
        """
        stat_insight = StatisticalInsight.from_win_rate(wins, total)

        # 신뢰도 레벨 결정
        if total >= MIN_SAMPLE_SIZE and stat_insight.is_statistically_significant:
            confidence_level = "HIGH"
        elif total >= MIN_SAMPLE_SIZE_RELAXED:
            confidence_level = "MEDIUM"
        else:
            confidence_level = "LOW"

        return cls(
            pattern_type=pattern_type,
            description=description,
            side=side,
            condition=condition,
            sample_size=total,
            win_rate=stat_insight.value,
            avg_pnl=avg_pnl,
            recommendation=recommendation,
            confidence_level=confidence_level,
            win_rate_lower=stat_insight.lower_bound,
            win_rate_upper=stat_insight.upper_bound,
            is_statistically_significant=stat_insight.is_statistically_significant,
        )


class TradeHistoryAnalyzer:
    """거래 이력 분석기

    PostgreSQL에 저장된 거래 이력을 분석하여 통계와 패턴을 생성합니다.
    AI 메모리 컨텍스트 생성에 필요한 데이터를 제공합니다.

    Example:
        >>> analyzer = TradeHistoryAnalyzer(trade_db)
        >>> stats = await analyzer.get_overall_stats(bot_id="btc-bot", days=7)
        >>> print(f"승률: {stats.win_rate}%")
    """

    def __init__(self, db: TradeHistoryDB) -> None:
        """분석기 초기화

        Args:
            db: TradeHistoryDB 인스턴스
        """
        self.db = db
        self._log = logger.bind(module="trade_analyzer")

    async def get_overall_stats(
        self,
        bot_id: Optional[str] = None,
        days: int = 7,
    ) -> TradingStats:
        """전체 거래 통계 조회

        Args:
            bot_id: 봇 ID (선택, 미지정 시 전체)
            days: 조회 기간 (일)

        Returns:
            TradingStats: 종합 거래 통계
        """
        if self.db.pool is None:
            raise RuntimeError("Database pool not initialized. Call connect() first.")

        async with self.db.pool.acquire() as conn:
            # DB 함수 호출
            if bot_id:
                row = await conn.fetchrow(
                    "SELECT * FROM get_trading_summary($1::uuid, $2)",
                    bot_id,
                    days,
                )
            else:
                row = await conn.fetchrow(
                    "SELECT * FROM get_trading_summary(NULL, $1)",
                    days,
                )

            if row is None or row["total_trades"] is None or row["total_trades"] == 0:
                self._log.debug("거래 없음 - 빈 통계 반환")
                return TradingStats.empty()

            return TradingStats(
                total_trades=int(row["total_trades"]),
                winning_trades=int(row["winning_trades"]),
                losing_trades=int(row["losing_trades"]),
                win_rate=float(row["win_rate"]),
                total_pnl=float(row["total_pnl"]),
                avg_pnl=float(row["avg_pnl"]),
                avg_win=float(row["avg_win"]),
                avg_loss=float(row["avg_loss"]),
                profit_factor=float(row["profit_factor"]),
                avg_duration_minutes=float(row["avg_duration_minutes"]),
                best_trade_pnl=float(row["best_trade_pnl"]),
                worst_trade_pnl=float(row["worst_trade_pnl"]),
                long_trades=int(row["long_trades"]),
                short_trades=int(row["short_trades"]),
                long_win_rate=float(row["long_win_rate"]),
                short_win_rate=float(row["short_win_rate"]),
            )

    async def get_exit_reason_stats(
        self,
        bot_id: Optional[str] = None,
        days: int = 7,
    ) -> List[ExitReasonStats]:
        """청산 사유별 통계 조회

        Args:
            bot_id: 봇 ID (선택)
            days: 조회 기간 (일)

        Returns:
            List[ExitReasonStats]: 청산 사유별 통계 목록
        """
        if self.db.pool is None:
            raise RuntimeError("Database pool not initialized. Call connect() first.")

        async with self.db.pool.acquire() as conn:
            if bot_id:
                rows = await conn.fetch(
                    "SELECT * FROM get_exit_reason_stats($1::uuid, $2)",
                    bot_id,
                    days,
                )
            else:
                rows = await conn.fetch(
                    "SELECT * FROM get_exit_reason_stats(NULL, $1)",
                    days,
                )

            return [
                ExitReasonStats(
                    exit_reason=str(row["exit_reason"]),
                    side=str(row["side"]),
                    total_trades=int(row["total_trades"]),
                    winning_trades=int(row["winning_trades"]),
                    win_rate=float(row["win_rate"]),
                    avg_pnl=float(row["avg_pnl"]),
                    total_pnl=float(row["total_pnl"]),
                    avg_duration_minutes=float(row["avg_duration_minutes"]),
                )
                for row in rows
            ]

    async def get_rsi_condition_stats(
        self,
        bot_id: Optional[str] = None,
        days: int = 7,
    ) -> List[RSIConditionStats]:
        """RSI 조건별 통계 조회

        Args:
            bot_id: 봇 ID (선택)
            days: 조회 기간 (일)

        Returns:
            List[RSIConditionStats]: RSI 조건별 통계 목록
        """
        if self.db.pool is None:
            raise RuntimeError("Database pool not initialized. Call connect() first.")

        async with self.db.pool.acquire() as conn:
            if bot_id:
                rows = await conn.fetch(
                    "SELECT * FROM get_rsi_performance($1::uuid, $2)",
                    bot_id,
                    days,
                )
            else:
                rows = await conn.fetch(
                    "SELECT * FROM get_rsi_performance(NULL, $1)",
                    days,
                )

            return [
                RSIConditionStats(
                    rsi_zone=str(row["rsi_zone"]),
                    side=str(row["side"]),
                    total_trades=int(row["total_trades"]),
                    winning_trades=int(row["winning_trades"]),
                    losing_trades=int(row["losing_trades"]),
                    win_rate=float(row["win_rate"]),
                    avg_pnl=float(row["avg_pnl"]),
                    total_pnl=float(row["total_pnl"]),
                    avg_duration_minutes=float(row["avg_duration_minutes"]),
                )
                for row in rows
            ]

    async def get_hourly_stats(
        self,
        bot_id: Optional[str] = None,
        days: int = 7,
    ) -> List[TimeBasedStats]:
        """시간대별 통계 조회

        Args:
            bot_id: 봇 ID (선택)
            days: 조회 기간 (일)

        Returns:
            List[TimeBasedStats]: 시간대별 통계 목록
        """
        if self.db.pool is None:
            raise RuntimeError("Database pool not initialized. Call connect() first.")

        async with self.db.pool.acquire() as conn:
            if bot_id:
                rows = await conn.fetch(
                    "SELECT * FROM get_hourly_performance($1::uuid, $2)",
                    bot_id,
                    days,
                )
            else:
                rows = await conn.fetch(
                    "SELECT * FROM get_hourly_performance(NULL, $1)",
                    days,
                )

            return [
                TimeBasedStats(
                    hour_of_day=int(row["hour_of_day"]),
                    side=str(row["side"]),
                    total_trades=int(row["total_trades"]),
                    winning_trades=int(row["winning_trades"]),
                    losing_trades=int(row["total_trades"]) - int(row["winning_trades"]),
                    win_rate=float(row["win_rate"]),
                    avg_pnl=float(row["avg_pnl"]),
                    total_pnl=float(row["total_pnl"]),
                )
                for row in rows
            ]

    async def get_recent_trade_summary(
        self,
        limit: int = 10,
        bot_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """최근 거래 요약 조회

        Args:
            limit: 조회할 거래 수
            bot_id: 봇 ID (선택)

        Returns:
            Dict: 최근 거래 목록과 요약 정보
        """
        trades = await self.db.get_recent_trades(limit=limit, bot_id=bot_id)

        if not trades:
            return {
                "trades": [],
                "summary": {
                    "count": 0,
                    "winners": 0,
                    "losers": 0,
                    "total_pnl": 0.0,
                },
            }

        # 요약 계산
        winners = sum(1 for t in trades if t.get("pnl", 0) > 0)
        losers = len(trades) - winners
        total_pnl = sum(float(t.get("pnl", 0)) for t in trades)

        return {
            "trades": trades,
            "summary": {
                "count": len(trades),
                "winners": winners,
                "losers": losers,
                "total_pnl": total_pnl,
            },
        }

    async def get_current_streak(
        self,
        bot_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """현재 연승/연패 조회

        Args:
            bot_id: 봇 ID (선택)

        Returns:
            Dict: 연승/연패 정보
        """
        if self.db.pool is None:
            raise RuntimeError("Database pool not initialized. Call connect() first.")

        async with self.db.pool.acquire() as conn:
            if bot_id:
                row = await conn.fetchrow(
                    "SELECT * FROM get_current_streak($1::uuid)",
                    bot_id,
                )
            else:
                row = await conn.fetchrow(
                    "SELECT * FROM get_current_streak(NULL)",
                )

            if row is None or row["streak_type"] is None:
                return {
                    "streak_type": None,
                    "streak_count": 0,
                    "last_trade_time": None,
                }

            return {
                "streak_type": row["streak_type"],
                "streak_count": row["streak_count"],
                "last_trade_time": row["last_trade_time"],
            }

    async def get_pattern_insights(
        self,
        bot_id: Optional[str] = None,
        days: int = 7,
        min_sample_size: int = MIN_SAMPLE_SIZE,  # Phase 6.2: 5 → 30
        min_win_rate: float = 70.0,
        require_significance: bool = False,
    ) -> List[PatternInsight]:
        """패턴 인사이트 생성

        높은 승률을 보이는 조건들을 분석하여 인사이트 생성

        Phase 6.2: 통계적 신뢰도 정보 추가

        Args:
            bot_id: 봇 ID (선택)
            days: 조회 기간 (일)
            min_sample_size: 최소 샘플 수 (기본 30)
            min_win_rate: 최소 승률 (%)
            require_significance: 통계적 유의성 필수 여부

        Returns:
            List[PatternInsight]: 패턴 인사이트 목록
        """
        insights: List[PatternInsight] = []

        # RSI 조건별 분석
        rsi_stats = await self.get_rsi_condition_stats(bot_id=bot_id, days=days)
        for stat in rsi_stats:
            if stat.total_trades >= min_sample_size and stat.win_rate >= min_win_rate:
                zone_desc = self._get_rsi_zone_description(stat.rsi_zone)

                # Phase 6.2: 신뢰도 정보 포함
                insight = PatternInsight.with_confidence(
                    pattern_type="rsi_zone",
                    description=f"{zone_desc}에서 {stat.side} 진입",
                    side=stat.side,
                    condition=f"rsi_zone={stat.rsi_zone}",
                    wins=stat.winning_trades,
                    total=stat.total_trades,
                    avg_pnl=stat.avg_pnl,
                    recommendation=f"{zone_desc}에서 {stat.side} 진입 권장 (승률 {stat.win_rate:.1f}%)",
                )

                # 통계적 유의성 필터링
                if require_significance and not insight.is_statistically_significant:
                    continue

                insights.append(insight)

        # 시간대별 분석
        hourly_stats = await self.get_hourly_stats(bot_id=bot_id, days=days)
        for hourly_stat in hourly_stats:
            if hourly_stat.total_trades >= min_sample_size and hourly_stat.win_rate >= min_win_rate:
                insight = PatternInsight.with_confidence(
                    pattern_type="hourly",
                    description=f"{hourly_stat.hour_of_day}시에 {hourly_stat.side} 진입",
                    side=hourly_stat.side,
                    condition=f"hour={hourly_stat.hour_of_day}",
                    wins=hourly_stat.winning_trades,
                    total=hourly_stat.total_trades,
                    avg_pnl=hourly_stat.avg_pnl,
                    recommendation=f"{hourly_stat.hour_of_day}시에 {hourly_stat.side} 진입 권장 (승률 {hourly_stat.win_rate:.1f}%)",
                )

                if require_significance and not insight.is_statistically_significant:
                    continue

                insights.append(insight)

        # Phase 6.2: 신뢰도 + 승률 기준 정렬
        insights.sort(
            key=lambda x: (x.is_statistically_significant, x.win_rate),
            reverse=True,
        )

        return insights

    async def get_worst_patterns(
        self,
        bot_id: Optional[str] = None,
        days: int = 7,
        min_sample_size: int = MIN_SAMPLE_SIZE,  # Phase 6.2: 5 → 30
        max_win_rate: float = 40.0,
        require_significance: bool = False,
    ) -> List[PatternInsight]:
        """피해야 할 패턴 분석

        낮은 승률을 보이는 조건들을 분석

        Phase 6.2: 통계적 신뢰도 정보 추가

        Args:
            bot_id: 봇 ID (선택)
            days: 조회 기간 (일)
            min_sample_size: 최소 샘플 수 (기본 30)
            max_win_rate: 최대 승률 (%)
            require_significance: 통계적 유의성 필수 여부

        Returns:
            List[PatternInsight]: 피해야 할 패턴 목록
        """
        insights: List[PatternInsight] = []

        # RSI 조건별 분석
        rsi_stats = await self.get_rsi_condition_stats(bot_id=bot_id, days=days)
        for stat in rsi_stats:
            if stat.total_trades >= min_sample_size and stat.win_rate <= max_win_rate:
                zone_desc = self._get_rsi_zone_description(stat.rsi_zone)

                insight = PatternInsight.with_confidence(
                    pattern_type="rsi_zone",
                    description=f"{zone_desc}에서 {stat.side} 진입",
                    side=stat.side,
                    condition=f"rsi_zone={stat.rsi_zone}",
                    wins=stat.winning_trades,
                    total=stat.total_trades,
                    avg_pnl=stat.avg_pnl,
                    recommendation=f"{zone_desc}에서 {stat.side} 진입 피해야 함 (승률 {stat.win_rate:.1f}%)",
                )

                if require_significance and not insight.is_statistically_significant:
                    continue

                insights.append(insight)

        # 시간대별 분석
        hourly_stats = await self.get_hourly_stats(bot_id=bot_id, days=days)
        for hourly_stat in hourly_stats:
            if hourly_stat.total_trades >= min_sample_size and hourly_stat.win_rate <= max_win_rate:
                insight = PatternInsight.with_confidence(
                    pattern_type="hourly",
                    description=f"{hourly_stat.hour_of_day}시에 {hourly_stat.side} 진입",
                    side=hourly_stat.side,
                    condition=f"hour={hourly_stat.hour_of_day}",
                    wins=hourly_stat.winning_trades,
                    total=hourly_stat.total_trades,
                    avg_pnl=hourly_stat.avg_pnl,
                    recommendation=f"{hourly_stat.hour_of_day}시에 {hourly_stat.side} 진입 피해야 함 (승률 {hourly_stat.win_rate:.1f}%)",
                )

                if require_significance and not insight.is_statistically_significant:
                    continue

                insights.append(insight)

        # Phase 6.2: 신뢰도 + 승률 기준 정렬 (나쁜 패턴 먼저)
        insights.sort(
            key=lambda x: (-int(x.is_statistically_significant), x.win_rate),
        )

        return insights

    def _get_rsi_zone_description(self, zone: str) -> str:
        """RSI 구간 한글 설명 반환"""
        zone_descriptions = {
            "oversold": "RSI 30 이하 (과매도)",
            "low": "RSI 30-40 (저점)",
            "neutral": "RSI 40-60 (중립)",
            "high": "RSI 60-70 (고점)",
            "overbought": "RSI 70 이상 (과매수)",
            "unknown": "RSI 알 수 없음",
        }
        return zone_descriptions.get(zone, zone)
