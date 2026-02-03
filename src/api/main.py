"""
FastAPI 앱 팩토리

REST API 앱을 생성하고 라우터를 등록합니다.
Phase 4.1: CORS 환경변수 설정 추가
"""
import os
from typing import Optional

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from src.bot_manager import MultiBotManager
from src.api.config import APIConfig
from src.api.dependencies import set_bot_manager, set_api_config
from src.api.routes.health import router as health_router
from src.api.routes.bots import router as bots_router
from src.api.routes.n8n import router as n8n_router
from src.api.routes.analytics import router as analytics_router


def create_app(
    bot_manager: Optional[MultiBotManager] = None,
    api_config: Optional[APIConfig] = None,
) -> FastAPI:
    """FastAPI 앱 생성

    Args:
        bot_manager: MultiBotManager 인스턴스 (선택)
        api_config: API 설정 (선택)

    Returns:
        FastAPI 앱 인스턴스
    """
    # 설정 로드
    config = api_config or APIConfig.from_env()
    set_api_config(config)

    # 봇 매니저 설정
    if bot_manager is not None:
        set_bot_manager(bot_manager)

    # FastAPI 앱 생성
    app = FastAPI(
        title="High-Win Survival System API",
        description="멀티봇 트레이딩 시스템 REST API",
        version="1.0.0",
        docs_url="/docs" if config.debug else None,
        redoc_url="/redoc" if config.debug else None,
    )

    # CORS 미들웨어 추가 (환경변수로 제어)
    cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 전역 예외 핸들러
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        logger.warning(f"ValueError: {exc}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "error": "bad_request",
                "message": str(exc),
            },
        )

    @app.exception_handler(RuntimeError)
    async def runtime_error_handler(request: Request, exc: RuntimeError):
        logger.error(f"RuntimeError: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": "internal_error",
                "message": str(exc),
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.exception(f"Unhandled exception: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": "internal_error",
                "message": "An unexpected error occurred",
            },
        )

    # 라우터 등록
    app.include_router(health_router)
    app.include_router(bots_router, prefix="/api")
    app.include_router(n8n_router, prefix="/api")
    app.include_router(analytics_router, prefix="/api")  # Phase 4: Analytics API

    # 시작/종료 이벤트
    @app.on_event("startup")
    async def startup_event():
        logger.info("API 서버 시작")

    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("API 서버 종료")

    return app


# CLI에서 직접 실행할 때 사용
app = create_app()


def run_server(
    host: str = "0.0.0.0",
    port: int = 8000,
    reload: bool = False,
) -> None:
    """서버 실행

    Args:
        host: 바인딩 호스트
        port: 포트 번호
        reload: 자동 리로드 활성화
    """
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host=host,
        port=port,
        reload=reload,
    )


async def run_embedded_server(
    app: FastAPI,
    host: str = "0.0.0.0",
    port: int = 8000,
) -> None:
    """서버를 내장 모드로 비동기 실행

    main.py에서 FastAPI를 내장하여 실행할 때 사용합니다.
    uvicorn.Server.serve()를 사용하여 non-blocking으로 실행합니다.

    Args:
        app: FastAPI 앱 인스턴스
        host: 바인딩 호스트
        port: 포트 번호
    """
    import uvicorn

    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    config = APIConfig.from_env()
    run_server(host=config.host, port=config.port, reload=config.debug)
