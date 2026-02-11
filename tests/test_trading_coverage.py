"""
Trading 모듈 커버리지 개선 테스트

executor.py, trade_approval.py의 미커버 라인을 대상으로 합니다.
"""
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest

from src.config import TradingConfig
from src.trading.executor import TradingExecutor
from src.trading.trade_approval import (
    ApprovalStatus,
    TradeApprovalManager,
    TradeApprovalRequest,
)

# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_config():
    return TradingConfig(
        bot_name="test-bot",
        binance_api_key="test_key",
        binance_secret_key="test_secret",
        gemini_api_key="test_gemini",
        discord_webhook_url="https://test.com",
        symbol="BTCUSDT",
        leverage=15,
        position_size_pct=0.05,
        take_profit_pct=0.004,
        stop_loss_pct=0.004,
    )


@pytest.fixture
def mock_binance_client():
    client = Mock()
    client.set_leverage = AsyncMock(return_value={"leverage": 15})
    client.get_position = AsyncMock(return_value=None)
    client.create_market_order = AsyncMock(return_value={
        "orderId": 12345,
        "symbol": "BTCUSDT",
        "side": "BUY",
        "status": "FILLED",
    })
    client.close_position = AsyncMock(return_value={
        "orderId": 67890,
        "status": "FILLED",
    })
    client.get_account_balance = AsyncMock(return_value={
        "asset": "USDT",
        "balance": 5000.0,
        "available": 4500.0,
        "unrealized_pnl": 100.0,
    })
    return client


@pytest.fixture
def executor(mock_binance_client, mock_config):
    return TradingExecutor(mock_binance_client, mock_config)


# =============================================================================
# Executor: setup_leverage failure
# =============================================================================

class TestExecutorSetupLeverageFailure:
    """레버리지 설정 실패 테스트"""

    @pytest.mark.asyncio
    async def test_setup_leverage_failure(self, mock_binance_client, mock_config):
        """레버리지 설정 실패 시 False 반환"""
        mock_binance_client.set_leverage = AsyncMock(side_effect=Exception("API Error"))
        executor = TradingExecutor(mock_binance_client, mock_config)

        result = await executor.setup_leverage()
        assert result is False


# =============================================================================
# Executor: _get_available_balance error with cached value
# =============================================================================

class TestExecutorBalanceErrorWithCache:
    """잔고 조회 실패 시 캐시 사용"""

    @pytest.mark.asyncio
    async def test_balance_error_with_cached_value(self, mock_binance_client, mock_config):
        """조회 실패 + 캐시 값 → 캐시 사용"""
        executor = TradingExecutor(mock_binance_client, mock_config)
        # 먼저 캐시에 값 저장
        executor._cached_balance = 3000.0
        executor._balance_cache_time = datetime.now() - timedelta(minutes=5)  # 만료됨

        # API 에러 발생
        mock_binance_client.get_account_balance = AsyncMock(
            side_effect=Exception("API Error")
        )

        balance = await executor._get_available_balance()
        assert balance == 3000.0  # 캐시 값 사용

    @pytest.mark.asyncio
    async def test_balance_error_no_cache(self, mock_binance_client, mock_config):
        """조회 실패 + 캐시 없음 → 예외 발생"""
        executor = TradingExecutor(mock_binance_client, mock_config)
        mock_binance_client.get_account_balance = AsyncMock(
            side_effect=Exception("API Error")
        )

        with pytest.raises(Exception, match="API Error"):
            await executor._get_available_balance()


# =============================================================================
# Executor: open_position leverage failure
# =============================================================================

class TestExecutorOpenPositionLeverageFailure:
    """open_position 레버리지 실패"""

    @pytest.mark.asyncio
    async def test_open_position_leverage_failure(self, mock_binance_client, mock_config):
        """레버리지 설정 실패 → None 반환"""
        mock_binance_client.set_leverage = AsyncMock(side_effect=Exception("Leverage error"))
        executor = TradingExecutor(mock_binance_client, mock_config)

        result = await executor.open_position("LONG", 100000.0)
        assert result is None

    @pytest.mark.asyncio
    async def test_open_position_general_exception(self, mock_binance_client, mock_config):
        """open_position 일반 예외"""
        mock_binance_client.create_market_order = AsyncMock(
            side_effect=Exception("Order error")
        )
        executor = TradingExecutor(mock_binance_client, mock_config)

        result = await executor.open_position("LONG", 100000.0)
        assert result is None


# =============================================================================
# Executor: open_position_maker leverage failure and general exception
# =============================================================================

class TestExecutorOpenPositionMakerEdgeCases:
    """open_position_maker 엣지 케이스"""

    @pytest.mark.asyncio
    async def test_open_position_maker_leverage_failure(self, mock_binance_client, mock_config):
        """Maker 주문 레버리지 실패 → None"""
        mock_binance_client.set_leverage = AsyncMock(side_effect=Exception("Error"))
        executor = TradingExecutor(mock_binance_client, mock_config)

        result = await executor.open_position_maker("LONG", 100000.0)
        assert result is None

    @pytest.mark.asyncio
    async def test_open_position_maker_general_exception(self, mock_binance_client, mock_config):
        """Maker 주문 일반 예외"""
        mock_binance_client.create_limit_order = AsyncMock(
            side_effect=Exception("Order error")
        )
        executor = TradingExecutor(mock_binance_client, mock_config)

        result = await executor.open_position_maker("LONG", 100000.0)
        assert result is None


# =============================================================================
# Executor: _wait_for_fill error during check
# =============================================================================

class TestExecutorWaitForFillError:
    """_wait_for_fill 에러 처리"""

    @pytest.mark.asyncio
    async def test_wait_for_fill_exception(self, mock_binance_client, mock_config):
        """주문 상태 확인 중 예외 → False"""
        mock_binance_client.get_order_status = AsyncMock(
            side_effect=Exception("Status check error")
        )
        executor = TradingExecutor(mock_binance_client, mock_config)

        result = await executor._wait_for_fill(99999, timeout=5, check_interval=1)
        assert result is False


# =============================================================================
# Executor: close_position error
# =============================================================================

class TestExecutorClosePositionError:
    """close_position 에러 처리"""

    @pytest.mark.asyncio
    async def test_close_position_exception(self, mock_binance_client, mock_config):
        """청산 중 예외 → None"""
        mock_binance_client.get_position = AsyncMock(return_value={
            "side": "LONG",
            "position_amt": 0.01,
        })
        mock_binance_client.close_position = AsyncMock(
            side_effect=Exception("Close error")
        )
        executor = TradingExecutor(mock_binance_client, mock_config)

        result = await executor.close_position()
        assert result is None


# =============================================================================
# Executor: get_position error
# =============================================================================

class TestExecutorGetPositionError:
    """get_position 에러 처리"""

    @pytest.mark.asyncio
    async def test_get_position_exception(self, mock_binance_client, mock_config):
        """포지션 조회 예외 → None"""
        mock_binance_client.get_position = AsyncMock(
            side_effect=Exception("Position error")
        )
        executor = TradingExecutor(mock_binance_client, mock_config)

        result = await executor.get_position()
        assert result is None


# =============================================================================
# Executor: check_tp_sl error
# =============================================================================

class TestExecutorCheckTpSlError:
    """check_tp_sl 에러 처리"""

    @pytest.mark.asyncio
    async def test_check_tp_sl_exception(self, mock_binance_client, mock_config):
        """TP/SL 체크 중 예외 → None"""
        executor = TradingExecutor(mock_binance_client, mock_config)

        # entry_price 누락으로 예외 발생
        position = {"side": "LONG"}

        result = await executor.check_tp_sl(position, 100000.0)
        assert result is None


# =============================================================================
# Executor: check_tp_sl_dynamic error fallback
# =============================================================================

class TestExecutorCheckTpSlDynamicError:
    """check_tp_sl_dynamic 에러 처리"""

    @pytest.mark.asyncio
    async def test_check_tp_sl_dynamic_error_fallback(self, mock_binance_client):
        """ATR TP/SL 에러 시 기존 로직 fallback"""
        config = TradingConfig(
            bot_name="test-bot",
            binance_api_key="test_key",
            binance_secret_key="test_secret",
            gemini_api_key="test_gemini",
            discord_webhook_url="https://test.com",
            use_atr_tp_sl=True,
            atr_tp_multiplier=2.0,
            atr_sl_multiplier=1.0,
        )
        executor = TradingExecutor(mock_binance_client, config)

        # entry_atr 있지만 entry_price 키가 잘못된 이름 → 예외 발생 → fallback
        position = {
            "wrong_key": 100000.0,  # entry_price 아님
            "side": "LONG",
            "entry_atr": 500.0,
        }

        # fallback에서도 entry_price 없으면 None
        result = await executor.check_tp_sl_dynamic(position, 100000.0)
        assert result is None


# =============================================================================
# Executor: check_timecut error
# =============================================================================

class TestExecutorCheckTimecutError:
    """check_timecut 에러 처리"""

    def test_check_timecut_exception(self, mock_binance_client, mock_config):
        """타임컷 체크 중 예외 → False"""
        executor = TradingExecutor(mock_binance_client, mock_config)

        # entry_time이 잘못된 타입
        position = {"entry_time": "not-a-datetime"}

        result = executor.check_timecut(position)
        assert result is False


# =============================================================================
# Executor: open_position with ATR info in log
# =============================================================================

class TestExecutorOpenPositionWithATR:
    """open_position ATR 정보 로깅"""

    @pytest.mark.asyncio
    async def test_open_position_short_with_atr(self, mock_binance_client, mock_config):
        """SHORT 포지션 + ATR 정보 저장"""
        mock_binance_client.create_market_order = AsyncMock(return_value={
            "orderId": 99999,
            "symbol": "BTCUSDT",
            "side": "SELL",
            "status": "FILLED",
        })
        executor = TradingExecutor(mock_binance_client, mock_config)

        order = await executor.open_position("SHORT", 100000.0, entry_atr=600.0)

        assert order is not None
        assert executor.current_position["signal"] == "SHORT"
        assert executor.current_position["entry_atr"] == 600.0


# =============================================================================
# Executor: open_position_maker with ATR info
# =============================================================================

class TestExecutorMakerWithATR:
    """Maker 주문 ATR 정보"""

    @pytest.mark.asyncio
    async def test_open_position_maker_with_atr(self, mock_binance_client, mock_config):
        """Maker 주문 시 ATR 저장"""
        mock_binance_client.create_limit_order = AsyncMock(return_value={
            "orderId": 11111,
            "symbol": "BTCUSDT",
            "side": "BUY",
            "status": "NEW",
        })
        mock_binance_client.get_order_status = AsyncMock(return_value={
            "orderId": 11111,
            "status": "FILLED",
        })
        executor = TradingExecutor(mock_binance_client, mock_config)

        order = await executor.open_position_maker(
            "LONG", 100000.0, use_maker=True, entry_atr=500.0
        )

        assert order is not None
        assert executor.current_position["entry_atr"] == 500.0


# =============================================================================
# TradeApproval: Additional coverage
# =============================================================================

class TestTradeApprovalEdgeCases:
    """TradeApproval 추가 커버리지"""

    @pytest.mark.asyncio
    async def test_approve_nonexistent_request(self):
        """존재하지 않는 요청 승인 → False"""
        manager = TradeApprovalManager()
        result = await manager.approve("nonexistent", "user_1")
        assert result is False

    @pytest.mark.asyncio
    async def test_reject_nonexistent_request(self):
        """존재하지 않는 요청 거부 → False"""
        manager = TradeApprovalManager()
        result = await manager.reject("nonexistent", "user_1")
        assert result is False

    @pytest.mark.asyncio
    async def test_approve_already_processed(self):
        """이미 승인된 요청 재승인 → False"""
        manager = TradeApprovalManager()
        request = await manager.create_request("bot", "LONG", 50000, 0.001)
        await manager.approve(request.request_id, "user_1")

        # 다시 승인 시도
        result = await manager.approve(request.request_id, "user_2")
        assert result is False

    @pytest.mark.asyncio
    async def test_reject_already_processed(self):
        """이미 거부된 요청 재거부 → False"""
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
        """존재하지 않는 요청 조회 → None"""
        manager = TradeApprovalManager()
        found = await manager.get_request("nonexistent")
        assert found is None


class TestTradeApprovalManagerStats:
    """통계 조회 추가 테스트"""

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
