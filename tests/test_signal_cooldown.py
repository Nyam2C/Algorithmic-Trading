"""SignalCooldownManager 단위 테스트.

Redis 기반 시그널 쿨다운 & 중복 제거 기능을 테스트합니다.
"""
from unittest.mock import AsyncMock

import pytest

from src.trading.signal_cooldown import SignalCooldownManager


@pytest.fixture
def mock_redis():
    """Mock Redis 상태 관리자."""
    redis = AsyncMock()
    redis.key_exists = AsyncMock(return_value=False)
    redis.set_with_ttl = AsyncMock(return_value=True)
    return redis


@pytest.fixture
def cooldown_manager(mock_redis):
    """기본 설정의 SignalCooldownManager."""
    return SignalCooldownManager(
        redis_manager=mock_redis,
        bot_name="test-bot",
        symbol="BTCUSDT",
        signal_cooldown_seconds=300,
        post_loss_cooldown_seconds=600,
        alert_dedup_seconds=300,
    )


# =========================================================================
# 시그널 쿨다운 테스트
# =========================================================================


class TestSignalCooldown:
    """시그널 쿨다운 테스트."""

    @pytest.mark.asyncio
    async def test_not_on_cooldown(self, cooldown_manager, mock_redis):
        """쿨다운 아닌 경우 False 반환."""
        mock_redis.key_exists.return_value = False

        result = await cooldown_manager.is_signal_on_cooldown("LONG")

        assert result is False
        mock_redis.key_exists.assert_called_once_with(
            "trading:cooldown:test-bot:BTCUSDT:signal:LONG"
        )

    @pytest.mark.asyncio
    async def test_on_cooldown(self, cooldown_manager, mock_redis):
        """쿨다운 중인 경우 True 반환."""
        mock_redis.key_exists.return_value = True

        result = await cooldown_manager.is_signal_on_cooldown("SHORT")

        assert result is True
        mock_redis.key_exists.assert_called_once_with(
            "trading:cooldown:test-bot:BTCUSDT:signal:SHORT"
        )

    @pytest.mark.asyncio
    async def test_set_signal_cooldown(self, cooldown_manager, mock_redis):
        """시그널 쿨다운 설정."""
        result = await cooldown_manager.set_signal_cooldown("LONG")

        assert result is True
        mock_redis.set_with_ttl.assert_called_once_with(
            "trading:cooldown:test-bot:BTCUSDT:signal:LONG", "1", 300
        )

    @pytest.mark.asyncio
    async def test_set_signal_cooldown_redis_failure(self, cooldown_manager, mock_redis):
        """Redis 실패 시 False 반환."""
        mock_redis.set_with_ttl.return_value = False

        result = await cooldown_manager.set_signal_cooldown("LONG")

        assert result is False

    @pytest.mark.asyncio
    async def test_cooldown_disabled_when_zero(self, mock_redis):
        """쿨다운 0초면 항상 통과."""
        manager = SignalCooldownManager(
            redis_manager=mock_redis,
            bot_name="test-bot",
            symbol="BTCUSDT",
            signal_cooldown_seconds=0,
        )

        result = await manager.is_signal_on_cooldown("LONG")
        assert result is False
        mock_redis.key_exists.assert_not_called()

        result = await manager.set_signal_cooldown("LONG")
        assert result is False
        mock_redis.set_with_ttl.assert_not_called()

    @pytest.mark.asyncio
    async def test_cooldown_exception_returns_false(self, cooldown_manager, mock_redis):
        """Redis 예외 시 False (fail-open)."""
        mock_redis.key_exists.side_effect = Exception("connection lost")

        result = await cooldown_manager.is_signal_on_cooldown("LONG")

        assert result is False


# =========================================================================
# 손실 후 쿨다운 테스트
# =========================================================================


class TestPostLossCooldown:
    """손실 후 쿨다운 테스트."""

    @pytest.mark.asyncio
    async def test_not_active(self, cooldown_manager, mock_redis):
        """쿨다운 비활성 시 False."""
        mock_redis.key_exists.return_value = False

        result = await cooldown_manager.is_post_loss_cooldown_active()

        assert result is False
        mock_redis.key_exists.assert_called_once_with(
            "trading:cooldown:test-bot:BTCUSDT:post_loss"
        )

    @pytest.mark.asyncio
    async def test_active(self, cooldown_manager, mock_redis):
        """쿨다운 활성 시 True."""
        mock_redis.key_exists.return_value = True

        result = await cooldown_manager.is_post_loss_cooldown_active()

        assert result is True

    @pytest.mark.asyncio
    async def test_set_post_loss_cooldown(self, cooldown_manager, mock_redis):
        """손실 후 쿨다운 설정."""
        result = await cooldown_manager.set_post_loss_cooldown()

        assert result is True
        mock_redis.set_with_ttl.assert_called_once_with(
            "trading:cooldown:test-bot:BTCUSDT:post_loss", "1", 600
        )

    @pytest.mark.asyncio
    async def test_post_loss_disabled_when_zero(self, mock_redis):
        """쿨다운 0초면 항상 통과."""
        manager = SignalCooldownManager(
            redis_manager=mock_redis,
            bot_name="test-bot",
            symbol="BTCUSDT",
            post_loss_cooldown_seconds=0,
        )

        result = await manager.is_post_loss_cooldown_active()
        assert result is False
        mock_redis.key_exists.assert_not_called()

    @pytest.mark.asyncio
    async def test_post_loss_exception_returns_false(self, cooldown_manager, mock_redis):
        """Redis 예외 시 False (fail-open)."""
        mock_redis.key_exists.side_effect = Exception("timeout")

        result = await cooldown_manager.is_post_loss_cooldown_active()

        assert result is False


# =========================================================================
# 알림 중복 제거 테스트
# =========================================================================


class TestAlertDedup:
    """알림 중복 제거 테스트."""

    @pytest.mark.asyncio
    async def test_should_send_first_alert(self, cooldown_manager, mock_redis):
        """첫 알림은 전송 허용."""
        mock_redis.key_exists.return_value = False

        result = await cooldown_manager.should_send_alert("LONG")

        assert result is True
        mock_redis.key_exists.assert_called_once_with(
            "trading:dedup:test-bot:alert:LONG"
        )

    @pytest.mark.asyncio
    async def test_should_not_send_duplicate(self, cooldown_manager, mock_redis):
        """중복 알림 차단."""
        mock_redis.key_exists.return_value = True

        result = await cooldown_manager.should_send_alert("LONG")

        assert result is False

    @pytest.mark.asyncio
    async def test_mark_alert_sent(self, cooldown_manager, mock_redis):
        """알림 전송 기록."""
        result = await cooldown_manager.mark_alert_sent("SHORT")

        assert result is True
        mock_redis.set_with_ttl.assert_called_once_with(
            "trading:dedup:test-bot:alert:SHORT", "1", 300
        )

    @pytest.mark.asyncio
    async def test_alert_disabled_when_zero(self, mock_redis):
        """알림 dedup 0초면 항상 전송 허용."""
        manager = SignalCooldownManager(
            redis_manager=mock_redis,
            bot_name="test-bot",
            symbol="BTCUSDT",
            alert_dedup_seconds=0,
        )

        result = await manager.should_send_alert("LONG")
        assert result is True
        mock_redis.key_exists.assert_not_called()

        result = await manager.mark_alert_sent("LONG")
        assert result is False
        mock_redis.set_with_ttl.assert_not_called()

    @pytest.mark.asyncio
    async def test_alert_exception_returns_true(self, cooldown_manager, mock_redis):
        """Redis 예외 시 True (전송)."""
        mock_redis.key_exists.side_effect = Exception("network error")

        result = await cooldown_manager.should_send_alert("LONG")

        assert result is True


# =========================================================================
# Redis 유틸리티 메서드 테스트
# =========================================================================


class TestRedisUtilMethods:
    """RedisStateManager의 key_exists/set_with_ttl 테스트."""

    @pytest.mark.asyncio
    async def test_key_exists_real_manager(self):
        """RedisStateManager.key_exists 테스트 (mock client)."""
        try:
            from src.storage.redis_state import REDIS_AVAILABLE, RedisStateManager
        except ImportError:
            pytest.skip("redis 패키지 미설치")

        if not REDIS_AVAILABLE:
            pytest.skip("redis 패키지 미설치")

        manager = RedisStateManager(redis_url="redis://localhost:6379")
        mock_client = AsyncMock()
        mock_client.exists = AsyncMock(return_value=1)
        manager._client = mock_client

        result = await manager.key_exists("test:key")

        assert result is True
        mock_client.exists.assert_called_once_with("test:key")

    @pytest.mark.asyncio
    async def test_key_exists_not_found(self):
        """키가 없는 경우 False."""
        try:
            from src.storage.redis_state import REDIS_AVAILABLE, RedisStateManager
        except ImportError:
            pytest.skip("redis 패키지 미설치")

        if not REDIS_AVAILABLE:
            pytest.skip("redis 패키지 미설치")

        manager = RedisStateManager(redis_url="redis://localhost:6379")
        mock_client = AsyncMock()
        mock_client.exists = AsyncMock(return_value=0)
        manager._client = mock_client

        result = await manager.key_exists("nonexistent:key")

        assert result is False

    @pytest.mark.asyncio
    async def test_key_exists_no_client(self):
        """클라이언트 없으면 False."""
        try:
            from src.storage.redis_state import REDIS_AVAILABLE, RedisStateManager
        except ImportError:
            pytest.skip("redis 패키지 미설치")

        if not REDIS_AVAILABLE:
            pytest.skip("redis 패키지 미설치")

        manager = RedisStateManager(redis_url="redis://localhost:6379")
        manager._client = None

        result = await manager.key_exists("test:key")

        assert result is False

    @pytest.mark.asyncio
    async def test_set_with_ttl_real_manager(self):
        """RedisStateManager.set_with_ttl 테스트."""
        try:
            from src.storage.redis_state import REDIS_AVAILABLE, RedisStateManager
        except ImportError:
            pytest.skip("redis 패키지 미설치")

        if not REDIS_AVAILABLE:
            pytest.skip("redis 패키지 미설치")

        manager = RedisStateManager(redis_url="redis://localhost:6379")
        mock_client = AsyncMock()
        mock_client.set = AsyncMock()
        manager._client = mock_client

        result = await manager.set_with_ttl("test:key", "value", 60)

        assert result is True
        mock_client.set.assert_called_once_with("test:key", "value", ex=60)

    @pytest.mark.asyncio
    async def test_set_with_ttl_no_client(self):
        """클라이언트 없으면 False."""
        try:
            from src.storage.redis_state import REDIS_AVAILABLE, RedisStateManager
        except ImportError:
            pytest.skip("redis 패키지 미설치")

        if not REDIS_AVAILABLE:
            pytest.skip("redis 패키지 미설치")

        manager = RedisStateManager(redis_url="redis://localhost:6379")
        manager._client = None

        result = await manager.set_with_ttl("test:key", "value", 60)

        assert result is False

    @pytest.mark.asyncio
    async def test_dummy_key_exists(self):
        """DummyRedisStateManager.key_exists는 항상 False."""
        from src.storage.redis_state import DummyRedisStateManager

        manager = DummyRedisStateManager()

        result = await manager.key_exists("any:key")

        assert result is False

    @pytest.mark.asyncio
    async def test_dummy_set_with_ttl(self):
        """DummyRedisStateManager.set_with_ttl은 항상 False."""
        from src.storage.redis_state import DummyRedisStateManager

        manager = DummyRedisStateManager()

        result = await manager.set_with_ttl("any:key", "value", 60)

        assert result is False


# =========================================================================
# 키 패턴 테스트
# =========================================================================


class TestKeyPatterns:
    """Redis 키 패턴이 올바른지 검증."""

    def test_signal_key(self, cooldown_manager):
        """시그널 쿨다운 키 형식."""
        key = cooldown_manager._signal_key("LONG")
        assert key == "trading:cooldown:test-bot:BTCUSDT:signal:LONG"

    def test_post_loss_key(self, cooldown_manager):
        """손실 후 쿨다운 키 형식."""
        key = cooldown_manager._post_loss_key()
        assert key == "trading:cooldown:test-bot:BTCUSDT:post_loss"

    def test_alert_key(self, cooldown_manager):
        """알림 중복 키 형식."""
        key = cooldown_manager._alert_key("SHORT")
        assert key == "trading:dedup:test-bot:alert:SHORT"

    def test_different_bots_different_keys(self, mock_redis):
        """다른 봇은 다른 키를 사용."""
        mgr1 = SignalCooldownManager(mock_redis, "bot-a", "BTCUSDT")
        mgr2 = SignalCooldownManager(mock_redis, "bot-b", "ETHUSDT")

        assert mgr1._signal_key("LONG") != mgr2._signal_key("LONG")
        assert mgr1._post_loss_key() != mgr2._post_loss_key()
        assert mgr1._alert_key("LONG") != mgr2._alert_key("LONG")


# =========================================================================
# BotConfig 설정 필드 테스트
# =========================================================================


class TestBotConfigCooldownFields:
    """BotConfig에 쿨다운 설정 필드가 존재하는지 검증."""

    def test_default_values(self):
        """기본값 확인."""
        from src.bot_config import BotConfig

        config = BotConfig(bot_name="test-bot")
        assert config.signal_cooldown_seconds == 300
        assert config.post_loss_cooldown_seconds == 600
        assert config.alert_dedup_seconds == 300

    def test_custom_values(self):
        """커스텀 값 설정."""
        from src.bot_config import BotConfig

        config = BotConfig(
            bot_name="test-bot",
            signal_cooldown_seconds=60,
            post_loss_cooldown_seconds=120,
            alert_dedup_seconds=30,
        )
        assert config.signal_cooldown_seconds == 60
        assert config.post_loss_cooldown_seconds == 120
        assert config.alert_dedup_seconds == 30

    def test_zero_disables(self):
        """0은 비활성화."""
        from src.bot_config import BotConfig

        config = BotConfig(
            bot_name="test-bot",
            signal_cooldown_seconds=0,
            post_loss_cooldown_seconds=0,
            alert_dedup_seconds=0,
        )
        assert config.signal_cooldown_seconds == 0
        assert config.post_loss_cooldown_seconds == 0
        assert config.alert_dedup_seconds == 0

    def test_negative_raises(self):
        """음수는 유효성 에러."""
        from src.bot_config import BotConfig

        with pytest.raises(Exception):
            BotConfig(bot_name="test-bot", signal_cooldown_seconds=-1)


# =========================================================================
# 통합 시나리오 테스트
# =========================================================================


class TestIntegrationScenarios:
    """실제 사용 시나리오 테스트."""

    @pytest.mark.asyncio
    async def test_full_trade_cycle(self, mock_redis):
        """전체 거래 사이클: 시그널 → 쿨다운 → 손실 → 손실 쿨다운."""
        manager = SignalCooldownManager(
            mock_redis, "btc-bot", "BTCUSDT",
            signal_cooldown_seconds=300,
            post_loss_cooldown_seconds=600,
        )

        # 1. 시그널 쿨다운 없음
        mock_redis.key_exists.return_value = False
        assert await manager.is_signal_on_cooldown("LONG") is False

        # 2. 진입 후 쿨다운 설정
        await manager.set_signal_cooldown("LONG")
        mock_redis.set_with_ttl.assert_called_with(
            "trading:cooldown:btc-bot:BTCUSDT:signal:LONG", "1", 300
        )

        # 3. 쿨다운 중 재진입 차단
        mock_redis.key_exists.return_value = True
        assert await manager.is_signal_on_cooldown("LONG") is True

        # 4. 손실 후 쿨다운 설정
        await manager.set_post_loss_cooldown()
        mock_redis.set_with_ttl.assert_called_with(
            "trading:cooldown:btc-bot:BTCUSDT:post_loss", "1", 600
        )

        # 5. 손실 후 쿨다운 활성
        assert await manager.is_post_loss_cooldown_active() is True

    @pytest.mark.asyncio
    async def test_alert_dedup_cycle(self, mock_redis):
        """알림 중복 제거 사이클."""
        manager = SignalCooldownManager(
            mock_redis, "btc-bot", "BTCUSDT",
            alert_dedup_seconds=300,
        )

        # 1. 첫 알림 전송 가능
        mock_redis.key_exists.return_value = False
        assert await manager.should_send_alert("LONG") is True

        # 2. 전송 기록
        await manager.mark_alert_sent("LONG")

        # 3. 중복 알림 차단
        mock_redis.key_exists.return_value = True
        assert await manager.should_send_alert("LONG") is False

        # 4. 다른 시그널은 허용
        mock_redis.key_exists.return_value = False
        assert await manager.should_send_alert("SHORT") is True
