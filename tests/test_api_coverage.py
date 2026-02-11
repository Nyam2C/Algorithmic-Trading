"""
API 모듈 커버리지 향상 테스트

대상 모듈:
- src/api/dependencies.py (미커버 라인: 49, 78-80, 92, 103, 115-118, 133, 142, 166, 193, 200, 216, 228-230, 239)
- src/api/main.py (미커버 라인: 79-80, 91-92, 103-104, 123, 127, 148-150, 173-177)
- src/api/routes/dashboard.py (미커버 라인: 116-118, 135, 179-181, 233-235, 267-269, 296-301, 304-308, 314, 350-352, 365)
- src/api/services/n8n_callback.py (미커버 라인: 54-58, 65-68, 97-107, 172, 174, 176)
- src/api/services/bot_service.py (미커버 라인: 23개)
"""
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# =============================================================================
# src/api/dependencies.py 테스트
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


# =============================================================================
# src/api/main.py 테스트
# =============================================================================


class TestAppExceptionHandlers:
    """전역 예외 핸들러 테스트 (lines 79-80, 91-92, 103-104)"""

    @pytest.fixture
    def error_app(self):
        """에러를 발생시키는 테스트 앱"""
        from src.api.main import create_app

        app = create_app()

        @app.get("/test/value-error")
        async def raise_value_error():
            raise ValueError("테스트 값 에러")

        @app.get("/test/runtime-error")
        async def raise_runtime_error():
            raise RuntimeError("테스트 런타임 에러")

        @app.get("/test/general-error")
        async def raise_general_error():
            raise TypeError("테스트 일반 에러")

        return app

    def test_value_error_handler(self, error_app):
        """ValueError 핸들러 테스트 (lines 79-80)"""
        client = TestClient(error_app, raise_server_exceptions=False)
        response = client.get("/test/value-error")

        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "bad_request"
        assert "테스트 값 에러" in data["message"]

    def test_runtime_error_handler(self, error_app):
        """RuntimeError 핸들러 테스트 (lines 91-92)"""
        client = TestClient(error_app, raise_server_exceptions=False)
        response = client.get("/test/runtime-error")

        assert response.status_code == 500
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "internal_error"

    def test_general_exception_handler(self, error_app):
        """일반 Exception 핸들러 테스트 (lines 103-104)"""
        client = TestClient(error_app, raise_server_exceptions=False)
        response = client.get("/test/general-error")

        assert response.status_code == 500
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "internal_error"
        assert data["message"] == "An unexpected error occurred"


class TestAppStartupShutdown:
    """앱 시작/종료 이벤트 테스트 (lines 123, 127)"""

    def test_startup_and_shutdown_events(self):
        """startup/shutdown 이벤트가 정상 동작"""
        from src.api.main import create_app

        app = create_app()
        # TestClient 사용으로 startup/shutdown 이벤트가 실행됨
        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200


class TestAppRateLimitConfig:
    """Rate Limit 설정 테스트"""

    def test_rate_limit_disabled(self):
        """Rate limit 비활성화"""
        from src.api.main import create_app

        with patch.dict(os.environ, {"RATE_LIMIT_ENABLED": "false"}):
            app = create_app()
            assert app is not None

    def test_rate_limit_custom_values(self):
        """Rate limit 사용자 정의 값"""
        from src.api.main import create_app

        with patch.dict(os.environ, {
            "RATE_LIMIT_ENABLED": "true",
            "RATE_LIMIT_DEFAULT": "200",
            "RATE_LIMIT_N8N": "50",
        }):
            app = create_app()
            assert app is not None


class TestRunServer:
    """run_server 테스트 (lines 148-150)"""

    def test_run_server_calls_uvicorn(self):
        """run_server가 uvicorn.run 호출"""
        from src.api.main import run_server

        with patch("src.api.main.uvicorn", create=True) as mock_uvicorn_module:
            # uvicorn 모듈이 import되기 때문에 직접 패치
            with patch.dict("sys.modules", {"uvicorn": mock_uvicorn_module}):
                mock_uvicorn_module.run = MagicMock()
                run_server(host="127.0.0.1", port=9000, reload=True)
                mock_uvicorn_module.run.assert_called_once_with(
                    "src.api.main:app",
                    host="127.0.0.1",
                    port=9000,
                    reload=True,
                )


class TestRunEmbeddedServer:
    """run_embedded_server 테스트 (lines 173-177)"""

    @pytest.mark.asyncio
    async def test_run_embedded_server(self):
        """내장 서버 실행"""
        from src.api.main import run_embedded_server

        mock_app = MagicMock()

        with patch("src.api.main.uvicorn", create=True) as mock_uvicorn_module:
            mock_server = MagicMock()
            mock_server.serve = AsyncMock()
            mock_config = MagicMock()
            mock_uvicorn_module.Config = MagicMock(return_value=mock_config)
            mock_uvicorn_module.Server = MagicMock(return_value=mock_server)

            with patch.dict("sys.modules", {"uvicorn": mock_uvicorn_module}):
                await run_embedded_server(mock_app, host="0.0.0.0", port=8080)

            mock_server.serve.assert_called_once()


class TestCreateAppWithConfig:
    """create_app 설정 관련 테스트"""

    def test_create_app_with_debug_config(self):
        """디버그 모드 설정"""
        from src.api.config import APIConfig
        from src.api.main import create_app

        config = APIConfig(debug=True)
        app = create_app(api_config=config)
        assert app.docs_url == "/docs"
        assert app.redoc_url == "/redoc"

    def test_create_app_without_debug_config(self):
        """프로덕션 모드 설정 (docs 비활성)"""
        from src.api.config import APIConfig
        from src.api.main import create_app

        config = APIConfig(debug=False)
        app = create_app(api_config=config)
        assert app.docs_url is None
        assert app.redoc_url is None

    def test_create_app_cors_origins(self):
        """CORS 오리진 환경변수 설정"""
        from src.api.main import create_app

        with patch.dict(os.environ, {"CORS_ORIGINS": "http://localhost:3000,http://example.com"}):
            app = create_app()
            assert app is not None


# =============================================================================
# src/api/routes/dashboard.py 테스트
# =============================================================================


class TestDashboardOverviewError:
    """대시보드 개요 에러 케이스 (lines 116-118)"""

    @pytest.fixture
    def mock_bot_manager_error(self):
        """에러를 발생시키는 Mock BotManager"""
        manager = MagicMock()
        manager.get_all_bots.side_effect = Exception("DB 연결 실패")
        return manager

    @pytest.fixture
    def app(self, mock_bot_manager_error):
        """테스트용 FastAPI 앱"""
        app = FastAPI()
        from src.api.dependencies import get_bot_manager
        from src.api.routes.dashboard import router

        app.include_router(router, prefix="/api")
        app.dependency_overrides[get_bot_manager] = lambda: mock_bot_manager_error
        return app

    @pytest.fixture
    def client(self, app):
        return TestClient(app, raise_server_exceptions=False)

    def test_overview_exception_returns_500(self, client):
        """개요 조회 예외 시 500 반환"""
        response = client.get("/api/dashboard/overview")
        assert response.status_code == 500


class TestDashboardBotMetricsError:
    """봇 메트릭 에러 케이스 (lines 135, 179-181)"""

    @pytest.fixture
    def app_metrics_error(self):
        """에러를 발생시키는 앱 설정"""
        app = FastAPI()
        from src.api.dependencies import get_bot_manager
        from src.api.routes.dashboard import router

        # bot_manager가 None인 경우 (line 135 - 503 에러)
        app.include_router(router, prefix="/api")
        app.dependency_overrides[get_bot_manager] = lambda: None
        return app

    def test_bot_metrics_no_manager(self, app_metrics_error):
        """BotManager 없을 때 봇 메트릭 조회 (line 135)"""
        client = TestClient(app_metrics_error, raise_server_exceptions=False)
        response = client.get("/api/dashboard/bots/test-bot/metrics")
        assert response.status_code == 503

    def test_bot_metrics_exception(self):
        """봇 메트릭 예외 발생 (lines 179-181)"""
        app = FastAPI()
        from src.api.dependencies import get_bot_manager
        from src.api.routes.dashboard import router

        mock_manager = MagicMock()
        mock_manager.get_bot_state.side_effect = RuntimeError("Internal error")

        app.include_router(router, prefix="/api")
        app.dependency_overrides[get_bot_manager] = lambda: mock_manager

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/dashboard/bots/test-bot/metrics")
        assert response.status_code == 500


class TestDashboardSignalPerformanceError:
    """신호 성과 조회 에러 케이스 (lines 233-235)"""

    def test_signal_performance_exception(self):
        """신호 성과 조회 예외 시 500 반환"""
        app = FastAPI()
        from src.api.dependencies import get_bot_manager, get_optional_signal_tracker
        from src.api.routes.dashboard import router

        mock_tracker = MagicMock()
        mock_tracker.get_signal_stats = AsyncMock(side_effect=Exception("DB 에러"))

        app.include_router(router, prefix="/api")
        app.dependency_overrides[get_bot_manager] = lambda: MagicMock()
        app.dependency_overrides[get_optional_signal_tracker] = lambda: mock_tracker

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/dashboard/signals/performance")
        assert response.status_code == 500


class TestDashboardAllBotsError:
    """모든 봇 상태 조회 에러 케이스 (lines 267-269)"""

    def test_all_bots_status_exception(self):
        """봇 상태 조회 예외 시 500 반환"""
        app = FastAPI()
        from src.api.dependencies import get_bot_manager
        from src.api.routes.dashboard import router

        mock_manager = MagicMock()
        mock_manager.get_all_bots.side_effect = Exception("DB 에러")

        app.include_router(router, prefix="/api")
        app.dependency_overrides[get_bot_manager] = lambda: mock_manager

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/dashboard/bots")
        assert response.status_code == 500


class TestDashboardRealtimeData:
    """_get_realtime_data 내부 함수 테스트 (lines 296-308, 314, 350-352)"""

    @pytest.mark.asyncio
    async def test_get_realtime_data_no_manager(self):
        """bot_manager가 None인 경우 (line 314)"""
        from src.api.routes.dashboard import _get_realtime_data

        result = await _get_realtime_data(None)
        assert result["type"] == "update"
        assert result["status"] == "no_manager"

    @pytest.mark.asyncio
    async def test_get_realtime_data_with_positions(self):
        """포지션이 있는 봇 데이터 (lines 296-301)"""
        from src.api.routes.dashboard import _get_realtime_data

        mock_manager = MagicMock()
        mock_manager.get_all_bots.return_value = [
            {
                "bot_name": "btc-bot",
                "is_running": True,
                "is_paused": False,
                "current_price": 50000.0,
                "last_signal": "LONG",
                "position": {
                    "side": "LONG",
                    "entry_price": 49000.0,
                    "unrealized_pnl": 100.0,
                },
            },
            {
                "bot_name": "eth-bot",
                "is_running": False,
                "is_paused": False,
                "current_price": 3000.0,
                "last_signal": "WAIT",
                "position": None,
            },
        ]

        result = await _get_realtime_data(mock_manager)

        assert result["type"] == "update"
        assert len(result["bots"]) == 2
        assert result["bots"][0]["position"]["side"] == "LONG"
        assert result["bots"][1]["position"] is None
        assert result["summary"]["total_bots"] == 2
        assert result["summary"]["running"] == 1
        assert result["summary"]["with_position"] == 1

    @pytest.mark.asyncio
    async def test_get_realtime_data_exception(self):
        """데이터 수집 예외 시 에러 응답 (lines 350-352)"""
        from src.api.routes.dashboard import _get_realtime_data

        mock_manager = MagicMock()
        mock_manager.get_all_bots.side_effect = Exception("데이터 수집 실패")

        result = await _get_realtime_data(mock_manager)

        assert result["type"] == "error"
        assert "데이터 수집 실패" in result["error"]


class TestBroadcastUpdate:
    """broadcast_update 테스트 (line 365)"""

    @pytest.mark.asyncio
    async def test_broadcast_update(self):
        """외부 브로드캐스트 호출"""
        from src.api.routes.dashboard import broadcast_update, manager

        mock_ws = AsyncMock()
        manager.active_connections = [mock_ws]

        await broadcast_update({"type": "test", "data": "hello"})

        mock_ws.send_json.assert_called_once_with({"type": "test", "data": "hello"})
        # 정리
        manager.active_connections = []


class TestDashboardWebSocketEdgeCases:
    """WebSocket 엣지 케이스 테스트 (lines 304-308)"""

    def test_websocket_with_disconnect(self):
        """WebSocket 연결 후 정상 해제"""
        app = FastAPI()
        from src.api.dependencies import get_bot_manager
        from src.api.routes.dashboard import router

        mock_manager = MagicMock()
        mock_manager.get_all_bots.return_value = [
            {
                "bot_name": "test-bot",
                "is_running": True,
                "is_paused": False,
                "current_price": 50000.0,
                "last_signal": "LONG",
                "position": None,
            }
        ]

        app.include_router(router, prefix="/api")
        app.dependency_overrides[get_bot_manager] = lambda: mock_manager

        client = TestClient(app)

        with client.websocket_connect("/api/dashboard/ws") as ws:
            data = ws.receive_json()
            assert data["type"] == "update"


# =============================================================================
# src/api/services/n8n_callback.py 커버리지 테스트
# =============================================================================


class TestN8NCallbackServiceSession:
    """N8NCallbackService 세션 관리 테스트 (lines 54-58, 65-68)"""

    @pytest.mark.asyncio
    async def test_get_session_creates_new(self):
        """세션이 없을 때 새로 생성 (lines 54-58)"""
        import aiohttp

        from src.api.services.n8n_callback import N8NCallbackService

        service = N8NCallbackService(webhook_url="https://example.com/webhook")
        assert service._session is None

        session = await service._get_session()
        assert isinstance(session, aiohttp.ClientSession)
        # 정리
        await session.close()

    @pytest.mark.asyncio
    async def test_get_session_reuses_existing(self):
        """기존 세션 재사용"""
        from src.api.services.n8n_callback import N8NCallbackService

        service = N8NCallbackService(webhook_url="https://example.com/webhook")

        session1 = await service._get_session()
        session2 = await service._get_session()
        assert session1 is session2
        await session1.close()

    @pytest.mark.asyncio
    async def test_close_session(self):
        """세션 종료 (lines 65-68)"""
        from src.api.services.n8n_callback import N8NCallbackService

        service = N8NCallbackService(webhook_url="https://example.com/webhook")

        # 세션 생성
        session = await service._get_session()
        assert service._session is not None

        # 세션 종료
        await service.close()
        assert service._session is None

    @pytest.mark.asyncio
    async def test_close_no_session(self):
        """세션 없을 때 close 호출"""
        from src.api.services.n8n_callback import N8NCallbackService

        service = N8NCallbackService(webhook_url="https://example.com/webhook")
        # 세션 없는 상태에서 close - 에러 없어야 함
        await service.close()
        assert service._session is None


class TestN8NCallbackSendErrors:
    """send_callback 에러 케이스 (lines 97-107)"""

    @pytest.mark.asyncio
    async def test_send_callback_http_error_status(self):
        """HTTP 에러 응답 (lines 97-100)"""
        from src.api.schemas.n8n import N8NCallbackPayload
        from src.api.services.n8n_callback import N8NCallbackService

        service = N8NCallbackService(webhook_url="https://example.com/webhook")

        mock_response = MagicMock()
        mock_response.status = 500

        mock_post_cm = MagicMock()
        mock_post_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_post_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.post.return_value = mock_post_cm

        with patch.object(service, "_get_session", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_session

            payload = N8NCallbackPayload(
                event_type="signal",
                bot_name="test-bot",
                data={"signal": "LONG"},
            )
            result = await service.send_callback(payload)
            assert result is False

    @pytest.mark.asyncio
    async def test_send_callback_client_error(self):
        """네트워크 에러 (lines 102-104)"""
        import aiohttp

        from src.api.schemas.n8n import N8NCallbackPayload
        from src.api.services.n8n_callback import N8NCallbackService

        service = N8NCallbackService(webhook_url="https://example.com/webhook")

        with patch.object(service, "_get_session", new_callable=AsyncMock) as mock_get:
            mock_session = MagicMock()
            mock_session.post.side_effect = aiohttp.ClientError("Connection refused")
            mock_get.return_value = mock_session

            payload = N8NCallbackPayload(
                event_type="signal",
                bot_name="test-bot",
                data={"signal": "LONG"},
            )
            result = await service.send_callback(payload)
            assert result is False

    @pytest.mark.asyncio
    async def test_send_callback_general_exception(self):
        """일반 예외 (lines 105-107)"""
        from src.api.schemas.n8n import N8NCallbackPayload
        from src.api.services.n8n_callback import N8NCallbackService

        service = N8NCallbackService(webhook_url="https://example.com/webhook")

        with patch.object(service, "_get_session", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = Exception("Unexpected error")

            payload = N8NCallbackPayload(
                event_type="signal",
                bot_name="test-bot",
                data={"signal": "LONG"},
            )
            result = await service.send_callback(payload)
            assert result is False


class TestN8NCallbackSendTradeWithOptionals:
    """send_trade 옵셔널 파라미터 테스트 (lines 172, 174, 176)"""

    @pytest.mark.asyncio
    async def test_send_trade_with_pnl_and_quantity(self):
        """pnl과 quantity가 포함된 거래 콜백"""
        from src.api.services.n8n_callback import N8NCallbackService

        service = N8NCallbackService(webhook_url="https://example.com/webhook")

        with patch.object(service, "send_callback", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            result = await service.send_trade(
                bot_name="test-bot",
                action="CLOSE",
                side="LONG",
                price=50000.0,
                pnl=100.0,
                quantity=0.01,
                metadata={"reason": "TP"},
            )

            assert result is True
            call_payload = mock_send.call_args[0][0]
            assert call_payload.data["pnl"] == 100.0
            assert call_payload.data["quantity"] == 0.01
            assert call_payload.data["reason"] == "TP"

    @pytest.mark.asyncio
    async def test_send_trade_without_optionals(self):
        """옵셔널 파라미터 없는 거래 콜백"""
        from src.api.services.n8n_callback import N8NCallbackService

        service = N8NCallbackService(webhook_url="https://example.com/webhook")

        with patch.object(service, "send_callback", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            result = await service.send_trade(
                bot_name="test-bot",
                action="OPEN",
                side="SHORT",
                price=3000.0,
            )

            assert result is True
            call_payload = mock_send.call_args[0][0]
            assert "pnl" not in call_payload.data
            assert "quantity" not in call_payload.data


class TestN8NCallbackInitMasking:
    """URL 마스킹 테스트"""

    def test_init_short_url(self):
        """짧은 URL 마스킹"""
        from src.api.services.n8n_callback import N8NCallbackService

        service = N8NCallbackService(webhook_url="http://short")
        assert service.is_enabled is True

    def test_init_long_url(self):
        """긴 URL 마스킹"""
        from src.api.services.n8n_callback import N8NCallbackService

        long_url = "https://n8n.example.com/webhook/very-long-path-here"
        service = N8NCallbackService(webhook_url=long_url)
        assert service.is_enabled is True


# =============================================================================
# src/api/services/bot_service.py 커버리지 테스트
# =============================================================================


class TestBotServiceControlErrors:
    """봇 제어 에러 케이스 (not found 시 ValueError)"""

    @pytest.fixture
    def mock_manager(self):
        manager = MagicMock()
        manager.get_bot.return_value = None
        manager.start_bot = AsyncMock()
        manager.stop_bot = AsyncMock()
        return manager

    @pytest.fixture
    def service(self, mock_manager):
        from src.api.services.bot_service import BotService
        return BotService(mock_manager)

    @pytest.mark.asyncio
    async def test_start_bot_not_found(self, service):
        """존재하지 않는 봇 시작 시 ValueError"""
        with pytest.raises(ValueError, match="not found"):
            await service.start_bot("nonexistent")

    @pytest.mark.asyncio
    async def test_stop_bot_not_found(self, service):
        """존재하지 않는 봇 정지 시 ValueError"""
        with pytest.raises(ValueError, match="not found"):
            await service.stop_bot("nonexistent")

    def test_pause_bot_not_found(self, service):
        """존재하지 않는 봇 일시정지 시 ValueError"""
        with pytest.raises(ValueError, match="not found"):
            service.pause_bot("nonexistent")

    def test_resume_bot_not_found(self, service):
        """존재하지 않는 봇 재개 시 ValueError"""
        with pytest.raises(ValueError, match="not found"):
            service.resume_bot("nonexistent")

    def test_emergency_close_not_found(self, service):
        """존재하지 않는 봇 긴급 청산 시 ValueError"""
        with pytest.raises(ValueError, match="not found"):
            service.emergency_close("nonexistent")


class TestBotServiceStartStopAll:
    """전체 봇 시작/정지 테스트"""

    @pytest.fixture
    def mock_manager(self):
        manager = MagicMock()
        manager.start_all = AsyncMock()
        manager.stop_all = AsyncMock()
        manager.running_count = 3
        return manager

    @pytest.fixture
    def service(self, mock_manager):
        from src.api.services.bot_service import BotService
        return BotService(mock_manager)

    @pytest.mark.asyncio
    async def test_start_all(self, service, mock_manager):
        """전체 봇 시작"""
        result = await service.start_all()
        assert result == 3
        mock_manager.start_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_all(self, service, mock_manager):
        """전체 봇 정지"""
        result = await service.stop_all()
        assert result == 3
        mock_manager.stop_all.assert_called_once()


class TestBotServiceUpdateBotAllFields:
    """봇 설정 수정 - 모든 필드 업데이트 테스트"""

    @pytest.fixture
    def mock_bot_full(self):
        from src.bot_config import BotConfig
        from src.bot_instance import BotInstance

        bot = MagicMock(spec=BotInstance)
        bot.bot_name = "test-bot"
        bot.is_running = False
        bot.is_paused = False
        bot.config = BotConfig(bot_name="test-bot", symbol="BTCUSDT", risk_level="medium")
        return bot

    @pytest.fixture
    def service_with_bot(self, mock_bot_full):
        from src.api.services.bot_service import BotService

        manager = MagicMock()
        manager.get_bot.return_value = mock_bot_full
        return BotService(manager), mock_bot_full

    def test_update_bot_all_fields(self, service_with_bot):
        """모든 필드 업데이트"""
        from src.api.schemas.bot import BotUpdateRequest

        service, bot = service_with_bot
        request = BotUpdateRequest(
            risk_level="high",
            leverage=20,
            position_size_pct=0.05,
            take_profit_pct=3.0,
            stop_loss_pct=2.0,
            time_cut_minutes=180,
            rsi_oversold=30.0,
            rsi_overbought=70.0,
            volume_threshold=1.5,
            is_testnet=False,
            is_active=True,
            description="Updated bot",
        )

        result = service.update_bot("test-bot", request)

        assert result is not None
        assert bot.config.risk_level == "high"
        assert bot.config.leverage == 20
        assert bot.config.position_size_pct == 0.05
        assert bot.config.take_profit_pct == 3.0
        assert bot.config.stop_loss_pct == 2.0
        assert bot.config.time_cut_minutes == 180
        assert bot.config.rsi_oversold == 30.0
        assert bot.config.rsi_overbought == 70.0
        assert bot.config.volume_threshold == 1.5
        assert bot.config.is_testnet is False
        assert bot.config.is_active is True
        assert bot.config.description == "Updated bot"


class TestBotServiceCreateBotWithAllFields:
    """봇 생성 - 모든 옵셔널 필드 포함"""

    def test_create_bot_with_all_optional_fields(self):
        """모든 옵셔널 필드를 포함한 봇 생성"""
        from src.api.schemas.bot import BotCreateRequest
        from src.api.services.bot_service import BotService
        from src.bot_instance import BotInstance

        mock_bot = MagicMock(spec=BotInstance)
        mock_bot.bot_name = "full-bot"
        mock_bot.is_running = False
        mock_bot.is_paused = False

        mock_manager = MagicMock()
        mock_manager.add_bot.return_value = mock_bot

        service = BotService(mock_manager)

        request = BotCreateRequest(
            bot_name="full-bot",
            symbol="ETHUSDT",
            risk_level="high",
            leverage=20,
            position_size_pct=0.05,
            take_profit_pct=3.0,
            stop_loss_pct=2.0,
            time_cut_minutes=180,
            rsi_oversold=30.0,
            rsi_overbought=70.0,
            volume_threshold=1.5,
            is_testnet=False,
            description="Full test bot",
        )

        result = service.create_bot(request)
        assert result["bot_name"] == "full-bot"
        mock_manager.add_bot.assert_called_once()


class TestDashboardSignalPerformanceWithBotId:
    """bot_id 파라미터를 사용한 신호 성과 조회"""

    def test_signal_performance_with_bot_id(self):
        """bot_id 파라미터 전달"""
        app = FastAPI()
        from src.api.dependencies import get_bot_manager, get_optional_signal_tracker
        from src.api.routes.dashboard import router

        mock_tracker = MagicMock()
        mock_tracker.get_signal_stats = AsyncMock(
            return_value=MagicMock(
                to_dict=lambda: {"total_signals": 50, "wins": 30}
            )
        )
        mock_tracker.get_win_rate_by_source = AsyncMock(return_value={"gemini": 75.0})
        mock_tracker.get_recent_signals = AsyncMock(return_value=[])

        app.include_router(router, prefix="/api")
        app.dependency_overrides[get_bot_manager] = lambda: MagicMock()
        app.dependency_overrides[get_optional_signal_tracker] = lambda: mock_tracker

        client = TestClient(app)
        response = client.get("/api/dashboard/signals/performance?days=30&bot_id=bot-123")

        assert response.status_code == 200
        data = response.json()
        assert data["period_days"] == 30
