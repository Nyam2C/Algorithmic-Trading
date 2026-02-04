"""
대시보드 API 테스트

Phase 6.3: REST API 및 WebSocket 테스트
"""
import pytest
from unittest.mock import MagicMock, AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.dashboard import router, ConnectionManager


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
