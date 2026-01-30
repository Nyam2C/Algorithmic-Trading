"""
FastAPI REST API 모듈

멀티봇 시스템을 위한 REST API와 n8n 통합을 제공합니다.
"""

from src.api.main import create_app

__all__ = ["create_app"]
