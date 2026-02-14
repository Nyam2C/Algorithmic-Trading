"""Phase 1: Redis 상태 강화 테스트.

리스크 상태 영속화, 하트비트, 명령 채널 기능 검증.
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.storage.redis_state import (
    DummyRedisStateManager,
    RedisStateManager,
)

# =========================================================================
# 픽스처
# =========================================================================


@pytest.fixture
def mock_redis_client():
    """Mock Redis 클라이언트."""
    client = AsyncMock()
    client.ping = AsyncMock(return_value=True)
    client.hset = AsyncMock()
    client.hgetall = AsyncMock(return_value={})
    client.set = AsyncMock()
    client.get = AsyncMock(return_value=None)
    client.rpush = AsyncMock()
    client.lpop = AsyncMock(return_value=None)
    client.hdel = AsyncMock(return_value=1)
    client.eval = AsyncMock(return_value=1)
    client.close = AsyncMock()
    return client


@pytest.fixture
def redis_manager(mock_redis_client):
    """Redis 상태 관리자 (mock client 주입)."""
    manager = RedisStateManager.__new__(RedisStateManager)
    manager._redis_url = "redis://localhost:6379"
    manager._redis_password = None
    manager._redis_db = 0
    manager._key_prefix = "trading"
    manager._client = mock_redis_client
    manager._log = MagicMock()
    return manager


@pytest.fixture
def dummy_manager():
    """더미 Redis 상태 관리자."""
    with patch.object(DummyRedisStateManager, "__init__", lambda self: None):
        mgr = DummyRedisStateManager.__new__(DummyRedisStateManager)
        mgr._log = MagicMock()
        return mgr


# =========================================================================
# 리스크 상태 영속화 테스트
# =========================================================================


class TestRiskStatePersistence:
    """리스크 매니저 상태 저장/복원 테스트."""

    @pytest.mark.asyncio
    async def test_save_risk_state(self, redis_manager, mock_redis_client):
        """리스크 상태 저장."""
        risk_data = {
            "daily_pnl": -15.5,
            "daily_start_balance": 1000.0,
            "consecutive_losses": 2,
            "peak_balance": 1050.0,
            "current_drawdown": 0.015,
            "total_trades": 10,
            "winning_trades": 6,
            "losing_trades": 4,
        }

        result = await redis_manager.save_risk_state("btc-bot", risk_data)

        assert result is True
        mock_redis_client.hset.assert_called_once()
        call_args = mock_redis_client.hset.call_args
        assert call_args.args[0] == "trading:bot:btc-bot:risk"

    @pytest.mark.asyncio
    async def test_load_risk_state(self, redis_manager, mock_redis_client):
        """리스크 상태 로드."""
        mock_redis_client.hgetall.return_value = {
            "daily_pnl": "__number__-15.5",
            "consecutive_losses": "__number__2",
            "peak_balance": "__number__1050.0",
        }

        result = await redis_manager.load_risk_state("btc-bot")

        assert result is not None
        assert result["daily_pnl"] == -15.5
        assert result["consecutive_losses"] == 2
        assert result["peak_balance"] == 1050.0

    @pytest.mark.asyncio
    async def test_load_risk_state_empty(self, redis_manager, mock_redis_client):
        """저장된 리스크 상태 없으면 None."""
        mock_redis_client.hgetall.return_value = {}

        result = await redis_manager.load_risk_state("btc-bot")
        assert result is None

    @pytest.mark.asyncio
    async def test_save_risk_state_no_connection(self, redis_manager):
        """연결 없으면 False."""
        redis_manager._client = None

        result = await redis_manager.save_risk_state("btc-bot", {"daily_pnl": 0})
        assert result is False

    @pytest.mark.asyncio
    async def test_load_risk_state_no_connection(self, redis_manager):
        """연결 없으면 None."""
        redis_manager._client = None

        result = await redis_manager.load_risk_state("btc-bot")
        assert result is None

    @pytest.mark.asyncio
    async def test_risk_state_roundtrip(self, redis_manager, mock_redis_client):
        """저장 → 로드 왕복 검증 (RiskManager.to_dict 형식)."""
        original = {
            "daily_pnl": -25.3,
            "daily_start_balance": 1000.0,
            "daily_reset_time": "2026-02-15T00:00:00",
            "consecutive_losses": 3,
            "cooldown_until": None,
            "peak_balance": 1050.0,
            "current_drawdown": 0.025,
            "total_trades": 15,
            "winning_trades": 8,
            "losing_trades": 7,
        }

        # Save
        await redis_manager.save_risk_state("btc-bot", original)

        # Simulate what Redis would store/return
        serialized = redis_manager._serialize_state(original)
        mock_redis_client.hgetall.return_value = serialized

        # Load
        loaded = await redis_manager.load_risk_state("btc-bot")

        assert loaded is not None
        assert loaded["daily_pnl"] == -25.3
        assert loaded["consecutive_losses"] == 3
        assert loaded["cooldown_until"] is None
        assert loaded["peak_balance"] == 1050.0


# =========================================================================
# 하트비트 테스트
# =========================================================================


class TestHeartbeat:
    """봇 하트비트 테스트."""

    @pytest.mark.asyncio
    async def test_write_heartbeat(self, redis_manager, mock_redis_client):
        """하트비트 기록."""
        data = {
            "timestamp": "2026-02-15T10:00:00",
            "loop_count": 42,
            "status": "running",
            "current_price": 98000.0,
            "has_position": True,
        }

        result = await redis_manager.write_heartbeat("btc-bot", data, ttl=600)

        assert result is True
        mock_redis_client.set.assert_called_once()
        call_args = mock_redis_client.set.call_args
        key = call_args[0][0]
        assert key == "trading:bot:btc-bot:heartbeat"
        assert call_args[1]["ex"] == 600

    @pytest.mark.asyncio
    async def test_read_heartbeat(self, redis_manager, mock_redis_client):
        """하트비트 조회."""
        heartbeat = {
            "timestamp": "2026-02-15T10:00:00",
            "loop_count": 42,
            "status": "running",
        }
        mock_redis_client.get.return_value = json.dumps(heartbeat)

        result = await redis_manager.read_heartbeat("btc-bot")

        assert result is not None
        assert result["loop_count"] == 42
        assert result["status"] == "running"

    @pytest.mark.asyncio
    async def test_read_heartbeat_expired(self, redis_manager, mock_redis_client):
        """TTL 만료 시 None."""
        mock_redis_client.get.return_value = None

        result = await redis_manager.read_heartbeat("btc-bot")
        assert result is None

    @pytest.mark.asyncio
    async def test_heartbeat_no_connection(self, redis_manager):
        """연결 없으면 False/None."""
        redis_manager._client = None

        assert await redis_manager.write_heartbeat("bot", {}, 60) is False
        assert await redis_manager.read_heartbeat("bot") is None


# =========================================================================
# 명령 채널 테스트
# =========================================================================


class TestCommandChannel:
    """봇 명령 큐 테스트."""

    @pytest.mark.asyncio
    async def test_push_command(self, redis_manager, mock_redis_client):
        """명령 큐에 추가."""
        cmd = {"action": "PAUSE"}
        result = await redis_manager.push_command("btc-bot", cmd)

        assert result is True
        mock_redis_client.rpush.assert_called_once()
        call_args = mock_redis_client.rpush.call_args
        assert call_args[0][0] == "trading:bot:btc-bot:command"
        assert json.loads(call_args[0][1]) == cmd

    @pytest.mark.asyncio
    async def test_pop_command(self, redis_manager, mock_redis_client):
        """명령 큐에서 꺼내기."""
        cmd = {"action": "EMERGENCY_CLOSE"}
        mock_redis_client.lpop.return_value = json.dumps(cmd)

        result = await redis_manager.pop_command("btc-bot")

        assert result is not None
        assert result["action"] == "EMERGENCY_CLOSE"

    @pytest.mark.asyncio
    async def test_pop_command_empty(self, redis_manager, mock_redis_client):
        """큐 비어있으면 None."""
        mock_redis_client.lpop.return_value = None

        result = await redis_manager.pop_command("btc-bot")
        assert result is None

    @pytest.mark.asyncio
    async def test_command_fifo_order(self, redis_manager, mock_redis_client):
        """FIFO 순서 검증."""
        cmds = [
            {"action": "PAUSE"},
            {"action": "RESUME"},
            {"action": "STOP"},
        ]

        # Push all
        for cmd in cmds:
            await redis_manager.push_command("btc-bot", cmd)

        # Simulate FIFO pop
        mock_redis_client.lpop.side_effect = [
            json.dumps(cmds[0]),
            json.dumps(cmds[1]),
            json.dumps(cmds[2]),
            None,
        ]

        results = []
        while True:
            cmd = await redis_manager.pop_command("btc-bot")
            if cmd is None:
                break
            results.append(cmd["action"])

        assert results == ["PAUSE", "RESUME", "STOP"]

    @pytest.mark.asyncio
    async def test_command_no_connection(self, redis_manager):
        """연결 없으면 False/None."""
        redis_manager._client = None

        assert await redis_manager.push_command("bot", {"action": "X"}) is False
        assert await redis_manager.pop_command("bot") is None


# =========================================================================
# BotInstance _check_redis_commands 테스트
# =========================================================================


class TestCheckRedisCommands:
    """BotInstance Redis 명령 처리 테스트."""

    def _create_bot_instance(self, redis_manager=None):
        """테스트용 BotInstance 생성."""
        from src.bot_config import BotConfig
        from src.bot_instance import BotInstance

        config = BotConfig(
            bot_name="test-bot",
            symbol="BTCUSDT",
            risk_level="medium",
        )
        instance = BotInstance(
            config=config,
            binance_api_key="test",
            binance_secret_key="test",
            redis_state_manager=redis_manager,
        )
        return instance

    @pytest.mark.asyncio
    async def test_pause_command(self):
        """PAUSE 명령 처리."""
        mock_redis = AsyncMock()
        mock_redis.pop_command = AsyncMock(side_effect=[
            {"action": "PAUSE"},
            None,
        ])

        bot = self._create_bot_instance(mock_redis)
        assert not bot.is_paused

        await bot._check_redis_commands()
        assert bot.is_paused

    @pytest.mark.asyncio
    async def test_resume_command(self):
        """RESUME 명령 처리."""
        mock_redis = AsyncMock()
        mock_redis.pop_command = AsyncMock(side_effect=[
            {"action": "RESUME"},
            None,
        ])

        bot = self._create_bot_instance(mock_redis)
        bot._is_paused = True

        await bot._check_redis_commands()
        assert not bot.is_paused

    @pytest.mark.asyncio
    async def test_emergency_close_command(self):
        """EMERGENCY_CLOSE 명령 처리."""
        mock_redis = AsyncMock()
        mock_redis.pop_command = AsyncMock(side_effect=[
            {"action": "EMERGENCY_CLOSE"},
            None,
        ])

        bot = self._create_bot_instance(mock_redis)
        await bot._check_redis_commands()

        assert bot._emergency_event.is_set()

    @pytest.mark.asyncio
    async def test_stop_command(self):
        """STOP 명령 처리."""
        mock_redis = AsyncMock()
        mock_redis.pop_command = AsyncMock(side_effect=[
            {"action": "STOP"},
            None,
        ])

        bot = self._create_bot_instance(mock_redis)
        bot._is_running = True

        await bot._check_redis_commands()
        assert not bot._is_running

    @pytest.mark.asyncio
    async def test_multiple_commands(self):
        """다중 명령 순차 처리."""
        mock_redis = AsyncMock()
        mock_redis.pop_command = AsyncMock(side_effect=[
            {"action": "PAUSE"},
            {"action": "RESUME"},
            None,
        ])

        bot = self._create_bot_instance(mock_redis)
        await bot._check_redis_commands()

        # PAUSE then RESUME -> not paused
        assert not bot.is_paused

    @pytest.mark.asyncio
    async def test_no_redis_manager(self):
        """Redis 없으면 스킵."""
        bot = self._create_bot_instance(None)
        # Should not raise
        await bot._check_redis_commands()

    @pytest.mark.asyncio
    async def test_unknown_command(self):
        """알 수 없는 명령은 무시."""
        mock_redis = AsyncMock()
        mock_redis.pop_command = AsyncMock(side_effect=[
            {"action": "UNKNOWN_ACTION"},
            None,
        ])

        bot = self._create_bot_instance(mock_redis)
        # Should not raise
        await bot._check_redis_commands()


# =========================================================================
# BotInstance 상태 동기화/복구 통합 테스트
# =========================================================================


class TestBotInstanceRiskSync:
    """BotInstance의 리스크 상태 동기화 테스트."""

    def _create_bot_instance(self, redis_manager=None):
        from src.bot_config import BotConfig
        from src.bot_instance import BotInstance

        config = BotConfig(
            bot_name="test-bot",
            symbol="BTCUSDT",
            risk_level="medium",
        )
        instance = BotInstance(
            config=config,
            binance_api_key="test",
            binance_secret_key="test",
            redis_state_manager=redis_manager,
        )
        return instance

    @pytest.mark.asyncio
    async def test_sync_saves_risk_state(self):
        """동기화 시 리스크 상태 저장."""
        mock_redis = AsyncMock()
        mock_redis.save_bot_state = AsyncMock(return_value=True)
        mock_redis.delete_position = AsyncMock(return_value=True)
        mock_redis.save_risk_state = AsyncMock(return_value=True)
        mock_redis.write_heartbeat = AsyncMock(return_value=True)

        bot = self._create_bot_instance(mock_redis)
        await bot._sync_state_to_redis()

        mock_redis.save_risk_state.assert_called_once()
        call_args = mock_redis.save_risk_state.call_args
        assert call_args[0][0] == "test-bot"
        risk_data = call_args[0][1]
        assert "daily_pnl" in risk_data

    @pytest.mark.asyncio
    async def test_sync_writes_heartbeat(self):
        """동기화 시 하트비트 기록."""
        mock_redis = AsyncMock()
        mock_redis.save_bot_state = AsyncMock(return_value=True)
        mock_redis.delete_position = AsyncMock(return_value=True)
        mock_redis.save_risk_state = AsyncMock(return_value=True)
        mock_redis.write_heartbeat = AsyncMock(return_value=True)

        bot = self._create_bot_instance(mock_redis)
        bot._loop_interval_seconds = 300
        await bot._sync_state_to_redis()

        mock_redis.write_heartbeat.assert_called_once()
        call_args = mock_redis.write_heartbeat.call_args
        assert call_args[0][0] == "test-bot"
        assert call_args[0][2] == 600  # TTL = 300 * 2

    @pytest.mark.asyncio
    async def test_restore_loads_risk_state(self):
        """복구 시 리스크 상태 로드."""
        mock_redis = AsyncMock()
        mock_redis.load_bot_state = AsyncMock(return_value={
            "is_paused": False,
            "loop_count": 5,
            "last_signal": "WAIT",
        })
        mock_redis.load_risk_state = AsyncMock(return_value={
            "daily_pnl": -20.0,
            "consecutive_losses": 3,
            "peak_balance": 1000.0,
            "current_drawdown": 0.02,
        })
        mock_redis.load_position = AsyncMock(return_value=None)

        bot = self._create_bot_instance(mock_redis)
        result = await bot._restore_state_from_redis()

        assert result is True
        mock_redis.load_risk_state.assert_called_once_with("test-bot")
        # Verify risk manager state was updated
        stats = bot._risk_manager.get_stats()
        assert stats["daily_pnl"] == -20.0


# =========================================================================
# Dummy 매니저 no-op 테스트
# =========================================================================


class TestDummyManagerNewMethods:
    """DummyRedisStateManager의 새 메서드 no-op 동작."""

    @pytest.mark.asyncio
    async def test_save_risk_state(self, dummy_manager):
        result = await dummy_manager.save_risk_state("bot", {"pnl": 0})
        assert result is False

    @pytest.mark.asyncio
    async def test_load_risk_state(self, dummy_manager):
        result = await dummy_manager.load_risk_state("bot")
        assert result is None

    @pytest.mark.asyncio
    async def test_write_heartbeat(self, dummy_manager):
        result = await dummy_manager.write_heartbeat("bot", {}, 60)
        assert result is False

    @pytest.mark.asyncio
    async def test_read_heartbeat(self, dummy_manager):
        result = await dummy_manager.read_heartbeat("bot")
        assert result is None

    @pytest.mark.asyncio
    async def test_push_command(self, dummy_manager):
        result = await dummy_manager.push_command("bot", {"action": "PAUSE"})
        assert result is False

    @pytest.mark.asyncio
    async def test_pop_command(self, dummy_manager):
        result = await dummy_manager.pop_command("bot")
        assert result is None

    @pytest.mark.asyncio
    async def test_check_and_reserve_exposure(self, dummy_manager):
        result = await dummy_manager.check_and_reserve_exposure("bot", 100, 500)
        assert result is True  # Always allows

    @pytest.mark.asyncio
    async def test_release_exposure(self, dummy_manager):
        result = await dummy_manager.release_exposure("bot")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_total_exposure(self, dummy_manager):
        result = await dummy_manager.get_total_exposure()
        assert result == {}


# =========================================================================
# 분산 노출도 테스트
# =========================================================================


class TestDistributedExposure:
    """분산 노출도 관리 테스트."""

    @pytest.mark.asyncio
    async def test_check_and_reserve_success(self, redis_manager, mock_redis_client):
        """한도 미만이면 예약 성공."""
        mock_redis_client.eval.return_value = 1

        result = await redis_manager.check_and_reserve_exposure(
            "btc-bot", 500.0, 2000.0
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_check_and_reserve_exceeded(self, redis_manager, mock_redis_client):
        """한도 초과면 예약 거부."""
        mock_redis_client.eval.return_value = 0

        result = await redis_manager.check_and_reserve_exposure(
            "btc-bot", 1500.0, 1000.0
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_release_exposure(self, redis_manager, mock_redis_client):
        """노출도 해제."""
        result = await redis_manager.release_exposure("btc-bot")

        assert result is True
        mock_redis_client.hdel.assert_called_once_with(
            "trading:exposure:bots", "btc-bot"
        )

    @pytest.mark.asyncio
    async def test_get_total_exposure(self, redis_manager, mock_redis_client):
        """전체 노출도 조회."""
        mock_redis_client.hgetall.return_value = {
            "btc-bot": "500.0",
            "eth-bot": "300.0",
        }

        result = await redis_manager.get_total_exposure()

        assert result == {"btc-bot": 500.0, "eth-bot": 300.0}

    @pytest.mark.asyncio
    async def test_exposure_no_connection(self, redis_manager):
        """연결 없으면 적절한 기본값."""
        redis_manager._client = None

        assert await redis_manager.check_and_reserve_exposure("b", 1, 2) is False
        assert await redis_manager.release_exposure("b") is False
        assert await redis_manager.get_total_exposure() == {}
