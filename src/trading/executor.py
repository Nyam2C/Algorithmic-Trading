"""Trading executor for opening and closing positions.

Phase 5: 리스크 관리 강화
- 실제 잔고 기반 포지션 사이징
- ATR 기반 동적 TP/SL
"""
import asyncio
from datetime import datetime, timedelta

from binance.enums import (
    SIDE_BUY,
    SIDE_SELL,
)
from binance.exceptions import BinanceAPIException
from loguru import logger

from src.utils.pnl import calculate_pnl_pct as _calculate_pnl_pct


class TradingExecutor:
    """Execute trades on Binance Futures.

    Phase 5: 리스크 관리 기능 추가
    - 실제 잔고 기반 포지션 사이징 (use_real_balance 옵션)
    - ATR 기반 동적 TP/SL (Phase 6.1)
    """

    MIN_ORDER_QTY = 0.001  # Binance BTC minimum order quantity
    PARTIAL_FILL_THRESHOLD = 0.99  # 99% fill threshold

    def __init__(self, binance_client, config):
        """Initialize trading executor.

        Args:
            binance_client: BinanceTestnetClient instance
            config: TradingConfig instance
        """
        self.client = binance_client
        self.config = config
        self.current_position: dict | None = None

        # Phase 5: 잔고 캐싱
        self._cached_balance: float | None = None
        self._balance_cache_time: datetime | None = None
        self._balance_cache_ttl_seconds: int = 60  # 1분 캐싱 (변동성 시장 대응)

        logger.info("Trading executor initialized")

    async def setup_leverage(self) -> bool:
        """Set leverage for the trading symbol.

        Returns:
            True if successful
        """
        try:
            await self.client.set_leverage(
                symbol=self.config.symbol,
                leverage=self.config.leverage,
            )
            logger.info(
                f"Leverage set to {self.config.leverage}x for {self.config.symbol}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to set leverage: {e}")
            return False

    async def _get_available_balance(self) -> float:
        """Get available USDT balance with caching.

        Phase 8: 미실현 손실이 있으면 캐시된 잔고에서 차감합니다.

        Returns:
            Available balance in USDT
        """
        now = datetime.now()

        # 캐시가 유효한지 확인
        if (
            self._cached_balance is not None
            and self._balance_cache_time is not None
            and (now - self._balance_cache_time).total_seconds()
            < self._balance_cache_ttl_seconds
        ):
            return self._deduct_unrealized_loss(self._cached_balance)

        # 새로운 잔고 조회
        try:
            balance_info = await self.client.get_account_balance()
            self._cached_balance = balance_info["available"]
            self._balance_cache_time = now
            logger.debug(f"잔고 조회 완료: ${self._cached_balance:,.2f} USDT")
            return self._deduct_unrealized_loss(self._cached_balance)
        except Exception as e:
            logger.error(f"잔고 조회 실패: {e}")
            # 캐시된 값이 TTL 내에 있으면 사용, 없거나 만료면 재발생
            if (
                self._cached_balance is not None
                and self._balance_cache_time is not None
                and (datetime.now() - self._balance_cache_time).total_seconds()
                < self._balance_cache_ttl_seconds
            ):
                logger.warning(f"캐시된 잔고 사용: ${self._cached_balance:,.2f}")
                return self._deduct_unrealized_loss(self._cached_balance)
            raise

    def _deduct_unrealized_loss(self, balance: float) -> float:
        """미실현 손실이 있으면 잔고에서 차감.

        Args:
            balance: 원래 잔고

        Returns:
            미실현 손실 차감 후 잔고 (최소 0)
        """
        if self.current_position:
            unrealized_pnl = self.current_position.get("unrealized_pnl", 0.0)
            if unrealized_pnl < 0:
                adjusted = balance + unrealized_pnl  # unrealized_pnl is negative
                balance = max(0.0, adjusted)
                logger.debug(
                    f"미실현 손실 차감: ${abs(unrealized_pnl):,.2f}, "
                    f"조정 잔고: ${balance:,.2f}"
                )
        return balance

    def _calculate_position_size(
        self, current_price: float, capital: float | None = None
    ) -> float:
        """Calculate position size based on configuration (동기 버전 - 테스트 호환).

        Args:
            current_price: Current market price
            capital: Capital to use (None = default 1000.0)

        Returns:
            Position quantity in base asset
        """
        # capital이 제공되지 않으면 기본값 사용 (테스트 호환성)
        if capital is None:
            capital = 1000.0
            logger.warning("기본 자본 $1000 사용 - use_real_balance 설정 권장")

        # Calculate position value in USDT
        position_value = capital * self.config.position_size_pct * self.config.leverage

        # Calculate quantity
        quantity = position_value / current_price

        # Round to appropriate precision (BTC = 3 decimals)
        quantity = round(quantity, 3)

        # Minimum order quantity check (Binance BTC minimum = 0.001)
        if quantity < self.MIN_ORDER_QTY:
            raise ValueError(
                f"포지션 수량 {quantity}이 최소 주문 수량(0.001) 미만입니다. "
                f"자본=${capital:,.2f}, 가격=${current_price:,.2f}"
            )

        logger.info(
            f"Position size calculated: {quantity} "
            f"@ ${current_price:,.2f} = ${position_value:,.2f} "
            f"(capital=${capital:,.2f}, {self.config.leverage}x leverage)"
        )

        return quantity

    async def _calculate_position_size_with_balance(
        self, current_price: float
    ) -> float:
        """Calculate position size based on real account balance (비동기 버전).

        Phase 5.1: 실제 잔고 기반 포지션 사이징

        Args:
            current_price: Current market price

        Returns:
            Position quantity in base asset
        """
        # use_real_balance 설정 확인 (기본값: False = 기존 동작 유지)
        use_real_balance = getattr(self.config, "use_real_balance", False)

        if use_real_balance:
            try:
                capital = await self._get_available_balance()
            except Exception as e:
                # Check if we have a recent cache (within 5 min)
                cache_age = (
                    (datetime.now() - self._balance_cache_time).total_seconds()
                    if self._balance_cache_time
                    else float("inf")
                )
                if (
                    self._cached_balance is not None
                    and cache_age < self._balance_cache_ttl_seconds
                ):
                    logger.warning(
                        "잔고 API 실패, 최근 캐시 사용: "
                        f"${self._cached_balance:,.2f}"
                    )
                    capital = self._cached_balance
                else:
                    raise RuntimeError(
                        f"잔고 조회 실패 - 캐시 만료 또는 없음. 거래 중단: {e}"
                    ) from e
        else:
            capital = 1000.0

        return self._calculate_position_size(current_price, capital)

    def _calculate_tp_sl_prices(
        self, side: str, entry_price: float, entry_atr: float | None = None
    ) -> tuple[float, float]:
        """TP/SL 가격 계산 (ATR 또는 고정 퍼센트 기반).

        Args:
            side: 포지션 방향 ("LONG" or "SHORT")
            entry_price: 진입 가격
            entry_atr: ATR 값 (None이면 고정 퍼센트 사용)

        Returns:
            (tp_price, sl_price) 튜플
        """
        use_atr = getattr(self.config, "use_atr_tp_sl", False)

        if use_atr and entry_atr:
            atr_tp_mul = getattr(self.config, "atr_tp_multiplier", 2.0)
            atr_sl_mul = getattr(self.config, "atr_sl_multiplier", 1.0)
            if side == "LONG":
                tp_price = round(entry_price + entry_atr * atr_tp_mul, 2)
                sl_price = round(entry_price - entry_atr * atr_sl_mul, 2)
            else:
                tp_price = round(entry_price - entry_atr * atr_tp_mul, 2)
                sl_price = round(entry_price + entry_atr * atr_sl_mul, 2)
        else:
            tp_pct = self.config.take_profit_pct
            sl_pct = self.config.stop_loss_pct
            if side == "LONG":
                tp_price = round(entry_price * (1 + tp_pct), 2)
                sl_price = round(entry_price * (1 - sl_pct), 2)
            else:
                tp_price = round(entry_price * (1 - tp_pct), 2)
                sl_price = round(entry_price * (1 + sl_pct), 2)

        return tp_price, sl_price

    def _handle_slippage_detection(
        self, order: dict, current_price: float
    ) -> tuple[bool, float]:
        """슬리피지 감지 및 처리 여부 판단.

        Args:
            order: 체결된 주문 정보
            current_price: 예상 진입 가격

        Returns:
            (should_close, actual_price) 튜플.
            should_close=True이면 과도한 슬리피지로 포지션 청산 필요.
            actual_price는 실제 체결 가격 (avgPrice 없으면 current_price 그대로).
        """
        avg_price_str = order.get("avgPrice")
        if not avg_price_str:
            return False, current_price

        avg_price = float(avg_price_str)
        if avg_price <= 0:
            logger.warning(
                f"거래소 avgPrice가 0 또는 음수 ({avg_price_str}), 원래 가격 사용"
            )
            return False, current_price

        slippage = abs(avg_price - current_price) / current_price
        max_slippage = self.config.max_slippage_pct

        if slippage > max_slippage:
            logger.critical(
                f"슬리피지 경고: {slippage:.4%} > {max_slippage:.4%} "
                f"(예상=${current_price:,.2f}, 체결=${avg_price:,.2f})"
            )
            close_on_slippage = self.config.close_on_excessive_slippage
            if close_on_slippage:
                return True, avg_price

        return False, avg_price

    async def _prepare_and_open_position(
        self,
        signal: str,
        current_price: float,
        entry_atr: float | None = None,
        order_type: str = "MARKET",  # noqa: ARG002
        use_maker: bool = False,
    ) -> dict | None:
        """포지션 오픈 공통 로직.

        포지션 체크, 레버리지 설정, 사이징, 주문 생성, 포지션 저장을 처리합니다.

        Args:
            signal: "LONG" or "SHORT"
            current_price: Current market price
            entry_atr: ATR value at entry (Phase 6.1: for dynamic TP/SL)
            order_type: "MARKET" or "MAKER"
            use_maker: Use Maker order (limit order) if True

        Returns:
            Order details or None if failed
        """
        # Check if we already have a position
        existing_position = await self.client.get_position(self.config.symbol)
        if existing_position:
            logger.warning(
                f"Already have a {existing_position['side']} position, skipping"
            )
            return None

        # Setup leverage
        leverage_ok = await self.setup_leverage()
        if not leverage_ok:
            logger.error("레버리지 설정 실패 - 거래 중단")
            return None

        # Calculate position size (Phase 5.1: 실제 잔고 사용 가능)
        quantity = await self._calculate_position_size_with_balance(current_price)

        # Determine order side
        side = SIDE_BUY if signal == "LONG" else SIDE_SELL

        # Create order based on type
        if use_maker:
            order = await self._create_maker_order(
                signal, side, quantity, current_price
            )
        else:
            logger.info(
                f"Opening {signal} position: {side} {quantity} "
                f"{self.config.symbol}"
            )
            order = await self.client.create_market_order(
                symbol=self.config.symbol,
                side=side,
                quantity=quantity,
            )

        # Slippage detection for market orders
        if not use_maker and order:
            should_close, current_price = self._handle_slippage_detection(
                order, current_price
            )
            if should_close:
                logger.critical("과도한 슬리피지 - 즉시 포지션 청산")
                try:
                    await self.client.close_position(self.config.symbol)
                except Exception as close_err:
                    logger.critical(f"슬리피지 청산 실패: {close_err}")
                return None

        # Calculate TP/SL prices for Redis persistence
        tp_price, sl_price = self._calculate_tp_sl_prices(
            signal, current_price, entry_atr
        )

        # Store position info with entry time
        self.current_position = {
            "signal": signal,
            "side": side,
            "quantity": quantity,
            "entry_price": current_price,
            "order_id": order["orderId"],
            "entry_time": datetime.now(),
            "entry_atr": entry_atr,  # Phase 6.1: ATR at entry for dynamic TP/SL
            "tp_price": tp_price,
            "sl_price": sl_price,
        }

        logger.info(
            f"Position opened: {signal} {quantity} @ ${current_price:,.2f}"
            + (f" (ATR={entry_atr:.2f})" if entry_atr else "")
        )

        # Place exchange-side TP/SL orders for crash protection
        sl_ok = await self._place_exchange_tp_sl(
            symbol=self.config.symbol,
            side=signal,
            quantity=quantity,
            entry_price=current_price,
            entry_atr=entry_atr,
        )
        if not sl_ok:
            # SL is mandatory for safety - close position immediately
            logger.critical("SL 배치 실패 - 포지션 즉시 청산")
            try:
                await self.client.close_position(self.config.symbol)
            except Exception as close_err:
                logger.critical(f"SL 실패 후 포지션 청산도 실패: {close_err}")
            self.current_position = None
            return None

        return order

    async def _create_maker_order(
        self, signal: str, side: str, quantity: float, current_price: float
    ) -> dict:
        """Maker (limit) 주문 생성. 미체결 시 Market 주문으로 fallback.

        Args:
            signal: "LONG" or "SHORT"
            side: SIDE_BUY or SIDE_SELL
            quantity: Order quantity
            current_price: Current market price

        Returns:
            Filled order details
        """
        price_offset_pct = 0.0001  # 0.01% offset for maker order
        if signal == "LONG":
            limit_price = current_price * (1 - price_offset_pct)
        else:  # SHORT
            limit_price = current_price * (1 + price_offset_pct)

        # Round price to appropriate precision
        limit_price = round(limit_price, 2)

        # Create limit order
        logger.info(
            f"Opening {signal} position (MAKER): {side} "
            f"{quantity} {self.config.symbol} @ ${limit_price:,.2f}"
        )
        order = await self.client.create_limit_order(
            symbol=self.config.symbol,
            side=side,
            quantity=quantity,
            price=limit_price,
        )

        # Wait for order to fill (max 30 seconds)
        filled = await self._wait_for_fill(order["orderId"], timeout=30)

        if not filled:
            logger.warning(
                "Limit order not filled within timeout, "
                "cancelling and using market order"
            )
            # Cancel unfilled order
            await self.client.cancel_order(
                self.config.symbol, order["orderId"]
            )

            # Fallback to market order
            order = await self.client.create_market_order(
                symbol=self.config.symbol,
                side=side,
                quantity=quantity,
            )
            logger.info("Fallback to market order completed")

        return order

    async def open_position(
        self, signal: str, current_price: float, entry_atr: float | None = None
    ) -> dict | None:
        """Open a new position based on signal.

        Args:
            signal: "LONG" or "SHORT"
            current_price: Current market price
            entry_atr: ATR value at entry (Phase 6.1: for dynamic TP/SL)

        Returns:
            Order details or None if failed
        """
        try:
            return await self._prepare_and_open_position(
                signal=signal,
                current_price=current_price,
                entry_atr=entry_atr,
                order_type="MARKET",
                use_maker=False,
            )
        except Exception as e:
            logger.error(f"Failed to open position: {e}")
            return None

    async def open_position_maker(
        self, signal: str, current_price: float, use_maker: bool = True,
        entry_atr: float | None = None
    ) -> dict | None:
        """Open a new position using Maker order (limit order).

        Args:
            signal: "LONG" or "SHORT"
            current_price: Current market price
            use_maker: Use Maker order (default: True)
            entry_atr: ATR value at entry (Phase 6.1: for dynamic TP/SL)

        Returns:
            Order details or None if failed
        """
        try:
            return await self._prepare_and_open_position(
                signal=signal,
                current_price=current_price,
                entry_atr=entry_atr,
                order_type="MAKER" if use_maker else "MARKET",
                use_maker=use_maker,
            )
        except Exception as e:
            logger.error(f"Failed to open position (maker): {e}")
            return None

    async def _wait_for_fill(
        self, order_id: int, timeout: int = 30, check_interval: int = 2
    ) -> bool:
        """Wait for order to be filled.

        Args:
            order_id: Order ID to check
            timeout: Maximum wait time in seconds
            check_interval: How often to check (seconds)

        Returns:
            True if filled, False if timeout
        """
        elapsed = 0
        while elapsed < timeout:
            try:
                order_status = await self.client.get_order_status(
                    self.config.symbol, order_id
                )

                if order_status["status"] == "FILLED":
                    logger.info(f"Order {order_id} filled")
                    return True

                if order_status["status"] in ["CANCELED", "REJECTED", "EXPIRED"]:
                    logger.warning(f"Order {order_id} status: {order_status['status']}")
                    return False

                await asyncio.sleep(check_interval)
                elapsed += check_interval

            except Exception as e:
                logger.error(f"Error checking order status: {e}")
                return False

        logger.warning(f"Order {order_id} not filled within {timeout}s")
        return False

    async def close_position(
        self, cancel_orders_first: bool = False
    ) -> dict | None:
        """Close current position.

        Note: Does NOT clear current_position. The caller must call
        clear_position() after completing DB writes and PnL tracking.

        Args:
            cancel_orders_first: Cancel all open orders before closing
                (use for force close to avoid race with exchange SL/TP)

        Returns:
            Order details or None if failed
        """
        try:
            # Check if we have a position
            position = await self.client.get_position(self.config.symbol)
            if not position:
                logger.info("No position to close")
                return None

            # Cancel open orders first if requested (race condition prevention)
            if cancel_orders_first:
                try:
                    await self.client.cancel_all_open_orders(self.config.symbol)
                    logger.info("사전 주문 취소 완료 (강제 청산 준비)")
                except Exception as e:
                    logger.warning(f"사전 주문 취소 실패 (계속 진행): {e}")

                # Re-check position after cancelling (SL may have already filled)
                position = await self.client.get_position(self.config.symbol)
                if not position:
                    logger.info("주문 취소 후 포지션 이미 없음 (SL/TP 체결됨)")
                    return None

            expected_qty = abs(position['position_amt'])
            logger.info(
                f"Closing position: {position['side']} {expected_qty}"
            )
            order = await self.client.close_position(self.config.symbol)

            # Check for partial fill
            if order:
                executed_qty = float(order.get("executedQty", 0))
                fill_ratio = executed_qty / expected_qty if expected_qty > 0 else 1.0
                if fill_ratio < self.PARTIAL_FILL_THRESHOLD:
                    remaining = round(expected_qty - executed_qty, 3)
                    logger.warning(
                        f"부분 체결 감지: {executed_qty}/{expected_qty}, "
                        f"잔여={remaining}"
                    )
                    # Retry with remaining quantity
                    try:
                        side = "SELL" if position['side'] == "LONG" else "BUY"
                        retry_order = await self.client.create_market_order(  # noqa: F841
                            symbol=self.config.symbol,
                            side=side,
                            quantity=remaining,
                        )
                        logger.info(f"잔여 수량 청산 완료: {remaining}")
                        # Merge executed quantities
                        order["executedQty"] = str(expected_qty)
                    except Exception as retry_err:
                        logger.critical(
                            f"잔여 수량 청산 실패 - 수동 확인 필요: {retry_err}"
                        )
                        raise RuntimeError(
                            f"Partial fill retry failed: {retry_err}"
                        ) from retry_err

            logger.info("Position closed successfully")
            return order

        except RuntimeError:
            raise  # Partial fill failure must propagate
        except (BinanceAPIException, ConnectionError):
            raise  # Exchange/network errors must propagate to caller
        except Exception as e:
            logger.error(f"Failed to close position: {e}")
            return None

    def clear_position(self) -> None:
        """Clear current position state.

        Must be called by the bot AFTER all DB writes and PnL tracking
        are complete following a close_position() call.
        """
        self.current_position = None

    async def get_position(self) -> dict | None:
        """Get current position from exchange.

        Returns:
            Position info or None if no position
        """
        try:
            return await self.client.get_position(self.config.symbol)
        except Exception as e:
            logger.error(f"Failed to get position: {e}")
            return None

    async def has_position(self) -> bool:
        """Check if we currently have an open position.

        Returns:
            True if has position, False otherwise
        """
        position = await self.get_position()
        return position is not None

    def calculate_pnl_pct(
        self, entry_price: float, current_price: float, side: str
    ) -> float:
        """Calculate PnL percentage.

        Args:
            entry_price: Entry price
            current_price: Current price
            side: "LONG" or "SHORT"

        Returns:
            PnL percentage
        """
        return _calculate_pnl_pct(entry_price, current_price, side)

    async def check_tp_sl(self, position: dict, current_price: float) -> str | None:
        """Check if TP or SL should be triggered.

        Args:
            position: Position info
            current_price: Current price

        Returns:
            "TP", "SL", or None
        """
        try:
            entry_price = position["entry_price"]
            side = position["side"]

            # Calculate current PnL
            pnl_pct = self.calculate_pnl_pct(entry_price, current_price, side) / 100

            logger.debug(f"Current PnL: {pnl_pct*100:.2f}%")

            # Check TP
            if pnl_pct >= self.config.take_profit_pct:
                logger.info(
                    f"Take profit triggered: {pnl_pct*100:.2f}% "
                    f">= {self.config.take_profit_pct*100:.2f}%"
                )
                return "TP"

            # Check SL
            if pnl_pct <= -self.config.stop_loss_pct:
                logger.info(
                    f"Stop loss triggered: {pnl_pct*100:.2f}% "
                    f"<= -{self.config.stop_loss_pct*100:.2f}%"
                )
                return "SL"

            return None

        except Exception as e:
            logger.error(f"Failed to check TP/SL: {e}")
            return None

    async def check_tp_sl_dynamic(
        self, position: dict, current_price: float
    ) -> str | None:
        """Phase 6.1: ATR 기반 동적 TP/SL 체크.

        ATR을 사용하여 시장 변동성에 따른 동적 TP/SL 레벨 설정.

        Args:
            position: Position info (must include entry_atr)
            current_price: Current price

        Returns:
            "TP", "SL", or None
        """
        try:
            entry_price = position["entry_price"]
            entry_atr = position.get("entry_atr")
            side = position.get("side") or position.get("signal")

            # ATR 정보가 없거나 use_atr_tp_sl이 비활성화면 기존 로직 사용
            use_atr = getattr(self.config, "use_atr_tp_sl", False)
            if not use_atr or not entry_atr:
                return await self.check_tp_sl(position, current_price)

            # ATR 승수 가져오기
            atr_tp_multiplier = getattr(self.config, "atr_tp_multiplier", 2.0)
            atr_sl_multiplier = getattr(self.config, "atr_sl_multiplier", 1.0)

            # 동적 TP/SL 가격 계산
            if side == "LONG":
                tp_price = entry_price + (entry_atr * atr_tp_multiplier)
                sl_price = entry_price - (entry_atr * atr_sl_multiplier)

                if current_price >= tp_price:
                    pnl_pct = ((current_price - entry_price) / entry_price) * 100
                    logger.info(
                        f"ATR TP 도달 (LONG): "
                        f"${current_price:,.2f} >= ${tp_price:,.2f} "
                        f"(ATR={entry_atr:.2f}, "
                        f"multiplier={atr_tp_multiplier}), "
                        f"PnL={pnl_pct:+.2f}%"
                    )
                    return "TP"

                if current_price <= sl_price:
                    pnl_pct = ((current_price - entry_price) / entry_price) * 100
                    logger.info(
                        f"ATR SL 도달 (LONG): "
                        f"${current_price:,.2f} <= ${sl_price:,.2f} "
                        f"(ATR={entry_atr:.2f}, "
                        f"multiplier={atr_sl_multiplier}), "
                        f"PnL={pnl_pct:+.2f}%"
                    )
                    return "SL"

            else:  # SHORT
                tp_price = entry_price - (entry_atr * atr_tp_multiplier)
                sl_price = entry_price + (entry_atr * atr_sl_multiplier)

                if current_price <= tp_price:
                    pnl_pct = ((entry_price - current_price) / entry_price) * 100
                    logger.info(
                        f"ATR TP 도달 (SHORT): "
                        f"${current_price:,.2f} <= ${tp_price:,.2f} "
                        f"(ATR={entry_atr:.2f}, "
                        f"multiplier={atr_tp_multiplier}), "
                        f"PnL={pnl_pct:+.2f}%"
                    )
                    return "TP"

                if current_price >= sl_price:
                    pnl_pct = ((entry_price - current_price) / entry_price) * 100
                    logger.info(
                        f"ATR SL 도달 (SHORT): "
                        f"${current_price:,.2f} >= ${sl_price:,.2f} "
                        f"(ATR={entry_atr:.2f}, "
                        f"multiplier={atr_sl_multiplier}), "
                        f"PnL={pnl_pct:+.2f}%"
                    )
                    return "SL"

            logger.debug(
                f"ATR TP/SL 미달: 현재=${current_price:,.2f}, "
                f"TP=${tp_price:,.2f}, SL=${sl_price:,.2f}"
            )
            return None

        except Exception as e:
            logger.error(f"ATR TP/SL 체크 실패: {e}")
            # Fallback to regular check
            return await self.check_tp_sl(position, current_price)

    async def _place_exchange_tp_sl(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        entry_atr: float | None = None,
    ) -> bool:
        """거래소 측 STOP_MARKET/TAKE_PROFIT_MARKET 주문 배치.

        포지션 오픈 후 호출하여 거래소 측에서 TP/SL을 관리하도록 합니다.
        SL 배치는 필수이며, TP 배치 실패는 경고만 남깁니다.

        Args:
            symbol: 거래쌍
            side: 포지션 방향 ("LONG" or "SHORT")
            quantity: 포지션 수량
            entry_price: 진입 가격
            entry_atr: ATR 값 (None이면 고정 퍼센트 사용)

        Returns:
            True if SL placed successfully, False if SL failed
        """
        close_side = "SELL" if side == "LONG" else "BUY"

        tp_price, sl_price = self._calculate_tp_sl_prices(
            side, entry_price, entry_atr
        )

        # 가격 유효성 검증 (방어)
        if sl_price <= 0 or tp_price <= 0:
            logger.error(
                f"TP/SL 가격 유효하지 않음: TP={tp_price}, SL={sl_price} "
                f"(entry={entry_price}). 주문 스킵."
            )
            return False

        # SL 주문 (필수 - 실패 시 False 반환)
        try:
            await self.client.create_stop_market_order(
                symbol=symbol,
                side=close_side,
                quantity=quantity,
                stop_price=sl_price,
            )
        except Exception as e:
            logger.error(f"거래소 SL 주문 배치 실패 (필수): {e}")
            return False

        # TP 주문 (비필수 - 실패 시 경고만)
        try:
            await self.client.create_take_profit_market_order(
                symbol=symbol,
                side=close_side,
                quantity=quantity,
                stop_price=tp_price,
            )
        except Exception as e:
            logger.warning(f"거래소 TP 주문 배치 실패 (비필수): {e}")

        logger.info(
            f"거래소 TP/SL 주문 배치 완료: "
            f"TP=, SL= ({side})"
        )
        return True

    def check_timecut(self, position: dict) -> bool:
        """Check if position should be closed due to timecut (2 hours).

        Args:
            position: Position info with entry_time

        Returns:
            True if timecut should be triggered
        """
        try:
            if "entry_time" not in position or position["entry_time"] is None:
                logger.warning(
                    "entry_time이 없어 타임컷 체크 불가"
                )
                return False

            entry_time = position["entry_time"]
            current_time = datetime.now()
            time_elapsed = current_time - entry_time

            # Get timecut duration from config (default 120 minutes = 2 hours)
            timecut_minutes = getattr(self.config, "time_cut_minutes", 120)
            timecut_duration = timedelta(minutes=timecut_minutes)

            logger.debug(
                f"Time elapsed: {time_elapsed.total_seconds()/60:.1f} minutes "
                f"(Timecut at {timecut_minutes} minutes)"
            )

            # Check if timecut should be triggered
            if time_elapsed >= timecut_duration:
                logger.info(
                    f"Timecut triggered: {time_elapsed.total_seconds()/60:.1f} minutes "
                    f">= {timecut_minutes} minutes"
                )
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to check timecut: {e}")
            return False
