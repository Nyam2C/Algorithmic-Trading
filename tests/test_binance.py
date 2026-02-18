"""
Tests for BinanceTestnetClient

Phase 4: AsyncClient 마이그레이션 대응
"""
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

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
                1704067200000,
                "100000.0",
                "101000.0",
                "99000.0",
                "100500.0",
                "1000.5",
                1704067500000,
                "100000.0",
                100,
                "500.0",
                "50000.0",
                "0"
            ],
            [
                1704067500000,
                "100000.0",
                "101000.0",
                "99000.0",
                "100600.0",
                "1000.5",
                1704067800000,
                "100000.0",
                100,
                "500.0",
                "50000.0",
                "0"
            ],
            [
                1704067800000,
                "100000.0",
                "101000.0",
                "99000.0",
                "100700.0",
                "1000.5",
                1704068100000,
                "100000.0",
                100,
                "500.0",
                "50000.0",
                "0"
            ],
            [
                1704068100000,
                "100000.0",
                "101000.0",
                "99000.0",
                "100800.0",
                "1000.5",
                1704068400000,
                "100000.0",
                100,
                "500.0",
                "50000.0",
                "0"
            ],
            [
                1704068400000,
                "100000.0",
                "101000.0",
                "99000.0",
                "100900.0",
                "1000.5",
                1704068700000,
                "100000.0",
                100,
                "500.0",
                "50000.0",
                "0"
            ],
            [
                1704068700000,
                "100000.0",
                "101000.0",
                "99000.0",
                "101000.0",
                "1000.5",
                1704069000000,
                "100000.0",
                100,
                "500.0",
                "50000.0",
                "0"
            ]
        ]
        mock_internal.futures_klines = AsyncMock(return_value=mock_klines)

        df = await client_instance.get_klines("BTCUSDT", limit=6)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 6
        assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
        assert df["close"].iloc[0] == 100500.0


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


# =============================================================================
# Exchange 모듈 커버리지 향상 테스트 (from test_exchange_coverage.py)
# =============================================================================


class TestBinanceClientProperty:
    """client 프로퍼티 테스트 - 연결 확인"""

    def test_client_property_raises_when_not_connected(self):
        """연결 안 된 상태에서 client 프로퍼티 접근 시 RuntimeError"""
        client = BinanceTestnetClient("key", "secret", testnet=True)
        assert client._client is None

        with pytest.raises(RuntimeError, match="연결되지 않았습니다"):
            _ = client.client

    def test_client_property_returns_client(self):
        """연결된 상태에서 client 프로퍼티 반환"""
        client = BinanceTestnetClient("key", "secret", testnet=True)
        mock_internal = AsyncMock()
        client._client = mock_internal

        result = client.client
        assert result is mock_internal


class TestBinanceConnect:
    """connect() 추가 테스트"""

    @pytest.mark.asyncio
    async def test_connect_already_connected(self):
        """이미 연결된 경우 재연결하지 않음"""
        client = BinanceTestnetClient("key", "secret", testnet=True)
        mock_internal = AsyncMock()
        client._client = mock_internal

        await client.connect()
        # _client가 변경되지 않음
        assert client._client is mock_internal

    @pytest.mark.asyncio
    async def test_connect_mainnet(self):
        """메인넷 연결 - 경고 로그"""
        with patch("src.exchange.binance.AsyncClient") as mock_async_client:
            mock_instance = AsyncMock()
            mock_async_client.create = AsyncMock(return_value=mock_instance)

            client = BinanceTestnetClient("key", "secret", testnet=False)
            await client.connect()

            assert client._client is not None
            mock_async_client.create.assert_called_once_with(
                api_key="key",
                api_secret="secret",
                testnet=False,
            )


class TestBinanceClose:
    """close() 추가 테스트"""

    @pytest.mark.asyncio
    async def test_close_no_client(self):
        """_client가 None일 때 close 호출"""
        client = BinanceTestnetClient("key", "secret", testnet=True)
        assert client._client is None
        await client.close()  # 에러 없어야 함
        assert client._client is None


class TestGetCurrentPriceError:
    """get_current_price 에러 핸들링"""

    @pytest.fixture
    def client_fixture(self):
        client = BinanceTestnetClient("key", "secret", testnet=True)
        mock_internal = AsyncMock()
        client._client = mock_internal
        return client, mock_internal

    @pytest.mark.asyncio
    async def test_get_current_price_generic_exception(self, client_fixture):
        """일반 예외 발생 시 re-raise"""
        client_instance, mock_internal = client_fixture
        mock_internal.futures_symbol_ticker = AsyncMock(
            side_effect=Exception("Unknown error")
        )

        with pytest.raises(Exception, match="Unknown error"):
            await client_instance.get_current_price("BTCUSDT")


class TestGetKlinesError:
    """get_klines 에러 핸들링"""

    @pytest.fixture
    def client_fixture(self):
        client = BinanceTestnetClient("key", "secret", testnet=True)
        mock_internal = AsyncMock()
        client._client = mock_internal
        return client, mock_internal

    @pytest.mark.asyncio
    async def test_get_klines_exception(self, client_fixture):
        """캔들 데이터 조회 실패"""
        client_instance, mock_internal = client_fixture
        mock_internal.futures_klines = AsyncMock(
            side_effect=Exception("Klines error")
        )

        with pytest.raises(Exception, match="Klines error"):
            await client_instance.get_klines("BTCUSDT")




class TestGetKlinesNanValidation:
    """get_klines NaN 데이터 검증 테스트"""

    @pytest.fixture
    def client(self):
        client = BinanceTestnetClient("key", "secret", testnet=True)
        mock_internal = AsyncMock()
        client._client = mock_internal
        yield client, mock_internal

    @pytest.mark.asyncio
    async def test_get_klines_with_nan_data_forward_filled(self, client):
        """NaN 포함 캔들 데이터가 forward-fill로 처리됨"""
        client_instance, mock_internal = client
        # 6 candles, one with NaN close
        base_ts = 1704067200000
        interval_ms = 300000
        mock_klines = []
        for i in range(6):
            ts = base_ts + i * interval_ms
            close_ts = ts + interval_ms
            close_val = "100500.0" if i != 2 else None  # 3rd candle has NaN close
            mock_klines.append([
                ts, "100000.0", "101000.0", "99000.0",
                close_val, "1000.5", close_ts,
                "100000.0", 100, "500.0", "50000.0", "0"
            ])
        mock_internal.futures_klines = AsyncMock(return_value=mock_klines)

        df = await client_instance.get_klines("BTCUSDT", limit=6)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 6
        # NaN should be forward-filled
        assert not df["close"].isna().any()


class TestGetTicker24hError:
    """get_ticker_24h 에러 핸들링"""

    @pytest.fixture
    def client_fixture(self):
        client = BinanceTestnetClient("key", "secret", testnet=True)
        mock_internal = AsyncMock()
        client._client = mock_internal
        return client, mock_internal

    @pytest.mark.asyncio
    async def test_get_ticker_24h_exception(self, client_fixture):
        """24시간 티커 조회 실패"""
        client_instance, mock_internal = client_fixture
        mock_internal.futures_ticker = AsyncMock(
            side_effect=Exception("Ticker error")
        )

        with pytest.raises(Exception, match="Ticker error"):
            await client_instance.get_ticker_24h("BTCUSDT")


class TestSetLeverageError:
    """set_leverage 에러 핸들링"""

    @pytest.fixture
    def client_fixture(self):
        client = BinanceTestnetClient("key", "secret", testnet=True)
        mock_internal = AsyncMock()
        client._client = mock_internal
        return client, mock_internal

    @pytest.mark.asyncio
    async def test_set_leverage_exception(self, client_fixture):
        """레버리지 설정 실패"""
        client_instance, mock_internal = client_fixture
        mock_internal.futures_change_leverage = AsyncMock(
            side_effect=Exception("Leverage error")
        )

        with pytest.raises(Exception, match="Leverage error"):
            await client_instance.set_leverage("BTCUSDT", 20)


class TestCreateOrderErrors:
    """주문 생성 에러 핸들링"""

    @pytest.fixture
    def client_fixture(self):
        client = BinanceTestnetClient("key", "secret", testnet=True)
        mock_internal = AsyncMock()
        client._client = mock_internal
        return client, mock_internal

    @pytest.mark.asyncio
    async def test_create_market_order_exception(self, client_fixture):
        """시장가 주문 실패"""
        client_instance, mock_internal = client_fixture
        mock_internal.futures_create_order = AsyncMock(
            side_effect=Exception("Order error")
        )

        with pytest.raises(Exception, match="Order error"):
            await client_instance.create_market_order("BTCUSDT", "BUY", 0.01)

    @pytest.mark.asyncio
    async def test_create_limit_order_exception(self, client_fixture):
        """지정가 주문 실패"""
        client_instance, mock_internal = client_fixture
        mock_internal.futures_create_order = AsyncMock(
            side_effect=Exception("Limit order error")
        )

        with pytest.raises(Exception, match="Limit order error"):
            await client_instance.create_limit_order("BTCUSDT", "SELL", 0.01, 100000.0)


class TestOrderManagementErrors:
    """주문 관리 에러 핸들링"""

    @pytest.fixture
    def client_fixture(self):
        client = BinanceTestnetClient("key", "secret", testnet=True)
        mock_internal = AsyncMock()
        client._client = mock_internal
        return client, mock_internal

    @pytest.mark.asyncio
    async def test_get_order_status_exception(self, client_fixture):
        """주문 상태 조회 실패"""
        client_instance, mock_internal = client_fixture
        mock_internal.futures_get_order = AsyncMock(
            side_effect=Exception("Order status error")
        )

        with pytest.raises(Exception, match="Order status error"):
            await client_instance.get_order_status("BTCUSDT", 12345)

    @pytest.mark.asyncio
    async def test_cancel_order_exception(self, client_fixture):
        """주문 취소 실패"""
        client_instance, mock_internal = client_fixture
        mock_internal.futures_cancel_order = AsyncMock(
            side_effect=Exception("Cancel error")
        )

        with pytest.raises(Exception, match="Cancel error"):
            await client_instance.cancel_order("BTCUSDT", 12345)


class TestGetPositionError:
    """get_position 에러 핸들링"""

    @pytest.fixture
    def client_fixture(self):
        client = BinanceTestnetClient("key", "secret", testnet=True)
        mock_internal = AsyncMock()
        client._client = mock_internal
        return client, mock_internal

    @pytest.mark.asyncio
    async def test_get_position_exception(self, client_fixture):
        """포지션 조회 실패"""
        client_instance, mock_internal = client_fixture
        mock_internal.futures_position_information = AsyncMock(
            side_effect=Exception("Position error")
        )

        with pytest.raises(Exception, match="Position error"):
            await client_instance.get_position("BTCUSDT")


class TestGetAllPositionsEdgeCases:
    """get_all_positions 추가 테스트"""

    @pytest.fixture
    def client_fixture(self):
        client = BinanceTestnetClient("key", "secret", testnet=True)
        mock_internal = AsyncMock()
        client._client = mock_internal
        return client, mock_internal

    @pytest.mark.asyncio
    async def test_get_all_positions_empty(self, client_fixture):
        """포지션이 없을 때 빈 리스트 반환"""
        client_instance, mock_internal = client_fixture
        mock_internal.futures_position_information = AsyncMock(return_value=[
            {
                "symbol": "BTCUSDT",
                "positionAmt": "0.0",
                "entryPrice": "0.0",
                "unRealizedProfit": "0.0",
                "leverage": "15",
                "markPrice": "100000.0",
                "marginType": "cross",
                "liquidationPrice": "0.0",
            }
        ])

        positions = await client_instance.get_all_positions()
        assert len(positions) == 0

    @pytest.mark.asyncio
    async def test_get_all_positions_exception(self, client_fixture):
        """전체 포지션 조회 예외 시 예외 전파 (P1: 빈 리스트와 구분)"""
        client_instance, mock_internal = client_fixture
        mock_internal.futures_position_information = AsyncMock(
            side_effect=Exception("API error")
        )

        with pytest.raises(Exception, match="API error"):
            await client_instance.get_all_positions()

    @pytest.mark.asyncio
    async def test_get_all_positions_ticker_fallback(self, client_fixture):
        """현재가 조회 실패 시 markPrice 사용"""
        client_instance, mock_internal = client_fixture
        mock_internal.futures_position_information = AsyncMock(return_value=[
            {
                "symbol": "BTCUSDT",
                "positionAmt": "0.01",
                "entryPrice": "100000.0",
                "unRealizedProfit": "50.0",
                "leverage": "15",
                "markPrice": "100500.0",
                "marginType": "cross",
                "liquidationPrice": "80000.0",
            }
        ])
        # futures_symbol_ticker 예외 -> markPrice 사용
        mock_internal.futures_symbol_ticker = AsyncMock(
            side_effect=Exception("Ticker failed")
        )

        positions = await client_instance.get_all_positions()
        assert len(positions) == 1
        assert positions[0]["current_price"] == 100500.0  # markPrice 사용

    @pytest.mark.asyncio
    async def test_get_all_positions_short_pnl_pct(self, client_fixture):
        """숏 포지션의 PnL % 계산"""
        client_instance, mock_internal = client_fixture
        mock_internal.futures_position_information = AsyncMock(return_value=[
            {
                "symbol": "BTCUSDT",
                "positionAmt": "-0.01",
                "entryPrice": "100000.0",
                "unRealizedProfit": "50.0",
                "leverage": "10",
                "markPrice": "99500.0",
                "marginType": "cross",
                "liquidationPrice": "120000.0",
            }
        ])
        mock_internal.futures_symbol_ticker = AsyncMock(
            return_value={"price": "99500.0"}
        )

        positions = await client_instance.get_all_positions()
        assert len(positions) == 1
        assert positions[0]["side"] == "SHORT"
        # PnL % = ((100000 - 99500) / 100000) * 100 * 10 = 5.0
        assert positions[0]["pnl_pct"] == pytest.approx(5.0, rel=0.01)

    @pytest.mark.asyncio
    async def test_get_all_positions_zero_entry_price(self, client_fixture):
        """entry_price가 0인 경우 pnl_pct는 0"""
        client_instance, mock_internal = client_fixture
        mock_internal.futures_position_information = AsyncMock(return_value=[
            {
                "symbol": "BTCUSDT",
                "positionAmt": "0.01",
                "entryPrice": "0.0",  # 0인 경우 (비정상 데이터)
                "unRealizedProfit": "0.0",
                "leverage": "10",
                "markPrice": "100000.0",
                "marginType": "cross",
                "liquidationPrice": "0.0",
            }
        ])
        mock_internal.futures_symbol_ticker = AsyncMock(
            return_value={"price": "100000.0"}
        )

        positions = await client_instance.get_all_positions()
        # positionAmt != 0 이지만 entryPrice == 0 -> pnl_pct = 0
        assert len(positions) == 1
        assert positions[0]["pnl_pct"] == 0


class TestClosePositionError:
    """close_position 에러 핸들링"""

    @pytest.fixture
    def client_fixture(self):
        client = BinanceTestnetClient("key", "secret", testnet=True)
        mock_internal = AsyncMock()
        client._client = mock_internal
        return client, mock_internal

    @pytest.mark.asyncio
    async def test_close_position_exception(self, client_fixture):
        """포지션 청산 실패"""
        client_instance, mock_internal = client_fixture

        # get_position이 포지션을 반환하지만 주문이 실패
        mock_internal.futures_position_information = AsyncMock(return_value=[
            {
                "symbol": "BTCUSDT",
                "positionAmt": "0.01",
                "entryPrice": "100000.0",
                "unRealizedProfit": "50.0",
                "leverage": "15",
            }
        ])
        mock_internal.futures_create_order = AsyncMock(
            side_effect=Exception("Order failed")
        )

        with pytest.raises(Exception, match="Order failed"):
            await client_instance.close_position("BTCUSDT")

    @pytest.mark.asyncio
    async def test_close_short_position(self, client_fixture):
        """숏 포지션 청산 (BUY 주문)"""
        client_instance, mock_internal = client_fixture

        mock_internal.futures_position_information = AsyncMock(return_value=[
            {
                "symbol": "BTCUSDT",
                "positionAmt": "-0.01",
                "entryPrice": "100000.0",
                "unRealizedProfit": "50.0",
                "leverage": "15",
            }
        ])
        mock_internal.futures_create_order = AsyncMock(return_value={
            "orderId": 789,
            "status": "FILLED",
        })

        result = await client_instance.close_position("BTCUSDT")
        assert result is not None
        assert result["orderId"] == 789
        # 숏 포지션이므로 BUY 주문
        call_args = mock_internal.futures_create_order.call_args
        assert call_args[1]["side"] == "BUY"


class TestFundingRateEdgeCases:
    """펀딩비 조회 엣지 케이스"""

    @pytest.fixture
    def client_fixture(self):
        client = BinanceTestnetClient("key", "secret", testnet=True)
        mock_internal = AsyncMock()
        client._client = mock_internal
        return client, mock_internal

    @pytest.mark.asyncio
    async def test_funding_rate_empty_response(self, client_fixture):
        """펀딩비 데이터가 빈 경우"""
        client_instance, mock_internal = client_fixture
        mock_internal.futures_funding_rate = AsyncMock(return_value=[])

        result = await client_instance.get_funding_rate("BTCUSDT")
        assert result["funding_rate"] == 0.0
        assert result["funding_time"] is None

    @pytest.mark.asyncio
    async def test_funding_rate_exception(self, client_fixture):
        """펀딩비 조회 예외"""
        client_instance, mock_internal = client_fixture
        mock_internal.futures_funding_rate = AsyncMock(
            side_effect=Exception("Funding error")
        )

        result = await client_instance.get_funding_rate("BTCUSDT")
        assert result["funding_rate"] == 0.0
        assert result["funding_time"] is None


class TestLongShortRatioEdgeCases:
    """롱숏비율 조회 엣지 케이스"""

    @pytest.fixture
    def client_fixture(self):
        client = BinanceTestnetClient("key", "secret", testnet=True)
        mock_internal = AsyncMock()
        client._client = mock_internal
        return client, mock_internal

    @pytest.mark.asyncio
    async def test_long_short_ratio_empty_response(self, client_fixture):
        """롱숏비율 데이터가 빈 경우"""
        client_instance, mock_internal = client_fixture
        mock_internal.futures_top_longshort_position_ratio = AsyncMock(return_value=[])

        result = await client_instance.get_long_short_ratio("BTCUSDT")
        assert result["long_ratio"] == 0.5
        assert result["short_ratio"] == 0.5
        assert result["long_short_ratio"] == 1.0

    @pytest.mark.asyncio
    async def test_long_short_ratio_exception(self, client_fixture):
        """롱숏비율 조회 예외"""
        client_instance, mock_internal = client_fixture
        mock_internal.futures_top_longshort_position_ratio = AsyncMock(
            side_effect=Exception("LS ratio error")
        )

        result = await client_instance.get_long_short_ratio("BTCUSDT")
        assert result["long_ratio"] == 0.5
        assert result["short_ratio"] == 0.5


class TestOpenInterestEdgeCases:
    """미결제약정 조회 엣지 케이스"""

    @pytest.fixture
    def client_fixture(self):
        client = BinanceTestnetClient("key", "secret", testnet=True)
        mock_internal = AsyncMock()
        client._client = mock_internal
        return client, mock_internal

    @pytest.mark.asyncio
    async def test_open_interest_exception(self, client_fixture):
        """미결제약정 조회 예외"""
        client_instance, mock_internal = client_fixture
        mock_internal.futures_open_interest = AsyncMock(
            side_effect=Exception("OI error")
        )

        result = await client_instance.get_open_interest("BTCUSDT")
        assert result["open_interest"] == 0.0
        assert result["symbol"] == "BTCUSDT"


class TestGetMarketSentiment:
    """시장 심리 통합 조회 테스트"""

    @pytest.fixture
    def client_fixture(self):
        client = BinanceTestnetClient("key", "secret", testnet=True)
        mock_internal = AsyncMock()
        client._client = mock_internal
        return client, mock_internal

    @pytest.mark.asyncio
    async def test_get_market_sentiment_success(self, client_fixture):
        """시장 심리 통합 조회 성공"""
        client_instance, mock_internal = client_fixture

        mock_internal.futures_funding_rate = AsyncMock(return_value=[
            {"fundingRate": "0.0002", "fundingTime": 1704067200000}
        ])
        mock_internal.futures_top_longshort_position_ratio = AsyncMock(return_value=[
            {"longAccount": "0.60", "shortAccount": "0.40", "longShortRatio": "1.50"}
        ])
        mock_internal.futures_open_interest = AsyncMock(return_value={
            "openInterest": "25000.0"
        })
        mock_internal.futures_mark_price = AsyncMock(return_value={
            "markPrice": "50100.0", "indexPrice": "50000.0"
        })
        mock_internal.futures_global_longshort_ratio = AsyncMock(return_value=[
            {"longAccount": "0.55", "shortAccount": "0.45", "longShortRatio": "1.22"}
        ])
        mock_internal.futures_taker_longshort_ratio = AsyncMock(return_value=[
            {"buySellRatio": "1.25", "buyVol": "1000.0", "sellVol": "800.0"}
        ])

        result = await client_instance.get_market_sentiment("BTCUSDT")

        assert result["funding_rate"] == pytest.approx(0.02, rel=0.01)  # 0.0002 * 100
        assert result["long_ratio"] == 0.60
        assert result["short_ratio"] == 0.40
        assert result["long_short_ratio"] == 1.50
        assert result["open_interest"] == 25000.0
        assert result["basis"] == pytest.approx(0.002, rel=0.01)
        assert result["global_long_ratio"] == 0.55
        assert result["global_short_ratio"] == 0.45
        assert result["taker_buy_sell_ratio"] == 1.25

    @pytest.mark.asyncio
    async def test_get_market_sentiment_partial_failure(self, client_fixture):
        """일부 데이터 조회 실패 시에도 결과 반환"""
        client_instance, mock_internal = client_fixture

        # 펀딩비 실패
        mock_internal.futures_funding_rate = AsyncMock(
            side_effect=Exception("Funding error")
        )
        # 롱숏비율 성공
        mock_internal.futures_top_longshort_position_ratio = AsyncMock(return_value=[
            {"longAccount": "0.55", "shortAccount": "0.45", "longShortRatio": "1.22"}
        ])
        # 미결제약정 성공
        mock_internal.futures_open_interest = AsyncMock(return_value={
            "openInterest": "20000.0"
        })
        mock_internal.futures_mark_price = AsyncMock(return_value={
            "markPrice": "50000.0", "indexPrice": "50000.0"
        })
        mock_internal.futures_global_longshort_ratio = AsyncMock(return_value=[
            {"longAccount": "0.50", "shortAccount": "0.50", "longShortRatio": "1.0"}
        ])
        mock_internal.futures_taker_longshort_ratio = AsyncMock(return_value=[
            {"buySellRatio": "1.0", "buyVol": "0.0", "sellVol": "0.0"}
        ])

        result = await client_instance.get_market_sentiment("BTCUSDT")

        # 펀딩비 기본값 사용
        assert result["funding_rate"] == 0.0
        assert result["long_ratio"] == 0.55
        assert result["open_interest"] == 20000.0


class TestGetPremiumIndex:
    """프리미엄 인덱스 조회 테스트"""

    @pytest.fixture
    def client_fixture(self):
        client = BinanceTestnetClient("key", "secret", testnet=True)
        mock_internal = AsyncMock()
        client._client = mock_internal
        return client, mock_internal

    @pytest.mark.asyncio
    async def test_get_premium_index_success(self, client_fixture):
        """프리미엄 인덱스 정상 조회"""
        client_instance, mock_internal = client_fixture
        mock_internal.futures_mark_price = AsyncMock(return_value={
            "markPrice": "50100.0",
            "indexPrice": "50000.0",
        })
        result = await client_instance.get_premium_index("BTCUSDT")
        assert result["mark_price"] == 50100.0
        assert result["index_price"] == 50000.0
        assert result["basis"] == pytest.approx(0.002, rel=0.01)
        assert result["is_error"] is False

    @pytest.mark.asyncio
    async def test_get_premium_index_zero_index(self, client_fixture):
        """index_price=0 → basis=0"""
        client_instance, mock_internal = client_fixture
        mock_internal.futures_mark_price = AsyncMock(return_value={
            "markPrice": "50000.0",
            "indexPrice": "0",
        })
        result = await client_instance.get_premium_index("BTCUSDT")
        assert result["basis"] == 0.0
        assert result["is_error"] is False

    @pytest.mark.asyncio
    async def test_get_premium_index_exception(self, client_fixture):
        """API 예외 → 기본값"""
        client_instance, mock_internal = client_fixture
        mock_internal.futures_mark_price = AsyncMock(
            side_effect=Exception("API error")
        )
        result = await client_instance.get_premium_index("BTCUSDT")
        assert result["basis"] == 0.0
        assert result["is_error"] is True

    @pytest.mark.asyncio
    async def test_get_premium_index_negative_basis(self, client_fixture):
        """마크 가격 < 인덱스 가격 → 음수 basis"""
        client_instance, mock_internal = client_fixture
        mock_internal.futures_mark_price = AsyncMock(return_value={
            "markPrice": "49900.0",
            "indexPrice": "50000.0",
        })
        result = await client_instance.get_premium_index("BTCUSDT")
        assert result["basis"] < 0
        assert result["is_error"] is False


class TestGetGlobalLongShortRatio:
    """글로벌 롱숏 비율 조회 테스트"""

    @pytest.fixture
    def client_fixture(self):
        client = BinanceTestnetClient("key", "secret", testnet=True)
        mock_internal = AsyncMock()
        client._client = mock_internal
        return client, mock_internal

    @pytest.mark.asyncio
    async def test_get_global_ls_ratio_success(self, client_fixture):
        """글로벌 롱숏 비율 정상 조회"""
        client_instance, mock_internal = client_fixture
        mock_internal.futures_global_longshort_ratio = AsyncMock(return_value=[
            {"longAccount": "0.55", "shortAccount": "0.45", "longShortRatio": "1.22"}
        ])
        result = await client_instance.get_global_long_short_ratio("BTCUSDT")
        assert result["long_ratio"] == 0.55
        assert result["short_ratio"] == 0.45
        assert result["long_short_ratio"] == 1.22
        assert result["is_error"] is False

    @pytest.mark.asyncio
    async def test_get_global_ls_ratio_empty(self, client_fixture):
        """빈 응답 → 기본값"""
        client_instance, mock_internal = client_fixture
        mock_internal.futures_global_longshort_ratio = AsyncMock(return_value=[])
        result = await client_instance.get_global_long_short_ratio("BTCUSDT")
        assert result["long_ratio"] == 0.5
        assert result["short_ratio"] == 0.5
        assert result["is_error"] is False

    @pytest.mark.asyncio
    async def test_get_global_ls_ratio_exception(self, client_fixture):
        """API 예외 → 기본값"""
        client_instance, mock_internal = client_fixture
        mock_internal.futures_global_longshort_ratio = AsyncMock(
            side_effect=Exception("API error")
        )
        result = await client_instance.get_global_long_short_ratio("BTCUSDT")
        assert result["long_ratio"] == 0.5
        assert result["is_error"] is True

    @pytest.mark.asyncio
    async def test_get_global_ls_ratio_extreme_values(self, client_fixture):
        """극단적 롱숏 비율"""
        client_instance, mock_internal = client_fixture
        mock_internal.futures_global_longshort_ratio = AsyncMock(return_value=[
            {"longAccount": "0.90", "shortAccount": "0.10", "longShortRatio": "9.0"}
        ])
        result = await client_instance.get_global_long_short_ratio("BTCUSDT")
        assert result["long_ratio"] == 0.9
        assert result["short_ratio"] == 0.1


class TestGetTakerLongShortRatio:
    """테이커 매수/매도 비율 조회 테스트"""

    @pytest.fixture
    def client_fixture(self):
        client = BinanceTestnetClient("key", "secret", testnet=True)
        mock_internal = AsyncMock()
        client._client = mock_internal
        return client, mock_internal

    @pytest.mark.asyncio
    async def test_get_taker_ratio_success(self, client_fixture):
        """테이커 비율 정상 조회"""
        client_instance, mock_internal = client_fixture
        mock_internal.futures_taker_longshort_ratio = AsyncMock(return_value=[
            {"buySellRatio": "1.25", "buyVol": "1000.0", "sellVol": "800.0"}
        ])
        result = await client_instance.get_taker_long_short_ratio("BTCUSDT")
        assert result["buy_sell_ratio"] == 1.25
        assert result["buy_vol"] == 1000.0
        assert result["sell_vol"] == 800.0
        assert result["is_error"] is False

    @pytest.mark.asyncio
    async def test_get_taker_ratio_empty(self, client_fixture):
        """빈 응답 → 기본값"""
        client_instance, mock_internal = client_fixture
        mock_internal.futures_taker_longshort_ratio = AsyncMock(return_value=[])
        result = await client_instance.get_taker_long_short_ratio("BTCUSDT")
        assert result["buy_sell_ratio"] == 1.0
        assert result["buy_vol"] == 0.0
        assert result["is_error"] is False

    @pytest.mark.asyncio
    async def test_get_taker_ratio_exception(self, client_fixture):
        """API 예외 → 기본값"""
        client_instance, mock_internal = client_fixture
        mock_internal.futures_taker_longshort_ratio = AsyncMock(
            side_effect=Exception("API error")
        )
        result = await client_instance.get_taker_long_short_ratio("BTCUSDT")
        assert result["buy_sell_ratio"] == 1.0
        assert result["is_error"] is True

    @pytest.mark.asyncio
    async def test_get_taker_ratio_strong_buy(self, client_fixture):
        """강한 매수 우위"""
        client_instance, mock_internal = client_fixture
        mock_internal.futures_taker_longshort_ratio = AsyncMock(return_value=[
            {"buySellRatio": "2.50", "buyVol": "5000.0", "sellVol": "2000.0"}
        ])
        result = await client_instance.get_taker_long_short_ratio("BTCUSDT")
        assert result["buy_sell_ratio"] == 2.5
        assert result["is_error"] is False


class TestGetAccountBalanceError:
    """get_account_balance 에러 핸들링"""

    @pytest.fixture
    def client_fixture(self):
        client = BinanceTestnetClient("key", "secret", testnet=True)
        mock_internal = AsyncMock()
        client._client = mock_internal
        return client, mock_internal

    @pytest.mark.asyncio
    async def test_get_account_balance_exception(self, client_fixture):
        """잔액 조회 예외 시 raise"""
        client_instance, mock_internal = client_fixture
        mock_internal.futures_account = AsyncMock(
            side_effect=Exception("Account error")
        )

        with pytest.raises(Exception, match="Account error"):
            await client_instance.get_account_balance()

    @pytest.mark.asyncio
    async def test_get_account_balance_usdt_not_found(self, client_fixture):
        """USDT 잔액 미발견 시 기본값 반환"""
        client_instance, mock_internal = client_fixture
        mock_internal.futures_account = AsyncMock(return_value={
            "assets": [
                {
                    "asset": "BNB",
                    "walletBalance": "1.0",
                    "availableBalance": "1.0",
                    "unrealizedProfit": "0.0",
                }
            ]
        })

        result = await client_instance.get_account_balance()
        assert result["asset"] == "USDT"
        assert result["balance"] == 0.0
        assert result["available"] == 0.0


class TestGetAllPositionsLongPnlPct:
    """롱 포지션 PnL % 계산 상세 테스트"""

    @pytest.fixture
    def client_fixture(self):
        client = BinanceTestnetClient("key", "secret", testnet=True)
        mock_internal = AsyncMock()
        client._client = mock_internal
        return client, mock_internal

    @pytest.mark.asyncio
    async def test_long_position_pnl_calculation(self, client_fixture):
        """롱 포지션 PnL % 계산 정확도"""
        client_instance, mock_internal = client_fixture

        mock_internal.futures_position_information = AsyncMock(return_value=[
            {
                "symbol": "BTCUSDT",
                "positionAmt": "0.01",
                "entryPrice": "100000.0",
                "unRealizedProfit": "100.0",
                "leverage": "10",
                "markPrice": "101000.0",
                "marginType": "cross",
                "liquidationPrice": "90000.0",
            }
        ])
        mock_internal.futures_symbol_ticker = AsyncMock(
            return_value={"price": "101000.0"}
        )

        positions = await client_instance.get_all_positions()
        assert len(positions) == 1
        pos = positions[0]
        assert pos["side"] == "LONG"
        # PnL % = ((101000 - 100000) / 100000) * 100 * 10 = 10.0
        assert pos["pnl_pct"] == pytest.approx(10.0, rel=0.01)
        assert pos["quantity"] == 0.01
        assert pos["margin_type"] == "cross"
        assert pos["liquidation_price"] == 90000.0



class TestIssueKGetPositionRetry:
    """get_position() should have @async_retry for transient failures."""

    @pytest.fixture
    def retry_client(self):
        """Connected BinanceTestnetClient mock for retry tests."""
        from src.exchange.binance import BinanceTestnetClient
        c = BinanceTestnetClient("test_key", "test_secret", testnet=True)
        c._client = AsyncMock()
        c._metrics = None
        return c

    @pytest.mark.asyncio
    async def test_get_position_retries_on_connection_error(self, retry_client):
        """get_position retries on ConnectionError and succeeds."""
        retry_client._client.futures_position_information = AsyncMock(
            side_effect=[
                ConnectionError("transient"),
                [{"symbol": "BTCUSDT", "positionAmt": "0.001",
                  "entryPrice": "50000.0", "unRealizedProfit": "10.0",
                  "leverage": "10"}],
            ]
        )
        result = await retry_client.get_position("BTCUSDT")
        assert result is not None
        assert result["symbol"] == "BTCUSDT"
        assert retry_client._client.futures_position_information.call_count == 2

    @pytest.mark.asyncio
    async def test_get_position_retries_on_timeout_error(self, retry_client):
        """get_position retries on TimeoutError."""
        retry_client._client.futures_position_information = AsyncMock(
            side_effect=[
                TimeoutError("timeout"),
                [{"symbol": "BTCUSDT", "positionAmt": "0",
                  "entryPrice": "0", "unRealizedProfit": "0"}],
            ]
        )
        result = await retry_client.get_position("BTCUSDT")
        assert result is None  # no position
        assert retry_client._client.futures_position_information.call_count == 2

    @pytest.mark.asyncio
    async def test_get_position_no_circuit_breaker(self, retry_client):
        """get_position should NOT have circuit breaker (critical for monitoring)."""
        # Fail 10 times - should NOT trigger CircuitBreakerOpen
        retry_client._client.futures_position_information = AsyncMock(
            side_effect=ConnectionError("fail")
        )
        for _ in range(10):
            with pytest.raises(ConnectionError):
                await retry_client.get_position("BTCUSDT")
        # Should still raise ConnectionError, NOT CircuitBreakerOpen
        with pytest.raises(ConnectionError):
            await retry_client.get_position("BTCUSDT")


class TestStopMarketOrderValidation:
    """create_stop_market_order 방어적 검증 테스트"""

    @pytest.fixture
    def client_fixture(self):
        client = BinanceTestnetClient("key", "secret", testnet=True)
        mock_internal = AsyncMock()
        client._client = mock_internal
        return client, mock_internal

    @pytest.mark.asyncio
    async def test_stop_market_order_zero_price_raises(self, client_fixture):
        """stop_price=0 -> ValueError"""
        client_instance, _ = client_fixture

        with pytest.raises(ValueError, match="Invalid stop_price"):
            await client_instance.create_stop_market_order(
                "BTCUSDT", "SELL", 0.01, 0.0
            )

    @pytest.mark.asyncio
    async def test_stop_market_order_negative_price_raises(self, client_fixture):
        """stop_price 음수 -> ValueError"""
        client_instance, _ = client_fixture

        with pytest.raises(ValueError, match="Invalid stop_price"):
            await client_instance.create_stop_market_order(
                "BTCUSDT", "SELL", 0.01, -100.0
            )

    @pytest.mark.asyncio
    async def test_stop_market_order_none_price_raises(self, client_fixture):
        """stop_price=None -> ValueError"""
        client_instance, _ = client_fixture

        with pytest.raises(ValueError, match="Invalid stop_price"):
            await client_instance.create_stop_market_order(
                "BTCUSDT", "SELL", 0.01, None
            )

    @pytest.mark.asyncio
    async def test_stop_market_order_valid_price_succeeds(self, client_fixture):
        """정상 stop_price -> 주문 성공"""
        client_instance, mock_internal = client_fixture
        mock_internal.futures_create_order = AsyncMock(return_value={
            "orderId": 77777, "type": "STOP_MARKET", "status": "NEW",
        })

        result = await client_instance.create_stop_market_order(
            "BTCUSDT", "SELL", 0.01, 99600.0
        )

        assert result["orderId"] == 77777
        mock_internal.futures_create_order.assert_called_once()
