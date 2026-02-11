"""Retry decorator with exponential backoff for API calls."""
import asyncio
import functools
import random
from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar

from loguru import logger

P = ParamSpec("P")
T = TypeVar("T")


def async_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    jitter: bool = False,
) -> Callable[[Callable[P, Any]], Callable[P, Any]]:
    """Async retry decorator with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay in seconds
        backoff: Backoff multiplier (delay *= backoff after each retry)
        exceptions: Tuple of exceptions to catch and retry
        jitter: Add random jitter to delay to prevent thundering herd

    Usage:
        @async_retry(max_attempts=3, delay=1.0, backoff=2.0)
        async def my_api_call():
            ...
    """

    def decorator(func: Callable[P, Any]) -> Callable[P, Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = delay
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except asyncio.CancelledError:
                    # CancelledError는 즉시 전파 (재시도하지 않음)
                    raise
                except exceptions as e:
                    last_exception = e

                    if attempt == max_attempts:
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise

                    logger.warning(
                        f"{func.__name__} attempt {attempt}/{max_attempts} "
                        f"failed: {e}. "
                        f"Retrying in {current_delay:.1f}s..."
                    )

                    actual_delay = current_delay
                    if jitter:
                        # +-25% 랜덤 지터로 thundering herd 방지
                        actual_delay = current_delay * (1 + random.uniform(-0.25, 0.25))

                    await asyncio.sleep(actual_delay)
                    current_delay *= backoff

            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
            return None

        return wrapper  # type: ignore[return-value]

    return decorator


def sync_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    jitter: bool = False,
) -> Callable[[Callable[P, Any]], Callable[P, Any]]:
    """Sync retry decorator with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay in seconds
        backoff: Backoff multiplier
        exceptions: Tuple of exceptions to catch and retry
        jitter: Add random jitter to delay to prevent thundering herd

    Usage:
        @sync_retry(max_attempts=3, delay=1.0, backoff=2.0)
        def my_function():
            ...
    """

    def decorator(func: Callable[P, Any]) -> Callable[P, Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            import time  # noqa: PLC0415

            # 이벤트 루프 내에서 호출 시 경고 (time.sleep이 루프를 블로킹함)
            try:
                asyncio.get_running_loop()
                logger.warning(
                    f"sync_retry로 감싸진 '{func.__name__}'이(가) "
                    f"실행 중인 이벤트 루프 내에서 호출되었습니다. "
                    f"time.sleep()이 이벤트 루프를 블로킹합니다. "
                    f"async_retry 사용을 권장합니다."
                )
            except RuntimeError:
                # 이벤트 루프가 없는 정상 동기 컨텍스트
                pass

            current_delay = delay
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_attempts:
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise

                    logger.warning(
                        f"{func.__name__} attempt {attempt}/{max_attempts} "
                        f"failed: {e}. "
                        f"Retrying in {current_delay:.1f}s..."
                    )

                    actual_delay = current_delay
                    if jitter:
                        # +-25% 랜덤 지터로 thundering herd 방지
                        actual_delay = current_delay * (1 + random.uniform(-0.25, 0.25))

                    time.sleep(actual_delay)
                    current_delay *= backoff

            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
            return None

        return wrapper  # type: ignore[return-value]

    return decorator
