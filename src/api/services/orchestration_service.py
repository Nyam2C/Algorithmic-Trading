"""오케스트레이션 서비스.

Redis를 통해 독립 봇 프로세스를 모니터링하고 제어합니다.
ORCHESTRATOR_MODE=true 시 사용.
"""
from typing import Any, Union

from loguru import logger

from src.storage.redis_state import DummyRedisStateManager, RedisStateManager


class OrchestrationService:
    """Redis 기반 봇 오케스트레이션 서비스.

    독립 프로세스로 실행되는 봇들을 Redis를 통해 모니터링/제어합니다.

    Attributes:
        redis_manager: Redis 상태 관리자

    Example:
        >>> service = OrchestrationService(redis_manager)
        >>> bots = await service.list_bots()
        >>> await service.pause_bot("btc-conservative")
    """

    def __init__(
        self,
        redis_manager: Union[RedisStateManager, DummyRedisStateManager],
    ) -> None:
        """초기화.

        Args:
            redis_manager: Redis 상태 관리자
        """
        self._redis = redis_manager
        self._log = logger.bind(component="OrchestrationService")

    async def list_bots(self) -> list[dict[str, Any]]:
        """등록된 봇 목록 조회 (하트비트 기반 생존 확인).

        Returns:
            봇 정보 리스트
        """
        registered = await self._redis.get_registered_bots()
        result = []

        for bot_name in registered:
            heartbeat = await self._redis.read_heartbeat(bot_name)
            state = await self._redis.load_bot_state(bot_name)

            bot_info: dict[str, Any] = {
                "bot_name": bot_name,
                "alive": heartbeat is not None,
                "heartbeat": heartbeat,
                "state": state,
            }
            result.append(bot_info)

        return result

    async def get_bot_state(self, bot_name: str) -> dict[str, Any] | None:
        """개별 봇 상태 조회.

        Args:
            bot_name: 봇 이름

        Returns:
            봇 상태 딕셔너리 또는 None
        """
        heartbeat = await self._redis.read_heartbeat(bot_name)
        state = await self._redis.load_bot_state(bot_name)
        risk_state = await self._redis.load_risk_state(bot_name)
        position = await self._redis.load_position(bot_name)

        if not state and not heartbeat:
            return None

        return {
            "bot_name": bot_name,
            "alive": heartbeat is not None,
            "heartbeat": heartbeat,
            "state": state,
            "risk_state": risk_state,
            "position": position,
        }

    async def pause_bot(self, bot_name: str) -> bool:
        """봇 일시정지 명령 전송.

        Args:
            bot_name: 봇 이름

        Returns:
            전송 성공 여부
        """
        self._log.info(f"봇 일시정지 명령: {bot_name}")
        return await self._redis.push_command(bot_name, {"action": "PAUSE"})

    async def resume_bot(self, bot_name: str) -> bool:
        """봇 재개 명령 전송.

        Args:
            bot_name: 봇 이름

        Returns:
            전송 성공 여부
        """
        self._log.info(f"봇 재개 명령: {bot_name}")
        return await self._redis.push_command(bot_name, {"action": "RESUME"})

    async def emergency_close(self, bot_name: str) -> bool:
        """봇 긴급 청산 명령 전송.

        Args:
            bot_name: 봇 이름

        Returns:
            전송 성공 여부
        """
        self._log.warning(f"봇 긴급 청산 명령: {bot_name}")
        return await self._redis.push_command(
            bot_name, {"action": "EMERGENCY_CLOSE"}
        )

    async def stop_bot(self, bot_name: str) -> bool:
        """봇 정지 명령 전송.

        Args:
            bot_name: 봇 이름

        Returns:
            전송 성공 여부
        """
        self._log.info(f"봇 정지 명령: {bot_name}")
        return await self._redis.push_command(bot_name, {"action": "STOP"})

    async def get_exposure_summary(self) -> dict[str, Any]:
        """분산 노출도 요약.

        Returns:
            노출도 요약 딕셔너리
        """
        exposure = await self._redis.get_total_exposure()
        total = sum(exposure.values())
        return {
            "total_exposure": total,
            "by_bot": exposure,
        }
