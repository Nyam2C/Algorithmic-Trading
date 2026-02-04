"""
Tests for BinanceTestnetClient

Phase 4: AsyncClient 마이그레이션 대응
"""
import pytest
from unittest.mock import AsyncMock, patch
import pandas as pd

from src.exchange.binance import BinanceTestnetClient


class TestBinanceTestnetClient:
    """BinanceTestnetClient 테스트"""

    def test_init_testnet(self):
        """테스트넷 초기화"""
        client = BinanceTestnetClient(
            api_key="test_key",
            secret_key="test_secret",
            testnet=True
        )
        assert client.testnet is True
        assert client._client is None  # connect() 전에는 None

    def test_init_mainnet(self):
        """메인넷 초기화"""
        client = BinanceTestnetClient(
            api_key="real_key",
            secret_key="real_secret",
            testnet=False
        )
        assert client.testnet is False

    @pytest.mark.asyncio
    async def test_connect(self):
        """connect() 테스트"""
        with patch("src.exchange.binance.AsyncClient") as mock_async_client:
            mock_instance = AsyncMock()
            mock_async_client.create = AsyncMock(return_value=mock_instance)

            client = BinanceTestnetClient("key", "secret", testnet=True)
            await client.connect()

            mock_async_client.create.assert_called_once_with(
                api_key="key",
                api_secret="secret",
                testnet=True,
            )
            assert client._client is not None

    @pytest.mark.asyncio
    async def test_close(self):
        """close() 테스트"""
        client = BinanceTestnetClient("key", "secret", testnet=True)
        mock_internal = AsyncMock()
        client._client = mock_internal

        await client.close()

        mock_internal.close_connection.assert_called_once()
        assert client._client is None


class TestGetCurrentPrice:
    """get_current_price 테스트"""

    @pytest.fixture
    def client(self):
        """테스트용 클라이언트"""
        client = BinanceTestnetClient("key", "secret", testnet=True)
        mock_internal = AsyncMock()
        client._client = mock_internal
        yield client, mock_internal

    @pytest.mark.asyncio
    async def test_get_current_price_success(self, client):
        """현재가 조회 성공"""
        client_instance, mock_internal = client
        mock_internal.futures_symbol_ticker = AsyncMock(return_value={"price": "105000.50"})

        price = await client_instance.get_current_price("BTCUSDT")

        assert price == 105000.50
        mock_internal.futures_symbol_ticker.assert_called_once_with(symbol="BTCUSDT")

    @pytest.mark.asyncio
    async def test_get_current_price_exception(self, client):
        """현재가 조회 실패 - 예외 발생"""
        client_instance, mock_internal = client
        mock_internal.futures_symbol_ticker = AsyncMock(side_effect=ConnectionError("API Error"))

        with pytest.raises(ConnectionError):
            await client_instance.get_current_price("BTCUSDT")


class TestGetKlines:
    """get_klines 테스트"""

    @pytest.fixture
    def client(self):
        """테스트용 클라이언트"""
        client = BinanceTestnetClient("key", "secret", testnet=True)
        mock_internal = AsyncMock()
        client._client = mock_internal
        yield client, mock_internal

    @pytest.mark.asyncio
    async def test_get_klines_success(self, client):
        """캔들 데이터 조회 성공"""
        client_instance, mock_internal = client
        mock_klines = [
            [
                1704067200000,  # timestamp
                "100000.0",     # open
                "101000.0",     # high
                "99000.0",      # low
                "100500.0",     # close
                "1000.5",       # volume
                1704070800000,  # close_time
                "100500000.0",  # quote_volume
                100,            # trades
                "500.25",       # taker_buy_base
                "50250000.0",   # taker_buy_quote
                "0"             # ignore
            ],
            [
                1704070800000,
                "100500.0",
                "102000.0",
                "100000.0",
                "101500.0",
                "1200.3",
                1704074400000,
                "121500000.0",
                120,
                "600.15",
                "60915000.0",
                "0"
            ]
        ]
        mock_internal.futures_klines = AsyncMock(return_value=mock_klines)

        df = await client_instance.get_klines("BTCUSDT", limit=2)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
        assert df["close"].iloc[0] == 100500.0
        assert df["volume"].iloc[1] == 1200.3


class TestSetLeverage:
    """set_leverage 테스트"""

    @pytest.fixture
    def client(self):
        client = BinanceTestnetClient("key", "secret", testnet=True)
        mock_internal = AsyncMock()
        client._client = mock_internal
        yield client, mock_internal

    @pytest.mark.asyncio
    async def test_set_leverage_success(self, client):
        """레버리지 설정 성공"""
        client_instance, mock_internal = client
        mock_internal.futures_change_leverage = AsyncMock(return_value={
            "leverage": 15,
            "symbol": "BTCUSDT"
        })

        result = await client_instance.set_leverage("BTCUSDT", 15)

        assert result["leverage"] == 15
        mock_internal.futures_change_leverage.assert_called_once_with(
            symbol="BTCUSDT", leverage=15
        )


class TestCreateOrders:
    """주문 생성 테스트"""

    @pytest.fixture
    def client(self):
        client = BinanceTestnetClient("key", "secret", testnet=True)
        mock_internal = AsyncMock()
        client._client = mock_internal
        yield client, mock_internal

    @pytest.mark.asyncio
    async def test_create_market_order_success(self, client):
        """시장가 주문 성공"""
        client_instance, mock_internal = client
        mock_internal.futures_create_order = AsyncMock(return_value={
            "orderId": 123456,
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "MARKET",
            "quantity": "0.01",
            "status": "FILLED"
        })

        result = await client_instance.create_market_order("BTCUSDT", "BUY", 0.01)

        assert result["orderId"] == 123456
        assert result["status"] == "FILLED"

    @pytest.mark.asyncio
    async def test_create_limit_order_success(self, client):
        """지정가 주문 성공"""
        client_instance, mock_internal = client
        mock_internal.futures_create_order = AsyncMock(return_value={
            "orderId": 123457,
            "symbol": "BTCUSDT",
            "side": "SELL",
            "type": "LIMIT",
            "price": "105000.0",
            "quantity": "0.01",
            "status": "NEW"
        })

        result = await client_instance.create_limit_order("BTCUSDT", "SELL", 0.01, 105000.0)

        assert result["orderId"] == 123457
        assert result["status"] == "NEW"


class TestGetPosition:
    """포지션 조회 테스트"""

    @pytest.fixture
    def client(self):
        client = BinanceTestnetClient("key", "secret", testnet=True)
        mock_internal = AsyncMock()
        client._client = mock_internal
        yield client, mock_internal

    @pytest.mark.asyncio
    async def test_get_position_long(self, client):
        """롱 포지션 조회"""
        client_instance, mock_internal = client
        mock_internal.futures_position_information = AsyncMock(return_value=[
            {
                "symbol": "BTCUSDT",
                "positionAmt": "0.01",
                "entryPrice": "100000.0",
                "unRealizedProfit": "50.0",
                "leverage": "15"
            }
        ])

        position = await client_instance.get_position("BTCUSDT")

        assert position is not None
        assert position["side"] == "LONG"
        assert position["position_amt"] == 0.01
        assert position["entry_price"] == 100000.0

    @pytest.mark.asyncio
    async def test_get_position_short(self, client):
        """숏 포지션 조회"""
        client_instance, mock_internal = client
        mock_internal.futures_position_information = AsyncMock(return_value=[
            {
                "symbol": "BTCUSDT",
                "positionAmt": "-0.01",
                "entryPrice": "100000.0",
                "unRealizedProfit": "-30.0",
                "leverage": "15"
            }
        ])

        position = await client_instance.get_position("BTCUSDT")

        assert position is not None
        assert position["side"] == "SHORT"
        assert position["position_amt"] == -0.01

    @pytest.mark.asyncio
    async def test_get_position_none(self, client):
        """포지션 없음"""
        client_instance, mock_internal = client
        mock_internal.futures_position_information = AsyncMock(return_value=[
            {
                "symbol": "BTCUSDT",
                "positionAmt": "0.0",
                "entryPrice": "0.0",
                "unRealizedProfit": "0.0"
            }
        ])

        position = await client_instance.get_position("BTCUSDT")

        assert position is None


class TestGetAllPositions:
    """전체 포지션 조회 테스트"""

    @pytest.fixture
    def client(self):
        client = BinanceTestnetClient("key", "secret", testnet=True)
        mock_internal = AsyncMock()
        client._client = mock_internal
        yield client, mock_internal

    @pytest.mark.asyncio
    async def test_get_all_positions_multiple(self, client):
        """여러 포지션 조회"""
        client_instance, mock_internal = client
        mock_internal.futures_position_information = AsyncMock(return_value=[
            {
                "symbol": "BTCUSDT",
                "positionAmt": "0.01",
                "entryPrice": "100000.0",
                "unRealizedProfit": "50.0",
                "leverage": "15",
                "markPrice": "100500.0",
                "marginType": "cross",
                "liquidationPrice": "80000.0"
            },
            {
                "symbol": "ETHUSDT",
                "positionAmt": "-0.1",
                "entryPrice": "3500.0",
                "unRealizedProfit": "-10.0",
                "leverage": "10",
                "markPrice": "3510.0",
                "marginType": "cross",
                "liquidationPrice": "4000.0"
            },
            {
                "symbol": "SOLUSDT",
                "positionAmt": "0.0",
                "entryPrice": "0.0",
                "unRealizedProfit": "0.0",
                "leverage": "20",
                "markPrice": "150.0",
                "marginType": "cross",
                "liquidationPrice": "0.0"
            }
        ])
        mock_internal.futures_symbol_ticker = AsyncMock(side_effect=[
            {"price": "100500.0"},
            {"price": "3510.0"}
        ])

        positions = await client_instance.get_all_positions()

        assert len(positions) == 2
        assert positions[0]["symbol"] == "BTCUSDT"
        assert positions[0]["side"] == "LONG"
        assert positions[1]["symbol"] == "ETHUSDT"
        assert positions[1]["side"] == "SHORT"


class TestClosePosition:
    """포지션 청산 테스트"""

    @pytest.fixture
    def client(self):
        client = BinanceTestnetClient("key", "secret", testnet=True)
        mock_internal = AsyncMock()
        client._client = mock_internal
        yield client, mock_internal

    @pytest.mark.asyncio
    async def test_close_long_position(self, client):
        """롱 포지션 청산"""
        client_instance, mock_internal = client
        mock_internal.futures_position_information = AsyncMock(return_value=[
            {
                "symbol": "BTCUSDT",
                "positionAmt": "0.01",
                "entryPrice": "100000.0",
                "unRealizedProfit": "50.0",
                "leverage": "15"
            }
        ])
        mock_internal.futures_create_order = AsyncMock(return_value={
            "orderId": 123456,
            "status": "FILLED"
        })

        result = await client_instance.close_position("BTCUSDT")

        assert result is not None
        mock_internal.futures_create_order.assert_called()

    @pytest.mark.asyncio
    async def test_close_no_position(self, client):
        """포지션 없으면 None 반환"""
        client_instance, mock_internal = client
        mock_internal.futures_position_information = AsyncMock(return_value=[
            {
                "symbol": "BTCUSDT",
                "positionAmt": "0.0",
                "entryPrice": "0.0",
                "unRealizedProfit": "0.0"
            }
        ])

        result = await client_instance.close_position("BTCUSDT")

        assert result is None


class TestMarketSentiment:
    """시장 심리 조회 테스트"""

    @pytest.fixture
    def client(self):
        client = BinanceTestnetClient("key", "secret", testnet=True)
        mock_internal = AsyncMock()
        client._client = mock_internal
        yield client, mock_internal

    @pytest.mark.asyncio
    async def test_get_funding_rate(self, client):
        """펀딩비 조회"""
        client_instance, mock_internal = client
        mock_internal.futures_funding_rate = AsyncMock(return_value=[
            {
                "fundingRate": "0.0001",
                "fundingTime": 1704067200000
            }
        ])

        result = await client_instance.get_funding_rate("BTCUSDT")

        assert result["funding_rate"] == 0.01  # 0.0001 * 100

    @pytest.mark.asyncio
    async def test_get_long_short_ratio(self, client):
        """롱숏 비율 조회"""
        client_instance, mock_internal = client
        mock_internal.futures_top_longshort_position_ratio = AsyncMock(return_value=[
            {
                "longAccount": "0.55",
                "shortAccount": "0.45",
                "longShortRatio": "1.22"
            }
        ])

        result = await client_instance.get_long_short_ratio("BTCUSDT")

        assert result["long_ratio"] == 0.55
        assert result["short_ratio"] == 0.45

    @pytest.mark.asyncio
    async def test_get_open_interest(self, client):
        """미결제약정 조회"""
        client_instance, mock_internal = client
        mock_internal.futures_open_interest = AsyncMock(return_value={
            "openInterest": "12345.67"
        })

        result = await client_instance.get_open_interest("BTCUSDT")

        assert result["open_interest"] == 12345.67


class TestGetAccountBalance:
    """계정 잔액 조회 테스트"""

    @pytest.fixture
    def client(self):
        client = BinanceTestnetClient("key", "secret", testnet=True)
        mock_internal = AsyncMock()
        client._client = mock_internal
        yield client, mock_internal

    @pytest.mark.asyncio
    async def test_get_account_balance_success(self, client):
        """USDT 잔액 조회 성공"""
        client_instance, mock_internal = client
        mock_internal.futures_account = AsyncMock(return_value={
            "assets": [
                {
                    "asset": "USDT",
                    "walletBalance": "10000.50",
                    "availableBalance": "9500.25",
                    "unrealizedProfit": "150.00"
                },
                {
                    "asset": "BNB",
                    "walletBalance": "1.0",
                    "availableBalance": "1.0",
                    "unrealizedProfit": "0.0"
                }
            ]
        })

        result = await client_instance.get_account_balance()

        assert result["asset"] == "USDT"
        assert result["balance"] == 10000.50
        assert result["available"] == 9500.25
        assert result["unrealized_pnl"] == 150.00

    @pytest.mark.asyncio
    async def test_get_account_balance_no_usdt(self, client):
        """USDT 잔액 없음"""
        client_instance, mock_internal = client
        mock_internal.futures_account = AsyncMock(return_value={
            "assets": [
                {
                    "asset": "BNB",
                    "walletBalance": "1.0",
                    "availableBalance": "1.0",
                    "unrealizedProfit": "0.0"
                }
            ]
        })

        result = await client_instance.get_account_balance()

        assert result["asset"] == "USDT"
        assert result["balance"] == 0.0


class TestGetTicker24h:
    """24시간 티커 조회 테스트"""

    @pytest.fixture
    def client(self):
        client = BinanceTestnetClient("key", "secret", testnet=True)
        mock_internal = AsyncMock()
        client._client = mock_internal
        yield client, mock_internal

    @pytest.mark.asyncio
    async def test_get_ticker_24h_success(self, client):
        """24시간 티커 조회 성공"""
        client_instance, mock_internal = client
        mock_internal.futures_ticker = AsyncMock(return_value={
            "highPrice": "108000.0",
            "lowPrice": "102000.0",
            "priceChangePercent": "2.5",
            "volume": "50000.0",
            "quoteVolume": "5250000000.0"
        })

        result = await client_instance.get_ticker_24h("BTCUSDT")

        assert result["high_24h"] == 108000.0
        assert result["low_24h"] == 102000.0
        assert result["change_24h"] == 2.5
        assert result["volume_24h"] == 50000.0


class TestOrderManagement:
    """주문 관리 테스트"""

    @pytest.fixture
    def client(self):
        client = BinanceTestnetClient("key", "secret", testnet=True)
        mock_internal = AsyncMock()
        client._client = mock_internal
        yield client, mock_internal

    @pytest.mark.asyncio
    async def test_get_order_status(self, client):
        """주문 상태 조회"""
        client_instance, mock_internal = client
        mock_internal.futures_get_order = AsyncMock(return_value={
            "orderId": 123456,
            "status": "FILLED",
            "executedQty": "0.01"
        })

        result = await client_instance.get_order_status("BTCUSDT", 123456)

        assert result["status"] == "FILLED"
        mock_internal.futures_get_order.assert_called_once_with(
            symbol="BTCUSDT", orderId=123456
        )

    @pytest.mark.asyncio
    async def test_cancel_order(self, client):
        """주문 취소"""
        client_instance, mock_internal = client
        mock_internal.futures_cancel_order = AsyncMock(return_value={
            "orderId": 123456,
            "status": "CANCELED"
        })

        result = await client_instance.cancel_order("BTCUSDT", 123456)

        assert result["status"] == "CANCELED"
