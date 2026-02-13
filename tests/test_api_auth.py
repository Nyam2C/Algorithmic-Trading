"""Tests for API authentication enforcement."""
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from src.api.dependencies import verify_api_key


class TestVerifyApiKey:
    """verify_api_key() 인증 강제 테스트"""

    @pytest.fixture(autouse=True)
    def _clear_env(self, monkeypatch):
        """환경변수 초기화"""
        monkeypatch.delenv("API_KEY", raising=False)
        monkeypatch.delenv("API_DEBUG", raising=False)

    def _make_request(self):
        """Mock FastAPI Request 생성"""
        request = MagicMock()
        request.url.path = "/test"
        request.client.host = "127.0.0.1"
        return request

    @pytest.mark.asyncio
    async def test_api_key_not_set_returns_500(self, monkeypatch):
        """API_KEY 미설정 시 500 에러 반환"""
        monkeypatch.delenv("API_KEY", raising=False)
        monkeypatch.delenv("API_DEBUG", raising=False)

        request = self._make_request()
        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key(request, x_api_key="any-key")

        assert exc_info.value.status_code == 500
        assert "API_KEY not configured" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_api_key_not_set_debug_mode_passes(self, monkeypatch):
        """API_KEY 미설정이지만 API_DEBUG=true이면 통과"""
        monkeypatch.delenv("API_KEY", raising=False)
        monkeypatch.setenv("API_DEBUG", "true")

        request = self._make_request()
        result = await verify_api_key(request, x_api_key=None)

        assert result is None

    @pytest.mark.asyncio
    async def test_valid_api_key_passes(self, monkeypatch):
        """유효한 API 키는 통과"""
        monkeypatch.setenv("API_KEY", "secret-key-123")

        request = self._make_request()
        result = await verify_api_key(request, x_api_key="secret-key-123")

        assert result == "secret-key-123"

    @pytest.mark.asyncio
    async def test_invalid_api_key_returns_401(self, monkeypatch):
        """유효하지 않은 API 키는 401 에러"""
        monkeypatch.setenv("API_KEY", "secret-key-123")

        request = self._make_request()
        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key(request, x_api_key="wrong-key")

        assert exc_info.value.status_code == 401
