"""
Circuit Breaker 패턴

Phase 6.2: API 호출 복원력 향상
- 연속 실패 시 자동 차단
- 복구 테스트 후 정상화
- 데코레이터 형태로 적용
"""
import asyncio
import functools
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Optional, Type, TypeVar

from loguru import logger


class CircuitState(Enum):
    """Circuit Breaker 상태

    Attributes:
        CLOSED: 정상 상태 - 모든 요청 통과
        OPEN: 차단 상태 - 모든 요청 즉시 실패
        HALF_OPEN: 복구 테스트 상태 - 일부 요청 허용
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    """Circuit Breaker 설정

    Attributes:
        failure_threshold: 연속 실패 횟수 임계값
        recovery_timeout: 복구 대기 시간 (초)
        half_open_max_calls: Half-Open 상태에서 허용할 테스트 호출 수
        success_threshold: CLOSED로 복구에 필요한 연속 성공 횟수
        exceptions: 실패로 간주할 예외 타입들
    """

    failure_threshold: int = 5
    recovery_timeout: int = 60
    half_open_max_calls: int = 3
    success_threshold: int = 2
    exceptions: tuple = (Exception,)


@dataclass
class CircuitBreakerStats:
    """Circuit Breaker 통계

    Attributes:
        total_calls: 총 호출 수
        successful_calls: 성공 호출 수
        failed_calls: 실패 호출 수
        rejected_calls: 차단된 호출 수
        state_changes: 상태 변경 횟수
        last_failure_time: 마지막 실패 시간
        last_success_time: 마지막 성공 시간
    """

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    state_changes: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "rejected_calls": self.rejected_calls,
            "state_changes": self.state_changes,
            "last_failure_time": self.last_failure_time,
            "last_success_time": self.last_success_time,
            "success_rate": (
                self.successful_calls / self.total_calls * 100
                if self.total_calls > 0
                else 0.0
            ),
        }


class CircuitBreakerOpen(Exception):
    """Circuit Breaker가 열려있을 때 발생하는 예외"""

    def __init__(
        self,
        circuit_name: str,
        remaining_time: float,
    ) -> None:
        self.circuit_name = circuit_name
        self.remaining_time = remaining_time
        super().__init__(
            f"Circuit '{circuit_name}' is OPEN. "
            f"Retry after {remaining_time:.1f} seconds."
        )


class CircuitBreaker:
    """Circuit Breaker 구현

    연속 실패 시 자동으로 요청을 차단하고,
    일정 시간 후 복구를 테스트합니다.

    Example:
        >>> breaker = CircuitBreaker(name="binance_api")
        >>> async with breaker:
        ...     await api_call()

        >>> # 또는 데코레이터로 사용
        >>> @breaker.decorate
        ... async def api_call():
        ...     pass
    """

    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ) -> None:
        """Circuit Breaker 초기화

        Args:
            name: Circuit Breaker 이름
            config: 설정 (선택)
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()
        self._stats = CircuitBreakerStats()
        self._log = logger.bind(circuit_breaker=name)

    @property
    def state(self) -> CircuitState:
        """현재 상태"""
        return self._state

    @property
    def stats(self) -> CircuitBreakerStats:
        """통계"""
        return self._stats

    def _change_state(self, new_state: CircuitState) -> None:
        """상태 변경"""
        if new_state != self._state:
            old_state = self._state
            self._state = new_state
            self._stats.state_changes += 1
            self._log.info(f"상태 변경: {old_state.value} → {new_state.value}")

    async def _check_state(self) -> bool:
        """상태 확인 및 요청 허용 여부 결정

        Returns:
            True면 요청 허용, False면 차단
        """
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                # 복구 시간 경과 확인
                if self._last_failure_time is not None:
                    elapsed = time.time() - self._last_failure_time

                    if elapsed >= self.config.recovery_timeout:
                        # HALF_OPEN으로 전환
                        self._change_state(CircuitState.HALF_OPEN)
                        self._half_open_calls = 0
                        self._success_count = 0
                        return True

                # 아직 복구 시간 안됨
                return False

            if self._state == CircuitState.HALF_OPEN:
                # 테스트 호출 허용 여부
                if self._half_open_calls < self.config.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                return False

            return False

    def _get_remaining_time(self) -> float:
        """복구까지 남은 시간"""
        if self._last_failure_time is None:
            return 0.0

        elapsed = time.time() - self._last_failure_time
        remaining = self.config.recovery_timeout - elapsed
        return max(0.0, remaining)

    async def _record_success(self) -> None:
        """성공 기록"""
        async with self._lock:
            self._stats.total_calls += 1
            self._stats.successful_calls += 1
            self._stats.last_success_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1

                if self._success_count >= self.config.success_threshold:
                    # 충분한 성공 -> CLOSED로 복구
                    self._change_state(CircuitState.CLOSED)
                    self._failure_count = 0
                    self._log.info("Circuit 복구 완료")

            elif self._state == CircuitState.CLOSED:
                # 성공 시 실패 카운터 리셋
                self._failure_count = 0

    async def _record_failure(self, exc: Exception) -> None:
        """실패 기록"""
        async with self._lock:
            self._stats.total_calls += 1
            self._stats.failed_calls += 1
            self._stats.last_failure_time = time.time()
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                # 복구 테스트 실패 -> OPEN으로 복귀
                self._change_state(CircuitState.OPEN)
                self._log.warning(f"복구 테스트 실패: {exc}")

            elif self._state == CircuitState.CLOSED:
                self._failure_count += 1

                if self._failure_count >= self.config.failure_threshold:
                    # 임계값 도달 -> OPEN으로 전환
                    self._change_state(CircuitState.OPEN)
                    self._log.warning(
                        f"연속 {self._failure_count}회 실패 - Circuit OPEN"
                    )

    async def __aenter__(self) -> "CircuitBreaker":
        """비동기 컨텍스트 매니저 진입"""
        allowed = await self._check_state()

        if not allowed:
            self._stats.rejected_calls += 1
            raise CircuitBreakerOpen(
                self.name,
                self._get_remaining_time(),
            )

        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Any,
    ) -> bool:
        """비동기 컨텍스트 매니저 종료"""
        if exc_val is None:
            await self._record_success()
        elif isinstance(exc_val, self.config.exceptions):
            await self._record_failure(exc_val)

        return False  # 예외를 전파

    def decorate(
        self,
        func: Callable,
    ) -> Callable:
        """함수 데코레이터

        Args:
            func: 래핑할 함수

        Returns:
            래핑된 함수
        """

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            async with self:
                return await func(*args, **kwargs)

        return wrapper

    def reset(self) -> None:
        """상태 리셋 (테스트용)"""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
        self._half_open_calls = 0
        self._log.info("Circuit 리셋")

    def get_status(self) -> Dict[str, Any]:
        """현재 상태 정보"""
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "remaining_time": self._get_remaining_time(),
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout,
            },
            "stats": self._stats.to_dict(),
        }


# 전역 Circuit Breaker 레지스트리
_circuit_breakers: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    name: str,
    config: Optional[CircuitBreakerConfig] = None,
) -> CircuitBreaker:
    """Circuit Breaker 인스턴스 조회/생성

    Args:
        name: Circuit Breaker 이름
        config: 설정 (첫 생성 시에만 적용)

    Returns:
        CircuitBreaker 인스턴스
    """
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(name, config)

    return _circuit_breakers[name]


def reset_all_circuit_breakers() -> None:
    """모든 Circuit Breaker 리셋 (테스트용)"""
    for breaker in _circuit_breakers.values():
        breaker.reset()


# ============================================================================
# 데코레이터 팩토리
# ============================================================================

F = TypeVar("F", bound=Callable[..., Any])


def circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    exceptions: tuple = (Exception,),
) -> Callable[[F], F]:
    """Circuit Breaker 데코레이터 팩토리

    Args:
        name: Circuit Breaker 이름
        failure_threshold: 실패 임계값
        recovery_timeout: 복구 대기 시간 (초)
        exceptions: 실패로 간주할 예외 타입들

    Returns:
        데코레이터

    Example:
        >>> @circuit_breaker(name="binance_api", failure_threshold=5, recovery_timeout=60)
        ... async def api_call():
        ...     pass
    """
    config = CircuitBreakerConfig(
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        exceptions=exceptions,
    )
    breaker = get_circuit_breaker(name, config)

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            async with breaker:
                return await func(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator
