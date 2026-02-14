"""시그널 쿨다운 & 중복 제거 모듈.

Redis 기반으로 시그널 쿨다운, 손실 후 쿨다운, 알림 중복 제거를 관리합니다.
Redis 미연결 시 모든 체크가 통과(fail-open)됩니다.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Union

from loguru import logger

if TYPE_CHECKING:
    from src.storage.redis_state import DummyRedisStateManager, RedisStateManager


class SignalCooldownManager:
    """시그널 쿨다운 & 중복 제거 관리자.

    Redis를 사용하여 시그널 쿨다운, 손실 후 쿨다운, 알림 중복 제거를 관리합니다.
    Redis 미연결 시 fail-open (통과) 정책을 따릅니다.

    Attributes:
        bot_name: 봇 이름
        symbol: 거래 심볼

    Example:
        >>> manager = SignalCooldownManager(redis, "btc-bot", "BTCUSDT")
        >>> if not await manager.is_signal_on_cooldown("LONG"):
        ...     # 진입 로직
        ...     await manager.set_signal_cooldown("LONG")
    """

    def __init__(
        self,
        redis_manager: Union[RedisStateManager, DummyRedisStateManager],
        bot_name: str,
        symbol: str,
        signal_cooldown_seconds: int = 300,
        post_loss_cooldown_seconds: int = 600,
        alert_dedup_seconds: int = 300,
    ) -> None:
        """초기화.

        Args:
            redis_manager: Redis 상태 관리자
            bot_name: 봇 이름
            symbol: 거래 심볼
            signal_cooldown_seconds: 시그널 쿨다운 (초, 기본 5분)
            post_loss_cooldown_seconds: 손실 후 쿨다운 (초, 기본 10분)
            alert_dedup_seconds: 알림 중복 제거 (초, 기본 5분)
        """
        self._redis = redis_manager
        self.bot_name = bot_name
        self.symbol = symbol
        self._signal_cooldown_seconds = signal_cooldown_seconds
        self._post_loss_cooldown_seconds = post_loss_cooldown_seconds
        self._alert_dedup_seconds = alert_dedup_seconds
        self._log = logger.bind(
            component="SignalCooldownManager", bot_name=bot_name
        )

    # =========================================================================
    # 키 생성
    # =========================================================================

    def _signal_key(self, signal: str) -> str:
        """시그널 쿨다운 키."""
        return f"trading:cooldown:{self.bot_name}:{self.symbol}:signal:{signal}"

    def _post_loss_key(self) -> str:
        """손실 후 쿨다운 키."""
        return f"trading:cooldown:{self.bot_name}:{self.symbol}:post_loss"

    def _alert_key(self, signal: str) -> str:
        """알림 중복 제거 키."""
        return f"trading:dedup:{self.bot_name}:alert:{signal}"

    # =========================================================================
    # 시그널 쿨다운
    # =========================================================================

    async def is_signal_on_cooldown(self, signal: str) -> bool:
        """시그널이 쿨다운 중인지 확인.

        Args:
            signal: 시그널 ("LONG" 또는 "SHORT")

        Returns:
            쿨다운 중이면 True (Redis 미연결 시 False = 통과)
        """
        if self._signal_cooldown_seconds <= 0:
            return False

        try:
            key = self._signal_key(signal)
            on_cooldown = await self._redis.key_exists(key)
            if on_cooldown:
                self._log.info(f"시그널 쿨다운 중: {signal}")
            return on_cooldown
        except Exception as e:
            self._log.warning(f"시그널 쿨다운 확인 실패 (통과): {e}")
            return False

    async def set_signal_cooldown(self, signal: str) -> bool:
        """시그널 쿨다운 설정.

        Args:
            signal: 시그널 ("LONG" 또는 "SHORT")

        Returns:
            설정 성공 여부 (Redis 미연결 시 False)
        """
        if self._signal_cooldown_seconds <= 0:
            return False

        try:
            key = self._signal_key(signal)
            result = await self._redis.set_with_ttl(
                key, "1", self._signal_cooldown_seconds
            )
            if result:
                self._log.debug(
                    f"시그널 쿨다운 설정: {signal} ({self._signal_cooldown_seconds}초)"
                )
            return result
        except Exception as e:
            self._log.warning(f"시그널 쿨다운 설정 실패: {e}")
            return False

    # =========================================================================
    # 손실 후 쿨다운
    # =========================================================================

    async def is_post_loss_cooldown_active(self) -> bool:
        """손실 후 쿨다운이 활성화되어 있는지 확인.

        Returns:
            쿨다운 중이면 True (Redis 미연결 시 False = 통과)
        """
        if self._post_loss_cooldown_seconds <= 0:
            return False

        try:
            key = self._post_loss_key()
            active = await self._redis.key_exists(key)
            if active:
                self._log.info("손실 후 쿨다운 활성")
            return active
        except Exception as e:
            self._log.warning(f"손실 후 쿨다운 확인 실패 (통과): {e}")
            return False

    async def set_post_loss_cooldown(self) -> bool:
        """손실 후 쿨다운 설정.

        Returns:
            설정 성공 여부 (Redis 미연결 시 False)
        """
        if self._post_loss_cooldown_seconds <= 0:
            return False

        try:
            key = self._post_loss_key()
            result = await self._redis.set_with_ttl(
                key, "1", self._post_loss_cooldown_seconds
            )
            if result:
                self._log.info(
                    f"손실 후 쿨다운 설정 ({self._post_loss_cooldown_seconds}초)"
                )
            return result
        except Exception as e:
            self._log.warning(f"손실 후 쿨다운 설정 실패: {e}")
            return False

    # =========================================================================
    # 알림 중복 제거
    # =========================================================================

    async def should_send_alert(self, signal: str) -> bool:
        """알림을 보내도 되는지 확인.

        Args:
            signal: 시그널 ("LONG" 또는 "SHORT")

        Returns:
            보내도 되면 True (Redis 미연결 시 True = 전송)
        """
        if self._alert_dedup_seconds <= 0:
            return True

        try:
            key = self._alert_key(signal)
            already_sent = await self._redis.key_exists(key)
            if already_sent:
                self._log.debug(f"알림 중복 제거: {signal}")
            return not already_sent
        except Exception as e:
            self._log.warning(f"알림 중복 확인 실패 (전송): {e}")
            return True

    async def mark_alert_sent(self, signal: str) -> bool:
        """알림 전송 기록.

        Args:
            signal: 시그널 ("LONG" 또는 "SHORT")

        Returns:
            기록 성공 여부 (Redis 미연결 시 False)
        """
        if self._alert_dedup_seconds <= 0:
            return False

        try:
            key = self._alert_key(signal)
            return await self._redis.set_with_ttl(
                key, "1", self._alert_dedup_seconds
            )
        except Exception as e:
            self._log.warning(f"알림 전송 기록 실패: {e}")
            return False
