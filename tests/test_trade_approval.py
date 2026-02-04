"""
Tests for Trade Approval System

Phase 7.4: 수동 승인 모드
"""
import pytest

from src.trading.trade_approval import (
    TradeApprovalManager,
    ApprovalStatus,
    TradeApprovalRequest,
)


class TestApprovalStatus:
    """ApprovalStatus Enum 테스트"""

    def test_pending(self):
        assert ApprovalStatus.PENDING.value == "pending"

    def test_approved(self):
        assert ApprovalStatus.APPROVED.value == "approved"

    def test_rejected(self):
        assert ApprovalStatus.REJECTED.value == "rejected"

    def test_timeout(self):
        assert ApprovalStatus.TIMEOUT.value == "timeout"


class TestTradeApprovalRequest:
    """TradeApprovalRequest 테스트"""

    def test_create_request(self):
        """요청 생성"""
        request = TradeApprovalRequest(
            bot_name="btc-bot",
            signal="LONG",
            price=50000.0,
            quantity=0.001,
        )

        assert request.bot_name == "btc-bot"
        assert request.signal == "LONG"
        assert request.status == ApprovalStatus.PENDING

    def test_approve(self):
        """승인"""
        request = TradeApprovalRequest(
            bot_name="btc-bot",
            signal="LONG",
            price=50000.0,
            quantity=0.001,
        )

        request.approve(user_id="user_123")

        assert request.status == ApprovalStatus.APPROVED
        assert request.approver_id == "user_123"

    def test_reject(self):
        """거부"""
        request = TradeApprovalRequest(
            bot_name="btc-bot",
            signal="LONG",
            price=50000.0,
            quantity=0.001,
        )

        request.reject(user_id="user_123", reason="Too risky")

        assert request.status == ApprovalStatus.REJECTED
        assert request.rejection_reason == "Too risky"

    def test_to_dict(self):
        """딕셔너리 변환"""
        request = TradeApprovalRequest(
            bot_name="btc-bot",
            signal="LONG",
            price=50000.0,
            quantity=0.001,
            rsi=45.0,
        )

        data = request.to_dict()
        assert data["bot_name"] == "btc-bot"
        assert data["signal"] == "LONG"
        assert data["market_data"]["rsi"] == 45.0


class TestTradeApprovalManager:
    """TradeApprovalManager 테스트"""

    @pytest.fixture
    def manager(self):
        """기본 Manager"""
        return TradeApprovalManager(
            manual_approval_enabled=True,
            manual_approval_trades=5,
        )

    @pytest.fixture
    def disabled_manager(self):
        """비활성 Manager"""
        return TradeApprovalManager(
            manual_approval_enabled=False,
        )

    def test_init_enabled(self, manager):
        """활성화된 매니저"""
        assert manager.is_enabled() is True
        assert manager.manual_approval_trades == 5

    def test_init_disabled(self, disabled_manager):
        """비활성 매니저"""
        assert disabled_manager.is_enabled() is False

    @pytest.mark.asyncio
    async def test_requires_approval_first_trades(self, manager):
        """첫 N거래는 승인 필요"""
        assert await manager.requires_approval("btc-bot") is True

    @pytest.mark.asyncio
    async def test_no_approval_after_threshold(self, manager):
        """N거래 후 승인 불필요"""
        # 5거래 완료 기록
        for _ in range(5):
            await manager.record_trade_completed("btc-bot")

        assert await manager.requires_approval("btc-bot") is False

    @pytest.mark.asyncio
    async def test_create_approval_request(self, manager):
        """승인 요청 생성"""
        request = await manager.create_request(
            bot_name="btc-bot",
            signal="LONG",
            price=50000.0,
            quantity=0.001,
        )

        assert request is not None
        assert request.signal == "LONG"
        assert request.status == ApprovalStatus.PENDING

    @pytest.mark.asyncio
    async def test_approve_request(self, manager):
        """요청 승인"""
        request = await manager.create_request(
            bot_name="btc-bot",
            signal="LONG",
            price=50000.0,
            quantity=0.001,
        )

        result = await manager.approve(request.request_id, "user_123")

        assert result is True
        assert request.status == ApprovalStatus.APPROVED

    @pytest.mark.asyncio
    async def test_reject_request(self, manager):
        """요청 거부"""
        request = await manager.create_request(
            bot_name="btc-bot",
            signal="LONG",
            price=50000.0,
            quantity=0.001,
        )

        result = await manager.reject(request.request_id, "user_123", "Too risky")

        assert result is True
        assert request.status == ApprovalStatus.REJECTED

    @pytest.mark.asyncio
    async def test_get_pending_requests(self, manager):
        """대기 중 요청 조회"""
        await manager.create_request("btc-bot", "LONG", 50000.0, 0.001)
        await manager.create_request("eth-bot", "SHORT", 3000.0, 0.01)

        pending = await manager.get_pending_requests()
        assert len(pending) == 2

    @pytest.mark.asyncio
    async def test_disabled_manager_no_approval(self, disabled_manager):
        """비활성 매니저는 항상 승인 불필요"""
        assert await disabled_manager.requires_approval("btc-bot") is False


class TestTradeApprovalManagerStats:
    """통계 테스트"""

    @pytest.fixture
    def manager(self):
        return TradeApprovalManager(manual_approval_enabled=True)

    @pytest.mark.asyncio
    async def test_get_stats(self, manager):
        """통계 조회"""
        await manager.create_request("btc-bot", "LONG", 50000.0, 0.001)
        request = await manager.create_request("btc-bot", "SHORT", 50000.0, 0.001)
        await manager.approve(request.request_id, "user")

        stats = manager.get_stats()
        assert stats["total_requests"] == 2
        assert stats["pending"] == 1
        assert stats["approved"] == 1
