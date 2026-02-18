"""Tests for split TP functionality in TradingExecutor.

APEX-V Phase A-4: 소프트웨어 측 분할 익절 테스트
- Exchange-side TP 주문 대신 소프트웨어 모니터링으로 전환
- SL만 exchange-side (closePosition 크래시 보호)
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.trading.executor import TradingExecutor


@pytest.fixture
def mock_config():
    """Split TP 활성화된 설정"""
    config = MagicMock()
    config.symbol = "BTCUSDT"
    config.leverage = 10
    config.position_size_pct = 0.05
    config.take_profit_pct = 0.008
    config.stop_loss_pct = 0.004
    config.use_atr_tp_sl = True
    config.atr_tp_multiplier = 2.0
    config.atr_sl_multiplier = 1.0
    config.use_split_tp = True
    config.split_tp_ratios = [0.5, 0.3, 0.2]
    config.split_tp_atr_multipliers = [1.0, 1.5, 2.5]
    config.max_slippage_pct = 0.005
    config.close_on_excessive_slippage = False
    config.estimated_fee_rate = 0.0008
    return config


@pytest.fixture
def mock_client():
    """Mock Binance client"""
    client = AsyncMock()
    client.create_stop_market_order = AsyncMock(return_value={"orderId": 1})
    client.create_take_profit_market_order = AsyncMock(return_value={"orderId": 2})
    client.create_market_order = AsyncMock(return_value={
        "orderId": 100, "executedQty": "0.005",
    })
    client.cancel_all_open_orders = AsyncMock(return_value=None)
    return client


@pytest.fixture
def executor(mock_client, mock_config):
    """TradingExecutor with split TP config"""
    return TradingExecutor(mock_client, mock_config)


# ──────────────────────────────────────────────
# 1. SL-only exchange placement + TP state init
# ──────────────────────────────────────────────
class TestSplitTPPlacement:
    """분할 TP 배치: SL만 거래소, TP는 소프트웨어 상태"""

    @pytest.mark.asyncio
    async def test_sl_placed_on_exchange(self, executor, mock_client):
        """SL은 거래소에 배치되어야 함"""
        result = await executor._place_split_tp_sl(
            symbol="BTCUSDT", side="LONG",
            quantity=0.01, entry_price=50000.0, entry_atr=500.0,
        )
        assert result is True
        mock_client.create_stop_market_order.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_exchange_tp_orders(self, executor, mock_client):
        """거래소 TP 주문은 생성하지 않음"""
        await executor._place_split_tp_sl(
            symbol="BTCUSDT", side="LONG",
            quantity=0.01, entry_price=50000.0, entry_atr=500.0,
        )
        mock_client.create_take_profit_market_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_pending_state_initialized(self, executor):
        """_pending_split_tp_state가 올바르게 초기화"""
        await executor._place_split_tp_sl(
            symbol="BTCUSDT", side="LONG",
            quantity=0.01, entry_price=50000.0, entry_atr=500.0,
        )
        state = executor._pending_split_tp_state
        assert state is not None
        assert state["enabled"] is True
        assert len(state["levels"]) == 3
        assert state["original_quantity"] == 0.01
        assert state["remaining_quantity"] == 0.01
        assert state["accumulated_pnl_usd"] == 0.0
        assert state["sl_moved_to_be"] is False

    @pytest.mark.asyncio
    async def test_long_tp_prices(self, executor):
        """LONG 분할 TP 가격이 올바른지"""
        await executor._place_split_tp_sl(
            symbol="BTCUSDT", side="LONG",
            quantity=0.01, entry_price=50000.0, entry_atr=500.0,
        )
        levels = executor._pending_split_tp_state["levels"]
        # TP1: 50000 + 500*1.0 = 50500
        assert levels[0]["price"] == 50500.0
        # TP2: 50000 + 500*1.5 = 50750
        assert levels[1]["price"] == 50750.0
        # TP3: 50000 + 500*2.5 = 51250
        assert levels[2]["price"] == 51250.0

    @pytest.mark.asyncio
    async def test_short_tp_prices(self, executor):
        """SHORT 분할 TP 가격이 올바른지"""
        await executor._place_split_tp_sl(
            symbol="BTCUSDT", side="SHORT",
            quantity=0.01, entry_price=50000.0, entry_atr=500.0,
        )
        levels = executor._pending_split_tp_state["levels"]
        # TP1: 50000 - 500*1.0 = 49500
        assert levels[0]["price"] == 49500.0
        # TP2: 50000 - 500*1.5 = 49250
        assert levels[1]["price"] == 49250.0
        # TP3: 50000 - 500*2.5 = 48750
        assert levels[2]["price"] == 48750.0

    @pytest.mark.asyncio
    async def test_sl_failure_returns_false(self, executor, mock_client):
        """SL 주문 실패 시 False 반환"""
        mock_client.create_stop_market_order.side_effect = Exception("SL failed")
        result = await executor._place_split_tp_sl(
            symbol="BTCUSDT", side="LONG",
            quantity=0.01, entry_price=50000.0, entry_atr=500.0,
        )
        assert result is False
        assert executor._pending_split_tp_state is None

    @pytest.mark.asyncio
    async def test_delegates_when_enabled(self, executor, mock_client):
        """use_split_tp=True + ATR → _place_split_tp_sl 위임"""
        result = await executor._place_exchange_tp_sl(
            symbol="BTCUSDT", side="LONG",
            quantity=0.01, entry_price=50000.0, entry_atr=500.0,
        )
        assert result is True
        # SL 1회만 (TP는 exchange 주문 없음)
        assert mock_client.create_stop_market_order.call_count == 1
        assert mock_client.create_take_profit_market_order.call_count == 0

    @pytest.mark.asyncio
    async def test_disabled_uses_single_tp(self, mock_client):
        """use_split_tp=False면 기존 단일 TP"""
        config = MagicMock()
        config.symbol = "BTCUSDT"
        config.use_split_tp = False
        config.use_atr_tp_sl = True
        config.atr_tp_multiplier = 2.0
        config.atr_sl_multiplier = 1.0
        config.take_profit_pct = 0.008
        config.stop_loss_pct = 0.004
        executor = TradingExecutor(mock_client, config)

        result = await executor._place_exchange_tp_sl(
            symbol="BTCUSDT", side="LONG",
            quantity=0.01, entry_price=50000.0, entry_atr=500.0,
        )
        assert result is True
        assert mock_client.create_stop_market_order.call_count == 1
        assert mock_client.create_take_profit_market_order.call_count == 1

    @pytest.mark.asyncio
    async def test_without_atr_falls_back(self, executor, mock_client):
        """ATR 없으면 기존 단일 TP로 fallback"""
        result = await executor._place_exchange_tp_sl(
            symbol="BTCUSDT", side="LONG",
            quantity=0.01, entry_price=50000.0, entry_atr=None,
        )
        assert result is True
        assert mock_client.create_stop_market_order.call_count == 1
        assert mock_client.create_take_profit_market_order.call_count == 1


# ──────────────────────────────────────────────
# 2. check_split_tp() — TP/SL level detection
# ──────────────────────────────────────────────
class TestCheckSplitTP:
    """분할 TP 레벨 트리거 감지"""

    def _make_position(self, side="LONG", entry=50000.0, atr=500.0):
        """테스트용 포지션 + split_tp_state 생성"""
        if side == "LONG":
            tp_prices = [
                entry + atr * 1.0,  # 50500
                entry + atr * 1.5,  # 50750
                entry + atr * 2.5,  # 51250
            ]
            sl = entry - atr * 1.0  # 49500
        else:
            tp_prices = [
                entry - atr * 1.0,  # 49500
                entry - atr * 1.5,  # 49250
                entry - atr * 2.5,  # 48750
            ]
            sl = entry + atr * 1.0  # 50500

        return {
            "signal": side,
            "side": side,
            "entry_price": entry,
            "entry_atr": atr,
            "quantity": 0.01,
            "tp_price": tp_prices[-1],
            "sl_price": sl,
            "split_tp_state": {
                "enabled": True,
                "levels": [
                    {"ratio": 0.5, "atr_mul": 1.0, "price": tp_prices[0], "hit": False},
                    {"ratio": 0.3, "atr_mul": 1.5, "price": tp_prices[1], "hit": False},
                    {"ratio": 0.2, "atr_mul": 2.5, "price": tp_prices[2], "hit": False},
                ],
                "original_quantity": 0.01,
                "remaining_quantity": 0.01,
                "accumulated_pnl_usd": 0.0,
                "sl_moved_to_be": False,
            },
        }

    @pytest.mark.asyncio
    async def test_long_tp1_trigger(self, executor):
        """LONG TP1 트리거"""
        executor.current_position = self._make_position("LONG")
        result = await executor.check_split_tp(50500.0)
        assert result == "SPLIT_TP1"

    @pytest.mark.asyncio
    async def test_long_tp2_trigger(self, executor):
        """LONG TP2 (TP1 이미 hit)"""
        executor.current_position = self._make_position("LONG")
        executor.current_position["split_tp_state"]["levels"][0]["hit"] = True
        result = await executor.check_split_tp(50750.0)
        assert result == "SPLIT_TP2"

    @pytest.mark.asyncio
    async def test_long_tp3_trigger_returns_tp(self, executor):
        """LONG TP3 (마지막) → 'TP' 반환 (전체 청산)"""
        executor.current_position = self._make_position("LONG")
        executor.current_position["split_tp_state"]["levels"][0]["hit"] = True
        executor.current_position["split_tp_state"]["levels"][1]["hit"] = True
        result = await executor.check_split_tp(51250.0)
        assert result == "TP"

    @pytest.mark.asyncio
    async def test_long_sl_trigger(self, executor):
        """LONG SL 트리거"""
        executor.current_position = self._make_position("LONG")
        result = await executor.check_split_tp(49500.0)
        assert result == "SL"

    @pytest.mark.asyncio
    async def test_long_be_sl_trigger(self, executor):
        """LONG break-even SL (TP1 후)"""
        executor.current_position = self._make_position("LONG")
        state = executor.current_position["split_tp_state"]
        state["levels"][0]["hit"] = True
        state["sl_moved_to_be"] = True
        result = await executor.check_split_tp(50000.0)  # entry price
        assert result == "SL"

    @pytest.mark.asyncio
    async def test_short_tp1_trigger(self, executor):
        """SHORT TP1 트리거"""
        executor.current_position = self._make_position("SHORT")
        result = await executor.check_split_tp(49500.0)
        assert result == "SPLIT_TP1"

    @pytest.mark.asyncio
    async def test_short_sl_trigger(self, executor):
        """SHORT SL 트리거"""
        executor.current_position = self._make_position("SHORT")
        result = await executor.check_split_tp(50500.0)
        assert result == "SL"

    @pytest.mark.asyncio
    async def test_no_trigger(self, executor):
        """가격 미달 시 None"""
        executor.current_position = self._make_position("LONG")
        result = await executor.check_split_tp(50200.0)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_split_state_delegates(self, executor):
        """split_tp_state 없으면 기존 check_tp_sl_dynamic 위임"""
        executor.current_position = {
            "signal": "LONG", "side": "LONG",
            "entry_price": 50000.0, "entry_atr": 500.0,
        }
        with patch.object(
            executor, "check_tp_sl_dynamic", new_callable=AsyncMock
        ) as mock_dynamic:
            mock_dynamic.return_value = "TP"
            result = await executor.check_split_tp(60000.0)
            assert result == "TP"
            mock_dynamic.assert_called_once()


# ──────────────────────────────────────────────
# 3. execute_partial_close()
# ──────────────────────────────────────────────
class TestExecutePartialClose:
    """부분 청산 실행 테스트"""

    def _make_position(self):
        return {
            "signal": "LONG", "side": "LONG",
            "entry_price": 50000.0, "entry_atr": 500.0,
            "quantity": 0.1, "sl_price": 49500.0,
            "split_tp_state": {
                "enabled": True,
                "levels": [
                    {"ratio": 0.5, "atr_mul": 1.0, "price": 50500.0, "hit": False},
                    {"ratio": 0.3, "atr_mul": 1.5, "price": 50750.0, "hit": False},
                    {"ratio": 0.2, "atr_mul": 2.5, "price": 51250.0, "hit": False},
                ],
                "original_quantity": 0.1,
                "remaining_quantity": 0.1,
                "accumulated_pnl_usd": 0.0,
                "sl_moved_to_be": False,
            },
        }

    @pytest.mark.asyncio
    async def test_partial_close_tp1(self, executor, mock_client):
        """TP1 부분 청산: 50% 수량"""
        executor.current_position = self._make_position()
        result = await executor.execute_partial_close(0, 50500.0)

        assert result is not None
        # 0.1 * 0.5 = 0.05
        mock_client.create_market_order.assert_called_once_with(
            symbol="BTCUSDT", side="SELL", quantity=0.05,
        )

        state = executor.current_position["split_tp_state"]
        assert state["levels"][0]["hit"] is True
        assert state["remaining_quantity"] == 0.05
        assert state["accumulated_pnl_usd"] != 0.0

    @pytest.mark.asyncio
    async def test_partial_close_pnl_calculation(self, executor, mock_client):
        """부분 청산 PnL 계산: (50500-50000)*0.05 - fee"""
        executor.current_position = self._make_position()
        await executor.execute_partial_close(0, 50500.0)

        state = executor.current_position["split_tp_state"]
        # (50500-50000)*0.05 = 25.0, fee = 0.05*50500*0.0008 = 2.02
        expected_pnl = 25.0 - (0.05 * 50500.0 * 0.0008)
        assert abs(state["accumulated_pnl_usd"] - expected_pnl) < 0.01

    @pytest.mark.asyncio
    async def test_tp1_triggers_be_sl_move(self, executor, mock_client):
        """TP1 후 SL → break-even 이동"""
        executor.current_position = self._make_position()
        await executor.execute_partial_close(0, 50500.0)

        # cancel_all_open_orders + create_stop_market_order 호출 확인
        mock_client.cancel_all_open_orders.assert_called_once()
        # SL 재배치: entry_price (50000)로
        calls = mock_client.create_stop_market_order.call_args_list
        assert len(calls) == 1  # BE SL
        assert calls[0].kwargs["stop_price"] == 50000.0

        state = executor.current_position["split_tp_state"]
        assert state["sl_moved_to_be"] is True

    @pytest.mark.asyncio
    async def test_tp2_no_be_move(self, executor, mock_client):
        """TP2에서는 BE SL 이동 안함"""
        executor.current_position = self._make_position()
        state = executor.current_position["split_tp_state"]
        state["levels"][0]["hit"] = True
        state["remaining_quantity"] = 0.05
        state["sl_moved_to_be"] = True

        mock_client.cancel_all_open_orders.reset_mock()
        await executor.execute_partial_close(1, 50750.0)

        # TP2에서는 cancel/재배치 안함
        mock_client.cancel_all_open_orders.assert_not_called()

    @pytest.mark.asyncio
    async def test_already_hit_returns_none(self, executor):
        """이미 hit된 레벨은 None 반환"""
        executor.current_position = self._make_position()
        executor.current_position["split_tp_state"]["levels"][0]["hit"] = True
        result = await executor.execute_partial_close(0, 50500.0)
        assert result is None

    @pytest.mark.asyncio
    async def test_order_failure_returns_none(self, executor, mock_client):
        """주문 실패 시 None 반환, hit=False 유지"""
        executor.current_position = self._make_position()
        mock_client.create_market_order.side_effect = Exception("Order failed")
        result = await executor.execute_partial_close(0, 50500.0)

        assert result is None
        assert executor.current_position["split_tp_state"]["levels"][0]["hit"] is False


# ──────────────────────────────────────────────
# 4. _move_sl_to_breakeven()
# ──────────────────────────────────────────────
class TestMoveSLToBreakeven:
    """SL → break-even 이동 테스트"""

    @pytest.mark.asyncio
    async def test_successful_move(self, executor, mock_client):
        """정상 이동: 취소 → 재배치"""
        executor.current_position = {
            "signal": "LONG", "side": "LONG",
            "entry_price": 50000.0, "sl_price": 49500.0,
            "split_tp_state": {
                "remaining_quantity": 0.05,
                "sl_moved_to_be": False,
            },
        }
        result = await executor._move_sl_to_breakeven()

        assert result is True
        mock_client.cancel_all_open_orders.assert_called_once_with("BTCUSDT")
        mock_client.create_stop_market_order.assert_called_once_with(
            symbol="BTCUSDT", side="SELL",
            quantity=0.05, stop_price=50000.0,
        )
        assert executor.current_position["sl_price"] == 50000.0
        assert executor.current_position["split_tp_state"]["sl_moved_to_be"] is True

    @pytest.mark.asyncio
    async def test_cancel_failure_returns_false(self, executor, mock_client):
        """주문 취소 실패 시 False"""
        executor.current_position = {
            "signal": "LONG", "side": "LONG",
            "entry_price": 50000.0, "sl_price": 49500.0,
            "split_tp_state": {
                "remaining_quantity": 0.05,
                "sl_moved_to_be": False,
            },
        }
        mock_client.cancel_all_open_orders.side_effect = Exception("Cancel failed")
        result = await executor._move_sl_to_breakeven()
        assert result is False

    @pytest.mark.asyncio
    async def test_sl_placement_failure(self, executor, mock_client):
        """SL 재배치 실패 시 False (원래 SL이 유효할 수 있음)"""
        executor.current_position = {
            "signal": "SHORT", "side": "SHORT",
            "entry_price": 50000.0, "sl_price": 50500.0,
            "split_tp_state": {
                "remaining_quantity": 0.05,
                "sl_moved_to_be": False,
            },
        }
        mock_client.create_stop_market_order.side_effect = Exception("SL failed")
        result = await executor._move_sl_to_breakeven()
        assert result is False
        # sl_moved_to_be should NOT be set
        assert executor.current_position["split_tp_state"]["sl_moved_to_be"] is False


# ──────────────────────────────────────────────
# 5. Edge cases
# ──────────────────────────────────────────────
class TestSplitTPEdgeCases:
    """분할 TP 엣지 케이스"""

    @pytest.mark.asyncio
    async def test_tiny_quantity_skipped(self, executor, mock_client):
        """최소 수량 미만 → hit=True, 주문 스킵"""
        executor.current_position = {
            "signal": "LONG", "side": "LONG",
            "entry_price": 50000.0, "sl_price": 49500.0,
            "split_tp_state": {
                "enabled": True,
                "levels": [
                    {"ratio": 0.2, "atr_mul": 2.5, "price": 51250.0, "hit": False},
                ],
                "original_quantity": 0.002,  # 0.002 * 0.2 = 0.0004 < MIN
                "remaining_quantity": 0.002,
                "accumulated_pnl_usd": 0.0,
                "sl_moved_to_be": False,
            },
        }
        result = await executor.execute_partial_close(0, 51250.0)
        assert result is None
        # hit should be marked True
        assert executor.current_position["split_tp_state"]["levels"][0]["hit"] is True
        mock_client.create_market_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_short_partial_close(self, executor, mock_client):
        """SHORT 부분 청산: close_side=BUY"""
        executor.current_position = {
            "signal": "SHORT", "side": "SHORT",
            "entry_price": 50000.0, "sl_price": 50500.0,
            "split_tp_state": {
                "enabled": True,
                "levels": [
                    {"ratio": 0.5, "atr_mul": 1.0, "price": 49500.0, "hit": False},
                ],
                "original_quantity": 0.1,
                "remaining_quantity": 0.1,
                "accumulated_pnl_usd": 0.0,
                "sl_moved_to_be": False,
            },
        }
        await executor.execute_partial_close(0, 49500.0)
        mock_client.create_market_order.assert_called_once_with(
            symbol="BTCUSDT", side="BUY", quantity=0.05,
        )

    @pytest.mark.asyncio
    async def test_no_position_returns_none(self, executor):
        """포지션 없으면 None"""
        executor.current_position = None
        result = await executor.check_split_tp(50500.0)
        assert result is None
        result = await executor.execute_partial_close(0, 50500.0)
        assert result is None


# ──────────────────────────────────────────────
# 6. Full integration scenario
# ──────────────────────────────────────────────
class TestSplitTPIntegration:
    """전체 TP1→TP2→TP3 시나리오"""

    @pytest.mark.asyncio
    async def test_full_tp1_tp2_tp3_sequence(self, executor, mock_client):
        """TP1 → TP2 → TP3(전체 청산) 순차 시나리오"""
        executor.current_position = {
            "signal": "LONG", "side": "LONG",
            "entry_price": 50000.0, "entry_atr": 500.0,
            "quantity": 0.1, "sl_price": 49500.0,
            "split_tp_state": {
                "enabled": True,
                "levels": [
                    {"ratio": 0.5, "atr_mul": 1.0, "price": 50500.0, "hit": False},
                    {"ratio": 0.3, "atr_mul": 1.5, "price": 50750.0, "hit": False},
                    {"ratio": 0.2, "atr_mul": 2.5, "price": 51250.0, "hit": False},
                ],
                "original_quantity": 0.1,
                "remaining_quantity": 0.1,
                "accumulated_pnl_usd": 0.0,
                "sl_moved_to_be": False,
            },
        }

        # TP1
        assert await executor.check_split_tp(50500.0) == "SPLIT_TP1"
        await executor.execute_partial_close(0, 50500.0)
        state = executor.current_position["split_tp_state"]
        assert state["levels"][0]["hit"] is True
        assert state["remaining_quantity"] == 0.05
        assert state["sl_moved_to_be"] is True

        # TP2
        assert await executor.check_split_tp(50750.0) == "SPLIT_TP2"
        await executor.execute_partial_close(1, 50750.0)
        assert state["levels"][1]["hit"] is True
        assert state["remaining_quantity"] == 0.02

        # TP3 → 전체 청산
        assert await executor.check_split_tp(51250.0) == "TP"

        # 누적 PnL 확인 (TP1 + TP2)
        assert state["accumulated_pnl_usd"] > 0

    @pytest.mark.asyncio
    async def test_tp1_then_sl_at_breakeven(self, executor, mock_client):
        """TP1 → SL(break-even) 시나리오"""
        executor.current_position = {
            "signal": "LONG", "side": "LONG",
            "entry_price": 50000.0, "entry_atr": 500.0,
            "quantity": 0.1, "sl_price": 49500.0,
            "split_tp_state": {
                "enabled": True,
                "levels": [
                    {"ratio": 0.5, "atr_mul": 1.0, "price": 50500.0, "hit": False},
                    {"ratio": 0.3, "atr_mul": 1.5, "price": 50750.0, "hit": False},
                    {"ratio": 0.2, "atr_mul": 2.5, "price": 51250.0, "hit": False},
                ],
                "original_quantity": 0.1,
                "remaining_quantity": 0.1,
                "accumulated_pnl_usd": 0.0,
                "sl_moved_to_be": False,
            },
        }

        # TP1 체결
        await executor.execute_partial_close(0, 50500.0)
        state = executor.current_position["split_tp_state"]
        tp1_pnl = state["accumulated_pnl_usd"]
        assert tp1_pnl > 0

        # 가격 하락 → break-even SL
        assert await executor.check_split_tp(50000.0) == "SL"
        # 잔여 50%는 entry price에서 SL → PnL ≈ 0 (수수료만)
        # 총 PnL = TP1 이익 + 잔여분 0 = TP1 이익만

    @pytest.mark.asyncio
    async def test_state_injection_via_prepare(self, executor, mock_client):
        """_prepare_and_open_position에서 split_tp_state 주입 확인"""
        mock_client.get_position = AsyncMock(return_value=None)
        mock_client.set_leverage = AsyncMock(return_value=True)
        mock_client.get_account_balance = AsyncMock(
            return_value={"available": 10000.0}
        )
        mock_client.create_market_order = AsyncMock(return_value={
            "orderId": 1, "avgPrice": "50000.0",
        })
        executor.config.use_real_balance = False

        order = await executor._prepare_and_open_position(
            signal="LONG", current_price=50000.0, entry_atr=500.0,
        )
        assert order is not None
        assert executor.current_position is not None
        assert "split_tp_state" in executor.current_position
        assert executor.current_position["split_tp_state"]["enabled"] is True
        assert executor._pending_split_tp_state is None


# ──────────────────────────────────────────────
# 7. BotConfig validation (기존 유지)
# ──────────────────────────────────────────────
class TestBotConfigSplitTP:
    """BotConfig split TP 설정 테스트"""

    def test_default_split_tp_disabled(self):
        """기본값: split TP 비활성화"""
        from src.bot_config import BotConfig
        config = BotConfig(bot_name="test", stop_loss_pct=0.003, leverage=3)
        assert config.use_split_tp is False

    def test_split_tp_ratios_default(self):
        """기본 분할 비율"""
        from src.bot_config import BotConfig
        config = BotConfig(bot_name="test", stop_loss_pct=0.003, leverage=3)
        assert config.split_tp_ratios == [0.5, 0.3, 0.2]

    def test_split_tp_ratios_must_sum_to_one(self):
        """분할 비율 합이 1.0이 아니면 에러"""
        from src.bot_config import BotConfig
        with pytest.raises(ValueError, match=r"sum must be 1\.0"):
            BotConfig(
                bot_name="test",
                stop_loss_pct=0.003,
                leverage=3,
                split_tp_ratios=[0.5, 0.3, 0.3],  # sum = 1.1
            )

    def test_split_tp_custom_ratios(self):
        """커스텀 분할 비율"""
        from src.bot_config import BotConfig
        config = BotConfig(
            bot_name="test",
            stop_loss_pct=0.003,
            leverage=3,
            split_tp_ratios=[0.6, 0.25, 0.15],
        )
        assert config.split_tp_ratios == [0.6, 0.25, 0.15]

    def test_use_adx_regime_default(self):
        """기본값: ADX regime 비활성화"""
        from src.bot_config import BotConfig
        config = BotConfig(bot_name="test", stop_loss_pct=0.003, leverage=3)
        assert config.use_adx_regime is False
