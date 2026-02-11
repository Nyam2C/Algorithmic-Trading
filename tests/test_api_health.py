"""
Health Check API 테스트

/health 및 /ready 엔드포인트 테스트입니다.
"""
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app


@pytest.fixture
def client():
    """테스트 클라이언트 fixture"""
    app = create_app()
    return TestClient(app)


class TestHealthEndpoint:
    """GET /health 테스트"""

    def test_health_returns_ok(self, client: TestClient):
        """헬스체크가 OK를 반환하는지 확인"""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_includes_version(self, client: TestClient):
        """헬스체크에 버전 정보가 포함되는지 확인"""
        response = client.get("/health")

        data = response.json()
        assert "version" in data


class TestReadyEndpoint:
    """GET /ready 테스트"""

    def test_ready_returns_ok_without_manager(self, client: TestClient):
        """매니저 없이도 ready가 OK를 반환하는지 확인"""
        response = client.get("/ready")

        # 매니저가 없으면 service_unavailable (503)
        assert response.status_code in [200, 503]

    def test_ready_with_manager(self):
        """매니저가 있을 때 ready가 OK를 반환하는지 확인"""
        from unittest.mock import MagicMock

        from src.bot_manager import MultiBotManager

        # Mock 매니저 생성
        mock_manager = MagicMock(spec=MultiBotManager)
        mock_manager.bot_count = 2
        mock_manager.running_count = 2

        app = create_app(bot_manager=mock_manager)
        client = TestClient(app)

        response = client.get("/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["bots"]["total"] == 2
        assert data["bots"]["running"] == 2

    def test_ready_not_ready_when_no_bots_running(self):
        """봇이 실행되지 않을 때 not ready를 반환하는지 확인"""
        from unittest.mock import MagicMock

        from src.bot_manager import MultiBotManager

        # Mock 매니저 생성 (봇은 있지만 실행 중이 아님)
        mock_manager = MagicMock(spec=MultiBotManager)
        mock_manager.bot_count = 2
        mock_manager.running_count = 0

        app = create_app(bot_manager=mock_manager)
        client = TestClient(app)

        response = client.get("/ready")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"


class TestHealthResponseFormat:
    """응답 형식 테스트"""

    def test_health_response_is_json(self, client: TestClient):
        """응답이 JSON 형식인지 확인"""
        response = client.get("/health")

        assert response.headers["content-type"] == "application/json"

    def test_ready_response_is_json(self, client: TestClient):
        """응답이 JSON 형식인지 확인"""
        response = client.get("/ready")

        assert response.headers["content-type"] == "application/json"


# =============================================================================
# src/api/dependencies.py 커버리지 테스트 (from test_api_coverage.py)
# =============================================================================


class TestDependenciesGetBotManager:
    """get_bot_manager 미커버 라인 테스트 (line 49)"""

    def test_get_bot_manager_raises_when_not_configured(self):
        """_bot_manager가 None일 때 RuntimeError 발생"""
        import src.api.dependencies as deps

        # 기존 상태 백업
        original = deps._bot_manager
        try:
            deps._bot_manager = None
            with pytest.raises(RuntimeError, match="MultiBotManager not configured"):
                deps.get_bot_manager()
        finally:
            deps._bot_manager = original


class TestDependenciesApiConfig:
    """get_api_config 미커버 라인 테스트 (lines 78-80)"""

    def test_get_api_config_returns_from_env_when_none(self):
        """_api_config가 None이면 APIConfig.from_env() 반환"""
        import src.api.dependencies as deps
        from src.api.config import APIConfig

        original = deps._api_config
        try:
            deps._api_config = None
            result = deps.get_api_config()
            assert isinstance(result, APIConfig)
        finally:
            deps._api_config = original

    def test_get_api_config_returns_stored(self):
        """_api_config가 설정되어 있으면 그것을 반환"""
        import src.api.dependencies as deps
        from src.api.config import APIConfig

        original = deps._api_config
        try:
            config = APIConfig(host="127.0.0.1", port=9000)
            deps.set_api_config(config)
            result = deps.get_api_config()
            assert result.port == 9000
        finally:
            deps._api_config = original


class TestDependenciesRedisState:
    """Redis 상태 관리 관련 dependencies 테스트 (lines 92, 103, 115-118)"""

    def test_set_and_get_redis_state_manager(self):
        """Redis 상태 관리자 설정 및 조회"""
        import src.api.dependencies as deps

        original = deps._redis_state_manager
        try:
            mock_manager = MagicMock()
            deps.set_redis_state_manager(mock_manager)
            result = deps.get_redis_state_manager()
            assert result is mock_manager
        finally:
            deps._redis_state_manager = original

    def test_get_redis_state_manager_returns_none(self):
        """Redis 관리자가 없을 때 None 반환"""
        import src.api.dependencies as deps

        original = deps._redis_state_manager
        try:
            deps._redis_state_manager = None
            result = deps.get_redis_state_manager()
            assert result is None
        finally:
            deps._redis_state_manager = original

    @pytest.mark.asyncio
    async def test_check_redis_health_no_manager(self):
        """Redis 관리자가 없을 때 False 반환 (line 113)"""
        import src.api.dependencies as deps

        original = deps._redis_state_manager
        try:
            deps._redis_state_manager = None
            result = await deps.check_redis_health()
            assert result is False
        finally:
            deps._redis_state_manager = original

    @pytest.mark.asyncio
    async def test_check_redis_health_success(self):
        """Redis ping 성공 (lines 115-116)"""
        import src.api.dependencies as deps

        original = deps._redis_state_manager
        try:
            mock_manager = MagicMock()
            mock_manager.ping = AsyncMock(return_value=True)
            deps._redis_state_manager = mock_manager
            result = await deps.check_redis_health()
            assert result is True
        finally:
            deps._redis_state_manager = original

    @pytest.mark.asyncio
    async def test_check_redis_health_exception(self):
        """Redis ping 예외 발생 시 False 반환 (lines 117-118)"""
        import src.api.dependencies as deps

        original = deps._redis_state_manager
        try:
            mock_manager = MagicMock()
            mock_manager.ping = AsyncMock(side_effect=Exception("Connection lost"))
            deps._redis_state_manager = mock_manager
            result = await deps.check_redis_health()
            assert result is False
        finally:
            deps._redis_state_manager = original


class TestDependenciesTradeAnalyzer:
    """TradeHistoryAnalyzer 의존성 테스트 (lines 133, 142)"""

    def test_set_and_get_trade_analyzer(self):
        """TradeHistoryAnalyzer 설정 및 조회"""
        import src.api.dependencies as deps

        original = deps._trade_analyzer
        try:
            mock_analyzer = MagicMock()
            deps.set_trade_analyzer(mock_analyzer)
            result = deps.get_trade_analyzer()
            assert result is mock_analyzer
        finally:
            deps._trade_analyzer = original

    def test_get_trade_analyzer_returns_none(self):
        """TradeHistoryAnalyzer가 없을 때 None 반환"""
        import src.api.dependencies as deps

        original = deps._trade_analyzer
        try:
            deps._trade_analyzer = None
            result = deps.get_trade_analyzer()
            assert result is None
        finally:
            deps._trade_analyzer = original


class TestDependenciesN8NApiKey:
    """n8n API 키 검증 테스트 (line 166)"""

    @pytest.mark.asyncio
    async def test_verify_n8n_api_key_no_env_key(self):
        """N8N_API_KEY 환경변수 미설정 시 500 에러"""
        from fastapi import HTTPException

        from src.api.dependencies import verify_n8n_api_key

        with patch.dict(os.environ, {}, clear=True):
            # N8N_API_KEY를 제거
            os.environ.pop("N8N_API_KEY", None)
            with pytest.raises(HTTPException) as exc_info:
                await verify_n8n_api_key(x_n8n_api_key="some-key")
            assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_verify_n8n_api_key_invalid(self):
        """잘못된 n8n API 키 - 401 에러"""
        from fastapi import HTTPException

        from src.api.dependencies import verify_n8n_api_key

        with patch.dict(os.environ, {"N8N_API_KEY": "correct-key"}):
            with pytest.raises(HTTPException) as exc_info:
                await verify_n8n_api_key(x_n8n_api_key="wrong-key")
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_verify_n8n_api_key_success(self):
        """n8n API 키 검증 성공"""
        from src.api.dependencies import verify_n8n_api_key

        with patch.dict(os.environ, {"N8N_API_KEY": "valid-key"}):
            result = await verify_n8n_api_key(x_n8n_api_key="valid-key")
            assert result == "valid-key"


class TestDependenciesApiKey:
    """일반 API 키 검증 테스트 (lines 193, 200)"""

    @pytest.mark.asyncio
    async def test_verify_api_key_no_env_key(self):
        """API_KEY 환경변수 미설정 시 500 에러"""
        from fastapi import HTTPException

        from src.api.dependencies import verify_api_key

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("API_KEY", None)
            with pytest.raises(HTTPException) as exc_info:
                await verify_api_key(x_api_key="some-key")
            assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_verify_api_key_invalid(self):
        """잘못된 API 키 - 401 에러"""
        from fastapi import HTTPException

        from src.api.dependencies import verify_api_key

        with patch.dict(os.environ, {"API_KEY": "correct-key"}):
            with pytest.raises(HTTPException) as exc_info:
                await verify_api_key(x_api_key="wrong-key")
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_verify_api_key_success(self):
        """API 키 검증 성공"""
        from src.api.dependencies import verify_api_key

        with patch.dict(os.environ, {"API_KEY": "valid-key"}):
            result = await verify_api_key(x_api_key="valid-key")
            assert result == "valid-key"


class TestDependenciesSignalTracker:
    """SignalTracker 의존성 테스트 (lines 216, 228-230, 239)"""

    def test_set_and_get_signal_tracker(self):
        """SignalTracker 설정 및 조회"""
        import src.api.dependencies as deps

        original = deps._signal_tracker
        try:
            mock_tracker = MagicMock()
            deps.set_signal_tracker(mock_tracker)
            result = deps.get_signal_tracker()
            assert result is mock_tracker
        finally:
            deps._signal_tracker = original

    def test_get_signal_tracker_raises_when_none(self):
        """SignalTracker가 None일 때 RuntimeError 발생 (lines 228-230)"""
        import src.api.dependencies as deps

        original = deps._signal_tracker
        try:
            deps._signal_tracker = None
            with pytest.raises(RuntimeError, match="SignalTracker not configured"):
                deps.get_signal_tracker()
        finally:
            deps._signal_tracker = original

    def test_get_optional_signal_tracker_returns_none(self):
        """optional signal tracker가 None 반환 (line 239)"""
        import src.api.dependencies as deps

        original = deps._signal_tracker
        try:
            deps._signal_tracker = None
            result = deps.get_optional_signal_tracker()
            assert result is None
        finally:
            deps._signal_tracker = original

    def test_get_optional_signal_tracker_returns_tracker(self):
        """optional signal tracker가 값을 반환"""
        import src.api.dependencies as deps

        original = deps._signal_tracker
        try:
            mock_tracker = MagicMock()
            deps._signal_tracker = mock_tracker
            result = deps.get_optional_signal_tracker()
            assert result is mock_tracker
        finally:
            deps._signal_tracker = original
