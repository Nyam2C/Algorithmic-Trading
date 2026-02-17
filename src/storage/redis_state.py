"""Redis 상태 관리 모듈.

봇 상태, 포지션 정보를 Redis에 영구 저장하여
컨테이너 재시작 시 복구할 수 있도록 합니다.
"""
import json
from datetime import datetime
from typing import Any

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
MARKET_CONTEXT_KEY = f"{KEY_PREFIX}:market_context"
BOT_RISK_KEY = f"{KEY_PREFIX}:bot:{{bot_name}}:risk"
BOT_HEARTBEAT_KEY = f"{KEY_PREFIX}:bot:{{bot_name}}:heartbeat"
BOT_COMMAND_KEY = f"{KEY_PREFIX}:bot:{{bot_name}}:command"
EXPOSURE_KEY = f"{KEY_PREFIX}:exposure:bots"

# Market context TTL (1시간)
MARKET_CONTEXT_TTL = 3600

# 직렬화 접두사 상수
_NULL_PREFIX = "__null__"
_DATETIME_PREFIX = "__datetime__"
_BOOL_PREFIX = "__bool__"
_NUMBER_PREFIX = "__number__"
_DICT_PREFIX = "__dict__"
_LIST_PREFIX = "__list__"


class RedisStateManager:
    """Redis 상태 관리자.

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
        redis_password: str | None = None,
        redis_db: int = 0,
        key_prefix: str = KEY_PREFIX,
    ) -> None:
        """초기화.

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
        self._client: redis.Redis | None = None
        self._log = logger.bind(component="RedisStateManager")

    @property
    def is_connected(self) -> bool:
        """Redis 연결 상태.

        클라이언트 객체 존재 여부만 확인합니다.
        실제 연결 상태 확인은 ping() 메서드를 사용하세요.
        """
        return self._client is not None

    # =========================================================================
    # 연결 관리
    # =========================================================================

    async def connect(self) -> None:
        """Redis 연결."""
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
        """Redis 연결 해제."""
        if self._client is not None:
            await self._client.close()
            self._client = None
            self._log.info("Redis 연결 해제")

    async def ping(self) -> bool:
        """Redis 연결 상태 확인.

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
        """봇 상태 키 생성."""
        return f"{self._key_prefix}:bot:{bot_name}:state"

    def _get_position_key(self, bot_name: str) -> str:
        """봇 포지션 키 생성."""
        return f"{self._key_prefix}:bot:{bot_name}:position"

    async def save_bot_state(self, bot_name: str, state: dict[str, Any]) -> bool:
        """봇 상태 저장.

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

            # 마지막 업데이트 시간을 mapping에 포함하여 단일 hset으로 원자적 저장
            serializable_state["last_updated"] = datetime.now().isoformat()
            await self._client.hset(key, mapping=serializable_state)  # type: ignore[misc]

            self._log.debug(f"봇 상태 저장: {bot_name}")
            return True

        except Exception as e:
            self._log.error(f"봇 상태 저장 실패: {bot_name}, {e}")
            return False

    async def load_bot_state(self, bot_name: str) -> dict[str, Any] | None:
        """봇 상태 로드.

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
        """봇 상태 삭제.

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
        """포지션 저장.

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

            # 마지막 업데이트 시간을 mapping에 포함하여 단일 hset으로 원자적 저장
            serializable["last_updated"] = datetime.now().isoformat()
            await self._client.hset(key, mapping=serializable)  # type: ignore[misc]

            self._log.debug(f"포지션 저장: {bot_name}")
            return True

        except Exception as e:
            self._log.error(f"포지션 저장 실패: {bot_name}, {e}")
            return False

    async def load_position(self, bot_name: str) -> dict[str, Any] | None:
        """포지션 로드.

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
        """포지션 삭제.

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
        """봇 등록.

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
        """봇 등록 해제.

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
        """등록된 봇 목록.

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
        """봇 실행 상태로 설정.

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
        """봇 정지 상태로 설정.

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
        """실행 중인 봇 목록.

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
        """실행 중인 봇 목록 초기화 (서버 시작 시 호출).

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
    # 범용 키 유틸리티
    # =========================================================================

    async def key_exists(self, key: str) -> bool:
        """Redis 키 존재 여부 확인.

        Args:
            key: 확인할 키

        Returns:
            키 존재 여부 (연결 실패 시 False)
        """
        if self._client is None:
            return False

        try:
            return bool(await self._client.exists(key))  # type: ignore[misc]
        except Exception:
            return False

    async def set_with_ttl(self, key: str, value: str, ttl_seconds: int) -> bool:
        """Redis 키 설정 (TTL 포함).

        Args:
            key: 설정할 키
            value: 값
            ttl_seconds: TTL (초)

        Returns:
            설정 성공 여부
        """
        if self._client is None:
            return False

        try:
            await self._client.set(key, value, ex=ttl_seconds)  # type: ignore[misc]
            return True
        except Exception:
            return False

    # =========================================================================
    # 외부 시장 컨텍스트
    # =========================================================================

    async def save_market_context(self, data: dict[str, Any]) -> bool:
        """외부 시장 컨텍스트 저장.

        Args:
            data: 시장 컨텍스트 데이터

        Returns:
            저장 성공 여부
        """
        if self._client is None:
            self._log.warning("Redis 연결되지 않음 - 시장 컨텍스트 저장 스킵")
            return False

        try:
            json_data = json.dumps(data, default=str)
            await self._client.set(  # type: ignore[misc]
                MARKET_CONTEXT_KEY, json_data, ex=MARKET_CONTEXT_TTL
            )
            self._log.debug("시장 컨텍스트 저장 완료")
            return True
        except Exception as e:
            self._log.error(f"시장 컨텍스트 저장 실패: {e}")
            return False

    async def load_market_context(self) -> dict[str, Any] | None:
        """외부 시장 컨텍스트 로드.

        Returns:
            시장 컨텍스트 딕셔너리 또는 None (만료/없음)
        """
        if self._client is None:
            self._log.warning("Redis 연결되지 않음 - 시장 컨텍스트 로드 스킵")
            return None

        try:
            raw = await self._client.get(MARKET_CONTEXT_KEY)  # type: ignore[misc]
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as e:
            self._log.error(f"시장 컨텍스트 로드 실패: {e}")
            return None


    # =========================================================================
    # 리스크 매니저 상태 영속화 (Phase 1)
    # =========================================================================

    def _get_risk_key(self, bot_name: str) -> str:
        """봇 리스크 상태 키 생성."""
        return f"{self._key_prefix}:bot:{bot_name}:risk"

    async def save_risk_state(self, bot_name: str, risk_data: dict[str, Any]) -> bool:
        """리스크 매니저 상태 저장.

        Args:
            bot_name: 봇 이름
            risk_data: RiskManager.to_dict() 결과

        Returns:
            저장 성공 여부
        """
        if self._client is None:
            return False

        try:
            key = self._get_risk_key(bot_name)
            serializable = self._serialize_state(risk_data)
            serializable["last_updated"] = datetime.now().isoformat()
            await self._client.hset(key, mapping=serializable)  # type: ignore[misc]
            self._log.debug(f"리스크 상태 저장: {bot_name}")
            return True
        except Exception as e:
            self._log.error(f"리스크 상태 저장 실패: {bot_name}, {e}")
            return False

    async def load_risk_state(self, bot_name: str) -> dict[str, Any] | None:
        """리스크 매니저 상태 로드.

        Args:
            bot_name: 봇 이름

        Returns:
            리스크 상태 딕셔너리 또는 None
        """
        if self._client is None:
            return None

        try:
            key = self._get_risk_key(bot_name)
            state = await self._client.hgetall(key)  # type: ignore[misc]
            if not state:
                return None
            return self._deserialize_state(state)
        except Exception as e:
            self._log.error(f"리스크 상태 로드 실패: {bot_name}, {e}")
            return None

    # =========================================================================
    # 봇 하트비트 (Phase 1)
    # =========================================================================

    async def write_heartbeat(
        self, bot_name: str, data: dict[str, Any], ttl: int
    ) -> bool:
        """봇 하트비트 기록.

        Args:
            bot_name: 봇 이름
            data: 하트비트 데이터 (timestamp, loop_count, status 등)
            ttl: TTL (초). 만료 시 봇 사망으로 간주.

        Returns:
            기록 성공 여부
        """
        if self._client is None:
            return False

        try:
            key = f"{self._key_prefix}:bot:{bot_name}:heartbeat"
            json_data = json.dumps(data, default=str)
            await self._client.set(key, json_data, ex=ttl)  # type: ignore[misc]
            return True
        except Exception as e:
            self._log.error(f"하트비트 기록 실패: {bot_name}, {e}")
            return False

    async def read_heartbeat(self, bot_name: str) -> dict[str, Any] | None:
        """봇 하트비트 조회.

        TTL 만료 시 None 반환 (= 봇 사망).

        Args:
            bot_name: 봇 이름

        Returns:
            하트비트 데이터 또는 None (만료/없음)
        """
        if self._client is None:
            return None

        try:
            key = f"{self._key_prefix}:bot:{bot_name}:heartbeat"
            raw = await self._client.get(key)  # type: ignore[misc]
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as e:
            self._log.error(f"하트비트 조회 실패: {bot_name}, {e}")
            return None

    # =========================================================================
    # 봇 명령 채널 (Phase 1)
    # =========================================================================

    async def push_command(self, bot_name: str, command: dict[str, Any]) -> bool:
        """봇 명령 큐에 명령 추가 (FIFO).

        Args:
            bot_name: 봇 이름
            command: 명령 딕셔너리 (예: {"action": "PAUSE"})

        Returns:
            추가 성공 여부
        """
        if self._client is None:
            return False

        try:
            key = f"{self._key_prefix}:bot:{bot_name}:command"
            json_data = json.dumps(command, default=str)
            await self._client.rpush(key, json_data)  # type: ignore[misc]
            action = command.get('action', 'UNKNOWN')
            self._log.info(f"명령 전송: {bot_name} <- {action}")
            return True
        except Exception as e:
            self._log.error(f"명령 전송 실패: {bot_name}, {e}")
            return False

    async def pop_command(self, bot_name: str) -> dict[str, Any] | None:
        """봇 명령 큐에서 명령 꺼내기 (FIFO).

        Args:
            bot_name: 봇 이름

        Returns:
            명령 딕셔너리 또는 None (큐 비어있음)
        """
        if self._client is None:
            return None

        try:
            key = f"{self._key_prefix}:bot:{bot_name}:command"
            raw = await self._client.lpop(key)  # type: ignore[misc]
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as e:
            self._log.error(f"명령 수신 실패: {bot_name}, {e}")
            return None

    # =========================================================================
    # 분산 노출도 관리 (Phase 2)
    # =========================================================================

    async def check_and_reserve_exposure(
        self, bot_name: str, value: float, max_total: float
    ) -> bool:
        """원자적 노출도 체크+예약 (Lua script).

        Args:
            bot_name: 봇 이름
            value: 예약할 노출도 (USDT)
            max_total: 최대 총 노출도 (USDT)

        Returns:
            True: 예약 성공, False: 한도 초과
        """
        if self._client is None:
            return False

        lua_script = """
        local key = KEYS[1]
        local bot_name = ARGV[1]
        local value = tonumber(ARGV[2])
        local max_total = tonumber(ARGV[3])

        -- 현재 총 노출도 계산
        local all = redis.call('HGETALL', key)
        local total = 0
        for i = 1, #all, 2 do
            if all[i] ~= bot_name then
                total = total + tonumber(all[i+1])
            end
        end

        -- 한도 체크
        if total + value > max_total then
            return 0
        end

        -- 예약
        redis.call('HSET', key, bot_name, tostring(value))
        return 1
        """

        try:
            key = f"{self._key_prefix}:exposure:bots"
            result = await self._client.eval(  # type: ignore[misc]
                lua_script, 1, key, bot_name, str(value), str(max_total)
            )
            if result == 1:
                self._log.info(
                    f"노출도 예약 성공: {bot_name} = ${value:,.2f}"
                )
                return True
            self._log.warning(
                f"노출도 예약 거부 (한도 초과): {bot_name} = ${value:,.2f}"
            )
            return False
        except Exception as e:
            self._log.error(f"노출도 체크 실패: {bot_name}, {e}")
            return False

    async def release_exposure(self, bot_name: str) -> bool:
        """노출도 예약 해제.

        Args:
            bot_name: 봇 이름

        Returns:
            해제 성공 여부
        """
        if self._client is None:
            return False

        try:
            key = f"{self._key_prefix}:exposure:bots"
            result = await self._client.hdel(key, bot_name)  # type: ignore[misc]
            if result:
                self._log.info(f"노출도 해제: {bot_name}")
            return bool(result)
        except Exception as e:
            self._log.error(f"노출도 해제 실패: {bot_name}, {e}")
            return False

    async def get_total_exposure(self) -> dict[str, float]:
        """전체 노출도 조회.

        Returns:
            봇별 노출도 딕셔너리
        """
        if self._client is None:
            return {}

        try:
            key = f"{self._key_prefix}:exposure:bots"
            raw = await self._client.hgetall(key)  # type: ignore[misc]
            return {k: float(v) for k, v in raw.items()}
        except Exception as e:
            self._log.error(f"노출도 조회 실패: {e}")
            return {}


    # =========================================================================
    # OI / LS 스냅샷 캐시 (Phase B)
    # =========================================================================

    async def save_oi_snapshot(
        self, symbol: str, oi: float, price: float
    ) -> None:
        """OI 스냅샷 저장 (FIFO 12개 유지).

        Args:
            symbol: 심볼 (예: BTCUSDT)
            oi: Open Interest
            price: 현재 가격
        """
        if self._client is None:
            return

        try:
            key = f"{self._key_prefix}:oi_history:{symbol}"
            snapshot = json.dumps({"oi": oi, "price": price})
            await self._client.rpush(key, snapshot)  # type: ignore[misc]
            await self._client.ltrim(key, -12, -1)  # type: ignore[misc]
        except Exception as e:
            self._log.error(f"OI 스냅샷 저장 실패: {symbol}, {e}")

    async def load_oi_history(
        self, symbol: str, count: int = 12
    ) -> list[dict]:
        """OI 히스토리 로드.

        Args:
            symbol: 심볼
            count: 로드할 개수

        Returns:
            OI 스냅샷 리스트
        """
        if self._client is None:
            return []

        try:
            key = f"{self._key_prefix}:oi_history:{symbol}"
            raw_list = await self._client.lrange(key, -count, -1)  # type: ignore[misc]
            return [json.loads(item) for item in raw_list]
        except Exception as e:
            self._log.error(f"OI 히스토리 로드 실패: {symbol}, {e}")
            return []

    async def save_ls_snapshot(
        self, symbol: str, ratio: float, price: float
    ) -> None:
        """Long/Short ratio 스냅샷 저장 (FIFO 12개 유지).

        Args:
            symbol: 심볼
            ratio: Long/Short ratio
            price: 현재 가격
        """
        if self._client is None:
            return

        try:
            key = f"{self._key_prefix}:ls_history:{symbol}"
            snapshot = json.dumps({"ratio": ratio, "price": price})
            await self._client.rpush(key, snapshot)  # type: ignore[misc]
            await self._client.ltrim(key, -12, -1)  # type: ignore[misc]
        except Exception as e:
            self._log.error(f"LS 스냅샷 저장 실패: {symbol}, {e}")

    async def load_ls_history(
        self, symbol: str, count: int = 12
    ) -> list[dict]:
        """Long/Short ratio 히스토리 로드.

        Args:
            symbol: 심볼
            count: 로드할 개수

        Returns:
            LS 스냅샷 리스트
        """
        if self._client is None:
            return []

        try:
            key = f"{self._key_prefix}:ls_history:{symbol}"
            raw_list = await self._client.lrange(key, -count, -1)  # type: ignore[misc]
            return [json.loads(item) for item in raw_list]
        except Exception as e:
            self._log.error(f"LS 히스토리 로드 실패: {symbol}, {e}")
            return []

    # =========================================================================
    # 직렬화/역직렬화
    # =========================================================================

    def _serialize_state(self, state: dict[str, Any]) -> dict[str, str]:
        """상태 딕셔너리를 Redis 저장용으로 직렬화.

        Args:
            state: 상태 딕셔너리

        Returns:
            문자열 딕셔너리

        NOTE: 중첩된 dict/list 내부의 datetime 등 특수 타입은
        json.dumps(default=str)에 의해 문자열로 변환되며,
        역직렬화 시 원래 타입으로 복원되지 않습니다.
        중첩 구조에 특수 타입이 필요한 경우 최상위 키로 분리하세요.
        """
        result = {}
        for key, value in state.items():
            if value is None:
                result[key] = _NULL_PREFIX
            elif isinstance(value, datetime):
                result[key] = f"{_DATETIME_PREFIX}{value.isoformat()}"
            elif isinstance(value, bool):
                result[key] = f"{_BOOL_PREFIX}{str(value).lower()}"
            elif isinstance(value, (int, float)):
                result[key] = f"{_NUMBER_PREFIX}{value}"
            elif isinstance(value, dict):
                # NOTE: 내부 datetime 등은 str로 변환됨 (복원 불가)
                result[key] = f"{_DICT_PREFIX}{json.dumps(value, default=str)}"
            elif isinstance(value, list):
                # NOTE: 내부 datetime 등은 str로 변환됨 (복원 불가)
                result[key] = f"{_LIST_PREFIX}{json.dumps(value, default=str)}"
            else:
                result[key] = str(value)
        return result

    def _deserialize_state(self, state: dict[str, str]) -> dict[str, Any]:
        """Redis에서 로드된 상태를 역직렬화.

        Args:
            state: 문자열 딕셔너리

        Returns:
            상태 딕셔너리
        """
        result: dict[str, Any] = {}
        for key, value in state.items():
            if value == _NULL_PREFIX:
                result[key] = None
            elif value.startswith(_DATETIME_PREFIX):
                dt_str = value[len(_DATETIME_PREFIX):]
                result[key] = datetime.fromisoformat(dt_str)
            elif value.startswith(_BOOL_PREFIX):
                result[key] = value[len(_BOOL_PREFIX):] == "true"
            elif value.startswith(_NUMBER_PREFIX):
                num_str = value[len(_NUMBER_PREFIX):]
                result[key] = float(num_str) if "." in num_str else int(num_str)
            elif value.startswith(_DICT_PREFIX):
                result[key] = json.loads(value[len(_DICT_PREFIX):])
            elif value.startswith(_LIST_PREFIX):
                result[key] = json.loads(value[len(_LIST_PREFIX):])
            else:
                result[key] = value
        return result


# Fallback을 위한 더미 매니저
class DummyRedisStateManager:
    """Redis 연결 실패 시 사용되는 더미 매니저.

    모든 저장 연산이 False를 반환하여 호출자가 데이터가
    영구 저장되지 않았음을 인지할 수 있도록 합니다.
    """

    def __init__(self) -> None:
        self._log = logger.bind(component="DummyRedisStateManager")
        self._log.warning("Redis 연결 실패 - 더미 상태 관리자 사용")
        self._log.warning("DummyRedisStateManager: 상태가 영구 저장되지 않습니다")

    @property
    def is_connected(self) -> bool:
        return False

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def ping(self) -> bool:
        return False

    async def save_bot_state(self, _bot_name: str, _state: dict[str, Any]) -> bool:
        return False

    async def load_bot_state(self, _bot_name: str) -> dict[str, Any] | None:
        return None

    async def delete_bot_state(self, _bot_name: str) -> bool:
        return False

    async def save_position(self, _bot_name: str, _position: dict[str, Any]) -> bool:
        return False

    async def load_position(self, _bot_name: str) -> dict[str, Any] | None:
        return None

    async def delete_position(self, _bot_name: str) -> bool:
        return False

    async def register_bot(self, _bot_name: str) -> bool:
        return False

    async def unregister_bot(self, _bot_name: str) -> bool:
        return False

    async def get_registered_bots(self) -> list[str]:
        return []

    async def set_bot_running(self, _bot_name: str) -> bool:
        return False

    async def set_bot_stopped(self, _bot_name: str) -> bool:
        return False

    async def get_running_bots(self) -> list[str]:
        return []

    async def clear_running_bots(self) -> bool:
        return False

    async def key_exists(self, _key: str) -> bool:
        return False

    async def set_with_ttl(self, _key: str, _value: str, _ttl_seconds: int) -> bool:
        return False


    async def save_risk_state(self, _bot_name: str, _risk_data: dict[str, Any]) -> bool:
        return False

    async def load_risk_state(self, _bot_name: str) -> dict[str, Any] | None:
        return None

    async def write_heartbeat(
        self, _bot_name: str, _data: dict[str, Any], _ttl: int
    ) -> bool:
        return False

    async def read_heartbeat(self, _bot_name: str) -> dict[str, Any] | None:
        return None

    async def push_command(self, _bot_name: str, _command: dict[str, Any]) -> bool:
        return False

    async def pop_command(self, _bot_name: str) -> dict[str, Any] | None:
        return None

    async def check_and_reserve_exposure(
        self, _bot_name: str, _value: float, _max_total: float
    ) -> bool:
        return True

    async def release_exposure(self, _bot_name: str) -> bool:
        return False

    async def get_total_exposure(self) -> dict[str, float]:
        return {}


    async def save_oi_snapshot(self, _symbol: str, _oi: float, _price: float) -> None:
        pass

    async def load_oi_history(self, _symbol: str, _count: int = 12) -> list[dict]:
        return []

    async def save_ls_snapshot(
        self, _symbol: str, _ratio: float, _price: float
    ) -> None:
        pass

    async def load_ls_history(self, _symbol: str, _count: int = 12) -> list[dict]:
        return []

    async def save_market_context(self, _data: dict[str, Any]) -> bool:
        return False

    async def load_market_context(self) -> dict[str, Any] | None:
        return None


async def create_redis_manager(
    redis_url: str,
    redis_password: str | None = None,
    redis_db: int = 0,
    fallback_on_error: bool = True,
) -> RedisStateManager | DummyRedisStateManager:
    """Redis 상태 관리자 생성.

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
