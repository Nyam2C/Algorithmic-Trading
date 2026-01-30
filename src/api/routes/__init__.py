"""
API 라우트 모듈
"""

from src.api.routes.health import router as health_router
from src.api.routes.bots import router as bots_router
from src.api.routes.n8n import router as n8n_router

__all__ = ["health_router", "bots_router", "n8n_router"]
