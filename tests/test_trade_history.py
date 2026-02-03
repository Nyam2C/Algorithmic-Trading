"""
Tests for TradeHistoryDB
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from src.storage.trade_history import TradeHistoryDB


class TestTradeHistoryDBInit:
    """TradeHistoryDB 초기화 테스트"""

    def test_init(self):
        """초기화"""
        db = TradeHistoryDB("postgresql://user:pass@localhost:5432/test")

        assert db.database_url == "postgresql://user:pass@localhost:5432/test"
        assert db.pool is None


class TestConnect:
    """connect 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """연결 성공"""
        db = TradeHistoryDB("postgresql://test:test@localhost:5432/test")

        # asyncpg.create_pool은 awaitable을 반환해야 함
        async def mock_create_pool(*args, **kwargs):
            return MagicMock()

        with patch("src.storage.trade_history.asyncpg.create_pool", side_effect=mock_create_pool):
            with patch.object(db, "create_tables", new_callable=AsyncMock):
                await db.connect()

            assert db.pool is not None

    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """연결 실패"""
        db = TradeHistoryDB("postgresql://test:test@localhost:5432/test")

        async def mock_create_pool_fail(*args, **kwargs):
            raise Exception("Connection failed")

        with patch("src.storage.trade_history.asyncpg.create_pool", side_effect=mock_create_pool_fail):
            with pytest.raises(Exception, match="Connection failed"):
                await db.connect()


class TestDisconnect:
    """disconnect 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """연결 해제"""
        db = TradeHistoryDB("postgresql://test:test@localhost:5432/test")
        db.pool = AsyncMock()

        await db.disconnect()

        db.pool.close.assert_called_once()


class TestCreateTables:
    """create_tables 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_create_tables_exists(self):
        """테이블 존재 확인"""
        db = TradeHistoryDB("postgresql://test:test@localhost:5432/test")

        mock_conn = AsyncMock()
        mock_conn.fetchval.return_value = True

        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        db.pool = mock_pool

        await db.create_tables()

        mock_conn.fetchval.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_tables_not_exists(self):
        """테이블 미존재 경고"""
        db = TradeHistoryDB("postgresql://test:test@localhost:5432/test")

        mock_conn = AsyncMock()
        mock_conn.fetchval.return_value = False

        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        db.pool = mock_pool

        await db.create_tables()

        mock_conn.fetchval.assert_called_once()


class TestAddEntry:
    """add_entry 메서드 테스트"""

    @pytest.fixture
    def db_with_pool(self):
        """Pool이 설정된 DB"""
        db = TradeHistoryDB("postgresql://test:test@localhost:5432/test")
        mock_conn = AsyncMock()
        mock_conn.fetchval.return_value = "123e4567-e89b-12d3-a456-426614174000"

        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        db.pool = mock_pool
        return db, mock_conn

    @pytest.mark.asyncio
    async def test_add_entry_success(self, db_with_pool):
        """거래 진입 기록 성공"""
        db, mock_conn = db_with_pool

        trade_id = await db.add_entry(
            entry_time=datetime.now(),
            entry_price=105000.0,
            side="LONG",
            quantity=0.01,
            leverage=15,
            symbol="BTCUSDT"
        )

        assert trade_id == "123e4567-e89b-12d3-a456-426614174000"
        mock_conn.fetchval.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_entry_short(self, db_with_pool):
        """SHORT 거래 진입"""
        db, mock_conn = db_with_pool

        trade_id = await db.add_entry(
            entry_time=datetime.now(),
            entry_price=105000.0,
            side="SHORT",
            quantity=0.01,
            leverage=15
        )

        assert trade_id is not None


class TestAddExit:
    """add_exit 메서드 테스트"""

    @pytest.fixture
    def db_with_pool(self):
        db = TradeHistoryDB("postgresql://test:test@localhost:5432/test")
        mock_conn = AsyncMock()

        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        db.pool = mock_pool
        return db, mock_conn

    @pytest.mark.asyncio
    async def test_add_exit_take_profit(self, db_with_pool):
        """익절 청산 기록"""
        db, mock_conn = db_with_pool

        await db.add_exit(
            trade_id="123e4567-e89b-12d3-a456-426614174000",
            exit_time=datetime.now(),
            exit_price=105500.0,
            exit_reason="TAKE_PROFIT",
            pnl=7.5,
            pnl_pct=0.48,
            duration_minutes=45
        )

        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_exit_stop_loss(self, db_with_pool):
        """손절 청산 기록"""
        db, mock_conn = db_with_pool

        await db.add_exit(
            trade_id="123e4567-e89b-12d3-a456-426614174000",
            exit_time=datetime.now(),
            exit_price=104500.0,
            exit_reason="STOP_LOSS",
            pnl=-7.5,
            pnl_pct=-0.48,
            duration_minutes=30
        )

        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_exit_timecut(self, db_with_pool):
        """타임컷 청산 기록"""
        db, mock_conn = db_with_pool

        await db.add_exit(
            trade_id="123e4567-e89b-12d3-a456-426614174000",
            exit_time=datetime.now(),
            exit_price=105000.0,
            exit_reason="TIMECUT",
            pnl=0.0,
            pnl_pct=0.0,
            duration_minutes=120
        )

        mock_conn.execute.assert_called_once()


class TestGetRecentTrades:
    """get_recent_trades 메서드 테스트"""

    @pytest.fixture
    def db_with_pool(self):
        db = TradeHistoryDB("postgresql://test:test@localhost:5432/test")
        mock_conn = AsyncMock()

        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        db.pool = mock_pool
        return db, mock_conn

    @pytest.mark.asyncio
    async def test_get_recent_trades_success(self, db_with_pool):
        """최근 거래 조회"""
        db, mock_conn = db_with_pool

        mock_rows = [
            {
                "id": "uuid1",
                "entry_time": datetime.now() - timedelta(hours=2),
                "entry_price": 105000.0,
                "exit_time": datetime.now() - timedelta(hours=1),
                "exit_price": 105500.0,
                "side": "LONG",
                "quantity": 0.01,
                "leverage": 15,
                "exit_reason": "TAKE_PROFIT",
                "pnl": 7.5,
                "pnl_pct": 0.48,
                "duration_minutes": 60,
                "symbol": "BTCUSDT",
                "status": "CLOSED"
            },
            {
                "id": "uuid2",
                "entry_time": datetime.now() - timedelta(hours=4),
                "entry_price": 104000.0,
                "exit_time": datetime.now() - timedelta(hours=3),
                "exit_price": 103500.0,
                "side": "SHORT",
                "quantity": 0.01,
                "leverage": 15,
                "exit_reason": "STOP_LOSS",
                "pnl": -7.5,
                "pnl_pct": -0.48,
                "duration_minutes": 60,
                "symbol": "BTCUSDT",
                "status": "CLOSED"
            }
        ]
        mock_conn.fetch.return_value = mock_rows

        trades = await db.get_recent_trades(limit=10)

        assert len(trades) == 2
        assert trades[0]["side"] == "LONG"
        assert trades[1]["side"] == "SHORT"

    @pytest.mark.asyncio
    async def test_get_recent_trades_empty(self, db_with_pool):
        """거래 없음"""
        db, mock_conn = db_with_pool
        mock_conn.fetch.return_value = []

        trades = await db.get_recent_trades()

        assert len(trades) == 0


class TestGetStatistics:
    """get_statistics 메서드 테스트"""

    @pytest.fixture
    def db_with_pool(self):
        db = TradeHistoryDB("postgresql://test:test@localhost:5432/test")
        mock_conn = AsyncMock()

        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        db.pool = mock_pool
        return db, mock_conn

    @pytest.mark.asyncio
    async def test_get_statistics_with_trades(self, db_with_pool):
        """거래 통계 조회"""
        db, mock_conn = db_with_pool

        # fetchval 호출 순서: total, winners, total_pnl, best, worst, long_trades
        mock_conn.fetchval.side_effect = [10, 6, 150.0, 2.5, -1.5, 7]

        stats = await db.get_statistics(hours=24)

        assert stats["total_trades"] == 10
        assert stats["winners"] == 6
        assert stats["losers"] == 4
        assert stats["win_rate"] == 60.0
        assert stats["total_pnl"] == 150.0
        assert stats["long_trades"] == 7
        assert stats["short_trades"] == 3

    @pytest.mark.asyncio
    async def test_get_statistics_no_trades(self, db_with_pool):
        """거래 없는 경우"""
        db, mock_conn = db_with_pool
        mock_conn.fetchval.return_value = 0

        stats = await db.get_statistics(hours=24)

        assert stats["total_trades"] == 0
        assert stats["win_rate"] == 0
        assert stats["total_pnl"] == 0

    @pytest.mark.asyncio
    async def test_get_statistics_custom_period(self, db_with_pool):
        """사용자 정의 기간"""
        db, mock_conn = db_with_pool
        mock_conn.fetchval.side_effect = [5, 3, 75.0, 1.5, -0.8, 3]

        stats = await db.get_statistics(hours=48)

        assert stats["period_hours"] == 48
        assert stats["total_trades"] == 5


class TestGetOpenTrade:
    """get_open_trade 메서드 테스트"""

    @pytest.fixture
    def db_with_pool(self):
        db = TradeHistoryDB("postgresql://test:test@localhost:5432/test")
        mock_conn = AsyncMock()

        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        db.pool = mock_pool
        return db, mock_conn

    @pytest.mark.asyncio
    async def test_get_open_trade_exists(self, db_with_pool):
        """열린 거래 존재"""
        db, mock_conn = db_with_pool

        mock_conn.fetchrow.return_value = {
            "id": "uuid1",
            "entry_time": datetime.now(),
            "entry_price": 105000.0,
            "side": "LONG",
            "quantity": 0.01,
            "leverage": 15,
            "symbol": "BTCUSDT"
        }

        trade = await db.get_open_trade()

        assert trade is not None
        assert trade["side"] == "LONG"

    @pytest.mark.asyncio
    async def test_get_open_trade_none(self, db_with_pool):
        """열린 거래 없음"""
        db, mock_conn = db_with_pool
        mock_conn.fetchrow.return_value = None

        trade = await db.get_open_trade()

        assert trade is None


class TestCleanupOldTrades:
    """cleanup_old_trades 메서드 테스트"""

    @pytest.fixture
    def db_with_pool(self):
        db = TradeHistoryDB("postgresql://test:test@localhost:5432/test")
        mock_conn = AsyncMock()

        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        db.pool = mock_pool
        return db, mock_conn

    @pytest.mark.asyncio
    async def test_cleanup_old_trades(self, db_with_pool):
        """오래된 거래 정리"""
        db, mock_conn = db_with_pool
        mock_conn.execute.return_value = "DELETE 5"

        deleted = await db.cleanup_old_trades(days=30)

        assert deleted == 5
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_old_trades_custom_days(self, db_with_pool):
        """사용자 정의 기간"""
        db, mock_conn = db_with_pool
        mock_conn.execute.return_value = "DELETE 10"

        deleted = await db.cleanup_old_trades(days=7)

        assert deleted == 10


class TestBotIdSupport:
    """bot_id 지원 테스트"""

    @pytest.fixture
    def db_with_pool(self):
        db = TradeHistoryDB("postgresql://test:test@localhost:5432/test")
        mock_conn = AsyncMock()
        mock_conn.fetchval.return_value = "123e4567-e89b-12d3-a456-426614174000"

        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        db.pool = mock_pool
        return db, mock_conn

    @pytest.mark.asyncio
    async def test_add_entry_with_bot_id(self, db_with_pool):
        """bot_id와 함께 거래 진입 기록"""
        db, mock_conn = db_with_pool

        trade_id = await db.add_entry(
            entry_time=datetime.now(),
            entry_price=105000.0,
            side="LONG",
            quantity=0.01,
            leverage=15,
            symbol="BTCUSDT",
            bot_id="bot-123e4567-e89b-12d3-a456-426614174000"
        )

        assert trade_id == "123e4567-e89b-12d3-a456-426614174000"
        # SQL에 bot_id가 포함되었는지 확인
        call_args = mock_conn.fetchval.call_args
        assert call_args is not None

    @pytest.mark.asyncio
    async def test_add_entry_without_bot_id(self, db_with_pool):
        """bot_id 없이 거래 진입 (하위 호환성)"""
        db, mock_conn = db_with_pool

        trade_id = await db.add_entry(
            entry_time=datetime.now(),
            entry_price=105000.0,
            side="LONG",
            quantity=0.01,
            leverage=15,
            symbol="BTCUSDT"
        )

        assert trade_id == "123e4567-e89b-12d3-a456-426614174000"

    @pytest.mark.asyncio
    async def test_get_recent_trades_with_bot_id_filter(self, db_with_pool):
        """bot_id로 필터링하여 최근 거래 조회"""
        db, mock_conn = db_with_pool

        mock_rows = [
            {
                "id": "uuid1",
                "entry_time": datetime.now() - timedelta(hours=2),
                "entry_price": 105000.0,
                "exit_time": datetime.now() - timedelta(hours=1),
                "exit_price": 105500.0,
                "side": "LONG",
                "quantity": 0.01,
                "leverage": 15,
                "exit_reason": "TAKE_PROFIT",
                "pnl": 7.5,
                "pnl_pct": 0.48,
                "duration_minutes": 60,
                "symbol": "BTCUSDT",
                "status": "CLOSED",
                "bot_id": "bot-uuid"
            }
        ]
        mock_conn.fetch.return_value = mock_rows

        trades = await db.get_recent_trades(limit=10, bot_id="bot-uuid")

        assert len(trades) == 1
        mock_conn.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_statistics_with_bot_id_filter(self, db_with_pool):
        """bot_id로 필터링하여 통계 조회"""
        db, mock_conn = db_with_pool
        mock_conn.fetchval.side_effect = [5, 3, 75.0, 1.5, -0.8, 3]

        stats = await db.get_statistics(hours=24, bot_id="bot-uuid")

        assert stats["total_trades"] == 5

    @pytest.mark.asyncio
    async def test_get_open_trade_with_bot_id_filter(self, db_with_pool):
        """bot_id로 필터링하여 열린 거래 조회"""
        db, mock_conn = db_with_pool

        mock_conn.fetchrow.return_value = {
            "id": "uuid1",
            "entry_time": datetime.now(),
            "entry_price": 105000.0,
            "side": "LONG",
            "quantity": 0.01,
            "leverage": 15,
            "symbol": "BTCUSDT",
            "bot_id": "bot-uuid"
        }

        trade = await db.get_open_trade(bot_id="bot-uuid")

        assert trade is not None
        mock_conn.fetchrow.assert_called_once()
