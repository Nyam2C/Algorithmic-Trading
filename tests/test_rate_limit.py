"""
Rate Limiting 미들웨어 테스트

Phase 6.1: RateLimiter, RateLimitMiddleware 테스트
"""
import asyncio
import pytest
import time
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.middleware.rate_limit import (
    TokenBucket,
    RateLimitConfig,
    RateLimiter,
    RateLimitMiddleware,
)


class TestTokenBucket:
    """TokenBucket 테스트"""

    def test_initial_tokens(self):
        """초기 토큰이 최대 용량인지 확인"""
        bucket = TokenBucket(capacity=10.0, refill_rate=1.0)

        assert bucket.tokens == 10.0

    def test_consume_success(self):
        """토큰 소비 성공 테스트"""
        bucket = TokenBucket(capacity=10.0, refill_rate=1.0)

        allowed, wait_time = bucket.consume(1)

        assert allowed is True
        assert wait_time == 0.0
        assert bucket.tokens == 9.0

    def test_consume_multiple(self):
        """다중 토큰 소비 테스트"""
        bucket = TokenBucket(capacity=10.0, refill_rate=1.0)

        allowed, _ = bucket.consume(5)

        assert allowed is True
        assert bucket.tokens == 5.0

    def test_consume_exceeds_capacity(self):
        """용량 초과 소비 실패 테스트"""
        bucket = TokenBucket(capacity=5.0, refill_rate=1.0)

        allowed, wait_time = bucket.consume(6)

        assert allowed is False
        assert wait_time > 0  # 대기 시간 필요

    def test_consume_empty_bucket(self):
        """빈 버킷 소비 실패 테스트"""
        bucket = TokenBucket(capacity=3.0, refill_rate=1.0)

        # 모든 토큰 소비
        bucket.consume(3)

        allowed, wait_time = bucket.consume(1)

        assert allowed is False
        assert wait_time == pytest.approx(1.0, rel=0.1)  # 1초 대기

    def test_refill(self):
        """토큰 보충 테스트"""
        bucket = TokenBucket(capacity=10.0, refill_rate=10.0)  # 초당 10토큰

        # 모든 토큰 소비
        bucket.consume(10)
        assert bucket.tokens == 0.0

        # 0.5초 대기
        time.sleep(0.5)

        # 다시 소비 시도 (refill 발생)
        allowed, _ = bucket.consume(4)

        # 5개 정도 보충됨 (오차 허용)
        assert allowed is True


class TestRateLimitConfig:
    """RateLimitConfig 테스트"""

    def test_capacity(self):
        """버스트 용량 계산 테스트"""
        config = RateLimitConfig(requests_per_minute=100, burst_multiplier=1.5)

        assert config.capacity == 150.0

    def test_refill_rate(self):
        """초당 토큰 보충 속도 테스트"""
        config = RateLimitConfig(requests_per_minute=60)

        assert config.refill_rate == 1.0  # 60/60 = 1


class TestRateLimiter:
    """RateLimiter 테스트"""

    @pytest.fixture
    def limiter(self):
        """테스트용 limiter 생성"""
        return RateLimiter(default_limit=100, n8n_limit=30)

    @pytest.fixture
    def mock_request(self):
        """Mock Request 생성"""
        request = MagicMock()
        request.client.host = "127.0.0.1"
        request.url.path = "/api/bots"
        request.headers = {}
        return request

    def test_get_client_id_from_host(self, limiter, mock_request):
        """클라이언트 호스트에서 ID 추출 테스트"""
        client_id = limiter._get_client_id(mock_request)

        assert client_id == "127.0.0.1"

    def test_get_client_id_from_forwarded(self, limiter, mock_request):
        """X-Forwarded-For 헤더에서 ID 추출 테스트"""
        mock_request.headers = {"x-forwarded-for": "192.168.1.1, 10.0.0.1"}

        client_id = limiter._get_client_id(mock_request)

        assert client_id == "192.168.1.1"

    def test_get_client_id_from_api_key(self, limiter, mock_request):
        """API 키에서 ID 추출 테스트"""
        mock_request.headers = {"x-api-key": "sk-1234567890abcdef"}
        mock_request.client = None

        client_id = limiter._get_client_id(mock_request)

        assert client_id == "api:sk-12345"

    def test_get_config_type_default(self, limiter):
        """기본 설정 타입 테스트"""
        config_type = limiter._get_config_type("/api/bots")

        assert config_type == "default"

    def test_get_config_type_n8n(self, limiter):
        """n8n 설정 타입 테스트"""
        config_type = limiter._get_config_type("/api/n8n/webhook")

        assert config_type == "n8n"

    @pytest.mark.asyncio
    async def test_check_rate_limit_allowed(self, limiter, mock_request):
        """요청 허용 테스트"""
        allowed, retry_after = await limiter.check_rate_limit(mock_request)

        assert allowed is True
        assert retry_after == 0.0

    @pytest.mark.asyncio
    async def test_check_rate_limit_exceeded(self, mock_request):
        """요청 제한 초과 테스트"""
        # 매우 낮은 제한으로 테스트
        limiter = RateLimiter(default_limit=2, burst_multiplier=1.0)

        # 첫 2개 요청 성공
        await limiter.check_rate_limit(mock_request)
        await limiter.check_rate_limit(mock_request)

        # 3번째 요청 실패
        allowed, retry_after = await limiter.check_rate_limit(mock_request)

        assert allowed is False
        assert retry_after > 0

    def test_get_limits_for_path(self, limiter):
        """경로별 제한 정보 테스트"""
        default_limits = limiter.get_limits_for_path("/api/bots")
        n8n_limits = limiter.get_limits_for_path("/api/n8n/webhook")

        assert default_limits["requests_per_minute"] == 100
        assert n8n_limits["requests_per_minute"] == 30

    def test_add_custom_limit(self, limiter):
        """커스텀 제한 추가 테스트"""
        limiter.add_custom_limit("premium", requests_per_minute=500)

        assert "premium" in limiter._configs
        assert limiter._configs["premium"].requests_per_minute == 500


class TestRateLimitMiddleware:
    """RateLimitMiddleware 테스트"""

    @pytest.fixture
    def app(self):
        """테스트용 FastAPI 앱 생성"""
        app = FastAPI()

        @app.get("/api/test")
        def test_endpoint():
            return {"status": "ok"}

        @app.get("/api/n8n/webhook")
        def n8n_endpoint():
            return {"status": "ok"}

        @app.get("/health")
        def health():
            return {"status": "healthy"}

        return app

    def test_middleware_allows_normal_requests(self, app):
        """정상 요청 허용 테스트"""
        limiter = RateLimiter(default_limit=100)
        app.add_middleware(RateLimitMiddleware, limiter=limiter)
        client = TestClient(app)

        response = client.get("/api/test")

        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response.headers
        assert response.headers["X-RateLimit-Limit"] == "100"

    def test_middleware_returns_429_when_exceeded(self, app):
        """제한 초과 시 429 반환 테스트"""
        limiter = RateLimiter(default_limit=2, burst_multiplier=1.0)
        app.add_middleware(RateLimitMiddleware, limiter=limiter)
        client = TestClient(app)

        # 첫 2개 요청 성공
        client.get("/api/test")
        client.get("/api/test")

        # 3번째 요청 실패
        response = client.get("/api/test")

        assert response.status_code == 429
        data = response.json()
        assert data["error"] == "rate_limit_exceeded"
        assert "retry_after" in data
        assert "Retry-After" in response.headers

    def test_middleware_excludes_health_endpoint(self, app):
        """헬스 엔드포인트 제외 테스트"""
        limiter = RateLimiter(default_limit=1, burst_multiplier=1.0)
        app.add_middleware(RateLimitMiddleware, limiter=limiter)
        client = TestClient(app)

        # /health는 제한 없이 계속 호출 가능
        for _ in range(10):
            response = client.get("/health")
            assert response.status_code == 200

    def test_middleware_different_limits_for_n8n(self, app):
        """n8n 엔드포인트 다른 제한 테스트"""
        limiter = RateLimiter(default_limit=100, n8n_limit=2, burst_multiplier=1.0)
        app.add_middleware(RateLimitMiddleware, limiter=limiter)
        client = TestClient(app)

        # n8n 첫 2개 요청 성공
        client.get("/api/n8n/webhook")
        client.get("/api/n8n/webhook")

        # 3번째 n8n 요청 실패
        response = client.get("/api/n8n/webhook")
        assert response.status_code == 429

        # 일반 API는 여전히 성공
        response = client.get("/api/test")
        assert response.status_code == 200

    def test_middleware_different_clients(self, app):
        """클라이언트별 별도 제한 테스트"""
        limiter = RateLimiter(default_limit=2, burst_multiplier=1.0)
        app.add_middleware(RateLimitMiddleware, limiter=limiter)
        client = TestClient(app)

        # 클라이언트 1 (기본 IP)
        client.get("/api/test")
        client.get("/api/test")
        response = client.get("/api/test")
        assert response.status_code == 429

        # 클라이언트 2 (다른 IP)
        response = client.get(
            "/api/test",
            headers={"X-Forwarded-For": "10.0.0.1"}
        )
        assert response.status_code == 200


class TestRateLimiterConcurrency:
    """RateLimiter 동시성 테스트"""

    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """동시 요청 처리 테스트"""
        limiter = RateLimiter(default_limit=10, burst_multiplier=1.5)  # 15 용량

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.url.path = "/api/test"
        mock_request.headers = {}

        # 10개 동시 요청
        tasks = [limiter.check_rate_limit(mock_request) for _ in range(10)]
        results = await asyncio.gather(*tasks)

        # 모두 성공해야 함 (용량 15)
        allowed_count = sum(1 for allowed, _ in results if allowed)
        assert allowed_count == 10

    @pytest.mark.asyncio
    async def test_cleanup_old_buckets(self):
        """오래된 버킷 정리 테스트"""
        limiter = RateLimiter()
        limiter._cleanup_interval = 0  # 즉시 정리

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.url.path = "/api/test"
        mock_request.headers = {}

        # 버킷 생성
        await limiter.check_rate_limit(mock_request)
        assert "127.0.0.1" in limiter._buckets

        # 버킷을 오래된 것으로 설정
        for bucket in limiter._buckets["127.0.0.1"].values():
            bucket.last_refill = time.time() - 700  # 10분+ 전

        # 정리 트리거
        limiter._last_cleanup = 0
        await limiter._maybe_cleanup()

        # 버킷이 정리됨
        assert "127.0.0.1" not in limiter._buckets
