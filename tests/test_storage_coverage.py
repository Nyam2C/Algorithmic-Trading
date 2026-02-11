"""
Storage 모듈 커버리지 향상 테스트

대상 모듈:
- src/storage/redis_state.py (73.77%, 80 lines missed)
- src/storage/audit_log.py (78.43%, 22 lines missed)
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.storage.audit_log import (
    AuditEventType,
    AuditLog,
    AuditLogManager,
)
from src.storage.redis_state import (
    REDIS_AVAILABLE,
    DummyRedisStateManager,
    RedisStateManager,
    create_redis_manager,
)

# =============================================================================
# RedisStateManager 추가 커버리지 테스트
# =============================================================================


class TestRedisStateManagerConnect:
    """connect() 메서드 테스트 - 이미 연결된 경우, 연결 실패"""

    @pytest.fixture
    def state_manager(self):
        if not REDIS_AVAILABLE:
            pytest.skip("redis 패키지가 설치되지 않음")
        return RedisStateManager(redis_url="redis://localhost:6379")

    @pytest.mark.asyncio
    async def test_connect_already_connected(self, state_manager):
        """이미 연결된 경우 경고 후 리턴"""
        mock_client = AsyncMock()
        state_manager._client = mock_client

        # 이미 연결된 상태에서 connect 호출
        await state_manager.connect()
        # _client가 변경되지 않아야 함
        assert state_manager._client is mock_client

    @pytest.mark.asyncio
    async def test_connect_failure(self, state_manager):
        """연결 실패 시 예외 발생"""
        with patch("src.storage.redis_state.redis.Redis") as mock_redis_cls:
            mock_redis_instance = AsyncMock()
            mock_redis_instance.ping = AsyncMock(side_effect=ConnectionError("Connection refused"))
            mock_redis_cls.from_url.return_value = mock_redis_instance

            with pytest.raises(ConnectionError):
                await state_manager.connect()

            # 실패 시 _client는 None
            assert state_manager._client is None


class TestRedisStateManagerDisconnect:
    """disconnect() - 연결 없을 때"""

    @pytest.fixture
    def state_manager(self):
        if not REDIS_AVAILABLE:
            pytest.skip("redis 패키지가 설치되지 않음")
        return RedisStateManager(redis_url="redis://localhost:6379")

    @pytest.mark.asyncio
    async def test_disconnect_no_connection(self, state_manager):
        """연결이 없을 때 disconnect 호출"""
        assert state_manager._client is None
        await state_manager.disconnect()  # 에러 없어야 함
        assert state_manager._client is None


class TestRedisStateManagerSaveErrors:
    """save 메서드 에러 케이스 - 연결 없을 때, 예외 발생 시"""

    @pytest.fixture
    def mock_redis_client(self):
        client = AsyncMock()
        return client

    @pytest.fixture
    def state_manager(self, mock_redis_client):
        if not REDIS_AVAILABLE:
            pytest.skip("redis 패키지가 설치되지 않음")
        manager = RedisStateManager(redis_url="redis://localhost:6379")
        manager._client = mock_redis_client
        return manager

    @pytest.mark.asyncio
    async def test_save_bot_state_no_client(self):
        """클라이언트 없을 때 save_bot_state는 False 반환"""
        if not REDIS_AVAILABLE:
            pytest.skip("redis 패키지가 설치되지 않음")
        manager = RedisStateManager(redis_url="redis://localhost:6379")
        # _client가 None
        result = await manager.save_bot_state("bot", {"key": "val"})
        assert result is False

    @pytest.mark.asyncio
    async def test_save_bot_state_exception(self, state_manager, mock_redis_client):
        """save_bot_state 예외 발생 시 False 반환"""
        mock_redis_client.hset = AsyncMock(side_effect=Exception("Write error"))

        result = await state_manager.save_bot_state("bot", {"key": "val"})
        assert result is False

    @pytest.mark.asyncio
    async def test_load_bot_state_no_client(self):
        """클라이언트 없을 때 load_bot_state는 None 반환"""
        if not REDIS_AVAILABLE:
            pytest.skip("redis 패키지가 설치되지 않음")
        manager = RedisStateManager(redis_url="redis://localhost:6379")
        result = await manager.load_bot_state("bot")
        assert result is None

    @pytest.mark.asyncio
    async def test_load_bot_state_exception(self, state_manager, mock_redis_client):
        """load_bot_state 예외 발생 시 None 반환"""
        mock_redis_client.hgetall = AsyncMock(side_effect=Exception("Read error"))

        result = await state_manager.load_bot_state("bot")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_bot_state_no_client(self):
        """클라이언트 없을 때 delete_bot_state는 False 반환"""
        if not REDIS_AVAILABLE:
            pytest.skip("redis 패키지가 설치되지 않음")
        manager = RedisStateManager(redis_url="redis://localhost:6379")
        result = await manager.delete_bot_state("bot")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_bot_state_exception(self, state_manager, mock_redis_client):
        """delete_bot_state 예외 발생 시 False 반환"""
        mock_redis_client.delete = AsyncMock(side_effect=Exception("Delete error"))

        result = await state_manager.delete_bot_state("bot")
        assert result is False


class TestRedisStateManagerPositionErrors:
    """포지션 save/load/delete 에러 케이스"""

    @pytest.fixture
    def mock_redis_client(self):
        client = AsyncMock()
        return client

    @pytest.fixture
    def state_manager(self, mock_redis_client):
        if not REDIS_AVAILABLE:
            pytest.skip("redis 패키지가 설치되지 않음")
        manager = RedisStateManager(redis_url="redis://localhost:6379")
        manager._client = mock_redis_client
        return manager

    @pytest.mark.asyncio
    async def test_save_position_no_client(self):
        """클라이언트 없을 때 save_position은 False 반환"""
        if not REDIS_AVAILABLE:
            pytest.skip("redis 패키지가 설치되지 않음")
        manager = RedisStateManager(redis_url="redis://localhost:6379")
        result = await manager.save_position("bot", {"side": "LONG"})
        assert result is False

    @pytest.mark.asyncio
    async def test_save_position_exception(self, state_manager, mock_redis_client):
        """save_position 예외 시 False 반환"""
        mock_redis_client.hset = AsyncMock(side_effect=Exception("Write error"))
        result = await state_manager.save_position("bot", {"side": "LONG"})
        assert result is False

    @pytest.mark.asyncio
    async def test_load_position_no_client(self):
        """클라이언트 없을 때 load_position은 None 반환"""
        if not REDIS_AVAILABLE:
            pytest.skip("redis 패키지가 설치되지 않음")
        manager = RedisStateManager(redis_url="redis://localhost:6379")
        result = await manager.load_position("bot")
        assert result is None

    @pytest.mark.asyncio
    async def test_load_position_exception(self, state_manager, mock_redis_client):
        """load_position 예외 시 None 반환"""
        mock_redis_client.hgetall = AsyncMock(side_effect=Exception("Read error"))
        result = await state_manager.load_position("bot")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_position_no_client(self):
        """클라이언트 없을 때 delete_position은 False 반환"""
        if not REDIS_AVAILABLE:
            pytest.skip("redis 패키지가 설치되지 않음")
        manager = RedisStateManager(redis_url="redis://localhost:6379")
        result = await manager.delete_position("bot")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_position_exception(self, state_manager, mock_redis_client):
        """delete_position 예외 시 False 반환"""
        mock_redis_client.delete = AsyncMock(side_effect=Exception("Delete error"))
        result = await state_manager.delete_position("bot")
        assert result is False


class TestRedisStateManagerBotRegistrationErrors:
    """봇 등록/해제 에러 케이스"""

    @pytest.fixture
    def mock_redis_client(self):
        client = AsyncMock()
        return client

    @pytest.fixture
    def state_manager(self, mock_redis_client):
        if not REDIS_AVAILABLE:
            pytest.skip("redis 패키지가 설치되지 않음")
        manager = RedisStateManager(redis_url="redis://localhost:6379")
        manager._client = mock_redis_client
        return manager

    @pytest.mark.asyncio
    async def test_register_bot_no_client(self):
        """클라이언트 없을 때 register_bot은 False 반환"""
        if not REDIS_AVAILABLE:
            pytest.skip("redis 패키지가 설치되지 않음")
        manager = RedisStateManager(redis_url="redis://localhost:6379")
        result = await manager.register_bot("bot")
        assert result is False

    @pytest.mark.asyncio
    async def test_register_bot_exception(self, state_manager, mock_redis_client):
        """register_bot 예외 시 False 반환"""
        mock_redis_client.sadd = AsyncMock(side_effect=Exception("SADD error"))
        result = await state_manager.register_bot("bot")
        assert result is False

    @pytest.mark.asyncio
    async def test_unregister_bot_no_client(self):
        """클라이언트 없을 때 unregister_bot은 False 반환"""
        if not REDIS_AVAILABLE:
            pytest.skip("redis 패키지가 설치되지 않음")
        manager = RedisStateManager(redis_url="redis://localhost:6379")
        result = await manager.unregister_bot("bot")
        assert result is False

    @pytest.mark.asyncio
    async def test_unregister_bot_exception(self, state_manager, mock_redis_client):
        """unregister_bot 예외 시 False 반환"""
        mock_redis_client.srem = AsyncMock(side_effect=Exception("SREM error"))
        result = await state_manager.unregister_bot("bot")
        assert result is False

    @pytest.mark.asyncio
    async def test_unregister_bot_success_cleans_up(self, state_manager, mock_redis_client):
        """unregister_bot 성공 시 상태/포지션/running도 정리"""
        mock_redis_client.srem = AsyncMock()
        mock_redis_client.delete = AsyncMock()

        result = await state_manager.unregister_bot("bot")
        assert result is True
        # srem (unregister) + delete (state) + delete (position) + srem (stopped)
        assert mock_redis_client.srem.call_count >= 1
        assert mock_redis_client.delete.call_count >= 1

    @pytest.mark.asyncio
    async def test_get_registered_bots_no_client(self):
        """클라이언트 없을 때 get_registered_bots는 빈 리스트 반환"""
        if not REDIS_AVAILABLE:
            pytest.skip("redis 패키지가 설치되지 않음")
        manager = RedisStateManager(redis_url="redis://localhost:6379")
        result = await manager.get_registered_bots()
        assert result == []

    @pytest.mark.asyncio
    async def test_get_registered_bots_exception(self, state_manager, mock_redis_client):
        """get_registered_bots 예외 시 빈 리스트 반환"""
        mock_redis_client.smembers = AsyncMock(side_effect=Exception("SMEMBERS error"))
        result = await state_manager.get_registered_bots()
        assert result == []


class TestRedisStateManagerRunningErrors:
    """실행 상태 에러 케이스"""

    @pytest.fixture
    def mock_redis_client(self):
        client = AsyncMock()
        return client

    @pytest.fixture
    def state_manager(self, mock_redis_client):
        if not REDIS_AVAILABLE:
            pytest.skip("redis 패키지가 설치되지 않음")
        manager = RedisStateManager(redis_url="redis://localhost:6379")
        manager._client = mock_redis_client
        return manager

    @pytest.mark.asyncio
    async def test_set_bot_running_no_client(self):
        """클라이언트 없을 때 set_bot_running은 False 반환"""
        if not REDIS_AVAILABLE:
            pytest.skip("redis 패키지가 설치되지 않음")
        manager = RedisStateManager(redis_url="redis://localhost:6379")
        result = await manager.set_bot_running("bot")
        assert result is False

    @pytest.mark.asyncio
    async def test_set_bot_running_exception(self, state_manager, mock_redis_client):
        """set_bot_running 예외 시 False 반환"""
        mock_redis_client.sadd = AsyncMock(side_effect=Exception("SADD error"))
        result = await state_manager.set_bot_running("bot")
        assert result is False

    @pytest.mark.asyncio
    async def test_set_bot_stopped_no_client(self):
        """클라이언트 없을 때 set_bot_stopped은 False 반환"""
        if not REDIS_AVAILABLE:
            pytest.skip("redis 패키지가 설치되지 않음")
        manager = RedisStateManager(redis_url="redis://localhost:6379")
        result = await manager.set_bot_stopped("bot")
        assert result is False

    @pytest.mark.asyncio
    async def test_set_bot_stopped_exception(self, state_manager, mock_redis_client):
        """set_bot_stopped 예외 시 False 반환"""
        mock_redis_client.srem = AsyncMock(side_effect=Exception("SREM error"))
        result = await state_manager.set_bot_stopped("bot")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_running_bots_no_client(self):
        """클라이언트 없을 때 get_running_bots는 빈 리스트 반환"""
        if not REDIS_AVAILABLE:
            pytest.skip("redis 패키지가 설치되지 않음")
        manager = RedisStateManager(redis_url="redis://localhost:6379")
        result = await manager.get_running_bots()
        assert result == []

    @pytest.mark.asyncio
    async def test_get_running_bots_exception(self, state_manager, mock_redis_client):
        """get_running_bots 예외 시 빈 리스트 반환"""
        mock_redis_client.smembers = AsyncMock(side_effect=Exception("SMEMBERS error"))
        result = await state_manager.get_running_bots()
        assert result == []

    @pytest.mark.asyncio
    async def test_clear_running_bots_no_client(self):
        """클라이언트 없을 때 clear_running_bots은 False 반환"""
        if not REDIS_AVAILABLE:
            pytest.skip("redis 패키지가 설치되지 않음")
        manager = RedisStateManager(redis_url="redis://localhost:6379")
        result = await manager.clear_running_bots()
        assert result is False

    @pytest.mark.asyncio
    async def test_clear_running_bots_exception(self, state_manager, mock_redis_client):
        """clear_running_bots 예외 시 False 반환"""
        mock_redis_client.delete = AsyncMock(side_effect=Exception("DELETE error"))
        result = await state_manager.clear_running_bots()
        assert result is False


class TestRedisStateManagerProperties:
    """is_connected 프로퍼티 테스트"""

    def test_is_connected_false(self):
        """연결되지 않은 상태"""
        if not REDIS_AVAILABLE:
            pytest.skip("redis 패키지가 설치되지 않음")
        manager = RedisStateManager(redis_url="redis://localhost:6379")
        assert manager.is_connected is False

    def test_is_connected_true(self):
        """연결된 상태"""
        if not REDIS_AVAILABLE:
            pytest.skip("redis 패키지가 설치되지 않음")
        manager = RedisStateManager(redis_url="redis://localhost:6379")
        manager._client = MagicMock()
        assert manager.is_connected is True


class TestRedisStateManagerKeyGeneration:
    """키 생성 메서드 테스트"""

    def test_get_state_key(self):
        """봇 상태 키 생성"""
        if not REDIS_AVAILABLE:
            pytest.skip("redis 패키지가 설치되지 않음")
        manager = RedisStateManager(redis_url="redis://localhost:6379", key_prefix="test")
        key = manager._get_state_key("my-bot")
        assert key == "test:bot:my-bot:state"

    def test_get_position_key(self):
        """봇 포지션 키 생성"""
        if not REDIS_AVAILABLE:
            pytest.skip("redis 패키지가 설치되지 않음")
        manager = RedisStateManager(redis_url="redis://localhost:6379", key_prefix="test")
        key = manager._get_position_key("my-bot")
        assert key == "test:bot:my-bot:position"


class TestRedisStateManagerInitWithParams:
    """초기화 파라미터 테스트"""

    def test_init_with_password_and_db(self):
        """비밀번호와 DB 번호로 초기화"""
        if not REDIS_AVAILABLE:
            pytest.skip("redis 패키지가 설치되지 않음")
        manager = RedisStateManager(
            redis_url="redis://localhost:6379",
            redis_password="secret",
            redis_db=3,
            key_prefix="custom",
        )
        assert manager._redis_password == "secret"
        assert manager._redis_db == 3
        assert manager._key_prefix == "custom"


class TestDummyRedisStateManagerAdditional:
    """DummyRedisStateManager 추가 테스트"""

    @pytest.fixture
    def dummy(self):
        return DummyRedisStateManager()

    @pytest.mark.asyncio
    async def test_connect(self, dummy):
        """connect는 아무 동작도 안 함"""
        await dummy.connect()
        assert dummy.is_connected is False

    @pytest.mark.asyncio
    async def test_disconnect(self, dummy):
        """disconnect는 아무 동작도 안 함"""
        await dummy.disconnect()
        assert dummy.is_connected is False

    @pytest.mark.asyncio
    async def test_delete_bot_state(self, dummy):
        """delete_bot_state는 True 반환"""
        result = await dummy.delete_bot_state("bot")
        assert result is True

    @pytest.mark.asyncio
    async def test_save_position(self, dummy):
        """save_position은 True 반환"""
        result = await dummy.save_position("bot", {"side": "LONG"})
        assert result is True

    @pytest.mark.asyncio
    async def test_load_position(self, dummy):
        """load_position은 None 반환"""
        result = await dummy.load_position("bot")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_position(self, dummy):
        """delete_position은 True 반환"""
        result = await dummy.delete_position("bot")
        assert result is True

    @pytest.mark.asyncio
    async def test_register_bot(self, dummy):
        """register_bot은 True 반환"""
        result = await dummy.register_bot("bot")
        assert result is True

    @pytest.mark.asyncio
    async def test_unregister_bot(self, dummy):
        """unregister_bot은 True 반환"""
        result = await dummy.unregister_bot("bot")
        assert result is True

    @pytest.mark.asyncio
    async def test_set_bot_running(self, dummy):
        """set_bot_running은 True 반환"""
        result = await dummy.set_bot_running("bot")
        assert result is True

    @pytest.mark.asyncio
    async def test_set_bot_stopped(self, dummy):
        """set_bot_stopped은 True 반환"""
        result = await dummy.set_bot_stopped("bot")
        assert result is True

    @pytest.mark.asyncio
    async def test_get_running_bots(self, dummy):
        """get_running_bots은 빈 리스트 반환"""
        result = await dummy.get_running_bots()
        assert result == []

    @pytest.mark.asyncio
    async def test_clear_running_bots(self, dummy):
        """clear_running_bots은 True 반환"""
        result = await dummy.clear_running_bots()
        assert result is True


class TestCreateRedisManagerAdditional:
    """create_redis_manager 팩토리 추가 테스트"""

    @pytest.mark.asyncio
    async def test_create_with_redis_not_available(self):
        """redis 패키지 미설치 + fallback=True"""
        with patch("src.storage.redis_state.REDIS_AVAILABLE", False):
            manager = await create_redis_manager(
                redis_url="redis://localhost:6379",
                fallback_on_error=True,
            )
            assert isinstance(manager, DummyRedisStateManager)

    @pytest.mark.asyncio
    async def test_create_with_redis_not_available_no_fallback(self):
        """redis 패키지 미설치 + fallback=False"""
        with patch("src.storage.redis_state.REDIS_AVAILABLE", False):
            with pytest.raises(ImportError):
                await create_redis_manager(
                    redis_url="redis://localhost:6379",
                    fallback_on_error=False,
                )


# =============================================================================
# AuditLogManager 추가 커버리지 테스트
# =============================================================================


class TestAuditLogManagerSaveToDb:
    """_save_to_db 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_save_to_db_with_pool(self):
        """DB 풀이 있을 때 _save_to_db 실행"""
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()

        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

        manager = AuditLogManager(db_pool=mock_pool)

        log = AuditLog(
            event_type=AuditEventType.TRADE_OPEN,
            bot_name="btc-bot",
            details={"side": "LONG", "price": 50000.0},
            user_id="user_123",
            session_id="sess_abc",
        )

        await manager._save_to_db(log)

        mock_conn.execute.assert_called_once()
        # 5개 파라미터: event_type, bot_name, user_id, details_json, session_id
        call_args = mock_conn.execute.call_args
        assert call_args[0][1] == "TRADE_OPEN"
        assert call_args[0][2] == "btc-bot"
        assert call_args[0][3] == "user_123"

    @pytest.mark.asyncio
    async def test_save_to_db_no_pool(self):
        """DB 풀이 없을 때 _save_to_db는 아무것도 안 함"""
        manager = AuditLogManager(db_pool=None)

        log = AuditLog(
            event_type=AuditEventType.TRADE_OPEN,
            bot_name="btc-bot",
            details={},
        )

        # 에러 없이 완료되어야 함
        await manager._save_to_db(log)


class TestAuditLogManagerSaveLogDbError:
    """_save_log에서 DB 저장 실패 시 인메모리에는 저장"""

    @pytest.mark.asyncio
    async def test_save_log_db_error_fallback_to_memory(self):
        """DB 저장 실패 시 인메모리에만 저장"""
        mock_pool = MagicMock()

        manager = AuditLogManager(db_pool=mock_pool)

        # _save_to_db가 예외를 발생시키도록 설정
        with patch.object(manager, "_save_to_db", side_effect=Exception("DB 에러")):
            await manager.log_trade_open(
                bot_name="btc-bot",
                side="LONG",
                quantity=0.001,
                entry_price=50000.0,
            )

        # 인메모리에는 저장됨
        logs = await manager.get_recent_logs(bot_name="btc-bot")
        assert len(logs) == 1


class TestAuditLogManagerMaxMemoryLogs:
    """최대 인메모리 로그 수 초과 테스트"""

    @pytest.mark.asyncio
    async def test_memory_logs_trimmed(self):
        """최대 로그 수 초과 시 오래된 로그 삭제"""
        manager = AuditLogManager(max_memory_logs=5)

        for i in range(10):
            await manager.log_trade_open(
                bot_name=f"bot-{i}",
                side="LONG",
                quantity=0.001,
                entry_price=50000.0 + i,
            )

        # 최대 5개만 유지
        assert len(manager._memory_logs) == 5
        # 마지막 5개가 유지됨
        assert manager._memory_logs[0].bot_name == "bot-5"
        assert manager._memory_logs[4].bot_name == "bot-9"


class TestAuditLogManagerGetLogsByDateRange:
    """날짜 범위 로그 조회 테스트"""

    @pytest.mark.asyncio
    async def test_get_logs_by_date_range(self):
        """날짜 범위로 로그 조회"""
        manager = AuditLogManager()

        # 수동으로 로그 추가 (시간 제어)
        now = datetime.now(timezone.utc)
        log1 = AuditLog(
            event_type=AuditEventType.TRADE_OPEN,
            bot_name="btc-bot",
            details={"side": "LONG"},
            timestamp=now - timedelta(hours=2),
        )
        log2 = AuditLog(
            event_type=AuditEventType.TRADE_CLOSE,
            bot_name="btc-bot",
            details={"side": "LONG"},
            timestamp=now - timedelta(hours=1),
        )
        log3 = AuditLog(
            event_type=AuditEventType.BOT_PAUSE,
            bot_name="eth-bot",
            details={},
            timestamp=now,
        )

        manager._memory_logs = [log1, log2, log3]

        # 1.5시간 전부터 현재까지 조회
        start = now - timedelta(hours=1, minutes=30)
        end = now + timedelta(minutes=1)

        logs = await manager.get_logs_by_date_range(start, end)
        assert len(logs) == 2  # log2, log3

    @pytest.mark.asyncio
    async def test_get_logs_by_date_range_with_bot_name(self):
        """날짜 범위 + 봇 이름으로 로그 조회"""
        manager = AuditLogManager()

        now = datetime.now(timezone.utc)
        log1 = AuditLog(
            event_type=AuditEventType.TRADE_OPEN,
            bot_name="btc-bot",
            details={},
            timestamp=now - timedelta(hours=1),
        )
        log2 = AuditLog(
            event_type=AuditEventType.TRADE_OPEN,
            bot_name="eth-bot",
            details={},
            timestamp=now,
        )

        manager._memory_logs = [log1, log2]

        start = now - timedelta(hours=2)
        end = now + timedelta(minutes=1)

        logs = await manager.get_logs_by_date_range(start, end, bot_name="btc-bot")
        assert len(logs) == 1
        assert logs[0].bot_name == "btc-bot"


class TestAuditLogManagerGetStats:
    """감사 로그 통계 테스트"""

    @pytest.mark.asyncio
    async def test_get_stats_empty(self):
        """빈 로그에서 통계"""
        manager = AuditLogManager()
        stats = manager.get_stats()

        assert stats["total_logs"] == 0
        assert stats["event_counts"] == {}
        assert stats["db_connected"] is False

    @pytest.mark.asyncio
    async def test_get_stats_with_logs(self):
        """로그가 있을 때 통계"""
        manager = AuditLogManager()

        await manager.log_trade_open("bot1", "LONG", 0.001, 50000.0)
        await manager.log_trade_open("bot2", "SHORT", 0.01, 3000.0)
        await manager.log_trade_close("bot1", "LONG", "TP", 100.0, 1.0)
        await manager.log_bot_pause("bot1", reason="manual")

        stats = manager.get_stats()

        assert stats["total_logs"] == 4
        assert stats["event_counts"]["TRADE_OPEN"] == 2
        assert stats["event_counts"]["TRADE_CLOSE"] == 1
        assert stats["event_counts"]["BOT_PAUSE"] == 1
        assert stats["db_connected"] is False

    @pytest.mark.asyncio
    async def test_get_stats_with_db_pool(self):
        """DB 풀이 있을 때 db_connected=True"""
        manager = AuditLogManager(db_pool=MagicMock())
        stats = manager.get_stats()
        assert stats["db_connected"] is True


class TestAuditLogSessionId:
    """AuditLog의 session_id 필드 테스트"""

    def test_audit_log_with_session_id(self):
        """session_id가 있는 AuditLog"""
        log = AuditLog(
            event_type=AuditEventType.TRADE_OPEN,
            bot_name="btc-bot",
            details={},
            session_id="session-123",
        )
        assert log.session_id == "session-123"

        data = log.to_dict()
        assert data["session_id"] == "session-123"

    def test_audit_log_without_session_id(self):
        """session_id가 없는 AuditLog"""
        log = AuditLog(
            event_type=AuditEventType.TRADE_OPEN,
            bot_name="btc-bot",
            details={},
        )
        assert log.session_id is None


class TestAuditLogTradeOpenWithKwargs:
    """log_trade_open의 추가 kwargs 테스트"""

    @pytest.mark.asyncio
    async def test_log_trade_open_with_extra_fields(self):
        """추가 필드가 details에 포함되는지 확인"""
        manager = AuditLogManager()

        await manager.log_trade_open(
            bot_name="btc-bot",
            side="LONG",
            quantity=0.001,
            entry_price=50000.0,
            leverage=15,
            signal_source="gemini",
        )

        logs = await manager.get_recent_logs(bot_name="btc-bot", limit=1)
        assert len(logs) == 1
        assert logs[0].details["leverage"] == 15
        assert logs[0].details["signal_source"] == "gemini"


class TestAuditLogTradeCloseWithKwargs:
    """log_trade_close의 추가 kwargs 테스트"""

    @pytest.mark.asyncio
    async def test_log_trade_close_with_extra_fields(self):
        """추가 필드가 details에 포함되는지 확인"""
        manager = AuditLogManager()

        await manager.log_trade_close(
            bot_name="btc-bot",
            side="LONG",
            exit_reason="TP",
            pnl=100.0,
            pnl_pct=1.5,
            exit_price=51000.0,
        )

        logs = await manager.get_recent_logs(bot_name="btc-bot", limit=1)
        assert len(logs) == 1
        assert logs[0].details["exit_price"] == 51000.0
