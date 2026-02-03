"""
신호 추적 시스템 (SignalTracker)

Phase 6.1: 신호 추적 시스템
- 모든 AI/규칙 기반 신호 기록
- 신호 성과 추적 및 통계 계산
- 소스별 승률 분석
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

from loguru import logger


@dataclass
class SignalRecord:
    """신호 기록

    개별 신호의 모든 정보를 저장하는 데이터 클래스

    Attributes:
        signal_id: 신호 고유 ID
        timestamp: 신호 생성 시간
        bot_id: 봇 ID
        signal: 신호 종류 (LONG, SHORT, WAIT)
        source: 신호 소스 (rule_based, gemini, memory_gemini, ensemble)
        market_conditions: 시장 상황 데이터
        trade_result: 거래 결과 (win, loss, None)
        pnl: 손익
        reason: 신호 생성 이유
    """

    signal_id: str
    timestamp: datetime
    bot_id: str
    signal: str  # LONG, SHORT, WAIT
    source: str  # rule_based, gemini, memory_gemini, ensemble
    market_conditions: Dict[str, Any] = field(default_factory=dict)
    trade_result: Optional[str] = None  # win, loss, None
    pnl: Optional[float] = None
    reason: Optional[str] = None

    @classmethod
    def create(
        cls,
        bot_id: str,
        signal: str,
        source: str,
        market_conditions: Optional[Dict[str, Any]] = None,
        reason: Optional[str] = None,
    ) -> "SignalRecord":
        """신호 기록 생성

        Args:
            bot_id: 봇 ID
            signal: 신호 종류
            source: 신호 소스
            market_conditions: 시장 상황
            reason: 신호 생성 이유

        Returns:
            SignalRecord 인스턴스
        """
        return cls(
            signal_id=str(uuid4()),
            timestamp=datetime.now(),
            bot_id=bot_id,
            signal=signal,
            source=source,
            market_conditions=market_conditions or {},
            reason=reason,
        )

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data

    def update_result(self, result: str, pnl: float) -> None:
        """거래 결과 업데이트

        Args:
            result: 결과 (win, loss)
            pnl: 손익
        """
        self.trade_result = result
        self.pnl = pnl


@dataclass
class SignalStats:
    """신호 통계

    신호 성과 요약 통계

    Attributes:
        total_signals: 총 신호 수
        traded_signals: 실제 거래된 신호 수
        wins: 승리 수
        losses: 패배 수
        win_rate: 승률 (%)
        total_pnl: 총 손익
        avg_pnl: 평균 손익
        best_pnl: 최고 손익
        worst_pnl: 최저 손익
    """

    total_signals: int = 0
    traded_signals: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    avg_pnl: float = 0.0
    best_pnl: float = 0.0
    worst_pnl: float = 0.0

    def calculate(self) -> None:
        """통계 계산"""
        if self.traded_signals > 0:
            self.win_rate = (self.wins / self.traded_signals) * 100
            self.avg_pnl = self.total_pnl / self.traded_signals

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "total_signals": self.total_signals,
            "traded_signals": self.traded_signals,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": round(self.win_rate, 2),
            "total_pnl": round(self.total_pnl, 2),
            "avg_pnl": round(self.avg_pnl, 2),
            "best_pnl": round(self.best_pnl, 2),
            "worst_pnl": round(self.worst_pnl, 2),
        }


class SignalTracker:
    """신호 추적기

    모든 신호를 기록하고 성과를 추적합니다.

    Example:
        >>> tracker = SignalTracker()
        >>> signal_id = await tracker.record_signal(
        ...     bot_id="btc-bot",
        ...     signal="LONG",
        ...     source="gemini",
        ...     market_conditions={"rsi": 35.5},
        ...     reason="RSI 과매도 구간"
        ... )
        >>> await tracker.update_signal_result(signal_id, "win", 125.50)
        >>> stats = await tracker.get_signal_stats("btc-bot", "gemini", days=7)
    """

    def __init__(self, db_pool: Optional[Any] = None) -> None:
        """추적기 초기화

        Args:
            db_pool: asyncpg 연결 풀 (PostgreSQL)
        """
        self.db_pool = db_pool
        self._in_memory_signals: Dict[str, SignalRecord] = {}
        self._log = logger.bind(module="signal_tracker")
        self._log.info("SignalTracker 초기화 완료")

    def set_db_pool(self, pool: Any) -> None:
        """DB 연결 풀 설정

        Args:
            pool: asyncpg 연결 풀
        """
        self.db_pool = pool
        self._log.info("DB 연결 풀 설정 완료")

    async def record_signal(
        self,
        bot_id: str,
        signal: str,
        source: str,
        market_conditions: Optional[Dict[str, Any]] = None,
        reason: Optional[str] = None,
    ) -> str:
        """신호 기록

        Args:
            bot_id: 봇 ID
            signal: 신호 (LONG, SHORT, WAIT)
            source: 신호 소스
            market_conditions: 시장 상황
            reason: 신호 생성 이유

        Returns:
            신호 ID
        """
        record = SignalRecord.create(
            bot_id=bot_id,
            signal=signal,
            source=source,
            market_conditions=market_conditions,
            reason=reason,
        )

        # DB 저장 시도
        if self.db_pool is not None:
            try:
                await self._save_to_db(record)
            except Exception as e:
                self._log.warning(f"DB 저장 실패, 인메모리 저장: {e}")
                self._in_memory_signals[record.signal_id] = record
        else:
            # 인메모리 저장
            self._in_memory_signals[record.signal_id] = record

        self._log.debug(
            f"신호 기록: {signal} ({source}) - {record.signal_id[:8]}..."
        )
        return record.signal_id

    async def _save_to_db(self, record: SignalRecord) -> None:
        """DB에 신호 저장"""
        import json

        assert self.db_pool is not None, "db_pool is required for DB operations"
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO signal_history (
                    id, timestamp, bot_id, signal, source,
                    market_conditions, reason
                ) VALUES ($1, $2, $3::uuid, $4, $5, $6::jsonb, $7)
                """,
                record.signal_id,
                record.timestamp,
                record.bot_id,
                record.signal,
                record.source,
                json.dumps(record.market_conditions),
                record.reason,
            )

    async def update_signal_result(
        self,
        signal_id: str,
        result: str,
        pnl: float,
    ) -> bool:
        """신호 결과 업데이트

        Args:
            signal_id: 신호 ID
            result: 결과 (win, loss)
            pnl: 손익

        Returns:
            업데이트 성공 여부
        """
        # DB 업데이트 시도
        if self.db_pool is not None:
            try:
                async with self.db_pool.acquire() as conn:
                    await conn.execute(
                        """
                        UPDATE signal_history
                        SET trade_result = $2, pnl = $3, updated_at = NOW()
                        WHERE id = $1
                        """,
                        signal_id,
                        result,
                        pnl,
                    )
                self._log.debug(f"신호 결과 업데이트: {signal_id[:8]}... = {result}")
                return True
            except Exception as e:
                self._log.warning(f"DB 업데이트 실패: {e}")

        # 인메모리 업데이트
        if signal_id in self._in_memory_signals:
            self._in_memory_signals[signal_id].update_result(result, pnl)
            return True

        return False

    async def get_signal_stats(
        self,
        bot_id: Optional[str] = None,
        source: Optional[str] = None,
        days: int = 7,
    ) -> SignalStats:
        """신호 통계 조회

        Args:
            bot_id: 봇 ID (선택)
            source: 신호 소스 (선택)
            days: 조회 기간 (일)

        Returns:
            SignalStats
        """
        if self.db_pool is not None:
            try:
                return await self._get_stats_from_db(bot_id, source, days)
            except Exception as e:
                self._log.warning(f"DB 통계 조회 실패: {e}")

        # 인메모리 통계 계산
        return self._calculate_in_memory_stats(bot_id, source, days)

    async def _get_stats_from_db(
        self,
        bot_id: Optional[str],
        source: Optional[str],
        days: int,
    ) -> SignalStats:
        """DB에서 통계 조회"""
        assert self.db_pool is not None, "db_pool is required for DB operations"
        cutoff = datetime.now() - timedelta(days=days)

        async with self.db_pool.acquire() as conn:
            # 동적 쿼리 빌드
            conditions = ["timestamp >= $1"]
            params: List[Any] = [cutoff]
            param_idx = 2

            if bot_id:
                conditions.append(f"bot_id = ${param_idx}::uuid")
                params.append(bot_id)
                param_idx += 1

            if source:
                conditions.append(f"source = ${param_idx}")
                params.append(source)

            where_clause = " AND ".join(conditions)

            row = await conn.fetchrow(
                f"""
                SELECT
                    COUNT(*) as total_signals,
                    COUNT(*) FILTER (WHERE trade_result IS NOT NULL) as traded_signals,
                    COUNT(*) FILTER (WHERE trade_result = 'win') as wins,
                    COUNT(*) FILTER (WHERE trade_result = 'loss') as losses,
                    COALESCE(SUM(pnl), 0) as total_pnl,
                    COALESCE(MAX(pnl), 0) as best_pnl,
                    COALESCE(MIN(pnl), 0) as worst_pnl
                FROM signal_history
                WHERE {where_clause}
                """,
                *params,
            )

            stats = SignalStats(
                total_signals=row["total_signals"],
                traded_signals=row["traded_signals"],
                wins=row["wins"],
                losses=row["losses"],
                total_pnl=float(row["total_pnl"]),
                best_pnl=float(row["best_pnl"]),
                worst_pnl=float(row["worst_pnl"]),
            )
            stats.calculate()
            return stats

    def _calculate_in_memory_stats(
        self,
        bot_id: Optional[str],
        source: Optional[str],
        days: int,
    ) -> SignalStats:
        """인메모리 통계 계산"""
        cutoff = datetime.now() - timedelta(days=days)
        stats = SignalStats()

        for record in self._in_memory_signals.values():
            # 필터링
            if record.timestamp < cutoff:
                continue
            if bot_id and record.bot_id != bot_id:
                continue
            if source and record.source != source:
                continue

            stats.total_signals += 1

            if record.trade_result is not None:
                stats.traded_signals += 1
                pnl = record.pnl or 0

                if record.trade_result == "win":
                    stats.wins += 1
                else:
                    stats.losses += 1

                stats.total_pnl += pnl

                if pnl > stats.best_pnl:
                    stats.best_pnl = pnl
                if pnl < stats.worst_pnl:
                    stats.worst_pnl = pnl

        stats.calculate()
        return stats

    async def get_win_rate_by_source(
        self,
        days: int = 7,
        bot_id: Optional[str] = None,
    ) -> Dict[str, float]:
        """소스별 승률 조회

        Args:
            days: 조회 기간 (일)
            bot_id: 봇 ID (선택)

        Returns:
            소스별 승률 딕셔너리
        """
        if self.db_pool is not None:
            try:
                return await self._get_win_rate_by_source_from_db(days, bot_id)
            except Exception as e:
                self._log.warning(f"DB 승률 조회 실패: {e}")

        # 인메모리 계산
        return self._calculate_in_memory_win_rate_by_source(days, bot_id)

    async def _get_win_rate_by_source_from_db(
        self,
        days: int,
        bot_id: Optional[str],
    ) -> Dict[str, float]:
        """DB에서 소스별 승률 조회"""
        assert self.db_pool is not None, "db_pool is required for DB operations"
        cutoff = datetime.now() - timedelta(days=days)

        async with self.db_pool.acquire() as conn:
            if bot_id:
                rows = await conn.fetch(
                    """
                    SELECT
                        source,
                        COUNT(*) FILTER (WHERE trade_result IS NOT NULL) as traded,
                        COUNT(*) FILTER (WHERE trade_result = 'win') as wins
                    FROM signal_history
                    WHERE timestamp >= $1 AND bot_id = $2::uuid
                    GROUP BY source
                    """,
                    cutoff,
                    bot_id,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT
                        source,
                        COUNT(*) FILTER (WHERE trade_result IS NOT NULL) as traded,
                        COUNT(*) FILTER (WHERE trade_result = 'win') as wins
                    FROM signal_history
                    WHERE timestamp >= $1
                    GROUP BY source
                    """,
                    cutoff,
                )

            result: Dict[str, float] = {}
            for row in rows:
                traded = row["traded"]
                wins = row["wins"]
                if traded > 0:
                    result[row["source"]] = round((wins / traded) * 100, 2)
                else:
                    result[row["source"]] = 0.0

            return result

    def _calculate_in_memory_win_rate_by_source(
        self,
        days: int,
        bot_id: Optional[str],
    ) -> Dict[str, float]:
        """인메모리 소스별 승률 계산"""
        cutoff = datetime.now() - timedelta(days=days)
        source_stats: Dict[str, Dict[str, int]] = {}

        for record in self._in_memory_signals.values():
            if record.timestamp < cutoff:
                continue
            if bot_id and record.bot_id != bot_id:
                continue
            if record.trade_result is None:
                continue

            if record.source not in source_stats:
                source_stats[record.source] = {"traded": 0, "wins": 0}

            source_stats[record.source]["traded"] += 1
            if record.trade_result == "win":
                source_stats[record.source]["wins"] += 1

        result: Dict[str, float] = {}
        for source, stats in source_stats.items():
            if stats["traded"] > 0:
                result[source] = round((stats["wins"] / stats["traded"]) * 100, 2)
            else:
                result[source] = 0.0

        return result

    async def get_recent_signals(
        self,
        bot_id: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """최근 신호 목록 조회

        Args:
            bot_id: 봇 ID (선택)
            limit: 조회 개수

        Returns:
            신호 목록
        """
        if self.db_pool is not None:
            try:
                return await self._get_recent_signals_from_db(bot_id, limit)
            except Exception as e:
                self._log.warning(f"DB 신호 조회 실패: {e}")

        # 인메모리 조회
        signals = list(self._in_memory_signals.values())

        if bot_id:
            signals = [s for s in signals if s.bot_id == bot_id]

        # 최신순 정렬
        signals.sort(key=lambda x: x.timestamp, reverse=True)

        return [s.to_dict() for s in signals[:limit]]

    async def _get_recent_signals_from_db(
        self,
        bot_id: Optional[str],
        limit: int,
    ) -> List[Dict[str, Any]]:
        """DB에서 최근 신호 조회"""
        assert self.db_pool is not None, "db_pool is required for DB operations"
        async with self.db_pool.acquire() as conn:
            if bot_id:
                rows = await conn.fetch(
                    """
                    SELECT
                        id, timestamp, bot_id, signal, source,
                        market_conditions, trade_result, pnl, reason
                    FROM signal_history
                    WHERE bot_id = $1::uuid
                    ORDER BY timestamp DESC
                    LIMIT $2
                    """,
                    bot_id,
                    limit,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT
                        id, timestamp, bot_id, signal, source,
                        market_conditions, trade_result, pnl, reason
                    FROM signal_history
                    ORDER BY timestamp DESC
                    LIMIT $1
                    """,
                    limit,
                )

            return [
                {
                    "signal_id": str(row["id"]),
                    "timestamp": row["timestamp"].isoformat(),
                    "bot_id": str(row["bot_id"]),
                    "signal": row["signal"],
                    "source": row["source"],
                    "market_conditions": row["market_conditions"] or {},
                    "trade_result": row["trade_result"],
                    "pnl": float(row["pnl"]) if row["pnl"] else None,
                    "reason": row["reason"],
                }
                for row in rows
            ]

    async def cleanup_old_signals(self, days: int = 30) -> int:
        """오래된 신호 정리

        Args:
            days: 보관 기간 (일)

        Returns:
            삭제된 신호 수
        """
        cutoff = datetime.now() - timedelta(days=days)
        deleted = 0

        if self.db_pool is not None:
            try:
                async with self.db_pool.acquire() as conn:
                    result = await conn.execute(
                        """
                        DELETE FROM signal_history
                        WHERE timestamp < $1
                        """,
                        cutoff,
                    )
                    deleted = int(result.split()[-1]) if result else 0
                    self._log.info(f"오래된 신호 정리: {deleted}건 삭제 (DB)")
            except Exception as e:
                self._log.warning(f"DB 정리 실패: {e}")

        # 인메모리 정리
        to_delete = [
            signal_id
            for signal_id, record in self._in_memory_signals.items()
            if record.timestamp < cutoff
        ]
        for signal_id in to_delete:
            del self._in_memory_signals[signal_id]
            deleted += 1

        if to_delete:
            self._log.info(f"오래된 신호 정리: {len(to_delete)}건 삭제 (인메모리)")

        return deleted
