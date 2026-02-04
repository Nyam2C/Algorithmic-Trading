"""
감사 로그 모듈

Phase 7.3: 거래 감사 로그
- 모든 거래 및 봇 이벤트 기록
- PostgreSQL 영구 저장 (옵션)
- 인메모리 폴백 지원
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from loguru import logger


class AuditEventType(Enum):
    """감사 이벤트 타입

    거래 및 봇 관련 모든 이벤트 유형을 정의합니다.
    """
    TRADE_OPEN = "TRADE_OPEN"           # 포지션 진입
    TRADE_CLOSE = "TRADE_CLOSE"         # 포지션 청산
    BOT_PAUSE = "BOT_PAUSE"             # 봇 일시정지
    BOT_RESUME = "BOT_RESUME"           # 봇 재시작
    EMERGENCY_CLOSE = "EMERGENCY_CLOSE" # 긴급 청산
    CONFIG_CHANGE = "CONFIG_CHANGE"     # 설정 변경
    RISK_HALT = "RISK_HALT"             # 리스크 한도 도달


@dataclass
class AuditLog:
    """감사 로그 엔트리

    단일 감사 이벤트를 나타냅니다.

    Attributes:
        event_type: 이벤트 유형
        bot_name: 봇 이름
        details: 이벤트 상세 정보
        user_id: 사용자 ID (Discord 등)
        timestamp: 이벤트 발생 시간
        session_id: 세션 ID
    """
    event_type: AuditEventType
    bot_name: str
    details: Dict[str, Any] = field(default_factory=dict)
    user_id: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    session_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "event_type": self.event_type.value,
            "bot_name": self.bot_name,
            "details": self.details,
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat(),
            "session_id": self.session_id,
        }


class AuditLogManager:
    """감사 로그 매니저

    감사 로그를 기록하고 조회합니다.
    PostgreSQL DB 연결이 있으면 영구 저장하고,
    없으면 인메모리에 저장합니다.

    Attributes:
        _db_pool: PostgreSQL 연결 풀 (선택)
        _memory_logs: 인메모리 로그 저장소
        _max_memory_logs: 인메모리 최대 로그 수

    Example:
        >>> manager = AuditLogManager()
        >>> await manager.log_trade_open("btc-bot", "LONG", 0.001, 50000.0)
        >>> logs = await manager.get_recent_logs(bot_name="btc-bot", limit=10)
    """

    def __init__(
        self,
        db_pool: Optional[Any] = None,
        max_memory_logs: int = 1000,
    ) -> None:
        """감사 로그 매니저 초기화

        Args:
            db_pool: asyncpg 연결 풀 (선택)
            max_memory_logs: 인메모리 최대 로그 수
        """
        self._db_pool = db_pool
        self._memory_logs: List[AuditLog] = []
        self._max_memory_logs = max_memory_logs

        logger.debug(
            f"AuditLogManager 초기화: db_pool={'있음' if db_pool else '없음'}, "
            f"max_memory_logs={max_memory_logs}"
        )

    async def _save_log(self, log: AuditLog) -> None:
        """로그 저장 (DB 또는 메모리)"""
        # 인메모리 저장
        self._memory_logs.append(log)

        # 최대 개수 초과 시 오래된 로그 삭제
        if len(self._memory_logs) > self._max_memory_logs:
            self._memory_logs = self._memory_logs[-self._max_memory_logs:]

        # DB 저장 (연결이 있는 경우)
        if self._db_pool is not None:
            try:
                await self._save_to_db(log)
            except Exception as e:
                logger.warning(f"DB 저장 실패, 인메모리에만 저장: {e}")

    async def _save_to_db(self, log: AuditLog) -> None:
        """DB에 로그 저장"""
        if self._db_pool is None:
            return

        query = """
            INSERT INTO audit_logs (event_type, bot_name, user_id, action_details, session_id)
            VALUES ($1, $2, $3, $4, $5)
        """
        import json
        async with self._db_pool.acquire() as conn:
            await conn.execute(
                query,
                log.event_type.value,
                log.bot_name,
                log.user_id,
                json.dumps(log.details),
                log.session_id,
            )

    # =========================================================================
    # 편의 메서드 - 각 이벤트 타입별
    # =========================================================================

    async def log_trade_open(
        self,
        bot_name: str,
        side: str,
        quantity: float,
        entry_price: float,
        user_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """거래 진입 로깅

        Args:
            bot_name: 봇 이름
            side: 거래 방향 (LONG/SHORT)
            quantity: 수량
            entry_price: 진입 가격
            user_id: 사용자 ID (선택)
        """
        log = AuditLog(
            event_type=AuditEventType.TRADE_OPEN,
            bot_name=bot_name,
            user_id=user_id,
            details={
                "side": side,
                "quantity": quantity,
                "entry_price": entry_price,
                **kwargs,
            },
        )
        await self._save_log(log)
        logger.info(f"[AUDIT] TRADE_OPEN: {bot_name} {side} @ {entry_price}")

    async def log_trade_close(
        self,
        bot_name: str,
        side: str,
        exit_reason: str,
        pnl: float,
        pnl_pct: float,
        user_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """거래 청산 로깅

        Args:
            bot_name: 봇 이름
            side: 거래 방향
            exit_reason: 청산 사유 (TP, SL, TIMECUT, MANUAL 등)
            pnl: 실현 손익
            pnl_pct: 손익률 (%)
            user_id: 사용자 ID (선택)
        """
        log = AuditLog(
            event_type=AuditEventType.TRADE_CLOSE,
            bot_name=bot_name,
            user_id=user_id,
            details={
                "side": side,
                "exit_reason": exit_reason,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                **kwargs,
            },
        )
        await self._save_log(log)
        logger.info(
            f"[AUDIT] TRADE_CLOSE: {bot_name} {side} - {exit_reason}, "
            f"PnL: {pnl:+.2f} ({pnl_pct:+.2f}%)"
        )

    async def log_bot_pause(
        self,
        bot_name: str,
        reason: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        """봇 일시정지 로깅

        Args:
            bot_name: 봇 이름
            reason: 일시정지 사유
            user_id: 사용자 ID (선택)
        """
        log = AuditLog(
            event_type=AuditEventType.BOT_PAUSE,
            bot_name=bot_name,
            user_id=user_id,
            details={"reason": reason or "manual"},
        )
        await self._save_log(log)
        logger.info(f"[AUDIT] BOT_PAUSE: {bot_name} by {user_id or 'system'}")

    async def log_bot_resume(
        self,
        bot_name: str,
        user_id: Optional[str] = None,
    ) -> None:
        """봇 재시작 로깅

        Args:
            bot_name: 봇 이름
            user_id: 사용자 ID (선택)
        """
        log = AuditLog(
            event_type=AuditEventType.BOT_RESUME,
            bot_name=bot_name,
            user_id=user_id,
            details={},
        )
        await self._save_log(log)
        logger.info(f"[AUDIT] BOT_RESUME: {bot_name} by {user_id or 'system'}")

    async def log_emergency_close(
        self,
        bot_name: str,
        reason: str,
        pnl: Optional[float] = None,
        user_id: Optional[str] = None,
    ) -> None:
        """긴급 청산 로깅

        Args:
            bot_name: 봇 이름
            reason: 긴급 청산 사유
            pnl: 실현 손익 (선택)
            user_id: 사용자 ID (선택)
        """
        details: Dict[str, Any] = {"reason": reason}
        if pnl is not None:
            details["pnl"] = pnl

        log = AuditLog(
            event_type=AuditEventType.EMERGENCY_CLOSE,
            bot_name=bot_name,
            user_id=user_id,
            details=details,
        )
        await self._save_log(log)
        logger.warning(f"[AUDIT] EMERGENCY_CLOSE: {bot_name} - {reason}")

    async def log_risk_halt(
        self,
        bot_name: str,
        reason: str,
        daily_pnl: Optional[float] = None,
        daily_pnl_pct: Optional[float] = None,
    ) -> None:
        """리스크 한도 도달 로깅

        Args:
            bot_name: 봇 이름
            reason: 한도 도달 사유
            daily_pnl: 일일 손익
            daily_pnl_pct: 일일 손익률
        """
        details: Dict[str, Any] = {"reason": reason}
        if daily_pnl is not None:
            details["daily_pnl"] = daily_pnl
        if daily_pnl_pct is not None:
            details["daily_pnl_pct"] = daily_pnl_pct

        log = AuditLog(
            event_type=AuditEventType.RISK_HALT,
            bot_name=bot_name,
            details=details,
        )
        await self._save_log(log)
        logger.warning(f"[AUDIT] RISK_HALT: {bot_name} - {reason}")

    async def log_config_change(
        self,
        bot_name: str,
        changes: Dict[str, Any],
        user_id: Optional[str] = None,
    ) -> None:
        """설정 변경 로깅

        Args:
            bot_name: 봇 이름
            changes: 변경 내용 {"field": {"old": old_value, "new": new_value}}
            user_id: 사용자 ID (선택)
        """
        log = AuditLog(
            event_type=AuditEventType.CONFIG_CHANGE,
            bot_name=bot_name,
            user_id=user_id,
            details={"changes": changes},
        )
        await self._save_log(log)
        logger.info(f"[AUDIT] CONFIG_CHANGE: {bot_name} - {changes}")

    # =========================================================================
    # 조회 메서드
    # =========================================================================

    async def get_recent_logs(
        self,
        bot_name: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        limit: int = 50,
    ) -> List[AuditLog]:
        """최근 로그 조회

        Args:
            bot_name: 봇 이름으로 필터링 (선택)
            event_type: 이벤트 타입으로 필터링 (선택)
            limit: 최대 반환 개수

        Returns:
            AuditLog 리스트 (최신순)
        """
        # 인메모리에서 조회
        logs = self._memory_logs.copy()

        # 필터링
        if bot_name:
            logs = [log for log in logs if log.bot_name == bot_name]

        if event_type:
            logs = [log for log in logs if log.event_type == event_type]

        # 최신순 정렬 후 limit 적용
        logs.sort(key=lambda x: x.timestamp, reverse=True)
        return logs[:limit]

    async def get_logs_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        bot_name: Optional[str] = None,
    ) -> List[AuditLog]:
        """날짜 범위로 로그 조회

        Args:
            start_date: 시작 날짜
            end_date: 종료 날짜
            bot_name: 봇 이름 (선택)

        Returns:
            AuditLog 리스트
        """
        logs = self._memory_logs.copy()

        # 날짜 필터링
        logs = [
            log for log in logs
            if start_date <= log.timestamp <= end_date
        ]

        # 봇 이름 필터링
        if bot_name:
            logs = [log for log in logs if log.bot_name == bot_name]

        logs.sort(key=lambda x: x.timestamp, reverse=True)
        return logs

    def get_stats(self) -> Dict[str, Any]:
        """감사 로그 통계

        Returns:
            통계 정보 딕셔너리
        """
        event_counts: Dict[str, int] = {}
        for log in self._memory_logs:
            event_type = log.event_type.value
            event_counts[event_type] = event_counts.get(event_type, 0) + 1

        return {
            "total_logs": len(self._memory_logs),
            "event_counts": event_counts,
            "db_connected": self._db_pool is not None,
        }
