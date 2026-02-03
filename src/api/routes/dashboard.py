"""
대시보드 API

Phase 6.3: 실시간 대시보드
- 시스템 개요 조회
- 봇별 상세 메트릭
- 신호 성과 통계
- WebSocket 실시간 업데이트
"""
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from loguru import logger

from src.api.dependencies import get_bot_manager, get_optional_signal_tracker

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


# ============================================================================
# WebSocket 연결 관리
# ============================================================================

class ConnectionManager:
    """WebSocket 연결 관리자"""

    def __init__(self) -> None:
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """연결 수락"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.debug(f"WebSocket 연결: {len(self.active_connections)}개 활성")

    def disconnect(self, websocket: WebSocket) -> None:
        """연결 해제"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.debug(f"WebSocket 해제: {len(self.active_connections)}개 활성")

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """모든 연결에 메시지 브로드캐스트"""
        disconnected = []

        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        # 끊어진 연결 정리
        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()


# ============================================================================
# REST API 엔드포인트
# ============================================================================

@router.get("/overview")
async def get_dashboard_overview(
    bot_manager=Depends(get_bot_manager),
) -> Dict[str, Any]:
    """시스템 개요 조회

    Returns:
        시스템 전체 상태 요약
    """
    if bot_manager is None:
        return {
            "status": "no_manager",
            "message": "BotManager가 설정되지 않았습니다",
            "timestamp": datetime.now().isoformat(),
        }

    try:
        # 봇 상태 수집
        all_bots = bot_manager.get_all_bots()
        running_bots = [b for b in all_bots if b.get("is_running", False)]
        paused_bots = [b for b in all_bots if b.get("is_paused", False)]

        # 포지션 수집
        total_positions = 0
        total_pnl = 0.0

        for bot in all_bots:
            if bot.get("position"):
                total_positions += 1
                position = bot.get("position", {})
                total_pnl += position.get("unrealized_pnl", 0)

        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "bots": {
                "total": len(all_bots),
                "running": len(running_bots),
                "paused": len(paused_bots),
                "stopped": len(all_bots) - len(running_bots) - len(paused_bots),
            },
            "positions": {
                "total": total_positions,
                "unrealized_pnl": round(total_pnl, 2),
            },
            "system": {
                "websocket_connections": len(manager.active_connections),
            },
        }

    except Exception as e:
        logger.error(f"대시보드 개요 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bots/{bot_name}/metrics")
async def get_bot_metrics(
    bot_name: str,
    bot_manager=Depends(get_bot_manager),
) -> Dict[str, Any]:
    """봇별 상세 메트릭 조회

    Args:
        bot_name: 봇 이름

    Returns:
        봇 상세 메트릭
    """
    if bot_manager is None:
        raise HTTPException(status_code=503, detail="BotManager 미설정")

    try:
        bot_state = bot_manager.get_bot_state(bot_name)

        if not bot_state:
            raise HTTPException(status_code=404, detail=f"봇 '{bot_name}' 없음")

        # 리스크 통계
        risk_stats = bot_state.get("risk_stats", {})

        # 현재 포지션
        position = bot_state.get("position")

        return {
            "bot_name": bot_name,
            "timestamp": datetime.now().isoformat(),
            "status": {
                "is_running": bot_state.get("is_running", False),
                "is_paused": bot_state.get("is_paused", False),
                "uptime_start": bot_state.get("uptime_start"),
                "loop_count": bot_state.get("loop_count", 0),
            },
            "trading": {
                "symbol": bot_state.get("symbol"),
                "leverage": bot_state.get("leverage", 1),
                "current_price": bot_state.get("current_price", 0),
                "last_signal": bot_state.get("last_signal", "WAIT"),
                "last_signal_time": bot_state.get("last_signal_time"),
            },
            "position": position,
            "risk": {
                "daily_pnl": risk_stats.get("daily_pnl", 0),
                "daily_pnl_pct": risk_stats.get("daily_pnl_pct", 0),
                "consecutive_losses": risk_stats.get("consecutive_losses", 0),
                "max_drawdown": risk_stats.get("max_drawdown", 0),
                "is_halted": risk_stats.get("is_halted", False),
            },
            "regime": bot_state.get("market_regime", "UNKNOWN"),
            "memory_signals_enabled": bot_state.get("memory_signals_enabled", False),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"봇 메트릭 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signals/performance")
async def get_signal_performance(
    days: int = 7,
    bot_id: Optional[str] = None,
    signal_tracker=Depends(get_optional_signal_tracker),
) -> Dict[str, Any]:
    """신호 성과 통계 조회

    Args:
        days: 조회 기간 (일)
        bot_id: 봇 ID (선택)

    Returns:
        신호 성과 통계
    """
    if signal_tracker is None:
        return {
            "status": "unavailable",
            "message": "SignalTracker가 설정되지 않았습니다",
            "timestamp": datetime.now().isoformat(),
        }

    try:
        # 전체 통계
        overall_stats = await signal_tracker.get_signal_stats(
            bot_id=bot_id,
            days=days,
        )

        # 소스별 승률
        win_rates_by_source = await signal_tracker.get_win_rate_by_source(
            days=days,
            bot_id=bot_id,
        )

        # 최근 신호
        recent_signals = await signal_tracker.get_recent_signals(
            bot_id=bot_id,
            limit=10,
        )

        return {
            "timestamp": datetime.now().isoformat(),
            "period_days": days,
            "overall": overall_stats.to_dict(),
            "by_source": win_rates_by_source,
            "recent_signals": recent_signals,
        }

    except Exception as e:
        logger.error(f"신호 성과 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bots")
async def get_all_bots_status(
    bot_manager=Depends(get_bot_manager),
) -> List[Dict[str, Any]]:
    """모든 봇 상태 조회

    Returns:
        봇 상태 목록
    """
    if bot_manager is None:
        return []

    try:
        all_bots = bot_manager.get_all_bots()

        return [
            {
                "bot_name": bot.get("bot_name"),
                "symbol": bot.get("symbol"),
                "is_running": bot.get("is_running", False),
                "is_paused": bot.get("is_paused", False),
                "current_price": bot.get("current_price", 0),
                "last_signal": bot.get("last_signal", "WAIT"),
                "has_position": bot.get("position") is not None,
                "risk_level": bot.get("risk_level", "medium"),
            }
            for bot in all_bots
        ]

    except Exception as e:
        logger.error(f"봇 상태 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# WebSocket 엔드포인트
# ============================================================================

@router.websocket("/ws")
async def websocket_dashboard(
    websocket: WebSocket,
    bot_manager=Depends(get_bot_manager),
):
    """실시간 대시보드 WebSocket

    5초 간격으로 업데이트 전송
    """
    await manager.connect(websocket)

    try:
        # 초기 데이터 전송
        initial_data = await _get_realtime_data(bot_manager)
        await websocket.send_json(initial_data)

        # 주기적 업데이트
        while True:
            await asyncio.sleep(5)  # 5초 간격

            try:
                data = await _get_realtime_data(bot_manager)
                await websocket.send_json(data)
            except Exception as e:
                logger.warning(f"WebSocket 데이터 전송 실패: {e}")
                break

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.debug("클라이언트 연결 해제")
    except Exception as e:
        manager.disconnect(websocket)
        logger.error(f"WebSocket 오류: {e}")


async def _get_realtime_data(bot_manager) -> Dict[str, Any]:
    """실시간 데이터 수집"""
    if bot_manager is None:
        return {
            "type": "update",
            "timestamp": datetime.now().isoformat(),
            "status": "no_manager",
        }

    try:
        all_bots = bot_manager.get_all_bots()

        bots_data = []
        for bot in all_bots:
            position = bot.get("position")
            bots_data.append({
                "bot_name": bot.get("bot_name"),
                "is_running": bot.get("is_running", False),
                "is_paused": bot.get("is_paused", False),
                "current_price": bot.get("current_price", 0),
                "last_signal": bot.get("last_signal", "WAIT"),
                "position": {
                    "side": position.get("side") if position else None,
                    "entry_price": position.get("entry_price") if position else None,
                    "pnl": position.get("unrealized_pnl") if position else None,
                } if position else None,
            })

        return {
            "type": "update",
            "timestamp": datetime.now().isoformat(),
            "bots": bots_data,
            "summary": {
                "total_bots": len(all_bots),
                "running": sum(1 for b in all_bots if b.get("is_running")),
                "with_position": sum(1 for b in all_bots if b.get("position")),
            },
        }

    except Exception as e:
        logger.error(f"실시간 데이터 수집 실패: {e}")
        return {
            "type": "error",
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
        }


# ============================================================================
# 헬퍼 함수
# ============================================================================

async def broadcast_update(data: Dict[str, Any]) -> None:
    """외부에서 브로드캐스트 호출용"""
    await manager.broadcast(data)
