"""
Trade History Storage with PostgreSQL

Stores all trade entries and exits for analysis and reporting
"""
import asyncpg
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from loguru import logger


class TradeHistoryDB:
    """PostgreSQL database for trade history"""

    def __init__(self, database_url: str):
        """
        Initialize trade history database

        Args:
            database_url: PostgreSQL connection URL
        """
        self.database_url = database_url
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """Create database connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=1,
                max_size=10,
                command_timeout=60
            )
            logger.info("Connected to PostgreSQL trade history database")

            # Create tables if not exist
            await self.create_tables()

        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    async def disconnect(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Disconnected from trade history database")

    async def create_tables(self):
        """Create database tables"""
        async with self.pool.acquire() as conn:
            # Trades table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id SERIAL PRIMARY KEY,

                    -- Entry info
                    entry_time TIMESTAMP NOT NULL,
                    entry_price DECIMAL(12, 2) NOT NULL,
                    side VARCHAR(10) NOT NULL,  -- LONG or SHORT
                    size DECIMAL(12, 8) NOT NULL,
                    leverage INTEGER NOT NULL,

                    -- Exit info
                    exit_time TIMESTAMP,
                    exit_price DECIMAL(12, 2),
                    exit_reason VARCHAR(20),  -- TP, SL, TIMECUT, MANUAL

                    -- PnL
                    pnl_usd DECIMAL(12, 2),
                    pnl_pct DECIMAL(8, 4),

                    -- Strategy info
                    signal VARCHAR(10),  -- LONG, SHORT
                    rsi DECIMAL(6, 2),
                    ma_7 DECIMAL(12, 2),
                    volume_ratio DECIMAL(8, 4),

                    -- Metadata
                    symbol VARCHAR(20) NOT NULL DEFAULT 'BTCUSDT',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)

            # Create indexes
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_trades_entry_time
                ON trades(entry_time DESC)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_trades_exit_time
                ON trades(exit_time DESC)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_trades_symbol
                ON trades(symbol)
            """)

            logger.info("Trade history tables created/verified")

    async def add_entry(
        self,
        entry_time: datetime,
        entry_price: float,
        side: str,
        size: float,
        leverage: int,
        signal: str,
        rsi: float,
        ma_7: float,
        volume_ratio: float,
        symbol: str = "BTCUSDT"
    ) -> int:
        """
        Record trade entry

        Returns:
            Trade ID
        """
        async with self.pool.acquire() as conn:
            trade_id = await conn.fetchval("""
                INSERT INTO trades (
                    entry_time, entry_price, side, size, leverage,
                    signal, rsi, ma_7, volume_ratio, symbol
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING id
            """, entry_time, entry_price, side, size, leverage,
                signal, rsi, ma_7, volume_ratio, symbol)

            logger.info(f"Trade entry recorded: ID={trade_id}, {side} @ ${entry_price}")
            return trade_id

    async def add_exit(
        self,
        trade_id: int,
        exit_time: datetime,
        exit_price: float,
        exit_reason: str,
        pnl_usd: float,
        pnl_pct: float
    ):
        """Record trade exit"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE trades
                SET exit_time = $2,
                    exit_price = $3,
                    exit_reason = $4,
                    pnl_usd = $5,
                    pnl_pct = $6,
                    updated_at = NOW()
                WHERE id = $1
            """, trade_id, exit_time, exit_price, exit_reason, pnl_usd, pnl_pct)

            logger.info(
                f"Trade exit recorded: ID={trade_id}, "
                f"Exit={exit_reason} @ ${exit_price}, "
                f"PnL=${pnl_usd:+.2f} ({pnl_pct:+.2f}%)"
            )

    async def get_recent_trades(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent completed trades"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT
                    id, entry_time, entry_price, exit_time, exit_price,
                    side, size, leverage, exit_reason,
                    pnl_usd, pnl_pct, signal, symbol
                FROM trades
                WHERE exit_time IS NOT NULL
                ORDER BY exit_time DESC
                LIMIT $1
            """, limit)

            return [dict(row) for row in rows]

    async def get_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get trading statistics for the last N hours

        Returns:
            Dictionary with trading statistics
        """
        async with self.pool.acquire() as conn:
            cutoff_time = datetime.now() - timedelta(hours=hours)

            # Total trades
            total_trades = await conn.fetchval("""
                SELECT COUNT(*)
                FROM trades
                WHERE exit_time IS NOT NULL
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

            # Winners and losers
            winners = await conn.fetchval("""
                SELECT COUNT(*)
                FROM trades
                WHERE exit_time IS NOT NULL
                AND exit_time >= $1
                AND pnl_usd > 0
            """, cutoff_time)

            # Total PnL
            total_pnl = await conn.fetchval("""
                SELECT COALESCE(SUM(pnl_usd), 0)
                FROM trades
                WHERE exit_time IS NOT NULL
                AND exit_time >= $1
            """, cutoff_time)

            # Best and worst trades
            best_trade = await conn.fetchval("""
                SELECT COALESCE(MAX(pnl_pct), 0)
                FROM trades
                WHERE exit_time IS NOT NULL
                AND exit_time >= $1
            """, cutoff_time)

            worst_trade = await conn.fetchval("""
                SELECT COALESCE(MIN(pnl_pct), 0)
                FROM trades
                WHERE exit_time IS NOT NULL
                AND exit_time >= $1
            """, cutoff_time)

            # LONG vs SHORT
            long_trades = await conn.fetchval("""
                SELECT COUNT(*)
                FROM trades
                WHERE exit_time IS NOT NULL
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
        """Get current open trade (not yet exited)"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT
                    id, entry_time, entry_price, side, size, leverage,
                    signal, rsi, ma_7, volume_ratio, symbol
                FROM trades
                WHERE exit_time IS NULL
                ORDER BY entry_time DESC
                LIMIT 1
            """)

            return dict(row) if row else None

    async def cleanup_old_trades(self, days: int = 30):
        """Delete trades older than N days"""
        async with self.pool.acquire() as conn:
            cutoff_time = datetime.now() - timedelta(days=days)

            deleted = await conn.fetchval("""
                DELETE FROM trades
                WHERE exit_time < $1
                RETURNING COUNT(*)
            """, cutoff_time)

            logger.info(f"Cleaned up {deleted} old trades (older than {days} days)")
            return deleted
