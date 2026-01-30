"""
Health Check API 테스트

/health 및 /ready 엔드포인트 테스트입니다.
"""
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
