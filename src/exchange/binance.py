"""Binance Testnet Client for futures trading.

Phase 4: AsyncClient 마이그레이션 - 비동기 클라이언트 사용
"""
import asyncio
import contextlib
import time
from typing import Any

import pandas as pd
from binance import AsyncClient
from binance.enums import (
    ORDER_TYPE_LIMIT,
    ORDER_TYPE_MARKET,
    SIDE_BUY,
    SIDE_SELL,
    TIME_IN_FORCE_GTC,
)
from binance.exceptions import BinanceAPIException
from loguru import logger

from src.exchange.api_weight_tracker import APIWeightTracker
from src.utils.circuit_breaker import circuit_breaker
from src.utils.retry import async_retry
from src.utils.validation import validate_ohlcv_dataframe


class BinanceTestnetClient:
    """Binance Futures Testnet Client (Async).

    Phase 4: AsyncClient 마이그레이션 완료
    - 모든 API 호출이 진정한 비동기로 동작
    - connect() 호출 필수
    - close() 호출로 리소스 정리
    """

    def __init__(self, api_key: str, secret_key: str, testnet: bool = True):
        """Initialize Binance client.

        Args:
            api_key: Binance API key
            secret_key: Binance secret key
            testnet: Use testnet or real trading (default: True)
        """
        self._api_key = api_key
        self._secret_key = secret_key
        self._testnet = testnet
        self._client: AsyncClient | None = None
        self._metrics: Any | None = None
        self._weight_tracker = APIWeightTracker()
        try:
            from src.metrics.prometheus import _get_metrics  # noqa: PLC0415
            self._metrics = _get_metrics()
        except Exception:  # noqa: S110
            pass  # prometheus_client 미설치 시 스킵

    def _record_latency(self, endpoint: str, start: float) -> None:
        """API 지연시간 메트릭 기록."""
        if self._metrics:
            with contextlib.suppress(Exception):
                self._metrics.record_api_latency(endpoint, time.monotonic() - start)

    async def connect(self) -> None:
        """AsyncClient 초기화 (비동기).

        사용 전 반드시 호출해야 합니다.
        """
        if self._client is not None:
            logger.warning("클라이언트가 이미 연결되어 있습니다")
            return

        self._client = await AsyncClient.create(
            api_key=self._api_key,
            api_secret=self._secret_key,
            testnet=self._testnet,
        )

        if self._testnet:
            logger.info("Binance Testnet AsyncClient 연결 완료")
        else:
            logger.warning("Binance REAL trading AsyncClient 연결 완료")

    async def close(self) -> None:
        """연결 종료."""
        if self._client:
            await self._client.close_connection()
            self._client = None
            logger.info("Binance AsyncClient 연결 종료")

    @property
    def client(self) -> AsyncClient:
        """내부 클라이언트 반환 (연결 확인)."""
        if self._client is None:
            raise RuntimeError(
                "클라이언트가 연결되지 않았습니다. connect()를 먼저 호출하세요."
            )
        return self._client

    @property
    def testnet(self) -> bool:
        """Testnet 사용 여부."""
        return self._testnet

    @circuit_breaker(
        name="binance_market_data",
        failure_threshold=5,
        recovery_timeout=60,
        exceptions=(BinanceAPIException, ConnectionError, TimeoutError),
    )
    @async_retry(
        max_attempts=3,
        delay=1.0,
        backoff=2.0,
        exceptions=(BinanceAPIException, ConnectionError, TimeoutError),
    )
    async def get_current_price(self, symbol: str) -> float:
        """Get current price for a symbol (with retry).

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")

        Returns:
            Current price as float
        """
        t0 = time.monotonic()
        try:
            ticker = await self.client.futures_symbol_ticker(symbol=symbol)
            price = float(ticker["price"])
            logger.debug(f"{symbol} current price: ${price:,.2f}")
            return price
        except Exception as e:
            logger.error(f"Failed to get current price for {symbol}: {e}")
            raise
        finally:
            self._record_latency("get_current_price", t0)

    @circuit_breaker(
        name="binance_market_data",
        failure_threshold=5,
        recovery_timeout=60,
        exceptions=(BinanceAPIException, ConnectionError, TimeoutError),
    )
    @async_retry(
        max_attempts=3,
        delay=1.0,
        backoff=2.0,
        exceptions=(BinanceAPIException, ConnectionError, TimeoutError),
    )
    async def get_klines(
        self,
        symbol: str,
        interval: str = AsyncClient.KLINE_INTERVAL_5MINUTE,
        limit: int = 24,
    ) -> pd.DataFrame:
        """Get candlestick data (with retry).

        Args:
            symbol: Trading pair
            interval: Candle interval (default: 5 minutes)
            limit: Number of candles (default: 24 = 2 hours)

        Returns:
            DataFrame with OHLCV data
        """
        t0 = time.monotonic()
        try:
            klines = await self.client.futures_klines(
                symbol=symbol, interval=interval, limit=limit
            )

            # Convert to DataFrame
            df = pd.DataFrame(
                klines,
                columns=[
                    "timestamp",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "close_time",
                    "quote_volume",
                    "trades",
                    "taker_buy_base",
                    "taker_buy_quote",
                    "ignore",
                ],
            )

            # Convert types
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = df[col].astype(float)

            logger.debug(
                f"Fetched {len(df)} candles for {symbol} ({interval})"
            )
            result_df = df[["timestamp", "open", "high", "low", "close", "volume"]]
            return validate_ohlcv_dataframe(result_df, min_rows=5)

        except Exception as e:
            logger.error(f"Failed to get klines for {symbol}: {e}")
            raise
        finally:
            self._record_latency("get_klines", t0)

    @circuit_breaker(
        name="binance_market_data",
        failure_threshold=5,
        recovery_timeout=60,
        exceptions=(BinanceAPIException, ConnectionError, TimeoutError),
    )
    @async_retry(
        max_attempts=3,
        delay=1.0,
        backoff=2.0,
        exceptions=(BinanceAPIException, ConnectionError, TimeoutError),
    )
    async def get_ticker_24h(self, symbol: str) -> dict:
        """Get 24-hour ticker statistics.

        Args:
            symbol: Trading pair

        Returns:
            Dictionary with 24h stats
        """
        try:
            ticker = await self.client.futures_ticker(symbol=symbol)
            stats = {
                "high_24h": float(ticker["highPrice"]),
                "low_24h": float(ticker["lowPrice"]),
                "change_24h": float(ticker["priceChangePercent"]),
                "volume_24h": float(ticker["volume"]),
                "quote_volume_24h": float(ticker["quoteVolume"]),
            }
            logger.debug(f"{symbol} 24h change: {stats['change_24h']:.2f}%")
            return stats
        except Exception as e:
            logger.error(f"Failed to get 24h ticker for {symbol}: {e}")
            raise

    @circuit_breaker(
        name="binance_trading",
        failure_threshold=5,
        recovery_timeout=60,
        exceptions=(BinanceAPIException, ConnectionError, TimeoutError),
    )
    @async_retry(
        max_attempts=3,
        delay=1.0,
        backoff=2.0,
        exceptions=(BinanceAPIException, ConnectionError, TimeoutError),
    )
    async def set_leverage(self, symbol: str, leverage: int) -> dict:
        """Set leverage for a symbol (with retry).

        Args:
            symbol: Trading pair
            leverage: Leverage multiplier (1-125)

        Returns:
            Response from exchange
        """
        try:
            response = await self.client.futures_change_leverage(
                symbol=symbol, leverage=leverage
            )
            logger.info(f"Leverage set to {leverage}x for {symbol}")
            return response
        except Exception as e:
            logger.error(f"Failed to set leverage for {symbol}: {e}")
            raise

    @circuit_breaker(
        name="binance_trading",
        failure_threshold=5,
        recovery_timeout=60,
        exceptions=(BinanceAPIException, ConnectionError, TimeoutError),
    )
    @async_retry(
        max_attempts=3,
        delay=1.0,
        backoff=2.0,
        exceptions=(BinanceAPIException, ConnectionError, TimeoutError),
    )
    async def create_market_order(
        self, symbol: str, side: str, quantity: float
    ) -> dict:
        """Create a market order (with retry).

        Args:
            symbol: Trading pair
            side: "BUY" or "SELL"
            quantity: Order quantity in base asset

        Returns:
            Order details
        """
        t0 = time.monotonic()
        try:
            order = await self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type=ORDER_TYPE_MARKET,
                quantity=quantity,
            )
            logger.info(
                f"Market order created: {side} {quantity} {symbol} @ Market"
            )
            logger.info(f"Order ID: {order['orderId']}")
            return order
        except Exception as e:
            logger.error(f"Failed to create market order: {e}")
            raise
        finally:
            self._record_latency("create_market_order", t0)

    @circuit_breaker(
        name="binance_trading",
        failure_threshold=5,
        recovery_timeout=60,
        exceptions=(BinanceAPIException, ConnectionError, TimeoutError),
    )
    @async_retry(
        max_attempts=3,
        delay=1.0,
        backoff=2.0,
        exceptions=(BinanceAPIException, ConnectionError, TimeoutError),
    )
    async def create_limit_order(
        self, symbol: str, side: str, quantity: float, price: float
    ) -> dict:
        """Create a limit order (Maker order with retry).

        Args:
            symbol: Trading pair
            side: "BUY" or "SELL"
            quantity: Order quantity in base asset
            price: Limit price

        Returns:
            Order details
        """
        try:
            order = await self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type=ORDER_TYPE_LIMIT,
                timeInForce=TIME_IN_FORCE_GTC,
                quantity=quantity,
                price=price,
            )
            logger.info(
                f"Limit order created: {side} {quantity} {symbol} @ ${price:,.2f}"
            )
            logger.info(f"Order ID: {order['orderId']}")
            return order
        except Exception as e:
            logger.error(f"Failed to create limit order: {e}")
            raise

    @async_retry(
        max_attempts=3,
        delay=1.0,
        backoff=2.0,
        exceptions=(BinanceAPIException, ConnectionError, TimeoutError),
    )
    async def get_order_status(self, symbol: str, order_id: int) -> dict:
        """Get order status (with retry).

        Args:
            symbol: Trading pair
            order_id: Order ID

        Returns:
            Order details with status
        """
        try:
            order = await self.client.futures_get_order(symbol=symbol, orderId=order_id)
            logger.debug(f"Order {order_id} status: {order['status']}")
            return order
        except Exception as e:
            logger.error(f"Failed to get order status: {e}")
            raise

    @async_retry(
        max_attempts=3,
        delay=1.0,
        backoff=2.0,
        exceptions=(BinanceAPIException, ConnectionError, TimeoutError),
    )
    async def cancel_order(self, symbol: str, order_id: int) -> dict:
        """Cancel an open order (with retry).

        Args:
            symbol: Trading pair
            order_id: Order ID to cancel

        Returns:
            Cancel response
        """
        try:
            result = await self.client.futures_cancel_order(
                symbol=symbol, orderId=order_id
            )
            logger.info(f"Order {order_id} cancelled")
            return result
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            raise

    @async_retry(
        max_attempts=3,
        delay=1.0,
        backoff=2.0,
        exceptions=(BinanceAPIException, ConnectionError, TimeoutError),
    )
    async def get_position(self, symbol: str) -> dict | None:
        """Get current position for a symbol.

        Args:
            symbol: Trading pair

        Returns:
            Position info or None if no position
        """
        try:
            positions = await self.client.futures_position_information(symbol=symbol)

            for pos in positions:
                if float(pos["positionAmt"]) != 0:
                    position_info = {
                        "symbol": pos["symbol"],
                        "position_amt": float(pos["positionAmt"]),
                        "entry_price": float(pos["entryPrice"]),
                        "unrealized_pnl": float(pos["unRealizedProfit"]),
                        "leverage": int(pos.get("leverage", 1)),
                        "side": "LONG" if float(pos["positionAmt"]) > 0 else "SHORT",
                    }
                    logger.debug(
                        f"Position: {position_info['side']} "
                        f"{abs(position_info['position_amt'])} @ "
                        f"${position_info['entry_price']:,.2f}"
                    )
                    return position_info

            logger.debug(f"No position for {symbol}")
            return None

        except Exception as e:
            logger.error(f"Failed to get position for {symbol}: {e}")
            raise

    @async_retry(
        max_attempts=3,
        delay=1.0,
        backoff=2.0,
        exceptions=(BinanceAPIException, ConnectionError, TimeoutError),
    )
    async def get_all_positions(self) -> list:
        """계정 내 모든 열린 포지션 조회.

        Returns:
            열린 포지션 리스트 (포지션이 없으면 빈 리스트)

        Raises:
            Exception: 네트워크 오류 시 예외 전파 (빈 리스트와 구분하기 위함)
        """
        try:
            positions = await self.client.futures_position_information()
            open_positions = []

            for pos in positions:
                position_amt = float(pos["positionAmt"])
                if position_amt != 0:
                    # 현재가 조회
                    try:
                        ticker = await self.client.futures_symbol_ticker(
                            symbol=pos["symbol"]
                        )
                        current_price = float(ticker["price"])
                    except Exception:
                        current_price = float(pos["markPrice"])

                    entry_price = float(pos["entryPrice"])
                    unrealized_pnl = float(pos["unRealizedProfit"])
                    leverage = int(pos.get("leverage", 1))
                    side = "LONG" if position_amt > 0 else "SHORT"

                    # 거래소 수준의 PnL % 계산 (포지션 추적용)
                    # NOTE: trading 모듈의 PnL 계산과는 별도로,
                    # 거래소 API 응답 기반의 실시간 포지션 모니터링에 사용됩니다.
                    if entry_price > 0:
                        if side == "LONG":
                            pnl_pct = (
                                (current_price - entry_price) / entry_price
                            ) * 100 * leverage
                        else:
                            pnl_pct = (
                                (entry_price - current_price) / entry_price
                            ) * 100 * leverage
                    else:
                        pnl_pct = 0

                    position_info = {
                        "symbol": pos["symbol"],
                        "side": side,
                        "quantity": abs(position_amt),
                        "entry_price": entry_price,
                        "current_price": current_price,
                        "unrealized_pnl": unrealized_pnl,
                        "pnl_pct": pnl_pct,
                        "leverage": leverage,
                        "margin_type": pos.get("marginType", "cross"),
                        "liquidation_price": float(pos.get("liquidationPrice", 0)),
                    }
                    open_positions.append(position_info)

            logger.debug(f"열린 포지션 수: {len(open_positions)}")
            return open_positions

        except Exception as e:
            logger.error(f"전체 포지션 조회 실패: {e}")
            raise

    async def close_position(self, symbol: str) -> dict | None:
        """Close current position for a symbol.

        NOTE: @async_retry를 의도적으로 제거함.
        내부에서 호출하는 create_market_order()에 이미 @async_retry가 적용되어 있어
        이중 재시도(최대 9회) 시 중복 청산 위험이 있음.

        Args:
            symbol: Trading pair

        Returns:
            Order details or None if no position to close
        """
        try:
            position = await self.get_position(symbol)

            if not position:
                logger.info(f"No position to close for {symbol}")
                return None

            # Determine closing side (opposite of position)
            side = SIDE_SELL if position["side"] == "LONG" else SIDE_BUY
            quantity = abs(position["position_amt"])

            # Create closing order
            order = await self.create_market_order(symbol, side, quantity)
            logger.info(f"Position closed for {symbol}")
            return order

        except Exception as e:
            logger.error(f"Failed to close position for {symbol}: {e}")
            raise

    async def get_funding_rate(self, symbol: str) -> dict:
        """현재 펀딩비 조회.

        Args:
            symbol: 거래쌍 (예: "BTCUSDT")

        Returns:
            펀딩비 정보 딕셔너리. is_error=True이면 API 오류로 기본값 사용 중.
        """
        try:
            # 현재 펀딩비
            funding_info = await self.client.futures_funding_rate(
                symbol=symbol, limit=1
            )
            if funding_info:
                rate = float(funding_info[0]["fundingRate"]) * 100  # 퍼센트로 변환
                funding_time = funding_info[0]["fundingTime"]
                logger.debug(f"{symbol} 펀딩비: {rate:+.4f}%")
                return {
                    "funding_rate": rate,
                    "funding_time": funding_time,
                    "is_error": False,
                }
            return {"funding_rate": 0.0, "funding_time": None, "is_error": False}
        except Exception as e:
            logger.warning(f"펀딩비 조회 실패 {symbol}: {e} - 기본값 사용")
            return {"funding_rate": 0.0, "funding_time": None, "is_error": True}

    async def get_long_short_ratio(self, symbol: str) -> dict:
        """롱숏 비율 조회 (상위 트레이더 포지션 기준).

        Args:
            symbol: 거래쌍 (예: "BTCUSDT")

        Returns:
            롱숏 비율 정보. is_error=True이면 API 오류로 기본값 사용 중.
        """
        try:
            # 상위 트레이더 롱숏 비율
            ratio_data = await self.client.futures_top_longshort_position_ratio(
                symbol=symbol, period="5m", limit=1
            )
            if ratio_data:
                long_ratio = float(ratio_data[0]["longAccount"])
                short_ratio = float(ratio_data[0]["shortAccount"])
                ls_ratio = float(ratio_data[0]["longShortRatio"])
                logger.debug(
                    f"{symbol} 롱숏비율: 롱 {long_ratio:.1%} / 숏 {short_ratio:.1%}"
                )
                return {
                    "long_ratio": long_ratio,
                    "short_ratio": short_ratio,
                    "long_short_ratio": ls_ratio,
                    "is_error": False,
                }
            return {
                "long_ratio": 0.5, "short_ratio": 0.5,
                "long_short_ratio": 1.0, "is_error": False,
            }
        except Exception as e:
            logger.warning(f"롱숏 비율 조회 실패 {symbol}: {e} - 기본값 사용")
            return {
                "long_ratio": 0.5, "short_ratio": 0.5,
                "long_short_ratio": 1.0, "is_error": True,
            }

    async def get_open_interest(self, symbol: str) -> dict:
        """미결제약정 조회.

        Args:
            symbol: 거래쌍 (예: "BTCUSDT")

        Returns:
            미결제약정 정보. is_error=True이면 API 오류로 기본값 사용 중.
        """
        try:
            oi_data = await self.client.futures_open_interest(symbol=symbol)
            oi = float(oi_data["openInterest"])
            logger.debug(f"{symbol} 미결제약정: {oi:,.2f}")
            return {"open_interest": oi, "symbol": symbol, "is_error": False}
        except Exception as e:
            logger.warning(f"미결제약정 조회 실패 {symbol}: {e} - 기본값 사용")
            return {"open_interest": 0.0, "symbol": symbol, "is_error": True}

    async def get_premium_index(self, symbol: str) -> dict:
        """프리미엄 인덱스 조회 (Mark Price, Index Price, Basis).

        Args:
            symbol: 거래쌍 (예: "BTCUSDT")

        Returns:
            프리미엄 인덱스 정보. is_error=True이면 API 오류로 기본값 사용 중.
        """
        try:
            data = await self.client.futures_mark_price(symbol=symbol)
            mark_price = float(data["markPrice"])
            index_price = float(data["indexPrice"])
            basis = (mark_price - index_price) / index_price if index_price > 0 else 0.0
            logger.debug(f"{symbol} 프리미엄: mark={mark_price:.2f}, basis={basis:.6f}")
            return {
                "mark_price": mark_price,
                "index_price": index_price,
                "basis": basis,
                "is_error": False,
            }
        except Exception as e:
            logger.warning(f"프리미엄 인덱스 조회 실패 {symbol}: {e} - 기본값 사용")
            return {
                "mark_price": 0.0, "index_price": 0.0,
                "basis": 0.0, "is_error": True,
            }

    async def get_global_long_short_ratio(self, symbol: str) -> dict:
        """글로벌 롱숏 비율 조회 (전체 계정 기준).

        Args:
            symbol: 거래쌍 (예: "BTCUSDT")

        Returns:
            글로벌 롱숏 비율. is_error=True이면 API 오류로 기본값 사용 중.
        """
        try:
            data = await self.client.futures_global_longshort_ratio(
                symbol=symbol, period="5m", limit=1
            )
            if data:
                long_ratio = float(data[0]["longAccount"])
                short_ratio = float(data[0]["shortAccount"])
                ls_ratio = float(data[0]["longShortRatio"])
                logger.debug(
                    f"{symbol} 글로벌 롱숏: 롱 {long_ratio:.1%} / 숏 {short_ratio:.1%}"
                )
                return {
                    "long_ratio": long_ratio,
                    "short_ratio": short_ratio,
                    "long_short_ratio": ls_ratio,
                    "is_error": False,
                }
            return {
                "long_ratio": 0.5, "short_ratio": 0.5,
                "long_short_ratio": 1.0, "is_error": False,
            }
        except Exception as e:
            logger.warning(f"글로벌 롱숏 비율 조회 실패 {symbol}: {e} - 기본값 사용")
            return {
                "long_ratio": 0.5, "short_ratio": 0.5,
                "long_short_ratio": 1.0, "is_error": True,
            }

    async def get_taker_long_short_ratio(self, symbol: str) -> dict:
        """테이커 매수/매도 비율 조회.

        Args:
            symbol: 거래쌍 (예: "BTCUSDT")

        Returns:
            테이커 매수/매도 비율. is_error=True이면 API 오류로 기본값 사용 중.
        """
        try:
            data = await self.client.futures_taker_longshort_ratio(
                symbol=symbol, period="5m", limit=1
            )
            if data:
                buy_sell_ratio = float(data[0]["buySellRatio"])
                buy_vol = float(data[0]["buyVol"])
                sell_vol = float(data[0]["sellVol"])
                logger.debug(f"{symbol} 테이커 B/S 비율: {buy_sell_ratio:.3f}")
                return {
                    "buy_sell_ratio": buy_sell_ratio,
                    "buy_vol": buy_vol,
                    "sell_vol": sell_vol,
                    "is_error": False,
                }
            return {
                "buy_sell_ratio": 1.0, "buy_vol": 0.0,
                "sell_vol": 0.0, "is_error": False,
            }
        except Exception as e:
            logger.warning(f"테이커 롱숏 비율 조회 실패 {symbol}: {e} - 기본값 사용")
            return {
                "buy_sell_ratio": 1.0, "buy_vol": 0.0,
                "sell_vol": 0.0, "is_error": True,
            }

    async def get_market_sentiment(self, symbol: str) -> dict:
        """시장 심리 데이터 통합 조회 (펀딩비 + 롱숏비율 + 미결제약정).

        Args:
            symbol: 거래쌍 (예: "BTCUSDT")

        Returns:
            통합 시장 심리 데이터
        """
        # WS-6: API weight delay check
        delay = self._weight_tracker.should_delay()
        if delay > 0:
            await asyncio.sleep(delay)

        # 6개 API를 병렬로 호출하여 응답 시간 단축
        self._weight_tracker.record("get_market_sentiment")
        funding, ls_ratio, oi, premium, global_ls, taker_ls = await asyncio.gather(
            self.get_funding_rate(symbol),
            self.get_long_short_ratio(symbol),
            self.get_open_interest(symbol),
            self.get_premium_index(symbol),
            self.get_global_long_short_ratio(symbol),
            self.get_taker_long_short_ratio(symbol),
        )

        sentiment = {
            "funding_rate": funding["funding_rate"],
            "long_ratio": ls_ratio["long_ratio"],
            "short_ratio": ls_ratio["short_ratio"],
            "long_short_ratio": ls_ratio["long_short_ratio"],
            "open_interest": oi["open_interest"],
            "basis": premium["basis"],
            "global_long_ratio": global_ls["long_ratio"],
            "global_short_ratio": global_ls["short_ratio"],
            "taker_buy_sell_ratio": taker_ls["buy_sell_ratio"],
        }

        logger.debug(
            f"{symbol} 시장심리: 펀딩={sentiment['funding_rate']:+.4f}%, "
            f"롱숏={sentiment['long_ratio']:.1%}:{sentiment['short_ratio']:.1%}"
        )
        return sentiment

    @circuit_breaker(
        name="binance_account",
        failure_threshold=5,
        recovery_timeout=60,
        exceptions=(BinanceAPIException, ConnectionError, TimeoutError),
    )
    async def get_account_balance(self) -> dict:
        """Get account balance.

        Returns:
            Dictionary with USDT balance info
        """
        try:
            account = await self.client.futures_account()
            usdt_balance = None

            for asset in account["assets"]:
                if asset["asset"] == "USDT":
                    usdt_balance = {
                        "asset": "USDT",
                        "balance": float(asset["walletBalance"]),
                        "available": float(asset["availableBalance"]),
                        "unrealized_pnl": float(asset["unrealizedProfit"]),
                    }
                    break

            if usdt_balance:
                logger.debug(
                    f"Balance: ${usdt_balance['balance']:,.2f} USDT "
                    f"(Available: ${usdt_balance['available']:,.2f})"
                )
                return usdt_balance
            logger.warning("USDT balance not found")
            return {"asset": "USDT", "balance": 0.0, "available": 0.0}

        except Exception as e:
            logger.error(f"Failed to get account balance: {e}")
            raise

    @async_retry(
        max_attempts=3,
        delay=1.0,
        backoff=2.0,
        exceptions=(BinanceAPIException, ConnectionError, TimeoutError),
    )
    async def create_stop_market_order(
        self, symbol: str, side: str, quantity: float, stop_price: float
    ) -> dict:
        """거래소 측 STOP_MARKET 주문 생성 (스톱로스).

        Args:
            symbol: 거래쌍 (예: "BTCUSDT")
            side: 청산 방향 ("BUY" or "SELL")
            quantity: 주문 수량
            stop_price: 스톱 가격

        Returns:
            주문 응답 딕셔너리

        Raises:
            ValueError: stop_price가 유효하지 않을 때
        """
        if not stop_price or stop_price <= 0:
            raise ValueError(f"Invalid stop_price: {stop_price}")

        t0 = time.monotonic()
        try:
            order = await self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type="STOP_MARKET",
                stopPrice=stop_price,
                quantity=quantity,
                closePosition="true",
            )
            logger.info(
                f"STOP_MARKET 주문 생성: {side} {symbol} @ stop={stop_price:,.2f}"
            )
            return order
        except Exception as e:
            logger.error(f"STOP_MARKET 주문 실패: {e}")
            raise
        finally:
            self._record_latency("create_stop_market_order", t0)

    @async_retry(
        max_attempts=3,
        delay=1.0,
        backoff=2.0,
        exceptions=(BinanceAPIException, ConnectionError, TimeoutError),
    )
    async def create_take_profit_market_order(
        self, symbol: str, side: str, quantity: float, stop_price: float
    ) -> dict:
        """거래소 측 TAKE_PROFIT_MARKET 주문 생성 (익절).

        Args:
            symbol: 거래쌍 (예: "BTCUSDT")
            side: 청산 방향 ("BUY" or "SELL")
            quantity: 주문 수량
            stop_price: 트리거 가격

        Returns:
            주문 응답 딕셔너리
        """
        t0 = time.monotonic()
        try:
            order = await self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type="TAKE_PROFIT_MARKET",
                stopPrice=stop_price,
                quantity=quantity,
                closePosition="true",
            )
            logger.info(
                f"TAKE_PROFIT_MARKET 주문 생성: {side} {symbol} "
                f"@ stop={stop_price:,.2f}"
            )
            return order
        except Exception as e:
            logger.error(f"TAKE_PROFIT_MARKET 주문 실패: {e}")
            raise
        finally:
            self._record_latency("create_take_profit_market_order", t0)

    def get_api_weight_status(self) -> dict[str, int | float]:
        """API weight 사용량 모니터링.

        Returns:
            현재 weight 상태 딕셔너리
        """
        return self._weight_tracker.get_status()

    @async_retry(
        max_attempts=3,
        delay=1.0,
        backoff=2.0,
        exceptions=(BinanceAPIException, ConnectionError, TimeoutError),
    )
    async def cancel_all_open_orders(self, symbol: str) -> dict:
        """심볼의 모든 미체결 주문 취소.

        Args:
            symbol: 거래쌍 (예: "BTCUSDT")

        Returns:
            취소 응답 딕셔너리
        """
        try:
            result = await self.client.futures_cancel_all_open_orders(symbol=symbol)
            logger.info(f"{symbol} 모든 미체결 주문 취소 완료")
            return result
        except Exception as e:
            logger.error(f"{symbol} 미체결 주문 취소 실패: {e}")
            raise

