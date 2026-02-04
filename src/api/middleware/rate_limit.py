"""
Rate Limiting 미들웨어

Phase 6.1: API Rate Limiting
- Token Bucket 알고리즘 기반
- 엔드포인트별 차등 제한
- DoS 방지
"""
import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger


@dataclass
class TokenBucket:
    """토큰 버킷 알고리즘 구현

    요청 속도 제한을 위한 토큰 버킷

    Attributes:
        capacity: 버킷 최대 용량
        refill_rate: 초당 토큰 보충 속도
        tokens: 현재 토큰 수
        last_refill: 마지막 보충 시간
    """

    capacity: float
    refill_rate: float  # tokens per second
    tokens: float = field(default=0.0, init=False)
    last_refill: float = field(default_factory=time.time, init=False)

    def __post_init__(self) -> None:
        """초기화 후 토큰을 최대 용량으로 설정"""
        self.tokens = self.capacity

    def consume(self, tokens: int = 1) -> Tuple[bool, float]:
        """토큰 소비 시도

        Args:
            tokens: 소비할 토큰 수

        Returns:
            (성공 여부, 대기 시간(초))
        """
        self._refill()

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True, 0.0
        else:
            # 필요한 토큰이 채워질 때까지 대기 시간 계산
            needed = tokens - self.tokens
            wait_time = needed / self.refill_rate
            return False, wait_time

    def _refill(self) -> None:
        """토큰 보충"""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(
            self.capacity,
            self.tokens + (elapsed * self.refill_rate)
        )
        self.last_refill = now


@dataclass
class RateLimitConfig:
    """Rate Limit 설정

    Attributes:
        requests_per_minute: 분당 요청 수
        burst_multiplier: 버스트 허용 배수
    """

    requests_per_minute: int
    burst_multiplier: float = 1.5

    @property
    def capacity(self) -> float:
        """버킷 용량 (버스트 포함)"""
        return self.requests_per_minute * self.burst_multiplier

    @property
    def refill_rate(self) -> float:
        """초당 토큰 보충 속도"""
        return self.requests_per_minute / 60.0


class RateLimiter:
    """Rate Limiter

    클라이언트별 요청 속도를 제한합니다.

    Example:
        >>> limiter = RateLimiter(default_limit=100, n8n_limit=30)
        >>> allowed, retry_after = await limiter.check_rate_limit(request)
        >>> if not allowed:
        ...     return JSONResponse(status_code=429, ...)
    """

    # 기본 설정
    DEFAULT_LIMIT = 100  # /api/* 분당 100 요청
    N8N_LIMIT = 30  # /api/n8n/* 분당 30 요청
    BURST_MULTIPLIER = 1.5

    def __init__(
        self,
        default_limit: int = DEFAULT_LIMIT,
        n8n_limit: int = N8N_LIMIT,
        burst_multiplier: float = BURST_MULTIPLIER,
    ) -> None:
        """Rate Limiter 초기화

        Args:
            default_limit: 기본 분당 요청 수
            n8n_limit: n8n 엔드포인트 분당 요청 수
            burst_multiplier: 버스트 허용 배수
        """
        self._configs: Dict[str, RateLimitConfig] = {
            "default": RateLimitConfig(default_limit, burst_multiplier),
            "n8n": RateLimitConfig(n8n_limit, burst_multiplier),
        }

        # 클라이언트별 버킷 저장소
        self._buckets: Dict[str, Dict[str, TokenBucket]] = defaultdict(dict)

        # 정리 락
        self._cleanup_lock = asyncio.Lock()
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # 5분마다 정리

        self._log = logger.bind(module="rate_limiter")
        self._log.info(
            f"RateLimiter 초기화: default={default_limit}/min, n8n={n8n_limit}/min"
        )

    def _get_client_id(self, request: Request) -> str:
        """클라이언트 식별자 추출

        Args:
            request: FastAPI Request

        Returns:
            클라이언트 식별자 (IP 또는 API 키)
        """
        # X-Forwarded-For 헤더 확인 (프록시 뒤에 있는 경우)
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # 첫 번째 IP가 실제 클라이언트
            return forwarded.split(",")[0].strip()

        # X-Real-IP 헤더 확인
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # API 키가 있으면 사용
        api_key = request.headers.get("x-api-key")
        if api_key:
            return f"api:{api_key[:8]}"

        # 기본: 클라이언트 호스트
        client = request.client
        if client:
            return client.host

        return "unknown"

    def _get_config_type(self, path: str) -> str:
        """경로에 따른 설정 타입 결정

        Args:
            path: 요청 경로

        Returns:
            설정 타입 (default 또는 n8n)
        """
        if path.startswith("/api/n8n"):
            return "n8n"
        return "default"

    def _get_bucket(self, client_id: str, config_type: str) -> TokenBucket:
        """클라이언트의 토큰 버킷 조회/생성

        Args:
            client_id: 클라이언트 식별자
            config_type: 설정 타입

        Returns:
            TokenBucket
        """
        if config_type not in self._buckets[client_id]:
            config = self._configs[config_type]
            self._buckets[client_id][config_type] = TokenBucket(
                capacity=config.capacity,
                refill_rate=config.refill_rate,
            )

        return self._buckets[client_id][config_type]

    async def check_rate_limit(
        self,
        request: Request,
    ) -> Tuple[bool, float]:
        """요청 속도 제한 확인

        Args:
            request: FastAPI Request

        Returns:
            (허용 여부, 재시도까지 대기 시간(초))
        """
        # 주기적 정리
        await self._maybe_cleanup()

        client_id = self._get_client_id(request)
        config_type = self._get_config_type(request.url.path)
        bucket = self._get_bucket(client_id, config_type)

        allowed, retry_after = bucket.consume()

        if not allowed:
            self._log.warning(
                f"Rate limit exceeded: client={client_id}, "
                f"path={request.url.path}, retry_after={retry_after:.1f}s"
            )

        return allowed, retry_after

    async def _maybe_cleanup(self) -> None:
        """오래된 버킷 정리 (주기적)"""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return

        async with self._cleanup_lock:
            # 재확인 (락 대기 중 다른 스레드가 정리했을 수 있음)
            if now - self._last_cleanup < self._cleanup_interval:
                return

            # 오래된 버킷 정리 (10분 이상 사용하지 않은 경우)
            stale_threshold = now - 600
            stale_clients = [
                client_id
                for client_id, buckets in self._buckets.items()
                if all(
                    bucket.last_refill < stale_threshold
                    for bucket in buckets.values()
                )
            ]

            for client_id in stale_clients:
                del self._buckets[client_id]

            if stale_clients:
                self._log.debug(f"Rate limiter 정리: {len(stale_clients)}개 클라이언트 제거")

            self._last_cleanup = now

    def get_limits_for_path(self, path: str) -> Dict[str, Any]:
        """경로에 대한 제한 정보 반환

        Args:
            path: 요청 경로

        Returns:
            제한 정보 딕셔너리
        """
        config_type = self._get_config_type(path)
        config = self._configs[config_type]

        return {
            "requests_per_minute": config.requests_per_minute,
            "burst_capacity": config.capacity,
        }

    def add_custom_limit(
        self,
        name: str,
        requests_per_minute: int,
        burst_multiplier: float = 1.5,
    ) -> None:
        """커스텀 제한 추가

        Args:
            name: 설정 이름
            requests_per_minute: 분당 요청 수
            burst_multiplier: 버스트 배수
        """
        self._configs[name] = RateLimitConfig(requests_per_minute, burst_multiplier)
        self._log.info(f"커스텀 제한 추가: {name}={requests_per_minute}/min")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate Limit 미들웨어

    FastAPI 앱에 적용하여 모든 요청에 대해 속도 제한을 적용합니다.

    Example:
        >>> app = FastAPI()
        >>> limiter = RateLimiter()
        >>> app.add_middleware(RateLimitMiddleware, limiter=limiter)
    """

    def __init__(
        self,
        app: Any,
        limiter: Optional[RateLimiter] = None,
        exclude_paths: Optional[list] = None,
    ) -> None:
        """미들웨어 초기화

        Args:
            app: FastAPI 앱
            limiter: RateLimiter 인스턴스
            exclude_paths: 제외할 경로 목록
        """
        super().__init__(app)
        self.limiter = limiter or RateLimiter()
        self.exclude_paths = exclude_paths or [
            "/health",
            "/ready",
            "/metrics",
            "/docs",
            "/redoc",
            "/openapi.json",
        ]
        self._log = logger.bind(module="rate_limit_middleware")

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        """요청 처리

        Args:
            request: FastAPI Request
            call_next: 다음 핸들러

        Returns:
            Response
        """
        path = request.url.path

        # 제외 경로 확인
        if self._is_excluded(path):
            return await call_next(request)

        # Rate limit 확인
        allowed, retry_after = await self.limiter.check_rate_limit(request)

        if not allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "success": False,
                    "error": "rate_limit_exceeded",
                    "message": "요청이 너무 많습니다. 잠시 후 다시 시도해주세요.",
                    "retry_after": round(retry_after, 1),
                },
                headers={
                    "Retry-After": str(int(retry_after) + 1),
                    "X-RateLimit-Limit": str(
                        self.limiter.get_limits_for_path(path)["requests_per_minute"]
                    ),
                },
            )

        # Rate limit 헤더 추가
        response = await call_next(request)

        limits = self.limiter.get_limits_for_path(path)
        response.headers["X-RateLimit-Limit"] = str(limits["requests_per_minute"])

        return response

    def _is_excluded(self, path: str) -> bool:
        """경로가 제외 대상인지 확인

        Args:
            path: 요청 경로

        Returns:
            제외 여부
        """
        for excluded in self.exclude_paths:
            if path == excluded or path.startswith(excluded):
                return True
        return False
