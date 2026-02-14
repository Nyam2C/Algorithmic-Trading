"""
Redis 상태 관리자 테스트

RedisStateManager의 연결, 상태 저장/로드, 봇 등록 기능을 테스트합니다.
"""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.storage.redis_state import (
    REDIS_AVAILABLE,
    DummyRedisStateManager,
    RedisStateManager,
    create_redis_manager,
)


class TestRedisStateManager:
    """RedisStateManager 단위 테스트"""

    @pytest.fixture
    def mock_redis_client(self):
        """Mock Redis 클라이언트 생성"""
        client = AsyncMock()
        client.ping = AsyncMock(return_value=True)
        client.hset = AsyncMock()
        client.hgetall = AsyncMock(return_value={})
        client.delete = AsyncMock()
        client.sadd = AsyncMock()
        client.srem = AsyncMock()
        client.smembers = AsyncMock(return_value=set())
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def state_manager(self, mock_redis_client):
        """테스트용 상태 관리자"""
        if not REDIS_AVAILABLE:
            pytest.skip("redis 패키지가 설치되지 않음")

        manager = RedisStateManager(redis_url="redis://localhost:6379")
        manager._client = mock_redis_client
        return manager

    # =========================================================================
    # 연결 테스트
    # =========================================================================

    @pytest.mark.asyncio
    async def test_ping_success(self, state_manager, mock_redis_client):
        """ping 성공 테스트"""
        mock_redis_client.ping = AsyncMock(return_value=True)

        result = await state_manager.ping()

        assert result is True
        mock_redis_client.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_ping_failure(self, state_manager, mock_redis_client):
        """ping 실패 테스트"""
        mock_redis_client.ping = AsyncMock(side_effect=Exception("Connection failed"))

        result = await state_manager.ping()

        assert result is False

    @pytest.mark.asyncio
    async def test_ping_no_connection(self):
        """연결 없을 때 ping 테스트"""
        if not REDIS_AVAILABLE:
            pytest.skip("redis 패키지가 설치되지 않음")

        manager = RedisStateManager(redis_url="redis://localhost:6379")
        # _client를 None으로 유지

        result = await manager.ping()

        assert result is False

    @pytest.mark.asyncio
    async def test_disconnect(self, state_manager, mock_redis_client):
        """연결 해제 테스트"""
        await state_manager.disconnect()

        mock_redis_client.close.assert_called_once()
        assert state_manager._client is None

    # =========================================================================
    # 봇 상태 저장/로드 테스트
    # =========================================================================

    @pytest.mark.asyncio
    async def test_save_bot_state(self, state_manager, mock_redis_client):
        """봇 상태 저장 테스트"""
        state = {
            "is_running": True,
            "is_paused": False,
            "loop_count": 10,
            "current_price": 50000.0,
        }

        result = await state_manager.save_bot_state("btc-bot", state)

        assert result is True
        mock_redis_client.hset.assert_called()

    @pytest.mark.asyncio
    async def test_save_bot_state_with_datetime(self, state_manager, mock_redis_client):
        """datetime 포함 봇 상태 저장 테스트"""
        state = {
            "is_running": True,
            "uptime_start": datetime(2024, 1, 1, 12, 0, 0),
            "last_signal_time": datetime(2024, 1, 1, 12, 30, 0),
        }

        result = await state_manager.save_bot_state("btc-bot", state)

        assert result is True

    @pytest.mark.asyncio
    async def test_load_bot_state(self, state_manager, mock_redis_client):
        """봇 상태 로드 테스트"""
        mock_redis_client.hgetall = AsyncMock(return_value={
            "is_running": "__bool__true",
            "is_paused": "__bool__false",
            "loop_count": "__number__10",
            "current_price": "__number__50000.5",
            "last_signal": "LONG",
        })

        state = await state_manager.load_bot_state("btc-bot")

        assert state is not None
        assert state["is_running"] is True
        assert state["is_paused"] is False
        assert state["loop_count"] == 10
        assert state["current_price"] == 50000.5
        assert state["last_signal"] == "LONG"

    @pytest.mark.asyncio
    async def test_load_bot_state_with_datetime(self, state_manager, mock_redis_client):
        """datetime 포함 봇 상태 로드 테스트"""
        mock_redis_client.hgetall = AsyncMock(return_value={
            "uptime_start": "__datetime__2024-01-01T12:00:00",
            "last_signal_time": "__null__",
        })

        state = await state_manager.load_bot_state("btc-bot")

        assert state is not None
        assert isinstance(state["uptime_start"], datetime)
        assert state["last_signal_time"] is None

    @pytest.mark.asyncio
    async def test_load_bot_state_not_found(self, state_manager, mock_redis_client):
        """존재하지 않는 봇 상태 로드 테스트"""
        mock_redis_client.hgetall = AsyncMock(return_value={})

        state = await state_manager.load_bot_state("nonexistent-bot")

        assert state is None

    @pytest.mark.asyncio
    async def test_delete_bot_state(self, state_manager, mock_redis_client):
        """봇 상태 삭제 테스트"""
        result = await state_manager.delete_bot_state("btc-bot")

        assert result is True
        mock_redis_client.delete.assert_called_once()

    # =========================================================================
    # 포지션 저장/로드 테스트
    # =========================================================================

    @pytest.mark.asyncio
    async def test_save_position(self, state_manager, mock_redis_client):
        """포지션 저장 테스트"""
        position = {
            "side": "LONG",
            "entry_price": 50000.0,
            "quantity": 0.001,
            "entry_time": datetime.now(),
        }

        result = await state_manager.save_position("btc-bot", position)

        assert result is True
        mock_redis_client.hset.assert_called()

    @pytest.mark.asyncio
    async def test_load_position(self, state_manager, mock_redis_client):
        """포지션 로드 테스트"""
        mock_redis_client.hgetall = AsyncMock(return_value={
            "side": "LONG",
            "entry_price": "__number__50000.0",
            "quantity": "__number__0.001",
        })

        position = await state_manager.load_position("btc-bot")

        assert position is not None
        assert position["side"] == "LONG"
        assert position["entry_price"] == 50000.0
        assert position["quantity"] == 0.001

    @pytest.mark.asyncio
    async def test_load_position_not_found(self, state_manager, mock_redis_client):
        """존재하지 않는 포지션 로드 테스트"""
        mock_redis_client.hgetall = AsyncMock(return_value={})

        position = await state_manager.load_position("nonexistent-bot")

        assert position is None

    @pytest.mark.asyncio
    async def test_delete_position(self, state_manager, mock_redis_client):
        """포지션 삭제 테스트"""
        result = await state_manager.delete_position("btc-bot")

        assert result is True
        mock_redis_client.delete.assert_called_once()

    # =========================================================================
    # 봇 등록 테스트
    # =========================================================================

    @pytest.mark.asyncio
    async def test_register_bot(self, state_manager, mock_redis_client):
        """봇 등록 테스트"""
        result = await state_manager.register_bot("btc-bot")

        assert result is True
        mock_redis_client.sadd.assert_called()

    @pytest.mark.asyncio
    async def test_unregister_bot(self, state_manager, mock_redis_client):
        """봇 등록 해제 테스트"""
        result = await state_manager.unregister_bot("btc-bot")

        assert result is True
        mock_redis_client.srem.assert_called()

    @pytest.mark.asyncio
    async def test_get_registered_bots(self, state_manager, mock_redis_client):
        """등록된 봇 목록 조회 테스트"""
        mock_redis_client.smembers = AsyncMock(
            return_value={"btc-bot", "eth-bot", "sol-bot"}
        )

        bots = await state_manager.get_registered_bots()

        assert len(bots) == 3
        assert "btc-bot" in bots
        assert "eth-bot" in bots

    # =========================================================================
    # 실행 상태 테스트
    # =========================================================================

    @pytest.mark.asyncio
    async def test_set_bot_running(self, state_manager, mock_redis_client):
        """봇 실행 상태 설정 테스트"""
        result = await state_manager.set_bot_running("btc-bot")

        assert result is True
        mock_redis_client.sadd.assert_called()

    @pytest.mark.asyncio
    async def test_set_bot_stopped(self, state_manager, mock_redis_client):
        """봇 정지 상태 설정 테스트"""
        result = await state_manager.set_bot_stopped("btc-bot")

        assert result is True
        mock_redis_client.srem.assert_called()

    @pytest.mark.asyncio
    async def test_get_running_bots(self, state_manager, mock_redis_client):
        """실행 중인 봇 목록 조회 테스트"""
        mock_redis_client.smembers = AsyncMock(return_value={"btc-bot", "eth-bot"})

        bots = await state_manager.get_running_bots()

        assert len(bots) == 2
        assert "btc-bot" in bots

    @pytest.mark.asyncio
    async def test_clear_running_bots(self, state_manager, mock_redis_client):
        """실행 중인 봇 목록 초기화 테스트"""
        result = await state_manager.clear_running_bots()

        assert result is True
        mock_redis_client.delete.assert_called()

    # =========================================================================
    # 직렬화/역직렬화 테스트
    # =========================================================================

    def test_serialize_state(self, state_manager):
        """상태 직렬화 테스트"""
        state = {
            "is_running": True,
            "is_paused": False,
            "count": 10,
            "price": 50000.5,
            "time": datetime(2024, 1, 1, 12, 0, 0),
            "data": {"key": "value"},
            "items": [1, 2, 3],
            "empty": None,
            "text": "hello",
        }

        serialized = state_manager._serialize_state(state)

        assert serialized["is_running"] == "__bool__true"
        assert serialized["is_paused"] == "__bool__false"
        assert serialized["count"] == "__number__10"
        assert serialized["price"] == "__number__50000.5"
        assert serialized["time"].startswith("__datetime__")
        assert serialized["data"].startswith("__dict__")
        assert serialized["items"].startswith("__list__")
        assert serialized["empty"] == "__null__"
        assert serialized["text"] == "hello"

    def test_deserialize_state(self, state_manager):
        """상태 역직렬화 테스트"""
        serialized = {
            "is_running": "__bool__true",
            "is_paused": "__bool__false",
            "count": "__number__10",
            "price": "__number__50000.5",
            "time": "__datetime__2024-01-01T12:00:00",
            "data": '__dict__{"key": "value"}',
            "items": "__list__[1, 2, 3]",
            "empty": "__null__",
            "text": "hello",
        }

        deserialized = state_manager._deserialize_state(serialized)

        assert deserialized["is_running"] is True
        assert deserialized["is_paused"] is False
        assert deserialized["count"] == 10
        assert deserialized["price"] == 50000.5
        assert isinstance(deserialized["time"], datetime)
        assert deserialized["data"] == {"key": "value"}
        assert deserialized["items"] == [1, 2, 3]
        assert deserialized["empty"] is None
        assert deserialized["text"] == "hello"


class TestDummyRedisStateManager:
    """DummyRedisStateManager 테스트"""

    @pytest.fixture
    def dummy_manager(self):
        """더미 상태 관리자"""
        return DummyRedisStateManager()

    def test_is_connected_always_false(self, dummy_manager):
        """is_connected가 항상 False인지 확인"""
        assert dummy_manager.is_connected is False

    @pytest.mark.asyncio
    async def test_ping_returns_false(self, dummy_manager):
        """ping이 항상 False를 반환하는지 확인"""
        result = await dummy_manager.ping()
        assert result is False

    @pytest.mark.asyncio
    async def test_save_bot_state_returns_false(self, dummy_manager):
        """save_bot_state가 False를 반환하는지 확인 (저장 실패 표시)"""
        result = await dummy_manager.save_bot_state("test-bot", {"key": "value"})
        assert result is False

    @pytest.mark.asyncio
    async def test_load_bot_state_returns_none(self, dummy_manager):
        """load_bot_state가 None을 반환하는지 확인"""
        result = await dummy_manager.load_bot_state("test-bot")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_registered_bots_returns_empty(self, dummy_manager):
        """get_registered_bots가 빈 리스트를 반환하는지 확인"""
        result = await dummy_manager.get_registered_bots()
        assert result == []


class TestCreateRedisManager:
    """create_redis_manager 팩토리 함수 테스트"""

    @pytest.mark.asyncio
    async def test_fallback_on_connection_error(self):
        """연결 실패 시 더미 매니저 반환 테스트"""
        # 존재하지 않는 Redis 서버로 연결 시도
        manager = await create_redis_manager(
            redis_url="redis://nonexistent:6379",
            fallback_on_error=True,
        )

        assert isinstance(manager, DummyRedisStateManager)
        assert manager.is_connected is False

    @pytest.mark.asyncio
    async def test_raise_on_connection_error(self):
        """fallback_on_error=False일 때 예외 발생 테스트"""
        with pytest.raises(Exception):
            await create_redis_manager(
                redis_url="redis://nonexistent:6379",
                fallback_on_error=False,
            )


# =============================================================================
# RedisStateManager 추가 커버리지 테스트 (from test_storage_coverage.py)
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
        """delete_bot_state는 False 반환"""
        result = await dummy.delete_bot_state("bot")
        assert result is False

    @pytest.mark.asyncio
    async def test_save_position(self, dummy):
        """save_position은 False 반환"""
        result = await dummy.save_position("bot", {"side": "LONG"})
        assert result is False

    @pytest.mark.asyncio
    async def test_load_position(self, dummy):
        """load_position은 None 반환"""
        result = await dummy.load_position("bot")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_position(self, dummy):
        """delete_position은 False 반환"""
        result = await dummy.delete_position("bot")
        assert result is False

    @pytest.mark.asyncio
    async def test_register_bot(self, dummy):
        """register_bot은 False 반환"""
        result = await dummy.register_bot("bot")
        assert result is False

    @pytest.mark.asyncio
    async def test_unregister_bot(self, dummy):
        """unregister_bot은 False 반환"""
        result = await dummy.unregister_bot("bot")
        assert result is False

    @pytest.mark.asyncio
    async def test_set_bot_running(self, dummy):
        """set_bot_running은 False 반환"""
        result = await dummy.set_bot_running("bot")
        assert result is False

    @pytest.mark.asyncio
    async def test_set_bot_stopped(self, dummy):
        """set_bot_stopped은 False 반환"""
        result = await dummy.set_bot_stopped("bot")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_running_bots(self, dummy):
        """get_running_bots은 빈 리스트 반환"""
        result = await dummy.get_running_bots()
        assert result == []

    @pytest.mark.asyncio
    async def test_clear_running_bots(self, dummy):
        """clear_running_bots은 False 반환"""
        result = await dummy.clear_running_bots()
        assert result is False


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


class TestRedisMarketContext:
    """시장 컨텍스트 저장/로드 테스트"""

    @pytest.fixture
    def mock_redis_client(self):
        """Mock Redis 클라이언트 생성"""
        client = AsyncMock()
        client.ping = AsyncMock(return_value=True)
        client.set = AsyncMock()
        client.get = AsyncMock(return_value=None)
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def state_manager(self, mock_redis_client):
        """테스트용 상태 관리자"""
        if not REDIS_AVAILABLE:
            pytest.skip("redis 패키지가 설치되지 않음")

        manager = RedisStateManager(redis_url="redis://localhost:6379")
        manager._client = mock_redis_client
        return manager

    @pytest.mark.asyncio
    async def test_save_market_context(self, state_manager, mock_redis_client):
        """시장 컨텍스트 저장"""
        data = {"fear_greed_index": 75, "funding_rate": 0.0003}
        result = await state_manager.save_market_context(data)

        assert result is True
        mock_redis_client.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_market_context(self, state_manager, mock_redis_client):
        """시장 컨텍스트 로드"""
        import json
        mock_redis_client.get.return_value = json.dumps(
            {"fear_greed_index": 75, "funding_rate": 0.0003}
        )

        result = await state_manager.load_market_context()

        assert result is not None
        assert result["fear_greed_index"] == 75
        assert result["funding_rate"] == 0.0003

    @pytest.mark.asyncio
    async def test_load_market_context_none(self, state_manager, mock_redis_client):
        """시장 컨텍스트 없을 때 None"""
        mock_redis_client.get.return_value = None

        result = await state_manager.load_market_context()
        assert result is None

    @pytest.mark.asyncio
    async def test_save_market_context_not_connected(self):
        """연결 안 된 상태에서 저장 시 False"""
        if not REDIS_AVAILABLE:
            pytest.skip("redis 패키지가 설치되지 않음")

        manager = RedisStateManager(redis_url="redis://localhost:6379")
        # _client is None (not connected)
        result = await manager.save_market_context({"test": 1})
        assert result is False

    @pytest.mark.asyncio
    async def test_dummy_save_market_context(self):
        """DummyRedisStateManager 시장 컨텍스트 저장"""
        dummy = DummyRedisStateManager()
        result = await dummy.save_market_context({"test": 1})
        assert result is False

    @pytest.mark.asyncio
    async def test_dummy_load_market_context(self):
        """DummyRedisStateManager 시장 컨텍스트 로드"""
        dummy = DummyRedisStateManager()
        result = await dummy.load_market_context()
        assert result is None
