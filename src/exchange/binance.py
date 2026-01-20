"""
Binance Testnet Client for futures trading
"""
from typing import Dict, Optional
from binance.client import Client
from binance.enums import (
    SIDE_BUY,
    SIDE_SELL,
    ORDER_TYPE_MARKET,
    ORDER_TYPE_LIMIT,
    TIME_IN_FORCE_GTC,
)
from binance.exceptions import BinanceAPIException
import pandas as pd
from loguru import logger

from src.utils.retry import async_retry


class BinanceTestnetClient:
    """Binance Futures Testnet Client"""

    def __init__(self, api_key: str, secret_key: str, testnet: bool = True):
        """
        Initialize Binance client

        Args:
            api_key: Binance API key
            secret_key: Binance secret key
            testnet: Use testnet or real trading (default: True)
        """
        self.testnet = testnet

        if testnet:
            # Testnet base URL
            self.client = Client(
                api_key=api_key,
                api_secret=secret_key,
                testnet=True,
            )
            logger.info("Binance Testnet client initialized")
        else:
            # Real trading (for Sprint 3+)
            self.client = Client(
                api_key=api_key,
                api_secret=secret_key,
            )
            logger.warning("Binance REAL trading client initialized")

    @async_retry(
        max_attempts=3,
        delay=1.0,
        backoff=2.0,
        exceptions=(BinanceAPIException, ConnectionError, TimeoutError),
    )
    async def get_current_price(self, symbol: str) -> float:
        """
        Get current price for a symbol (with retry)

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")

        Returns:
            Current price as float
        """
        try:
            ticker = self.client.futures_symbol_ticker(symbol=symbol)
            price = float(ticker["price"])
            logger.debug(f"{symbol} current price: ${price:,.2f}")
            return price
        except Exception as e:
            logger.error(f"Failed to get current price for {symbol}: {e}")
            raise

    @async_retry(
        max_attempts=3,
        delay=1.0,
        backoff=2.0,
        exceptions=(BinanceAPIException, ConnectionError, TimeoutError),
    )
    async def get_klines(
        self,
        symbol: str,
        interval: str = Client.KLINE_INTERVAL_5MINUTE,
        limit: int = 24,
    ) -> pd.DataFrame:
        """
        Get candlestick data (with retry)

        Args:
            symbol: Trading pair
            interval: Candle interval (default: 5 minutes)
            limit: Number of candles (default: 24 = 2 hours)

        Returns:
            DataFrame with OHLCV data
        """
        try:
            klines = self.client.futures_klines(
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
            return df[["timestamp", "open", "high", "low", "close", "volume"]]

        except Exception as e:
            logger.error(f"Failed to get klines for {symbol}: {e}")
            raise

    async def get_ticker_24h(self, symbol: str) -> Dict:
        """
        Get 24-hour ticker statistics

        Args:
            symbol: Trading pair

        Returns:
            Dictionary with 24h stats
        """
        try:
            ticker = self.client.futures_ticker(symbol=symbol)
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

    @async_retry(
        max_attempts=3,
        delay=1.0,
        backoff=2.0,
        exceptions=(BinanceAPIException, ConnectionError, TimeoutError),
    )
    async def set_leverage(self, symbol: str, leverage: int) -> Dict:
        """
        Set leverage for a symbol (with retry)

        Args:
            symbol: Trading pair
            leverage: Leverage multiplier (1-125)

        Returns:
            Response from exchange
        """
        try:
            response = self.client.futures_change_leverage(
                symbol=symbol, leverage=leverage
            )
            logger.info(f"Leverage set to {leverage}x for {symbol}")
            return response
        except Exception as e:
            logger.error(f"Failed to set leverage for {symbol}: {e}")
            raise

    @async_retry(
        max_attempts=3,
        delay=1.0,
        backoff=2.0,
        exceptions=(BinanceAPIException, ConnectionError, TimeoutError),
    )
    async def create_market_order(
        self, symbol: str, side: str, quantity: float
    ) -> Dict:
        """
        Create a market order (with retry)

        Args:
            symbol: Trading pair
            side: "BUY" or "SELL"
            quantity: Order quantity in base asset

        Returns:
            Order details
        """
        try:
            order = self.client.futures_create_order(
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

    @async_retry(
        max_attempts=3,
        delay=1.0,
        backoff=2.0,
        exceptions=(BinanceAPIException, ConnectionError, TimeoutError),
    )
    async def create_limit_order(
        self, symbol: str, side: str, quantity: float, price: float
    ) -> Dict:
        """
        Create a limit order (Maker order with retry)

        Args:
            symbol: Trading pair
            side: "BUY" or "SELL"
            quantity: Order quantity in base asset
            price: Limit price

        Returns:
            Order details
        """
        try:
            order = self.client.futures_create_order(
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
    async def get_order_status(self, symbol: str, order_id: int) -> Dict:
        """
        Get order status (with retry)

        Args:
            symbol: Trading pair
            order_id: Order ID

        Returns:
            Order details with status
        """
        try:
            order = self.client.futures_get_order(symbol=symbol, orderId=order_id)
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
    async def cancel_order(self, symbol: str, order_id: int) -> Dict:
        """
        Cancel an open order (with retry)

        Args:
            symbol: Trading pair
            order_id: Order ID to cancel

        Returns:
            Cancel response
        """
        try:
            result = self.client.futures_cancel_order(symbol=symbol, orderId=order_id)
            logger.info(f"Order {order_id} cancelled")
            return result
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            raise

    async def get_position(self, symbol: str) -> Optional[Dict]:
        """
        Get current position for a symbol

        Args:
            symbol: Trading pair

        Returns:
            Position info or None if no position
        """
        try:
            positions = self.client.futures_position_information(symbol=symbol)

            for pos in positions:
                if float(pos["positionAmt"]) != 0:
                    position_info = {
                        "symbol": pos["symbol"],
                        "position_amt": float(pos["positionAmt"]),
                        "entry_price": float(pos["entryPrice"]),
                        "unrealized_pnl": float(pos["unRealizedProfit"]),
                        "leverage": int(pos.get("leverage", 1)),  # Default to 1x if not present
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
    async def close_position(self, symbol: str) -> Optional[Dict]:
        """
        Close current position for a symbol (with retry)

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

    async def get_funding_rate(self, symbol: str) -> Dict:
        """
        현재 펀딩비 조회

        Args:
            symbol: 거래쌍 (예: "BTCUSDT")

        Returns:
            펀딩비 정보 딕셔너리
        """
        try:
            # 현재 펀딩비
            funding_info = self.client.futures_funding_rate(symbol=symbol, limit=1)
            if funding_info:
                rate = float(funding_info[0]["fundingRate"]) * 100  # 퍼센트로 변환
                funding_time = funding_info[0]["fundingTime"]
                logger.debug(f"{symbol} 펀딩비: {rate:+.4f}%")
                return {
                    "funding_rate": rate,
                    "funding_time": funding_time,
                }
            return {"funding_rate": 0.0, "funding_time": None}
        except Exception as e:
            logger.error(f"펀딩비 조회 실패 {symbol}: {e}")
            return {"funding_rate": 0.0, "funding_time": None}

    async def get_long_short_ratio(self, symbol: str) -> Dict:
        """
        롱숏 비율 조회 (상위 트레이더 포지션 기준)

        Args:
            symbol: 거래쌍 (예: "BTCUSDT")

        Returns:
            롱숏 비율 정보
        """
        try:
            # 상위 트레이더 롱숏 비율
            ratio_data = self.client.futures_top_longshort_position_ratio(
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
                }
            return {"long_ratio": 0.5, "short_ratio": 0.5, "long_short_ratio": 1.0}
        except Exception as e:
            logger.error(f"롱숏 비율 조회 실패 {symbol}: {e}")
            return {"long_ratio": 0.5, "short_ratio": 0.5, "long_short_ratio": 1.0}

    async def get_open_interest(self, symbol: str) -> Dict:
        """
        미결제약정 조회

        Args:
            symbol: 거래쌍 (예: "BTCUSDT")

        Returns:
            미결제약정 정보
        """
        try:
            oi_data = self.client.futures_open_interest(symbol=symbol)
            oi = float(oi_data["openInterest"])
            logger.debug(f"{symbol} 미결제약정: {oi:,.2f}")
            return {"open_interest": oi, "symbol": symbol}
        except Exception as e:
            logger.error(f"미결제약정 조회 실패 {symbol}: {e}")
            return {"open_interest": 0.0, "symbol": symbol}

    async def get_market_sentiment(self, symbol: str) -> Dict:
        """
        시장 심리 데이터 통합 조회 (펀딩비 + 롱숏비율 + 미결제약정)

        Args:
            symbol: 거래쌍 (예: "BTCUSDT")

        Returns:
            통합 시장 심리 데이터
        """
        funding = await self.get_funding_rate(symbol)
        ls_ratio = await self.get_long_short_ratio(symbol)
        oi = await self.get_open_interest(symbol)

        sentiment = {
            "funding_rate": funding["funding_rate"],
            "long_ratio": ls_ratio["long_ratio"],
            "short_ratio": ls_ratio["short_ratio"],
            "long_short_ratio": ls_ratio["long_short_ratio"],
            "open_interest": oi["open_interest"],
        }

        logger.debug(
            f"{symbol} 시장심리: 펀딩={sentiment['funding_rate']:+.4f}%, "
            f"롱숏={sentiment['long_ratio']:.1%}:{sentiment['short_ratio']:.1%}"
        )
        return sentiment

    async def get_account_balance(self) -> Dict:
        """
        Get account balance

        Returns:
            Dictionary with USDT balance info
        """
        try:
            account = self.client.futures_account()
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
            else:
                logger.warning("USDT balance not found")
                return {"asset": "USDT", "balance": 0.0, "available": 0.0}

        except Exception as e:
            logger.error(f"Failed to get account balance: {e}")
            raise
