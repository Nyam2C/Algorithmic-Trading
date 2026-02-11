"""
Exchange 모듈 커버리지 향상 테스트

대상 모듈:
- src/exchange/binance.py (74.78%, 57 lines missed)
"""
from unittest.mock import AsyncMock, patch

import pytest

from src.exchange.binance import BinanceTestnetClient

# =============================================================================
# 연결 관련 테스트
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


# =============================================================================
# get_current_price 에러 케이스
# =============================================================================


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


# =============================================================================
# get_klines 에러 케이스
# =============================================================================


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


# =============================================================================
# get_ticker_24h 에러 케이스
# =============================================================================


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


# =============================================================================
# set_leverage 에러 케이스
# =============================================================================


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


# =============================================================================
# create_market_order / create_limit_order 에러 케이스
# =============================================================================


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


# =============================================================================
# get_order_status / cancel_order 에러 케이스
# =============================================================================


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


# =============================================================================
# get_position 에러 케이스
# =============================================================================


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


# =============================================================================
# get_all_positions 에러 및 엣지 케이스
# =============================================================================


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
        """전체 포지션 조회 예외 시 빈 리스트 반환"""
        client_instance, mock_internal = client_fixture
        mock_internal.futures_position_information = AsyncMock(
            side_effect=Exception("API error")
        )

        positions = await client_instance.get_all_positions()
        assert positions == []

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


# =============================================================================
# close_position 에러 케이스
# =============================================================================


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


# =============================================================================
# 펀딩비/롱숏비율/미결제약정 에러 핸들링
# =============================================================================


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


# =============================================================================
# get_market_sentiment 통합 테스트
# =============================================================================


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

        result = await client_instance.get_market_sentiment("BTCUSDT")

        assert result["funding_rate"] == pytest.approx(0.02, rel=0.01)  # 0.0002 * 100
        assert result["long_ratio"] == 0.60
        assert result["short_ratio"] == 0.40
        assert result["long_short_ratio"] == 1.50
        assert result["open_interest"] == 25000.0

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

        result = await client_instance.get_market_sentiment("BTCUSDT")

        # 펀딩비 기본값 사용
        assert result["funding_rate"] == 0.0
        assert result["long_ratio"] == 0.55
        assert result["open_interest"] == 20000.0


# =============================================================================
# get_account_balance 에러 케이스
# =============================================================================


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


# =============================================================================
# get_all_positions 롱 포지션 PnL % 계산
# =============================================================================


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
