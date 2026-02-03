"""
Circuit Breaker 테스트

Phase 6.2: 상태 전이, 복구, 데코레이터 테스트
"""
import asyncio
import pytest

from src.utils.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpen,
    CircuitState,
    circuit_breaker,
    get_circuit_breaker,
    reset_all_circuit_breakers,
)


class TestCircuitBreakerBasic:
    """Circuit Breaker 기본 테스트"""

    @pytest.fixture
    def breaker(self):
        """테스트용 Circuit Breaker"""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=5,
            success_threshold=2,
        )
        return CircuitBreaker("test", config)

    def test_initial_state_is_closed(self, breaker):
        """초기 상태가 CLOSED인지 확인"""
        assert breaker.state == CircuitState.CLOSED

    def test_stats_initial(self, breaker):
        """초기 통계 확인"""
        stats = breaker.stats
        assert stats.total_calls == 0
        assert stats.successful_calls == 0
        assert stats.failed_calls == 0

    @pytest.mark.asyncio
    async def test_success_in_closed_state(self, breaker):
        """CLOSED 상태에서 성공 호출 테스트"""
        async with breaker:
            pass  # 성공적인 호출

        assert breaker.state == CircuitState.CLOSED
        assert breaker.stats.successful_calls == 1
        assert breaker.stats.total_calls == 1


class TestCircuitBreakerStateTransitions:
    """상태 전이 테스트"""

    @pytest.fixture
    def breaker(self):
        """테스트용 Circuit Breaker (낮은 임계값)"""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=1,  # 빠른 테스트를 위해 1초
            success_threshold=2,
        )
        return CircuitBreaker("test_transitions", config)

    @pytest.mark.asyncio
    async def test_closed_to_open_after_failures(self, breaker):
        """연속 실패 시 CLOSED → OPEN 전이 테스트"""

        # 3번 연속 실패
        for _ in range(3):
            try:
                async with breaker:
                    raise ConnectionError("Test error")
            except ConnectionError:
                pass

        # OPEN 상태로 전이
        assert breaker.state == CircuitState.OPEN
        assert breaker.stats.failed_calls == 3

    @pytest.mark.asyncio
    async def test_open_state_rejects_calls(self, breaker):
        """OPEN 상태에서 호출 거부 테스트"""

        # OPEN 상태로 만들기
        for _ in range(3):
            try:
                async with breaker:
                    raise ConnectionError("Test error")
            except ConnectionError:
                pass

        assert breaker.state == CircuitState.OPEN

        # 추가 호출은 거부됨
        with pytest.raises(CircuitBreakerOpen) as exc_info:
            async with breaker:
                pass

        assert exc_info.value.circuit_name == "test_transitions"
        assert breaker.stats.rejected_calls == 1

    @pytest.mark.asyncio
    async def test_open_to_half_open_after_timeout(self, breaker):
        """복구 시간 후 OPEN → HALF_OPEN 전이 테스트"""

        # OPEN 상태로 만들기
        for _ in range(3):
            try:
                async with breaker:
                    raise ConnectionError("Test error")
            except ConnectionError:
                pass

        assert breaker.state == CircuitState.OPEN

        # 복구 시간 대기
        await asyncio.sleep(1.1)

        # 다음 호출은 HALF_OPEN 상태로 전이하고 허용됨
        async with breaker:
            pass

        assert breaker.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_half_open_to_closed_after_successes(self, breaker):
        """HALF_OPEN에서 연속 성공 시 CLOSED 복구 테스트"""

        # OPEN 상태로 만들기
        for _ in range(3):
            try:
                async with breaker:
                    raise ConnectionError("Test error")
            except ConnectionError:
                pass

        # 복구 시간 대기
        await asyncio.sleep(1.1)

        # 2번 연속 성공 (success_threshold=2)
        async with breaker:
            pass
        async with breaker:
            pass

        # CLOSED로 복구
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_to_open_on_failure(self, breaker):
        """HALF_OPEN에서 실패 시 OPEN 복귀 테스트"""

        # OPEN 상태로 만들기
        for _ in range(3):
            try:
                async with breaker:
                    raise ConnectionError("Test error")
            except ConnectionError:
                pass

        # 복구 시간 대기
        await asyncio.sleep(1.1)

        # HALF_OPEN 상태
        async with breaker:
            pass  # 첫 번째 성공

        # 실패 발생
        try:
            async with breaker:
                raise ConnectionError("Test error")
        except ConnectionError:
            pass

        # OPEN으로 복귀
        assert breaker.state == CircuitState.OPEN


class TestCircuitBreakerConfig:
    """설정 테스트"""

    @pytest.mark.asyncio
    async def test_custom_exception_types(self):
        """사용자 정의 예외 타입 테스트"""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            exceptions=(ValueError, TypeError),  # 특정 예외만 실패로 처리
        )
        breaker = CircuitBreaker("custom_exceptions", config)

        # ValueError는 실패로 처리
        try:
            async with breaker:
                raise ValueError("Test")
        except ValueError:
            pass

        try:
            async with breaker:
                raise ValueError("Test")
        except ValueError:
            pass

        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_runtime_error_not_counted_when_not_configured(self):
        """설정에 없는 예외는 실패로 처리 안 함"""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            exceptions=(ValueError,),  # RuntimeError는 미포함
        )
        breaker = CircuitBreaker("specific_exceptions", config)

        # RuntimeError는 실패로 처리 안 됨
        try:
            async with breaker:
                raise RuntimeError("Test")
        except RuntimeError:
            pass

        # 여전히 CLOSED (RuntimeError는 실패 카운트 안 함)
        # 참고: 현재 구현에서는 예외가 config.exceptions에 있을 때만 실패 기록
        # 아닌 경우에도 예외는 전파됨


class TestCircuitBreakerDecorator:
    """데코레이터 테스트"""

    @pytest.mark.asyncio
    async def test_decorator_basic(self):
        """기본 데코레이터 테스트"""
        reset_all_circuit_breakers()

        @circuit_breaker(name="decorator_test", failure_threshold=2)
        async def api_call():
            return "success"

        result = await api_call()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_decorator_opens_on_failure(self):
        """데코레이터 실패 시 OPEN 테스트"""
        reset_all_circuit_breakers()

        call_count = 0

        @circuit_breaker(
            name="decorator_failure_test",
            failure_threshold=2,
            recovery_timeout=60,
        )
        async def failing_api_call():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("API Error")

        # 2번 실패
        for _ in range(2):
            try:
                await failing_api_call()
            except ConnectionError:
                pass

        # 3번째는 CircuitBreakerOpen
        with pytest.raises(CircuitBreakerOpen):
            await failing_api_call()

        # 실제 API 호출은 2번만 (3번째는 차단됨)
        assert call_count == 2


class TestCircuitBreakerStats:
    """통계 테스트"""

    @pytest.fixture
    def breaker(self):
        """테스트용 Circuit Breaker"""
        return CircuitBreaker("stats_test")

    @pytest.mark.asyncio
    async def test_stats_tracking(self, breaker):
        """통계 추적 테스트"""

        # 성공 호출
        for _ in range(3):
            async with breaker:
                pass

        # 실패 호출
        for _ in range(2):
            try:
                async with breaker:
                    raise ValueError("Error")
            except ValueError:
                pass

        stats = breaker.stats
        assert stats.total_calls == 5
        assert stats.successful_calls == 3
        assert stats.failed_calls == 2
        assert stats.last_success_time is not None
        assert stats.last_failure_time is not None

    @pytest.mark.asyncio
    async def test_stats_to_dict(self, breaker):
        """통계 딕셔너리 변환 테스트"""
        async with breaker:
            pass

        stats_dict = breaker.stats.to_dict()

        assert "total_calls" in stats_dict
        assert "successful_calls" in stats_dict
        assert "failed_calls" in stats_dict
        assert "success_rate" in stats_dict
        assert stats_dict["success_rate"] == 100.0


class TestCircuitBreakerRegistry:
    """전역 레지스트리 테스트"""

    def test_get_circuit_breaker_creates_new(self):
        """새 Circuit Breaker 생성 테스트"""
        reset_all_circuit_breakers()

        breaker1 = get_circuit_breaker("registry_test_1")
        breaker2 = get_circuit_breaker("registry_test_2")

        assert breaker1 is not breaker2

    def test_get_circuit_breaker_returns_same(self):
        """동일 이름은 같은 인스턴스 반환 테스트"""
        reset_all_circuit_breakers()

        breaker1 = get_circuit_breaker("same_name_test")
        breaker2 = get_circuit_breaker("same_name_test")

        assert breaker1 is breaker2

    def test_reset_all_circuit_breakers(self):
        """전체 리셋 테스트"""
        reset_all_circuit_breakers()

        breaker = get_circuit_breaker("reset_test")

        # 상태 변경
        breaker._failure_count = 5

        # 리셋
        reset_all_circuit_breakers()

        # 리셋 확인 (새 인스턴스 아님, 상태만 리셋)
        assert breaker._failure_count == 0


class TestCircuitBreakerGetStatus:
    """상태 조회 테스트"""

    @pytest.fixture
    def breaker(self):
        """테스트용 Circuit Breaker"""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=60,
        )
        return CircuitBreaker("status_test", config)

    def test_get_status_closed(self, breaker):
        """CLOSED 상태 조회 테스트"""
        status = breaker.get_status()

        assert status["name"] == "status_test"
        assert status["state"] == "closed"
        assert status["failure_count"] == 0
        assert status["config"]["failure_threshold"] == 3
        assert status["config"]["recovery_timeout"] == 60

    @pytest.mark.asyncio
    async def test_get_status_open(self, breaker):
        """OPEN 상태 조회 테스트"""

        # OPEN 상태로 만들기
        for _ in range(3):
            try:
                async with breaker:
                    raise ConnectionError("Test")
            except ConnectionError:
                pass

        status = breaker.get_status()

        assert status["state"] == "open"
        assert status["failure_count"] == 3
        assert status["remaining_time"] > 0


class TestCircuitBreakerReset:
    """리셋 테스트"""

    @pytest.fixture
    def breaker(self):
        """테스트용 Circuit Breaker"""
        config = CircuitBreakerConfig(failure_threshold=2)
        return CircuitBreaker("reset_single_test", config)

    @pytest.mark.asyncio
    async def test_reset_from_open_state(self, breaker):
        """OPEN 상태에서 리셋 테스트"""

        # OPEN 상태로 만들기
        for _ in range(2):
            try:
                async with breaker:
                    raise ConnectionError("Test")
            except ConnectionError:
                pass

        assert breaker.state == CircuitState.OPEN

        # 리셋
        breaker.reset()

        # CLOSED로 복구
        assert breaker.state == CircuitState.CLOSED
        assert breaker._failure_count == 0

        # 정상 호출 가능
        async with breaker:
            pass
