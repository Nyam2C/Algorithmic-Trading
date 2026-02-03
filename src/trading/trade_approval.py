"""
거래 승인 시스템

Phase 7.4: 수동 승인 모드
- 첫 N거래는 Discord에서 수동 승인 필요
- 승인/거부 요청 관리
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
from loguru import logger


class ApprovalStatus(Enum):
    """승인 상태"""
    PENDING = "pending"      # 대기 중
    APPROVED = "approved"    # 승인됨
    REJECTED = "rejected"    # 거부됨
    TIMEOUT = "timeout"      # 시간 초과


@dataclass
class TradeApprovalRequest:
    """거래 승인 요청

    Attributes:
        request_id: 요청 ID
        bot_name: 봇 이름
        signal: 거래 신호 (LONG/SHORT)
        price: 현재 가격
        quantity: 수량
        status: 승인 상태
        created_at: 생성 시간
        approver_id: 승인자 ID
        rejection_reason: 거부 사유
    """
    bot_name: str
    signal: str
    price: float
    quantity: float
    request_id: str = field(default_factory=lambda: str(uuid4())[:8])
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    approver_id: Optional[str] = None
    rejection_reason: Optional[str] = None
    rsi: Optional[float] = None
    atr: Optional[float] = None

    def approve(self, user_id: str) -> None:
        """승인"""
        self.status = ApprovalStatus.APPROVED
        self.approver_id = user_id
        logger.info(f"거래 승인됨: {self.request_id} by {user_id}")

    def reject(self, user_id: str, reason: Optional[str] = None) -> None:
        """거부"""
        self.status = ApprovalStatus.REJECTED
        self.approver_id = user_id
        self.rejection_reason = reason
        logger.info(f"거래 거부됨: {self.request_id} by {user_id}, reason={reason}")

    def timeout(self) -> None:
        """시간 초과"""
        self.status = ApprovalStatus.TIMEOUT
        logger.info(f"거래 승인 시간 초과: {self.request_id}")

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return {
            "request_id": self.request_id,
            "bot_name": self.bot_name,
            "signal": self.signal,
            "price": self.price,
            "quantity": self.quantity,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "approver_id": self.approver_id,
            "rejection_reason": self.rejection_reason,
            "market_data": {
                "rsi": self.rsi,
                "atr": self.atr,
            },
        }


class TradeApprovalManager:
    """거래 승인 매니저

    첫 N거래에 대해 수동 승인을 요구합니다.
    Discord 봇과 통합하여 사용합니다.

    Attributes:
        manual_approval_enabled: 수동 승인 활성화 여부
        manual_approval_trades: 수동 승인 필요 거래 수
        approval_timeout: 승인 대기 시간 (초)

    Example:
        >>> manager = TradeApprovalManager(manual_approval_enabled=True)
        >>> if await manager.requires_approval("btc-bot"):
        ...     request = await manager.create_request("btc-bot", "LONG", 50000, 0.001)
        ...     # Discord에서 승인 대기
        ...     await manager.wait_for_approval(request)
    """

    def __init__(
        self,
        manual_approval_enabled: bool = True,
        manual_approval_trades: int = 5,
        approval_timeout: int = 60,
    ) -> None:
        """매니저 초기화

        Args:
            manual_approval_enabled: 수동 승인 활성화 여부
            manual_approval_trades: 수동 승인이 필요한 거래 수
            approval_timeout: 승인 대기 시간 (초)
        """
        self._enabled = manual_approval_enabled
        self.manual_approval_trades = manual_approval_trades
        self.approval_timeout = approval_timeout

        # 봇별 완료 거래 수
        self._completed_trades: Dict[str, int] = {}

        # 승인 요청 저장소
        self._requests: Dict[str, TradeApprovalRequest] = {}

        logger.debug(
            f"TradeApprovalManager 초기화: enabled={manual_approval_enabled}, "
            f"trades={manual_approval_trades}, timeout={approval_timeout}s"
        )

    def is_enabled(self) -> bool:
        """수동 승인 활성화 여부"""
        return self._enabled

    async def requires_approval(self, bot_name: str) -> bool:
        """승인이 필요한지 확인

        Args:
            bot_name: 봇 이름

        Returns:
            승인 필요 여부
        """
        if not self._enabled:
            return False

        completed = self._completed_trades.get(bot_name, 0)
        return completed < self.manual_approval_trades

    async def record_trade_completed(self, bot_name: str) -> None:
        """거래 완료 기록

        Args:
            bot_name: 봇 이름
        """
        current = self._completed_trades.get(bot_name, 0)
        self._completed_trades[bot_name] = current + 1

        logger.debug(f"거래 완료 기록: {bot_name} = {current + 1}")

    async def create_request(
        self,
        bot_name: str,
        signal: str,
        price: float,
        quantity: float,
        rsi: Optional[float] = None,
        atr: Optional[float] = None,
    ) -> TradeApprovalRequest:
        """승인 요청 생성

        Args:
            bot_name: 봇 이름
            signal: 거래 신호
            price: 현재 가격
            quantity: 수량
            rsi: RSI 값 (선택)
            atr: ATR 값 (선택)

        Returns:
            TradeApprovalRequest
        """
        request = TradeApprovalRequest(
            bot_name=bot_name,
            signal=signal,
            price=price,
            quantity=quantity,
            rsi=rsi,
            atr=atr,
        )

        self._requests[request.request_id] = request

        logger.info(
            f"거래 승인 요청 생성: {request.request_id} - "
            f"{bot_name} {signal} @ {price}"
        )

        return request

    async def approve(self, request_id: str, user_id: str) -> bool:
        """요청 승인

        Args:
            request_id: 요청 ID
            user_id: 승인자 ID

        Returns:
            성공 여부
        """
        request = self._requests.get(request_id)
        if request is None:
            logger.warning(f"요청을 찾을 수 없음: {request_id}")
            return False

        if request.status != ApprovalStatus.PENDING:
            logger.warning(f"이미 처리된 요청: {request_id}")
            return False

        request.approve(user_id)
        return True

    async def reject(
        self,
        request_id: str,
        user_id: str,
        reason: Optional[str] = None,
    ) -> bool:
        """요청 거부

        Args:
            request_id: 요청 ID
            user_id: 거부자 ID
            reason: 거부 사유

        Returns:
            성공 여부
        """
        request = self._requests.get(request_id)
        if request is None:
            logger.warning(f"요청을 찾을 수 없음: {request_id}")
            return False

        if request.status != ApprovalStatus.PENDING:
            logger.warning(f"이미 처리된 요청: {request_id}")
            return False

        request.reject(user_id, reason)
        return True

    async def get_pending_requests(
        self,
        bot_name: Optional[str] = None,
    ) -> List[TradeApprovalRequest]:
        """대기 중 요청 조회

        Args:
            bot_name: 봇 이름으로 필터링 (선택)

        Returns:
            대기 중인 요청 리스트
        """
        pending = [
            r for r in self._requests.values()
            if r.status == ApprovalStatus.PENDING
        ]

        if bot_name:
            pending = [r for r in pending if r.bot_name == bot_name]

        return pending

    async def get_request(self, request_id: str) -> Optional[TradeApprovalRequest]:
        """요청 조회

        Args:
            request_id: 요청 ID

        Returns:
            TradeApprovalRequest or None
        """
        return self._requests.get(request_id)

    def get_stats(self) -> Dict[str, Any]:
        """통계 조회

        Returns:
            통계 딕셔너리
        """
        requests = list(self._requests.values())

        pending = sum(1 for r in requests if r.status == ApprovalStatus.PENDING)
        approved = sum(1 for r in requests if r.status == ApprovalStatus.APPROVED)
        rejected = sum(1 for r in requests if r.status == ApprovalStatus.REJECTED)
        timeout = sum(1 for r in requests if r.status == ApprovalStatus.TIMEOUT)

        return {
            "enabled": self._enabled,
            "manual_approval_trades": self.manual_approval_trades,
            "total_requests": len(requests),
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "timeout": timeout,
            "completed_trades": dict(self._completed_trades),
        }

    def reset_bot_counter(self, bot_name: str) -> None:
        """봇 거래 카운터 리셋

        Args:
            bot_name: 봇 이름
        """
        self._completed_trades[bot_name] = 0
        logger.info(f"거래 카운터 리셋: {bot_name}")
