"""
Tests for retry decorators
"""
import pytest
import asyncio
from unittest.mock import patch
import time

from src.utils.retry import async_retry, sync_retry


class TestAsyncRetry:
    """async_retry 데코레이터 테스트"""

    @pytest.mark.asyncio
    async def test_success_first_attempt(self):
        """첫 번째 시도에서 성공"""
        call_count = 0

        @async_retry(max_attempts=3, delay=0.01)
        async def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await successful_func()

        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_success_after_retry(self):
        """재시도 후 성공"""
        call_count = 0

        @async_retry(max_attempts=3, delay=0.01)
        async def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary error")
            return "success"

        result = await failing_then_success()

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_max_attempts_exceeded(self):
        """최대 재시도 횟수 초과"""
        call_count = 0

        @async_retry(max_attempts=3, delay=0.01, exceptions=(ValueError,))
        async def always_failing():
            nonlocal call_count
            call_count += 1
            raise ValueError("Persistent error")

        with pytest.raises(ValueError, match="Persistent error"):
            await always_failing()

        assert call_count == 3

    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        """지수 백오프 확인"""
        delays = []
        original_sleep = asyncio.sleep

        async def mock_sleep(seconds):
            delays.append(seconds)
            await original_sleep(0.001)

        call_count = 0

        @async_retry(max_attempts=4, delay=0.1, backoff=2.0, exceptions=(ValueError,))
        async def failing_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Error")

        with patch("asyncio.sleep", mock_sleep):
            with pytest.raises(ValueError):
                await failing_func()

        # delay: 0.1, 0.2, 0.4 (마지막 시도 후에는 sleep 없음)
        assert len(delays) == 3
        assert delays[0] == pytest.approx(0.1, rel=0.1)
        assert delays[1] == pytest.approx(0.2, rel=0.1)
        assert delays[2] == pytest.approx(0.4, rel=0.1)

    @pytest.mark.asyncio
    async def test_specific_exceptions(self):
        """특정 예외만 재시도"""
        call_count = 0

        @async_retry(max_attempts=3, delay=0.01, exceptions=(ValueError,))
        async def specific_exception():
            nonlocal call_count
            call_count += 1
            raise TypeError("Different error")

        # TypeError는 재시도 대상이 아님
        with pytest.raises(TypeError):
            await specific_exception()

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_multiple_exception_types(self):
        """여러 예외 타입 재시도"""
        call_count = 0

        @async_retry(max_attempts=3, delay=0.01, exceptions=(ValueError, ConnectionError))
        async def multi_exception():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Value error")
            elif call_count == 2:
                raise ConnectionError("Connection error")
            return "success"

        result = await multi_exception()

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_preserves_function_metadata(self):
        """함수 메타데이터 보존"""
        @async_retry(max_attempts=3, delay=0.01)
        async def documented_func():
            """This is a docstring"""
            return "result"

        assert documented_func.__name__ == "documented_func"
        assert documented_func.__doc__ == "This is a docstring"

    @pytest.mark.asyncio
    async def test_default_parameters(self):
        """기본 파라미터"""
        @async_retry()
        async def default_retry():
            return "success"

        result = await default_retry()

        assert result == "success"


class TestSyncRetry:
    """sync_retry 데코레이터 테스트"""

    def test_success_first_attempt(self):
        """첫 번째 시도에서 성공"""
        call_count = 0

        @sync_retry(max_attempts=3, delay=0.01)
        def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_func()

        assert result == "success"
        assert call_count == 1

    def test_success_after_retry(self):
        """재시도 후 성공"""
        call_count = 0

        @sync_retry(max_attempts=3, delay=0.01)
        def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary error")
            return "success"

        result = failing_then_success()

        assert result == "success"
        assert call_count == 3

    def test_max_attempts_exceeded(self):
        """최대 재시도 횟수 초과"""
        call_count = 0

        @sync_retry(max_attempts=3, delay=0.01, exceptions=(ValueError,))
        def always_failing():
            nonlocal call_count
            call_count += 1
            raise ValueError("Persistent error")

        with pytest.raises(ValueError, match="Persistent error"):
            always_failing()

        assert call_count == 3

    def test_exponential_backoff(self):
        """지수 백오프 확인"""
        delays = []
        original_sleep = time.sleep

        def mock_sleep(seconds):
            delays.append(seconds)
            original_sleep(0.001)

        call_count = 0

        @sync_retry(max_attempts=4, delay=0.1, backoff=2.0, exceptions=(ValueError,))
        def failing_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Error")

        with patch("time.sleep", mock_sleep):
            with pytest.raises(ValueError):
                failing_func()

        # delay: 0.1, 0.2, 0.4
        assert len(delays) == 3
        assert delays[0] == pytest.approx(0.1, rel=0.1)
        assert delays[1] == pytest.approx(0.2, rel=0.1)
        assert delays[2] == pytest.approx(0.4, rel=0.1)

    def test_specific_exceptions(self):
        """특정 예외만 재시도"""
        call_count = 0

        @sync_retry(max_attempts=3, delay=0.01, exceptions=(ValueError,))
        def specific_exception():
            nonlocal call_count
            call_count += 1
            raise TypeError("Different error")

        with pytest.raises(TypeError):
            specific_exception()

        assert call_count == 1

    def test_preserves_function_metadata(self):
        """함수 메타데이터 보존"""
        @sync_retry(max_attempts=3, delay=0.01)
        def documented_func():
            """This is a docstring"""
            return "result"

        assert documented_func.__name__ == "documented_func"
        assert documented_func.__doc__ == "This is a docstring"


class TestRetryWithArguments:
    """인자가 있는 함수 재시도 테스트"""

    @pytest.mark.asyncio
    async def test_async_with_args(self):
        """비동기 함수 인자 전달"""
        call_count = 0

        @async_retry(max_attempts=3, delay=0.01)
        async def func_with_args(a, b, c=None):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Retry")
            return a + b + (c or 0)

        result = await func_with_args(1, 2, c=3)

        assert result == 6
        assert call_count == 2

    def test_sync_with_args(self):
        """동기 함수 인자 전달"""
        call_count = 0

        @sync_retry(max_attempts=3, delay=0.01)
        def func_with_args(a, b, c=None):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Retry")
            return a + b + (c or 0)

        result = func_with_args(1, 2, c=3)

        assert result == 6
        assert call_count == 2


class TestRetryEdgeCases:
    """경계값 테스트"""

    @pytest.mark.asyncio
    async def test_single_attempt(self):
        """최대 시도 1회"""
        call_count = 0

        @async_retry(max_attempts=1, delay=0.01, exceptions=(ValueError,))
        async def single_attempt():
            nonlocal call_count
            call_count += 1
            raise ValueError("Error")

        with pytest.raises(ValueError):
            await single_attempt()

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_zero_delay(self):
        """지연 시간 0"""
        call_count = 0

        @async_retry(max_attempts=3, delay=0, exceptions=(ValueError,))
        async def zero_delay():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Retry")
            return "success"

        result = await zero_delay()

        assert result == "success"

    @pytest.mark.asyncio
    async def test_no_backoff(self):
        """백오프 없음 (backoff=1.0)"""
        delays = []

        async def mock_sleep(seconds):
            delays.append(seconds)

        call_count = 0

        @async_retry(max_attempts=4, delay=0.1, backoff=1.0, exceptions=(ValueError,))
        async def no_backoff():
            nonlocal call_count
            call_count += 1
            raise ValueError("Error")

        with patch("asyncio.sleep", mock_sleep):
            with pytest.raises(ValueError):
                await no_backoff()

        # 모든 지연이 동일해야 함
        assert all(d == 0.1 for d in delays)


class TestRetryRealWorldScenarios:
    """실제 사용 시나리오 테스트"""

    @pytest.mark.asyncio
    async def test_api_call_simulation(self):
        """API 호출 시뮬레이션"""
        call_count = 0

        @async_retry(
            max_attempts=3,
            delay=0.01,
            backoff=2.0,
            exceptions=(ConnectionError, TimeoutError)
        )
        async def api_call():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Connection refused")
            elif call_count == 2:
                raise TimeoutError("Request timed out")
            return {"status": "ok"}

        result = await api_call()

        assert result == {"status": "ok"}
        assert call_count == 3

    def test_database_connection_simulation(self):
        """데이터베이스 연결 시뮬레이션"""
        call_count = 0

        class DatabaseError(Exception):
            pass

        @sync_retry(
            max_attempts=3,
            delay=0.01,
            exceptions=(DatabaseError,)
        )
        def db_connect():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise DatabaseError("Connection pool exhausted")
            return "connected"

        result = db_connect()

        assert result == "connected"
        assert call_count == 3
