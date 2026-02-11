"""
대시보드 API 테스트

Phase 6.3: REST API 및 WebSocket 테스트
"""
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.dashboard import ConnectionManager, router


class TestConnectionManager:
    """WebSocket ConnectionManager 테스트"""

    @pytest.fixture
    def manager(self):
        """테스트용 ConnectionManager"""
        return ConnectionManager()

    @pytest.mark.asyncio
    async def test_connect(self, manager):
        """연결 추가 테스트"""
        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()

        await manager.connect(mock_ws)

        assert mock_ws in manager.active_connections
        mock_ws.accept.assert_called_once()

    def test_disconnect(self, manager):
        """연결 해제 테스트"""
        mock_ws = MagicMock()
        manager.active_connections.append(mock_ws)

        manager.disconnect(mock_ws)

        assert mock_ws not in manager.active_connections

    @pytest.mark.asyncio
    async def test_broadcast(self, manager):
        """브로드캐스트 테스트"""
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        manager.active_connections = [mock_ws1, mock_ws2]

        await manager.broadcast({"type": "test"})

        mock_ws1.send_json.assert_called_once_with({"type": "test"})
        mock_ws2.send_json.assert_called_once_with({"type": "test"})

    @pytest.mark.asyncio
    async def test_broadcast_removes_disconnected(self, manager):
        """끊어진 연결 제거 테스트"""
        mock_ws_good = AsyncMock()
        mock_ws_bad = AsyncMock()
        mock_ws_bad.send_json = AsyncMock(side_effect=Exception("Connection closed"))
        manager.active_connections = [mock_ws_good, mock_ws_bad]

        await manager.broadcast({"type": "test"})

        # 끊어진 연결 제거됨
        assert mock_ws_good in manager.active_connections
        assert mock_ws_bad not in manager.active_connections


class TestDashboardAPI:
    """대시보드 REST API 테스트"""

    @pytest.fixture
    def mock_bot_manager(self):
        """Mock BotManager"""
        manager = MagicMock()
        manager.get_all_bots.return_value = [
            {
                "bot_name": "btc-bot",
                "symbol": "BTCUSDT",
                "is_running": True,
                "is_paused": False,
                "current_price": 50000.0,
                "last_signal": "LONG",
                "position": {
                    "side": "LONG",
                    "entry_price": 49000.0,
                    "unrealized_pnl": 100.0,
                },
                "risk_level": "medium",
            },
            {
                "bot_name": "eth-bot",
                "symbol": "ETHUSDT",
                "is_running": True,
                "is_paused": True,
                "current_price": 3000.0,
                "last_signal": "WAIT",
                "position": None,
                "risk_level": "low",
            },
        ]
        manager.get_bot_state.return_value = {
            "bot_name": "btc-bot",
            "symbol": "BTCUSDT",
            "is_running": True,
            "is_paused": False,
            "uptime_start": "2024-01-01T00:00:00",
            "loop_count": 100,
            "current_price": 50000.0,
            "last_signal": "LONG",
            "last_signal_time": "2024-01-01T12:00:00",
            "leverage": 10,
            "position": {
                "side": "LONG",
                "entry_price": 49000.0,
                "unrealized_pnl": 100.0,
            },
            "risk_stats": {
                "daily_pnl": 500.0,
                "daily_pnl_pct": 5.0,
                "consecutive_losses": 0,
                "max_drawdown": 2.0,
                "is_halted": False,
            },
            "market_regime": "STRONG_UPTREND",
            "memory_signals_enabled": True,
        }
        return manager

    @pytest.fixture
    def mock_signal_tracker(self):
        """Mock SignalTracker"""
        tracker = MagicMock()
        tracker.get_signal_stats = AsyncMock(
            return_value=MagicMock(
                to_dict=lambda: {
                    "total_signals": 100,
                    "traded_signals": 80,
                    "wins": 60,
                    "losses": 20,
                    "win_rate": 75.0,
                }
            )
        )
        tracker.get_win_rate_by_source = AsyncMock(
            return_value={
                "gemini": 78.0,
                "rule_based": 72.0,
                "scoring": 70.0,
            }
        )
        tracker.get_recent_signals = AsyncMock(
            return_value=[
                {
                    "signal_id": "abc123",
                    "signal": "LONG",
                    "source": "gemini",
                    "timestamp": "2024-01-01T12:00:00",
                },
            ]
        )
        return tracker

    @pytest.fixture
    def app(self, mock_bot_manager, mock_signal_tracker):
        """테스트용 FastAPI 앱"""
        app = FastAPI()
        app.include_router(router, prefix="/api")

        # 의존성 오버라이드
        from src.api.dependencies import (
            get_bot_manager,
            get_optional_signal_tracker,
        )

        app.dependency_overrides[get_bot_manager] = lambda: mock_bot_manager
        app.dependency_overrides[get_optional_signal_tracker] = (
            lambda: mock_signal_tracker
        )

        return app

    @pytest.fixture
    def client(self, app):
        """테스트 클라이언트"""
        return TestClient(app)

    def test_get_overview(self, client):
        """개요 조회 테스트"""
        response = client.get("/api/dashboard/overview")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["bots"]["total"] == 2
        assert data["bots"]["running"] == 2
        assert data["bots"]["paused"] == 1
        assert data["positions"]["total"] == 1

    def test_get_bot_metrics(self, client):
        """봇 메트릭 조회 테스트"""
        response = client.get("/api/dashboard/bots/btc-bot/metrics")

        assert response.status_code == 200
        data = response.json()
        assert data["bot_name"] == "btc-bot"
        assert data["status"]["is_running"] is True
        assert data["trading"]["symbol"] == "BTCUSDT"
        assert data["risk"]["daily_pnl"] == 500.0
        assert data["memory_signals_enabled"] is True

    def test_get_bot_metrics_not_found(self, client, mock_bot_manager):
        """존재하지 않는 봇 조회 테스트"""
        mock_bot_manager.get_bot_state.return_value = None

        response = client.get("/api/dashboard/bots/unknown-bot/metrics")

        assert response.status_code == 404

    def test_get_signal_performance(self, client):
        """신호 성과 조회 테스트"""
        response = client.get("/api/dashboard/signals/performance?days=7")

        assert response.status_code == 200
        data = response.json()
        assert data["period_days"] == 7
        assert "overall" in data
        assert "by_source" in data
        assert "recent_signals" in data

    def test_get_all_bots_status(self, client):
        """모든 봇 상태 조회 테스트"""
        response = client.get("/api/dashboard/bots")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["bot_name"] == "btc-bot"
        assert data[0]["has_position"] is True
        assert data[1]["bot_name"] == "eth-bot"
        assert data[1]["has_position"] is False


class TestDashboardAPIWithoutManager:
    """BotManager 없는 경우 테스트"""

    @pytest.fixture
    def app(self):
        """테스트용 FastAPI 앱 (BotManager 없음)"""
        app = FastAPI()
        app.include_router(router, prefix="/api")

        from src.api.dependencies import get_bot_manager, get_optional_signal_tracker

        app.dependency_overrides[get_bot_manager] = lambda: None
        app.dependency_overrides[get_optional_signal_tracker] = lambda: None

        return app

    @pytest.fixture
    def client(self, app):
        """테스트 클라이언트"""
        return TestClient(app)

    def test_get_overview_no_manager(self, client):
        """BotManager 없을 때 개요 조회 테스트"""
        response = client.get("/api/dashboard/overview")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "no_manager"

    def test_get_signal_performance_no_tracker(self, client):
        """SignalTracker 없을 때 신호 성과 조회 테스트"""
        response = client.get("/api/dashboard/signals/performance")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unavailable"

    def test_get_all_bots_no_manager(self, client):
        """BotManager 없을 때 봇 목록 조회 테스트"""
        response = client.get("/api/dashboard/bots")

        assert response.status_code == 200
        data = response.json()
        assert data == []


class TestWebSocket:
    """WebSocket 테스트"""

    @pytest.fixture
    def mock_bot_manager(self):
        """Mock BotManager"""
        manager = MagicMock()
        manager.get_all_bots.return_value = [
            {
                "bot_name": "btc-bot",
                "is_running": True,
                "is_paused": False,
                "current_price": 50000.0,
                "last_signal": "LONG",
                "position": None,
            },
        ]
        return manager

    @pytest.fixture
    def app(self, mock_bot_manager):
        """테스트용 FastAPI 앱"""
        app = FastAPI()
        app.include_router(router, prefix="/api")

        from src.api.dependencies import get_bot_manager

        app.dependency_overrides[get_bot_manager] = lambda: mock_bot_manager

        return app

    def test_websocket_connect(self, app, mock_bot_manager):
        """WebSocket 연결 테스트"""
        client = TestClient(app)

        with client.websocket_connect("/api/dashboard/ws") as websocket:
            # 초기 데이터 수신
            data = websocket.receive_json()

            assert data["type"] == "update"
            assert "bots" in data
            assert "summary" in data
            assert len(data["bots"]) == 1
            assert data["bots"][0]["bot_name"] == "btc-bot"


# =============================================================================
# src/api/main.py 커버리지 테스트 (from test_api_coverage.py)
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
# src/api/routes/dashboard.py 커버리지 테스트 (from test_api_coverage.py)
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
