"""
Redis 상태 관리 모듈

봇 상태, 포지션 정보를 Redis에 영구 저장하여
컨테이너 재시작 시 복구할 수 있도록 합니다.
"""
import json
from datetime import datetime
from typing import Any, Optional

from loguru import logger

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None  # type: ignore


# Redis Key Schema
KEY_PREFIX = "trading"
BOT_STATE_KEY = f"{KEY_PREFIX}:bot:{{bot_name}}:state"
BOT_POSITION_KEY = f"{KEY_PREFIX}:bot:{{bot_name}}:position"
REGISTERED_BOTS_KEY = f"{KEY_PREFIX}:manager:bots"
RUNNING_BOTS_KEY = f"{KEY_PREFIX}:manager:running"


class RedisStateManager:
    """Redis 상태 관리자

    봇 상태와 포지션 정보를 Redis에 저장하고 복구합니다.
    컨테이너 재시작 시에도 상태를 유지할 수 있습니다.

    Attributes:
        is_connected: Redis 연결 상태

    Example:
        >>> manager = RedisStateManager("redis://localhost:6379")
        >>> await manager.connect()
        >>> await manager.save_bot_state("btc-bot", {"is_running": True})
        >>> state = await manager.load_bot_state("btc-bot")
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        redis_password: Optional[str] = None,
        redis_db: int = 0,
        key_prefix: str = KEY_PREFIX,
    ) -> None:
        """초기화

        Args:
            redis_url: Redis 연결 URL
            redis_password: Redis 비밀번호 (선택)
            redis_db: Redis 데이터베이스 번호
            key_prefix: 키 접두사
        """
        if not REDIS_AVAILABLE:
            raise ImportError("redis 패키지가 설치되지 않았습니다. pip install redis")

        self._redis_url = redis_url
        self._redis_password = redis_password
        self._redis_db = redis_db
        self._key_prefix = key_prefix
        self._client: Optional[redis.Redis] = None
        self._log = logger.bind(component="RedisStateManager")

    @property
    def is_connected(self) -> bool:
        """Redis 연결 상태"""
        return self._client is not None

    # =========================================================================
    # 연결 관리
    # =========================================================================

    async def connect(self) -> None:
        """Redis 연결"""
        if self._client is not None:
            self._log.warning("이미 Redis에 연결되어 있습니다")
            return

        try:
            self._client = redis.Redis.from_url(
                self._redis_url,
                password=self._redis_password,
                db=self._redis_db,
                decode_responses=True,
            )
            # 연결 테스트
            await self._client.ping()  # type: ignore[misc]
            self._log.info("Redis 연결 성공", url=self._redis_url, db=self._redis_db)
        except Exception as e:
            self._client = None
            self._log.error(f"Redis 연결 실패: {e}")
            raise

    async def disconnect(self) -> None:
        """Redis 연결 해제"""
        if self._client is not None:
            await self._client.close()
            self._client = None
            self._log.info("Redis 연결 해제")

    async def ping(self) -> bool:
        """Redis 연결 상태 확인

        Returns:
            연결 성공 여부
        """
        if self._client is None:
            return False

        try:
            await self._client.ping()  # type: ignore[misc]
            return True
        except Exception:
            return False

    # =========================================================================
    # 봇 상태 관리
    # =========================================================================

    def _get_state_key(self, bot_name: str) -> str:
        """봇 상태 키 생성"""
        return f"{self._key_prefix}:bot:{bot_name}:state"

    def _get_position_key(self, bot_name: str) -> str:
        """봇 포지션 키 생성"""
        return f"{self._key_prefix}:bot:{bot_name}:position"

    async def save_bot_state(self, bot_name: str, state: dict[str, Any]) -> bool:
        """봇 상태 저장

        Args:
            bot_name: 봇 이름
            state: 상태 딕셔너리

        Returns:
            저장 성공 여부
        """
        if self._client is None:
            self._log.warning("Redis 연결되지 않음 - 상태 저장 스킵")
            return False

        try:
            key = self._get_state_key(bot_name)

            # datetime 객체를 ISO 문자열로 변환
            serializable_state = self._serialize_state(state)

            # Hash로 저장
            await self._client.hset(key, mapping=serializable_state)  # type: ignore[misc]

            # 마지막 업데이트 시간 추가
            await self._client.hset(key, "last_updated", datetime.now().isoformat())  # type: ignore[misc]

            self._log.debug(f"봇 상태 저장: {bot_name}")
            return True

        except Exception as e:
            self._log.error(f"봇 상태 저장 실패: {bot_name}, {e}")
            return False

    async def load_bot_state(self, bot_name: str) -> Optional[dict[str, Any]]:
        """봇 상태 로드

        Args:
            bot_name: 봇 이름

        Returns:
            상태 딕셔너리 또는 None
        """
        if self._client is None:
            self._log.warning("Redis 연결되지 않음 - 상태 로드 스킵")
            return None

        try:
            key = self._get_state_key(bot_name)
            state = await self._client.hgetall(key)  # type: ignore[misc]

            if not state:
                self._log.debug(f"저장된 상태 없음: {bot_name}")
                return None

            # 역직렬화
            deserialized = self._deserialize_state(state)
            self._log.debug(f"봇 상태 로드: {bot_name}")
            return deserialized

        except Exception as e:
            self._log.error(f"봇 상태 로드 실패: {bot_name}, {e}")
            return None

    async def delete_bot_state(self, bot_name: str) -> bool:
        """봇 상태 삭제

        Args:
            bot_name: 봇 이름

        Returns:
            삭제 성공 여부
        """
        if self._client is None:
            return False

        try:
            key = self._get_state_key(bot_name)
            await self._client.delete(key)  # type: ignore[misc]
            self._log.debug(f"봇 상태 삭제: {bot_name}")
            return True
        except Exception as e:
            self._log.error(f"봇 상태 삭제 실패: {bot_name}, {e}")
            return False

    # =========================================================================
    # 포지션 관리
    # =========================================================================

    async def save_position(self, bot_name: str, position: dict[str, Any]) -> bool:
        """포지션 저장

        Args:
            bot_name: 봇 이름
            position: 포지션 딕셔너리

        Returns:
            저장 성공 여부
        """
        if self._client is None:
            self._log.warning("Redis 연결되지 않음 - 포지션 저장 스킵")
            return False

        try:
            key = self._get_position_key(bot_name)
            serializable = self._serialize_state(position)
            await self._client.hset(key, mapping=serializable)  # type: ignore[misc]
            await self._client.hset(key, "last_updated", datetime.now().isoformat())  # type: ignore[misc]

            self._log.debug(f"포지션 저장: {bot_name}")
            return True

        except Exception as e:
            self._log.error(f"포지션 저장 실패: {bot_name}, {e}")
            return False

    async def load_position(self, bot_name: str) -> Optional[dict[str, Any]]:
        """포지션 로드

        Args:
            bot_name: 봇 이름

        Returns:
            포지션 딕셔너리 또는 None
        """
        if self._client is None:
            self._log.warning("Redis 연결되지 않음 - 포지션 로드 스킵")
            return None

        try:
            key = self._get_position_key(bot_name)
            position = await self._client.hgetall(key)  # type: ignore[misc]

            if not position:
                return None

            deserialized = self._deserialize_state(position)
            self._log.debug(f"포지션 로드: {bot_name}")
            return deserialized

        except Exception as e:
            self._log.error(f"포지션 로드 실패: {bot_name}, {e}")
            return None

    async def delete_position(self, bot_name: str) -> bool:
        """포지션 삭제

        Args:
            bot_name: 봇 이름

        Returns:
            삭제 성공 여부
        """
        if self._client is None:
            return False

        try:
            key = self._get_position_key(bot_name)
            await self._client.delete(key)  # type: ignore[misc]
            self._log.debug(f"포지션 삭제: {bot_name}")
            return True
        except Exception as e:
            self._log.error(f"포지션 삭제 실패: {bot_name}, {e}")
            return False

    # =========================================================================
    # 봇 등록 관리
    # =========================================================================

    async def register_bot(self, bot_name: str) -> bool:
        """봇 등록

        Args:
            bot_name: 봇 이름

        Returns:
            등록 성공 여부
        """
        if self._client is None:
            return False

        try:
            key = f"{self._key_prefix}:manager:bots"
            await self._client.sadd(key, bot_name)  # type: ignore[misc]
            self._log.info(f"봇 등록: {bot_name}")
            return True
        except Exception as e:
            self._log.error(f"봇 등록 실패: {bot_name}, {e}")
            return False

    async def unregister_bot(self, bot_name: str) -> bool:
        """봇 등록 해제

        Args:
            bot_name: 봇 이름

        Returns:
            해제 성공 여부
        """
        if self._client is None:
            return False

        try:
            key = f"{self._key_prefix}:manager:bots"
            await self._client.srem(key, bot_name)  # type: ignore[misc]

            # 상태 및 포지션도 삭제
            await self.delete_bot_state(bot_name)
            await self.delete_position(bot_name)
            await self.set_bot_stopped(bot_name)

            self._log.info(f"봇 등록 해제: {bot_name}")
            return True
        except Exception as e:
            self._log.error(f"봇 등록 해제 실패: {bot_name}, {e}")
            return False

    async def get_registered_bots(self) -> list[str]:
        """등록된 봇 목록

        Returns:
            봇 이름 리스트
        """
        if self._client is None:
            return []

        try:
            key = f"{self._key_prefix}:manager:bots"
            bots = await self._client.smembers(key)  # type: ignore[misc]
            return list(bots)
        except Exception as e:
            self._log.error(f"등록된 봇 조회 실패: {e}")
            return []

    # =========================================================================
    # 실행 상태 관리
    # =========================================================================

    async def set_bot_running(self, bot_name: str) -> bool:
        """봇 실행 상태로 설정

        Args:
            bot_name: 봇 이름

        Returns:
            설정 성공 여부
        """
        if self._client is None:
            return False

        try:
            key = f"{self._key_prefix}:manager:running"
            await self._client.sadd(key, bot_name)  # type: ignore[misc]
            self._log.debug(f"봇 실행 상태 설정: {bot_name}")
            return True
        except Exception as e:
            self._log.error(f"봇 실행 상태 설정 실패: {bot_name}, {e}")
            return False

    async def set_bot_stopped(self, bot_name: str) -> bool:
        """봇 정지 상태로 설정

        Args:
            bot_name: 봇 이름

        Returns:
            설정 성공 여부
        """
        if self._client is None:
            return False

        try:
            key = f"{self._key_prefix}:manager:running"
            await self._client.srem(key, bot_name)  # type: ignore[misc]
            self._log.debug(f"봇 정지 상태 설정: {bot_name}")
            return True
        except Exception as e:
            self._log.error(f"봇 정지 상태 설정 실패: {bot_name}, {e}")
            return False

    async def get_running_bots(self) -> list[str]:
        """실행 중인 봇 목록

        Returns:
            봇 이름 리스트
        """
        if self._client is None:
            return []

        try:
            key = f"{self._key_prefix}:manager:running"
            bots = await self._client.smembers(key)  # type: ignore[misc]
            return list(bots)
        except Exception as e:
            self._log.error(f"실행 중인 봇 조회 실패: {e}")
            return []

    async def clear_running_bots(self) -> bool:
        """실행 중인 봇 목록 초기화 (서버 시작 시 호출)

        Returns:
            초기화 성공 여부
        """
        if self._client is None:
            return False

        try:
            key = f"{self._key_prefix}:manager:running"
            await self._client.delete(key)  # type: ignore[misc]
            self._log.info("실행 중인 봇 목록 초기화")
            return True
        except Exception as e:
            self._log.error(f"실행 중인 봇 목록 초기화 실패: {e}")
            return False

    # =========================================================================
    # 직렬화/역직렬화
    # =========================================================================

    def _serialize_state(self, state: dict[str, Any]) -> dict[str, str]:
        """상태 딕셔너리를 Redis 저장용으로 직렬화

        Args:
            state: 상태 딕셔너리

        Returns:
            문자열 딕셔너리
        """
        result = {}
        for key, value in state.items():
            if value is None:
                result[key] = "__null__"
            elif isinstance(value, datetime):
                result[key] = f"__datetime__{value.isoformat()}"
            elif isinstance(value, bool):
                result[key] = f"__bool__{str(value).lower()}"
            elif isinstance(value, (int, float)):
                result[key] = f"__number__{value}"
            elif isinstance(value, dict):
                result[key] = f"__dict__{json.dumps(value, default=str)}"
            elif isinstance(value, list):
                result[key] = f"__list__{json.dumps(value, default=str)}"
            else:
                result[key] = str(value)
        return result

    def _deserialize_state(self, state: dict[str, str]) -> dict[str, Any]:
        """Redis에서 로드된 상태를 역직렬화

        Args:
            state: 문자열 딕셔너리

        Returns:
            상태 딕셔너리
        """
        result: dict[str, Any] = {}
        for key, value in state.items():
            if value == "__null__":
                result[key] = None
            elif value.startswith("__datetime__"):
                dt_str = value[12:]
                result[key] = datetime.fromisoformat(dt_str)
            elif value.startswith("__bool__"):
                result[key] = value[8:] == "true"
            elif value.startswith("__number__"):
                num_str = value[10:]
                result[key] = float(num_str) if "." in num_str else int(num_str)
            elif value.startswith("__dict__"):
                result[key] = json.loads(value[8:])
            elif value.startswith("__list__"):
                result[key] = json.loads(value[8:])
            else:
                result[key] = value
        return result


# Fallback을 위한 더미 매니저
class DummyRedisStateManager:
    """Redis 연결 실패 시 사용되는 더미 매니저

    모든 연산이 성공하지만 실제 저장은 하지 않습니다.
    """

    def __init__(self) -> None:
        self._log = logger.bind(component="DummyRedisStateManager")
        self._log.warning("Redis 연결 실패 - 더미 상태 관리자 사용")

    @property
    def is_connected(self) -> bool:
        return False

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def ping(self) -> bool:
        return False

    async def save_bot_state(self, bot_name: str, state: dict[str, Any]) -> bool:
        return True

    async def load_bot_state(self, bot_name: str) -> Optional[dict[str, Any]]:
        return None

    async def delete_bot_state(self, bot_name: str) -> bool:
        return True

    async def save_position(self, bot_name: str, position: dict[str, Any]) -> bool:
        return True

    async def load_position(self, bot_name: str) -> Optional[dict[str, Any]]:
        return None

    async def delete_position(self, bot_name: str) -> bool:
        return True

    async def register_bot(self, bot_name: str) -> bool:
        return True

    async def unregister_bot(self, bot_name: str) -> bool:
        return True

    async def get_registered_bots(self) -> list[str]:
        return []

    async def set_bot_running(self, bot_name: str) -> bool:
        return True

    async def set_bot_stopped(self, bot_name: str) -> bool:
        return True

    async def get_running_bots(self) -> list[str]:
        return []

    async def clear_running_bots(self) -> bool:
        return True


async def create_redis_manager(
    redis_url: str,
    redis_password: Optional[str] = None,
    redis_db: int = 0,
    fallback_on_error: bool = True,
) -> RedisStateManager | DummyRedisStateManager:
    """Redis 상태 관리자 생성

    연결 실패 시 fallback_on_error가 True이면 더미 매니저를 반환합니다.

    Args:
        redis_url: Redis 연결 URL
        redis_password: Redis 비밀번호
        redis_db: Redis 데이터베이스 번호
        fallback_on_error: 연결 실패 시 더미 매니저 사용 여부

    Returns:
        RedisStateManager 또는 DummyRedisStateManager
    """
    if not REDIS_AVAILABLE:
        if fallback_on_error:
            return DummyRedisStateManager()
        raise ImportError("redis 패키지가 설치되지 않았습니다")

    try:
        manager = RedisStateManager(
            redis_url=redis_url,
            redis_password=redis_password,
            redis_db=redis_db,
        )
        await manager.connect()
        return manager
    except Exception as e:
        logger.warning(f"Redis 연결 실패: {e}")
        if fallback_on_error:
            return DummyRedisStateManager()
        raise
