"""
거래 이력 저장소 (PostgreSQL)

모든 거래 진입/청산 기록을 분석 및 리포트용으로 저장
"""
import asyncpg
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from loguru import logger


class TradeHistoryDB:
    """PostgreSQL 거래 이력 데이터베이스"""

    def __init__(self, database_url: str):
        """
        거래 이력 데이터베이스 초기화

        Args:
            database_url: PostgreSQL 연결 URL
        """
        self.database_url = database_url
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """데이터베이스 연결 풀 생성"""
        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=1,
                max_size=10,
                command_timeout=60
            )
            logger.info("PostgreSQL 거래 이력 데이터베이스 연결 완료")

            # 테이블 확인
            await self.create_tables()

        except Exception as e:
            logger.error(f"데이터베이스 연결 실패: {e}")
            raise

    async def disconnect(self):
        """데이터베이스 연결 풀 종료"""
        if self.pool:
            await self.pool.close()
            logger.info("거래 이력 데이터베이스 연결 종료")

    async def create_tables(self):
        """데이터베이스 테이블 확인 - db/init.sql 스키마 사용"""
        # 테이블은 db/init.sql로 생성됨, 연결만 확인
        async with self.pool.acquire() as conn:
            # trades 테이블 존재 확인
            exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'trades'
                )
            """)
            if not exists:
                logger.warning("trades 테이블 없음 - db/init.sql 실행 필요")

            logger.info("거래 이력 테이블 확인 완료")

    async def add_entry(
        self,
        entry_time: datetime,
        entry_price: float,
        side: str,
        quantity: float,
        leverage: int,
        symbol: str = "BTCUSDT"
    ) -> str:
        """
        거래 진입 기록

        Returns:
            거래 ID (UUID)
        """
        async with self.pool.acquire() as conn:
            trade_id = await conn.fetchval("""
                INSERT INTO trades (
                    entry_time, entry_price, side, quantity, leverage, symbol, status
                ) VALUES ($1, $2, $3, $4, $5, $6, 'OPEN')
                RETURNING id
            """, entry_time, entry_price, side, quantity, leverage, symbol)

            logger.info(f"거래 진입 기록: ID={trade_id}, {side} @ ${entry_price}")
            return str(trade_id)

    async def add_exit(
        self,
        trade_id: str,
        exit_time: datetime,
        exit_price: float,
        exit_reason: str,
        pnl: float,
        pnl_pct: float,
        duration_minutes: int = None
    ):
        """거래 청산 기록"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE trades
                SET exit_time = $2,
                    exit_price = $3,
                    exit_reason = $4,
                    pnl = $5,
                    pnl_pct = $6,
                    duration_minutes = $7,
                    status = 'CLOSED',
                    updated_at = NOW()
                WHERE id = $1::uuid
            """, trade_id, exit_time, exit_price, exit_reason, pnl, pnl_pct, duration_minutes)

            logger.info(
                f"거래 청산 기록: ID={trade_id}, "
                f"사유={exit_reason} @ ${exit_price}, "
                f"손익=${pnl:+.2f} ({pnl_pct:+.2f}%)"
            )

    async def get_recent_trades(self, limit: int = 10) -> List[Dict[str, Any]]:
        """최근 완료된 거래 조회"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT
                    id, entry_time, entry_price, exit_time, exit_price,
                    side, quantity, leverage, exit_reason,
                    pnl, pnl_pct, duration_minutes, symbol, status
                FROM trades
                WHERE status = 'CLOSED'
                ORDER BY exit_time DESC
                LIMIT $1
            """, limit)

            return [dict(row) for row in rows]

    async def get_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """
        최근 N시간 동안의 거래 통계 조회

        Returns:
            거래 통계 딕셔너리
        """
        async with self.pool.acquire() as conn:
            cutoff_time = datetime.now() - timedelta(hours=hours)

            # 전체 거래 수
            total_trades = await conn.fetchval("""
                SELECT COUNT(*)
                FROM trades
                WHERE status = 'CLOSED'
                AND exit_time >= $1
            """, cutoff_time)

            if total_trades == 0:
                return {
                    "period_hours": hours,
                    "total_trades": 0,
                    "winners": 0,
                    "losers": 0,
                    "win_rate": 0,
                    "total_pnl": 0,
                    "best_trade": 0,
                    "worst_trade": 0,
                    "long_trades": 0,
                    "short_trades": 0,
                }

            # 수익/손실 거래
            winners = await conn.fetchval("""
                SELECT COUNT(*)
                FROM trades
                WHERE status = 'CLOSED'
                AND exit_time >= $1
                AND pnl > 0
            """, cutoff_time)

            # 총 손익
            total_pnl = await conn.fetchval("""
                SELECT COALESCE(SUM(pnl), 0)
                FROM trades
                WHERE status = 'CLOSED'
                AND exit_time >= $1
            """, cutoff_time)

            # 최고/최저 거래
            best_trade = await conn.fetchval("""
                SELECT COALESCE(MAX(pnl_pct), 0)
                FROM trades
                WHERE status = 'CLOSED'
                AND exit_time >= $1
            """, cutoff_time)

            worst_trade = await conn.fetchval("""
                SELECT COALESCE(MIN(pnl_pct), 0)
                FROM trades
                WHERE status = 'CLOSED'
                AND exit_time >= $1
            """, cutoff_time)

            # 롱 vs 숏
            long_trades = await conn.fetchval("""
                SELECT COUNT(*)
                FROM trades
                WHERE status = 'CLOSED'
                AND exit_time >= $1
                AND side = 'LONG'
            """, cutoff_time)

            losers = total_trades - winners
            win_rate = (winners / total_trades * 100) if total_trades > 0 else 0
            short_trades = total_trades - long_trades

            return {
                "period_hours": hours,
                "total_trades": total_trades,
                "winners": winners,
                "losers": losers,
                "win_rate": round(win_rate, 2),
                "total_pnl": float(total_pnl),
                "best_trade": float(best_trade),
                "worst_trade": float(worst_trade),
                "long_trades": long_trades,
                "short_trades": short_trades,
            }

    async def get_open_trade(self) -> Optional[Dict[str, Any]]:
        """현재 열린 거래 조회 (아직 청산되지 않음)"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT
                    id, entry_time, entry_price, side, quantity, leverage, symbol
                FROM trades
                WHERE status = 'OPEN'
                ORDER BY entry_time DESC
                LIMIT 1
            """)

            return dict(row) if row else None

    async def cleanup_old_trades(self, days: int = 30):
        """N일 이상 지난 거래 삭제"""
        async with self.pool.acquire() as conn:
            cutoff_time = datetime.now() - timedelta(days=days)

            deleted = await conn.fetchval("""
                DELETE FROM trades
                WHERE exit_time < $1
                RETURNING COUNT(*)
            """, cutoff_time)

            logger.info(f"오래된 거래 정리: {deleted}건 삭제 ({days}일 이전)")
            return deleted
