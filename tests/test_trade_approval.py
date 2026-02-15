"""
Tests for Trade Approval System

Phase 7.4: 수동 승인 모드
"""
import pytest

from src.trading.trade_approval import (
    ApprovalStatus,
    TradeApprovalManager,
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


# =============================================================================
# From test_trading_coverage.py: TradeApproval tests
# =============================================================================


class TestTradeApprovalEdgeCases:
    """TradeApproval 추가 커버리지"""

    @pytest.mark.asyncio
    async def test_approve_nonexistent_request(self):
        """존재하지 않는 요청 승인 -> False"""
        manager = TradeApprovalManager()
        result = await manager.approve("nonexistent", "user_1")
        assert result is False

    @pytest.mark.asyncio
    async def test_reject_nonexistent_request(self):
        """존재하지 않는 요청 거부 -> False"""
        manager = TradeApprovalManager()
        result = await manager.reject("nonexistent", "user_1")
        assert result is False

    @pytest.mark.asyncio
    async def test_approve_already_processed(self):
        """이미 승인된 요청 재승인 -> False"""
        manager = TradeApprovalManager()
        request = await manager.create_request("bot", "LONG", 50000, 0.001)
        await manager.approve(request.request_id, "user_1")

        # 다시 승인 시도
        result = await manager.approve(request.request_id, "user_2")
        assert result is False

    @pytest.mark.asyncio
    async def test_reject_already_processed(self):
        """이미 거부된 요청 재거부 -> False"""
        manager = TradeApprovalManager()
        request = await manager.create_request("bot", "SHORT", 50000, 0.001)
        await manager.reject(request.request_id, "user_1", "Bad signal")

        result = await manager.reject(request.request_id, "user_2")
        assert result is False


class TestTradeApprovalRequestTimeout:
    """TradeApprovalRequest timeout 테스트"""

    def test_timeout(self):
        """시간 초과 처리"""
        request = TradeApprovalRequest(
            bot_name="btc-bot",
            signal="LONG",
            price=50000.0,
            quantity=0.001,
        )

        request.timeout()
        assert request.status == ApprovalStatus.TIMEOUT


class TestTradeApprovalManagerGetRequest:
    """get_request 테스트"""

    @pytest.mark.asyncio
    async def test_get_existing_request(self):
        """존재하는 요청 조회"""
        manager = TradeApprovalManager()
        request = await manager.create_request("bot", "LONG", 50000, 0.001)

        found = await manager.get_request(request.request_id)
        assert found is not None
        assert found.signal == "LONG"

    @pytest.mark.asyncio
    async def test_get_nonexistent_request(self):
        """존재하지 않는 요청 조회 -> None"""
        manager = TradeApprovalManager()
        found = await manager.get_request("nonexistent")
        assert found is None


class TestTradeApprovalManagerStatsAllStatuses:
    """통계 조회 추가 테스트 (모든 상태)"""

    @pytest.mark.asyncio
    async def test_stats_with_all_statuses(self):
        """모든 상태의 요청이 있는 통계"""
        manager = TradeApprovalManager()

        # pending
        await manager.create_request("bot", "LONG", 50000, 0.001)

        # approved
        req = await manager.create_request("bot", "SHORT", 50000, 0.001)
        await manager.approve(req.request_id, "user")

        # rejected
        req = await manager.create_request("bot", "LONG", 51000, 0.001)
        await manager.reject(req.request_id, "user", "risk")

        # timeout
        req = await manager.create_request("bot", "SHORT", 49000, 0.001)
        req.timeout()

        stats = manager.get_stats()
        assert stats["total_requests"] == 4
        assert stats["pending"] == 1
        assert stats["approved"] == 1
        assert stats["rejected"] == 1
        assert stats["timeout"] == 1


class TestTradeApprovalManagerPendingFilter:
    """대기 중 요청 필터 테스트"""

    @pytest.mark.asyncio
    async def test_get_pending_by_bot_name(self):
        """봇 이름으로 필터링"""
        manager = TradeApprovalManager()
        await manager.create_request("bot-a", "LONG", 50000, 0.001)
        await manager.create_request("bot-b", "SHORT", 50000, 0.001)

        pending = await manager.get_pending_requests(bot_name="bot-a")
        assert len(pending) == 1
        assert pending[0].bot_name == "bot-a"


class TestTradeApprovalManagerResetCounter:
    """카운터 리셋 테스트"""

    @pytest.mark.asyncio
    async def test_reset_counter(self):
        """봇 거래 카운터 리셋"""
        manager = TradeApprovalManager(manual_approval_enabled=True, manual_approval_trades=5)

        # 5거래 완료
        for _ in range(5):
            await manager.record_trade_completed("bot-a")

        # 승인 불필요
        assert await manager.requires_approval("bot-a") is False

        # 카운터 리셋
        manager.reset_bot_counter("bot-a")

        # 다시 승인 필요
        assert await manager.requires_approval("bot-a") is True


class TestTradeApprovalRequestCreateWithRsiAtr:
    """RSI/ATR 정보 포함 요청"""

    @pytest.mark.asyncio
    async def test_create_request_with_rsi_atr(self):
        """RSI, ATR 정보 포함 요청 생성"""
        manager = TradeApprovalManager()
        request = await manager.create_request(
            bot_name="btc-bot",
            signal="LONG",
            price=50000.0,
            quantity=0.001,
            rsi=35.0,
            atr=500.0,
        )

        assert request.rsi == 35.0
        assert request.atr == 500.0

        data = request.to_dict()
        assert data["market_data"]["rsi"] == 35.0
        assert data["market_data"]["atr"] == 500.0


class TestTradeApprovalSignalConsistency:
    """validate_signal_consistency 테스트"""

    def test_matching_signals_return_true(self):
        """동일 시그널이면 True"""
        request = TradeApprovalRequest(
            bot_name="btc-bot",
            signal="LONG",
            price=50000.0,
            quantity=0.001,
            original_signal="LONG",
        )
        assert request.validate_signal_consistency("LONG") is True

    def test_different_signals_return_false(self):
        """다른 시그널이면 False"""
        request = TradeApprovalRequest(
            bot_name="btc-bot",
            signal="LONG",
            price=50000.0,
            quantity=0.001,
            original_signal="LONG",
        )
        assert request.validate_signal_consistency("SHORT") is False

    def test_empty_original_returns_true(self):
        """original_signal이 빈 문자열이면 True (체크 스킵)"""
        request = TradeApprovalRequest(
            bot_name="btc-bot",
            signal="LONG",
            price=50000.0,
            quantity=0.001,
        )
        assert request.original_signal == ""
        assert request.validate_signal_consistency("SHORT") is True

    @pytest.mark.asyncio
    async def test_create_request_sets_original_signal(self):
        """create_request가 original_signal을 설정"""
        manager = TradeApprovalManager()
        request = await manager.create_request("bot", "SHORT", 50000, 0.001)
        assert request.original_signal == "SHORT"
