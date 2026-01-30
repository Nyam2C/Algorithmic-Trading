"""
API 서버 설정 모듈

환경 변수에서 API 서버 설정을 로드합니다.
"""
import os
from typing import Optional
from pydantic import BaseModel, Field


class APIConfig(BaseModel):
    """API 서버 설정

    Attributes:
        host: 서버 바인딩 호스트 (기본값: 0.0.0.0)
        port: 서버 포트 (기본값: 8000)
        debug: 디버그 모드 (기본값: False)
        n8n_webhook_url: n8n 웹훅 URL (선택)
        api_key: API 인증 키 (선택)
    """

    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000, ge=1, le=65535)
    debug: bool = Field(default=False)
    n8n_webhook_url: Optional[str] = Field(default=None)
    api_key: Optional[str] = Field(default=None)

    @classmethod
    def from_env(cls) -> "APIConfig":
        """환경 변수에서 설정 로드

        Returns:
            APIConfig 인스턴스
        """
        return cls(
            host=os.getenv("API_HOST", "0.0.0.0"),
            port=int(os.getenv("API_PORT", "8000")),
            debug=os.getenv("API_DEBUG", "false").lower() == "true",
            n8n_webhook_url=os.getenv("N8N_WEBHOOK_URL"),
            api_key=os.getenv("API_KEY"),
        )
