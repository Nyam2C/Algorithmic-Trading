"""
Tests for trading executor
"""
import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timedelta

from src.trading.executor import TradingExecutor
from src.config import TradingConfig


@pytest.fixture
def mock_config():
    """Mock 설정 생성"""
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
    """Mock Binance 클라이언트"""
    client = Mock()
    client.set_leverage = AsyncMock(return_value={"leverage": 15})
    client.get_position = AsyncMock(return_value=None)
    client.create_market_order = AsyncMock(return_value={
        "orderId": 12345,
        "symbol": "BTCUSDT",
        "side": "BUY",
        "status": "FILLED"
    })
    client.close_position = AsyncMock(return_value={
        "orderId": 67890,
        "status": "FILLED"
    })
    return client


@pytest.fixture
def executor(mock_binance_client, mock_config):
    """TradingExecutor 인스턴스"""
    return TradingExecutor(mock_binance_client, mock_config)


class TestTradingExecutor:
    """TradingExecutor 테스트"""

    @pytest.mark.asyncio
    async def test_setup_leverage(self, executor, mock_binance_client):
        """레버리지 설정 테스트"""
        result = await executor.setup_leverage()

        assert result is True
        mock_binance_client.set_leverage.assert_called_once_with(
            symbol="BTCUSDT",
            leverage=15
        )

    def test_calculate_position_size(self, executor):
        """포지션 크기 계산 테스트"""
        current_price = 100000.0

        quantity = executor._calculate_position_size(current_price)

        # 검증: quantity는 양수
        assert quantity > 0

        # 검증: 레버리지와 비중을 고려한 크기
        # capital * size_pct * leverage / price
        expected_value = 1000 * 0.05 * 15  # = 750
        expected_quantity = expected_value / current_price  # = 0.0075
        # round(0.0075, 3) = 0.007 (소수점 3자리 반올림)
        expected_quantity_rounded = round(expected_quantity, 3)
        assert quantity == expected_quantity_rounded

    @pytest.mark.asyncio
    async def test_open_position_long(self, executor, mock_binance_client):
        """LONG 포지션 진입 테스트"""
        current_price = 100000.0

        order = await executor.open_position("LONG", current_price)

        assert order is not None
        assert order["orderId"] == 12345

        # 레버리지 설정 호출 확인
        mock_binance_client.set_leverage.assert_called_once()

        # 주문 생성 호출 확인
        mock_binance_client.create_market_order.assert_called_once()
        call_args = mock_binance_client.create_market_order.call_args
        assert call_args[1]["symbol"] == "BTCUSDT"
        assert call_args[1]["side"] == "BUY"

    @pytest.mark.asyncio
    async def test_open_position_short(self, executor, mock_binance_client):
        """SHORT 포지션 진입 테스트"""
        current_price = 100000.0

        order = await executor.open_position("SHORT", current_price)

        assert order is not None

        # SHORT는 SELL 주문
        call_args = mock_binance_client.create_market_order.call_args
        assert call_args[1]["side"] == "SELL"

    @pytest.mark.asyncio
    async def test_open_position_with_existing_position(self, executor, mock_binance_client):
        """이미 포지션이 있을 때 진입하지 않음"""
        # 기존 포지션 있음
        mock_binance_client.get_position.return_value = {
            "side": "LONG",
            "position_amt": 0.01
        }

        order = await executor.open_position("LONG", 100000.0)

        # 주문이 생성되지 않아야 함
        assert order is None
        mock_binance_client.create_market_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_close_position(self, executor, mock_binance_client):
        """포지션 청산 테스트"""
        # 포지션이 있다고 설정
        mock_binance_client.get_position.return_value = {
            "side": "LONG",
            "position_amt": 0.01,
            "entry_price": 100000.0
        }

        order = await executor.close_position()

        assert order is not None
        assert order["orderId"] == 67890

        mock_binance_client.close_position.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_position_no_position(self, executor, mock_binance_client):
        """포지션이 없을 때 청산 시도"""
        # 포지션 없음
        mock_binance_client.get_position.return_value = None

        order = await executor.close_position()

        # 청산되지 않아야 함
        assert order is None
        mock_binance_client.close_position.assert_not_called()

    @pytest.mark.asyncio
    async def test_has_position_true(self, executor, mock_binance_client):
        """포지션 있을 때"""
        mock_binance_client.get_position.return_value = {
            "side": "LONG",
            "position_amt": 0.01
        }

        has_pos = await executor.has_position()

        assert has_pos is True

    @pytest.mark.asyncio
    async def test_has_position_false(self, executor, mock_binance_client):
        """포지션 없을 때"""
        mock_binance_client.get_position.return_value = None

        has_pos = await executor.has_position()

        assert has_pos is False

    def test_calculate_pnl_pct_long_profit(self, executor):
        """LONG 포지션 수익 계산"""
        entry_price = 100000.0
        current_price = 100400.0  # +0.4%

        pnl_pct = executor.calculate_pnl_pct(entry_price, current_price, "LONG")

        assert pytest.approx(pnl_pct, rel=0.01) == 0.4

    def test_calculate_pnl_pct_long_loss(self, executor):
        """LONG 포지션 손실 계산"""
        entry_price = 100000.0
        current_price = 99600.0  # -0.4%

        pnl_pct = executor.calculate_pnl_pct(entry_price, current_price, "LONG")

        assert pytest.approx(pnl_pct, rel=0.01) == -0.4

    def test_calculate_pnl_pct_short_profit(self, executor):
        """SHORT 포지션 수익 계산"""
        entry_price = 100000.0
        current_price = 99600.0  # 가격 하락 = SHORT 수익

        pnl_pct = executor.calculate_pnl_pct(entry_price, current_price, "SHORT")

        assert pytest.approx(pnl_pct, rel=0.01) == 0.4

    def test_calculate_pnl_pct_short_loss(self, executor):
        """SHORT 포지션 손실 계산"""
        entry_price = 100000.0
        current_price = 100400.0  # 가격 상승 = SHORT 손실

        pnl_pct = executor.calculate_pnl_pct(entry_price, current_price, "SHORT")

        assert pytest.approx(pnl_pct, rel=0.01) == -0.4

    @pytest.mark.asyncio
    async def test_check_tp_sl_take_profit(self, executor):
        """익절 조건 체크"""
        position = {
            "entry_price": 100000.0,
            "side": "LONG"
        }
        current_price = 100400.0  # +0.4% (TP 도달)

        result = await executor.check_tp_sl(position, current_price)

        assert result == "TP"

    @pytest.mark.asyncio
    async def test_check_tp_sl_stop_loss(self, executor):
        """손절 조건 체크"""
        position = {
            "entry_price": 100000.0,
            "side": "LONG"
        }
        current_price = 99600.0  # -0.4% (SL 도달)

        result = await executor.check_tp_sl(position, current_price)

        assert result == "SL"

    @pytest.mark.asyncio
    async def test_check_tp_sl_no_trigger(self, executor):
        """TP/SL 조건 없음"""
        position = {
            "entry_price": 100000.0,
            "side": "LONG"
        }
        current_price = 100200.0  # +0.2% (TP/SL 미도달)

        result = await executor.check_tp_sl(position, current_price)

        assert result is None


class TestTimecutFeature:
    """타임컷 기능 테스트"""

    def test_check_timecut_not_triggered(self, executor):
        """타임컷 조건 미달 (1시간 경과)"""
        position = {
            "entry_time": datetime.now() - timedelta(hours=1),
            "side": "LONG"
        }

        result = executor.check_timecut(position)

        assert result is False

    def test_check_timecut_triggered(self, executor):
        """타임컷 조건 충족 (2시간 경과)"""
        position = {
            "entry_time": datetime.now() - timedelta(hours=2, minutes=1),
            "side": "LONG"
        }

        result = executor.check_timecut(position)

        assert result is True

    def test_check_timecut_exactly_2_hours(self, executor):
        """타임컷 정확히 2시간"""
        position = {
            "entry_time": datetime.now() - timedelta(hours=2),
            "side": "LONG"
        }

        result = executor.check_timecut(position)

        assert result is True

    def test_check_timecut_no_entry_time(self, executor):
        """entry_time 필드 없음"""
        position = {
            "side": "LONG"
        }

        result = executor.check_timecut(position)

        assert result is False

    def test_check_timecut_custom_duration(self, mock_binance_client):
        """커스텀 타임컷 시간 (60분)"""
        config = TradingConfig(
            bot_name="test-bot",
            binance_api_key="test_key",
            binance_secret_key="test_secret",
            gemini_api_key="test_gemini",
            discord_webhook_url="https://test.com",
            time_cut_minutes=60,  # 60분으로 설정
        )
        executor = TradingExecutor(mock_binance_client, config)

        position = {
            "entry_time": datetime.now() - timedelta(minutes=61),
            "side": "LONG"
        }

        result = executor.check_timecut(position)

        assert result is True


class TestMakerOrderFeature:
    """Maker 주문 기능 테스트"""

    @pytest.mark.asyncio
    async def test_open_position_maker_long_filled(self, mock_binance_client, mock_config):
        """LONG Maker 주문 정상 체결"""
        # Mock 설정
        mock_binance_client.create_limit_order = AsyncMock(return_value={
            "orderId": 11111,
            "symbol": "BTCUSDT",
            "side": "BUY",
            "status": "NEW"
        })
        mock_binance_client.get_order_status = AsyncMock(return_value={
            "orderId": 11111,
            "status": "FILLED"
        })

        executor = TradingExecutor(mock_binance_client, mock_config)
        current_price = 100000.0

        order = await executor.open_position_maker("LONG", current_price, use_maker=True)

        assert order is not None
        assert order["orderId"] == 11111

        # Limit order 호출 확인
        mock_binance_client.create_limit_order.assert_called_once()
        call_args = mock_binance_client.create_limit_order.call_args
        assert call_args[1]["symbol"] == "BTCUSDT"
        assert call_args[1]["side"] == "BUY"

        # LONG 주문은 현재가보다 0.01% 낮은 가격
        expected_price = round(current_price * (1 - 0.0001), 2)
        assert call_args[1]["price"] == expected_price

    @pytest.mark.asyncio
    async def test_open_position_maker_short_filled(self, mock_binance_client, mock_config):
        """SHORT Maker 주문 정상 체결"""
        # Mock 설정
        mock_binance_client.create_limit_order = AsyncMock(return_value={
            "orderId": 22222,
            "symbol": "BTCUSDT",
            "side": "SELL",
            "status": "NEW"
        })
        mock_binance_client.get_order_status = AsyncMock(return_value={
            "orderId": 22222,
            "status": "FILLED"
        })

        executor = TradingExecutor(mock_binance_client, mock_config)
        current_price = 100000.0

        order = await executor.open_position_maker("SHORT", current_price, use_maker=True)

        assert order is not None
        assert order["orderId"] == 22222

        # SHORT 주문은 현재가보다 0.01% 높은 가격
        call_args = mock_binance_client.create_limit_order.call_args
        expected_price = round(current_price * (1 + 0.0001), 2)
        assert call_args[1]["price"] == expected_price
        assert call_args[1]["side"] == "SELL"

    @pytest.mark.asyncio
    async def test_open_position_maker_timeout_fallback(self, mock_binance_client, mock_config):
        """Maker 주문 미체결 -> Market 주문으로 fallback"""
        # Limit order는 미체결 상태 유지
        mock_binance_client.create_limit_order = AsyncMock(return_value={
            "orderId": 33333,
            "symbol": "BTCUSDT",
            "side": "BUY",
            "status": "NEW"
        })
        # 계속 NEW 상태로 반환 (미체결)
        mock_binance_client.get_order_status = AsyncMock(return_value={
            "orderId": 33333,
            "status": "NEW"
        })
        mock_binance_client.cancel_order = AsyncMock(return_value={
            "orderId": 33333,
            "status": "CANCELED"
        })
        # Market order로 fallback
        mock_binance_client.create_market_order = AsyncMock(return_value={
            "orderId": 44444,
            "symbol": "BTCUSDT",
            "side": "BUY",
            "status": "FILLED"
        })

        executor = TradingExecutor(mock_binance_client, mock_config)
        current_price = 100000.0

        order = await executor.open_position_maker("LONG", current_price, use_maker=True)

        assert order is not None
        assert order["orderId"] == 44444  # Market order ID

        # Limit order 취소 확인
        mock_binance_client.cancel_order.assert_called_once_with("BTCUSDT", 33333)

        # Market order로 fallback 확인
        mock_binance_client.create_market_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_open_position_maker_with_use_maker_false(self, mock_binance_client, mock_config):
        """use_maker=False로 Market 주문 직접 사용"""
        executor = TradingExecutor(mock_binance_client, mock_config)
        current_price = 100000.0

        order = await executor.open_position_maker("LONG", current_price, use_maker=False)

        assert order is not None
        assert order["orderId"] == 12345  # Market order의 기본 mock ID

        # Limit order는 호출되지 않아야 함
        assert not hasattr(mock_binance_client, 'create_limit_order') or \
               not mock_binance_client.create_limit_order.called

        # Market order만 호출
        mock_binance_client.create_market_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_wait_for_fill_filled(self, mock_binance_client, mock_config):
        """_wait_for_fill: 주문 체결됨"""
        mock_binance_client.get_order_status = AsyncMock(return_value={
            "orderId": 99999,
            "status": "FILLED"
        })

        executor = TradingExecutor(mock_binance_client, mock_config)

        result = await executor._wait_for_fill(99999, timeout=10, check_interval=1)

        assert result is True

    @pytest.mark.asyncio
    async def test_wait_for_fill_canceled(self, mock_binance_client, mock_config):
        """_wait_for_fill: 주문 취소됨"""
        mock_binance_client.get_order_status = AsyncMock(return_value={
            "orderId": 99999,
            "status": "CANCELED"
        })

        executor = TradingExecutor(mock_binance_client, mock_config)

        result = await executor._wait_for_fill(99999, timeout=10, check_interval=1)

        assert result is False

    @pytest.mark.asyncio
    async def test_wait_for_fill_timeout(self, mock_binance_client, mock_config):
        """_wait_for_fill: 타임아웃"""
        # 계속 NEW 상태로 유지
        mock_binance_client.get_order_status = AsyncMock(return_value={
            "orderId": 99999,
            "status": "NEW"
        })

        executor = TradingExecutor(mock_binance_client, mock_config)

        # 짧은 타임아웃으로 테스트
        result = await executor._wait_for_fill(99999, timeout=3, check_interval=1)

        assert result is False

    @pytest.mark.asyncio
    async def test_open_position_maker_with_existing_position(self, mock_binance_client, mock_config):
        """Maker 주문: 이미 포지션 있을 때"""
        # 기존 포지션 있음
        mock_binance_client.get_position.return_value = {
            "side": "LONG",
            "position_amt": 0.01
        }

        executor = TradingExecutor(mock_binance_client, mock_config)

        order = await executor.open_position_maker("LONG", 100000.0, use_maker=True)

        # 주문이 생성되지 않아야 함
        assert order is None
