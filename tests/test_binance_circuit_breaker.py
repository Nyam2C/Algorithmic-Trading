"""Tests for circuit breaker integration in BinanceTestnetClient."""
from unittest.mock import AsyncMock

import pytest
from binance.exceptions import BinanceAPIException

from src.exchange.binance import BinanceTestnetClient
from src.utils.circuit_breaker import (
    CircuitBreakerOpen,
    reset_all_circuit_breakers,
)


@pytest.fixture(autouse=True)
def _reset_binance_circuit_breaker():
    """각 테스트 전후로 모든 circuit breaker 리셋."""
    reset_all_circuit_breakers()
    yield
    reset_all_circuit_breakers()


@pytest.fixture
def client():
    """연결된 BinanceTestnetClient 모의 객체."""
    c = BinanceTestnetClient("test_key", "test_secret", testnet=True)
    c._client = AsyncMock()
    c._metrics = None
    return c


class TestBinanceCircuitBreakerIntegration:
    """BinanceTestnetClient에 적용된 circuit breaker 테스트."""

    @pytest.mark.asyncio
    async def test_get_current_price_opens_circuit_after_failures(self, client):
        """get_current_price 연속 실패 시 circuit이 OPEN 상태로 전환."""
        client._client.futures_symbol_ticker = AsyncMock(
            side_effect=ConnectionError("connection failed")
        )

        for _ in range(5):
            with pytest.raises(ConnectionError):
                await client.get_current_price("BTCUSDT")

        with pytest.raises(CircuitBreakerOpen):
            await client.get_current_price("BTCUSDT")

    @pytest.mark.asyncio
    async def test_get_klines_opens_circuit_after_failures(self, client):
        """get_klines 연속 실패 시 circuit이 OPEN."""
        client._client.futures_klines = AsyncMock(
            side_effect=TimeoutError("timeout")
        )

        for _ in range(5):
            with pytest.raises(TimeoutError):
                await client.get_klines("BTCUSDT")

        with pytest.raises(CircuitBreakerOpen):
            await client.get_klines("BTCUSDT")

    @pytest.mark.asyncio
    async def test_create_market_order_opens_circuit_after_failures(self, client):
        """create_market_order 연속 실패 시 circuit이 OPEN."""
        client._client.futures_create_order = AsyncMock(
            side_effect=ConnectionError("connection failed")
        )

        for _ in range(5):
            with pytest.raises(ConnectionError):
                await client.create_market_order("BTCUSDT", "BUY", 0.001)

        with pytest.raises(CircuitBreakerOpen):
            await client.create_market_order("BTCUSDT", "BUY", 0.001)

    @pytest.mark.asyncio
    async def test_get_account_balance_opens_circuit_after_failures(self, client):
        """get_account_balance 연속 실패 시 circuit이 OPEN."""
        client._client.futures_account = AsyncMock(
            side_effect=ConnectionError("connection failed")
        )

        for _ in range(5):
            with pytest.raises(ConnectionError):
                await client.get_account_balance()

        with pytest.raises(CircuitBreakerOpen):
            await client.get_account_balance()

    @pytest.mark.asyncio
    async def test_create_limit_order_opens_circuit_after_failures(self, client):
        """create_limit_order 연속 실패 시 circuit이 OPEN."""
        client._client.futures_create_order = AsyncMock(
            side_effect=TimeoutError("timeout")
        )

        for _ in range(5):
            with pytest.raises(TimeoutError):
                await client.create_limit_order("BTCUSDT", "BUY", 0.001, 50000.0)

        with pytest.raises(CircuitBreakerOpen):
            await client.create_limit_order("BTCUSDT", "BUY", 0.001, 50000.0)

    @pytest.mark.asyncio
    async def test_set_leverage_opens_circuit_after_failures(self, client):
        """set_leverage 연속 실패 시 circuit이 OPEN."""
        client._client.futures_change_leverage = AsyncMock(
            side_effect=ConnectionError("connection failed")
        )

        for _ in range(5):
            with pytest.raises(ConnectionError):
                await client.set_leverage("BTCUSDT", 10)

        with pytest.raises(CircuitBreakerOpen):
            await client.set_leverage("BTCUSDT", 10)

    @pytest.mark.asyncio
    async def test_get_ticker_24h_opens_circuit_after_failures(self, client):
        """get_ticker_24h 연속 실패 시 circuit이 OPEN."""
        client._client.futures_ticker = AsyncMock(
            side_effect=TimeoutError("timeout")
        )

        for _ in range(5):
            with pytest.raises(TimeoutError):
                await client.get_ticker_24h("BTCUSDT")

        with pytest.raises(CircuitBreakerOpen):
            await client.get_ticker_24h("BTCUSDT")

    @pytest.mark.asyncio
    async def test_successful_calls_dont_open_circuit(self, client):
        """성공적인 호출은 circuit을 열지 않음."""
        client._client.futures_symbol_ticker = AsyncMock(
            return_value={"price": "50000.0"}
        )

        for _ in range(10):
            price = await client.get_current_price("BTCUSDT")
            assert price == 50000.0

    @pytest.mark.asyncio
    async def test_circuit_shared_across_market_data_methods(self, client):
        """시장 데이터 메서드가 동일한 'binance_market_data' circuit을 공유."""
        client._client.futures_symbol_ticker = AsyncMock(
            side_effect=ConnectionError("fail")
        )
        client._client.futures_klines = AsyncMock(
            side_effect=ConnectionError("fail")
        )

        # get_current_price에서 3번 실패
        for _ in range(3):
            with pytest.raises(ConnectionError):
                await client.get_current_price("BTCUSDT")

        # get_klines에서 2번 실패 -> 총 5번 = threshold 도달
        for _ in range(2):
            with pytest.raises(ConnectionError):
                await client.get_klines("BTCUSDT")

        # 같은 market_data 카테고리 메서드는 차단됨
        with pytest.raises(CircuitBreakerOpen):
            await client.get_current_price("BTCUSDT")

    @pytest.mark.asyncio
    async def test_binance_api_exception_triggers_circuit(self, client):
        """BinanceAPIException도 circuit breaker를 트리거."""
        mock_response = type("Response", (), {"status_code": 429, "text": "Rate limit", "headers": {}})()
        exc = BinanceAPIException(
            response=mock_response,
            status_code=429,
            text="Rate limit exceeded",
        )
        client._client.futures_symbol_ticker = AsyncMock(side_effect=exc)

        for _ in range(5):
            with pytest.raises(BinanceAPIException):
                await client.get_current_price("BTCUSDT")

        with pytest.raises(CircuitBreakerOpen):
            await client.get_current_price("BTCUSDT")

    @pytest.mark.asyncio
    async def test_non_tracked_exception_does_not_trigger_circuit(self, client):
        """추적하지 않는 예외는 circuit을 트리거하지 않음."""
        client._client.futures_symbol_ticker = AsyncMock(
            side_effect=ValueError("unexpected value")
        )

        # ValueError는 circuit breaker가 추적하지 않으므로 6번째도 ValueError
        for _ in range(6):
            with pytest.raises(ValueError):
                await client.get_current_price("BTCUSDT")
