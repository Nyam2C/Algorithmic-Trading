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
    MIN_STOP_PRICE = 0.10  # Binance minimum stop price (safety margin)
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

        # APEX-V Phase A-4: 분할 TP 소프트웨어 모니터링 상태
        self._pending_split_tp_state: dict | None = None

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
        self, current_price: float, capital: float | None = None,
        dynamic_size_pct: float | None = None,
    ) -> float:
        """Calculate position size based on configuration (동기 버전 - 테스트 호환).

        Args:
            current_price: Current market price
            capital: Capital to use (None = default 1000.0)
            dynamic_size_pct: 동적 포지션 크기 비율 (None = config 기본값)

        Returns:
            Position quantity in base asset
        """
        # capital이 제공되지 않으면 기본값 사용 (테스트 호환성)
        if capital is None:
            capital = 1000.0
            logger.warning("기본 자본 $1000 사용 - use_real_balance 설정 권장")

        # Calculate position value in USDT
        size_pct = (
            dynamic_size_pct
            if dynamic_size_pct is not None
            else self.config.position_size_pct
        )
        position_value = capital * size_pct * self.config.leverage

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
        self, current_price: float, dynamic_size_pct: float | None = None,
    ) -> float:
        """Calculate position size based on real account balance (비동기 버전).

        Phase 5.1: 실제 잔고 기반 포지션 사이징

        Args:
            current_price: Current market price
            dynamic_size_pct: 동적 포지션 크기 비율 (None = config 기본값)

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

        return self._calculate_position_size(current_price, capital, dynamic_size_pct)

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

    async def _prepare_and_open_position(  # noqa: PLR0912
        self,
        signal: str,
        current_price: float,
        entry_atr: float | None = None,
        order_type: str = "MARKET",  # noqa: ARG002
        use_maker: bool = False,
        dynamic_size_pct: float | None = None,
        microprice_data: dict | None = None,
    ) -> dict | None:
        """포지션 오픈 공통 로직.

        포지션 체크, 레버리지 설정, 사이징, 주문 생성, 포지션 저장을 처리합니다.

        Args:
            signal: "LONG" or "SHORT"
            current_price: Current market price
            entry_atr: ATR value at entry (Phase 6.1: for dynamic TP/SL)
            order_type: "MARKET" or "MAKER"
            use_maker: Use Maker order (limit order) if True
            dynamic_size_pct: 동적 포지션 크기 비율 (None = config 기본값)
            microprice_data: Microprice 지정가 데이터 (None = Market 주문)

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
        quantity = await self._calculate_position_size_with_balance(
            current_price, dynamic_size_pct,
        )

        # Determine order side
        side = SIDE_BUY if signal == "LONG" else SIDE_SELL

        # Create order based on type
        if use_maker:
            order = await self._create_maker_order(
                signal, side, quantity, current_price
            )
        elif microprice_data is not None:
            order = await self._execute_microprice_limit(
                signal, side, quantity, current_price, microprice_data
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

        # Slippage detection for market orders (skip for maker/microprice limit)
        if not use_maker and microprice_data is None and order:
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

            # 슬리피지 감지 후 가격 유효성 검증
            if current_price <= 0:
                logger.critical(
                    f"슬리피지 감지 후 가격 무효: {current_price}. 포지션 청산."
                )
                try:
                    await self.client.close_position(self.config.symbol)
                except Exception:
                    logger.exception("무효 가격 후 포지션 청산 실패")
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

        # APEX-V: 분할 TP 상태 주입
        if self._pending_split_tp_state and self.current_position:
            self.current_position["split_tp_state"] = self._pending_split_tp_state
            self._pending_split_tp_state = None

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

    async def _execute_microprice_limit(
        self,
        signal: str,
        side: str,
        quantity: float,
        current_price: float,  # noqa: ARG002
        microprice_data: dict,
    ) -> dict:
        """Microprice 기반 지정가 주문 실행 (Wait -> Slide -> Fallback).

        Args:
            signal: "LONG" or "SHORT"
            side: SIDE_BUY or SIDE_SELL
            quantity: 주문 수량
            current_price: 현재 시장가 (fallback용)
            microprice_data: best_bid, best_ask, bid_vol, ask_vol,
                             atr_1m, liquidity_tier, offset_factor, slide_factor

        Returns:
            체결된 주문 정보
        """
        from src.trading.microprice import (  # noqa: PLC0415
            WAIT_CONFIG,
            calculate_limit_price,
            calculate_microprice,
        )

        best_bid = microprice_data["best_bid"]
        best_ask = microprice_data["best_ask"]
        bid_vol = microprice_data["bid_vol"]
        ask_vol = microprice_data["ask_vol"]
        atr_1m = microprice_data["atr_1m"]
        tier = microprice_data.get("liquidity_tier", "medium")
        offset_factor = microprice_data.get("offset_factor", 0.1)
        slide_factor = microprice_data.get("slide_factor", 0.5)
        tier_config = WAIT_CONFIG[tier]

        # 1. Microprice 계산
        mp = calculate_microprice(best_bid, best_ask, bid_vol, ask_vol)
        if mp is None:
            logger.warning("Microprice 계산 실패 — Market fallback")
            return await self.client.create_market_order(
                symbol=self.config.symbol, side=side, quantity=quantity,
            )

        # 2. 1차 지정가 주문
        limit_price = calculate_limit_price(mp, signal, atr_1m, offset_factor)
        logger.info(
            f"Microprice limit ({tier}): {signal} {quantity} "
            f"@ ${limit_price:,.2f} (mp=${mp:,.2f})"
        )
        order = await self.client.create_limit_order(
            symbol=self.config.symbol, side=side,
            quantity=quantity, price=limit_price,
        )

        # 3. 1차 대기
        filled = await self._wait_for_fill(
            order["orderId"], timeout=tier_config["wait_seconds"]
        )
        if filled:
            return order

        # 4. 미체결 → 취소 → Slide
        await self.client.cancel_order(self.config.symbol, order["orderId"])

        slid_price = calculate_limit_price(
            mp, signal, atr_1m, offset_factor * slide_factor
        )
        logger.info(f"Microprice slide: ${limit_price:,.2f} → ${slid_price:,.2f}")
        order = await self.client.create_limit_order(
            symbol=self.config.symbol, side=side,
            quantity=quantity, price=slid_price,
        )

        # 5. 2차 대기
        filled = await self._wait_for_fill(
            order["orderId"], timeout=tier_config["slide_wait_seconds"]
        )
        if filled:
            return order

        # 6. 최종 미체결 → 취소 → Market 또는 포기
        await self.client.cancel_order(self.config.symbol, order["orderId"])

        if tier_config["allow_market_fallback"]:
            logger.warning("Microprice limit 미체결 — Market fallback")
            return await self.client.create_market_order(
                symbol=self.config.symbol, side=side, quantity=quantity,
            )

        # Low liquidity: Market 금지 → 진입 포기
        raise RuntimeError(
            f"Microprice limit 미체결 (low liquidity) — 진입 포기 "
            f"(slid=${slid_price:,.2f})"
        )

    async def open_position(
        self, signal: str, current_price: float, entry_atr: float | None = None,
        dynamic_size_pct: float | None = None,
        microprice_data: dict | None = None,
    ) -> dict | None:
        """Open a new position based on signal.

        Args:
            signal: "LONG" or "SHORT"
            current_price: Current market price
            entry_atr: ATR value at entry (Phase 6.1: for dynamic TP/SL)
            dynamic_size_pct: 동적 포지션 크기 비율 (None = config 기본값)
            microprice_data: Microprice 지정가 데이터 (None = Market 주문)

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
                dynamic_size_pct=dynamic_size_pct,
                microprice_data=microprice_data,
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
            dynamic_size_pct: 동적 포지션 크기 비율 (None = config 기본값)

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

        # APEX-V: 분할 TP 모드
        use_split_tp = getattr(self.config, "use_split_tp", False)
        if use_split_tp and entry_atr:
            return await self._place_split_tp_sl(
                symbol, side, quantity, entry_price, entry_atr
            )

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

        # 거래소 최소 가격 검증 (-4013 방지)
        if sl_price < self.MIN_STOP_PRICE:
            logger.error(
                f"SL 가격이 거래소 최소가 미만: {sl_price} < {self.MIN_STOP_PRICE} "
                f"(entry={entry_price}). SL 배치 스킵."
            )
            return False
        if tp_price < self.MIN_STOP_PRICE:
            logger.warning(
                f"TP 가격이 거래소 최소가 미만: {tp_price} < {self.MIN_STOP_PRICE}. "
                f"TP 스킵."
            )
            tp_price = 0  # TP 스킵 플래그

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

        # TP 주문 (비필수 - 실패 시 경고만, tp_price=0이면 스킵)
        if tp_price > 0:
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

    async def _place_split_tp_sl(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        entry_atr: float | None = None,
    ) -> bool:
        """분할 TP 소프트웨어 모니터링 + exchange-side SL 배치.

        Exchange-side TP는 closePosition 버그로 부분 청산 불가.
        TP 레벨을 소프트웨어 상태로 관리하고, SL만 거래소에 배치.

        Args:
            symbol: 거래쌍
            side: 포지션 방향 ("LONG" or "SHORT")
            quantity: 전체 포지션 수량
            entry_price: 진입 가격
            entry_atr: ATR 값

        Returns:
            True if SL placed successfully
        """
        close_side = "SELL" if side == "LONG" else "BUY"

        # SL 가격 계산 (전체 물량)
        _, sl_price = self._calculate_tp_sl_prices(side, entry_price, entry_atr)

        # SL 유효성 검증
        if sl_price <= 0 or sl_price < self.MIN_STOP_PRICE:
            logger.error(f"분할 TP: SL 가격 무효 ({sl_price})")
            return False

        # SL 주문 (closePosition=True, 크래시 보호)
        try:
            await self.client.create_stop_market_order(
                symbol=symbol,
                side=close_side,
                quantity=quantity,
                stop_price=sl_price,
            )
        except Exception as e:
            logger.error(f"분할 TP: SL 주문 실패 (필수): {e}")
            return False

        # TP 레벨을 소프트웨어 상태로 저장 (exchange 주문 없음)
        ratios = getattr(self.config, "split_tp_ratios", [0.5, 0.3, 0.2])
        atr_muls = getattr(self.config, "split_tp_atr_multipliers", [1.0, 1.5, 2.5])

        levels: list[dict] = []
        for ratio, atr_mul in zip(ratios, atr_muls, strict=False):
            if entry_atr:
                if side == "LONG":
                    tp_price = round(entry_price + entry_atr * atr_mul, 2)
                else:
                    tp_price = round(entry_price - entry_atr * atr_mul, 2)
            else:
                tp_pct = self.config.take_profit_pct * (len(levels) + 1)
                if side == "LONG":
                    tp_price = round(entry_price * (1 + tp_pct), 2)
                else:
                    tp_price = round(entry_price * (1 - tp_pct), 2)

            levels.append({
                "ratio": ratio,
                "atr_mul": atr_mul,
                "price": tp_price,
                "hit": False,
            })

        self._pending_split_tp_state = {
            "enabled": True,
            "levels": levels,
            "original_quantity": quantity,
            "remaining_quantity": quantity,
            "accumulated_pnl_usd": 0.0,
            "sl_moved_to_be": False,
        }

        logger.info(
            f"분할 TP 상태 초기화: {len(levels)}레벨, "
            f"SL=${sl_price:,.2f} ({side})"
        )
        return True

    async def check_split_tp(
        self, current_price: float
    ) -> str | None:
        """분할 TP 소프트웨어 모니터링.

        current_position의 split_tp_state를 확인하여
        TP 레벨 도달 여부를 판단합니다.

        Args:
            current_price: 현재 가격

        Returns:
            "SPLIT_TP1", "SPLIT_TP2" (부분 청산),
            "TP" (마지막 레벨, 전체 청산),
            "SL" (손절),
            None (미달)
        """
        if not self.current_position:
            return None

        state = self.current_position.get("split_tp_state")
        if not state or not state.get("enabled"):
            # split_tp_state 없으면 기존 로직 위임
            return await self.check_tp_sl_dynamic(self.current_position, current_price)

        side = str(
            self.current_position.get("side") or self.current_position.get("signal")
        )
        entry_price = self.current_position["entry_price"]

        # SL 체크
        sl_result = self._check_split_sl(state, side, entry_price, current_price)
        if sl_result:
            return sl_result

        # TP 레벨 체크: 첫 번째 hit=False 레벨
        return self._check_split_tp_levels(state, side, current_price)

    def _check_split_sl(
        self, state: dict, side: str, entry_price: float, current_price: float
    ) -> str | None:
        """분할 TP SL 체크 헬퍼."""
        sl_price = (
            entry_price if state.get("sl_moved_to_be")
            else self.current_position.get("sl_price", 0.0)  # type: ignore[union-attr]
        )
        if sl_price <= 0:
            return None

        be_tag = " (BE)" if state.get("sl_moved_to_be") else ""
        hit = (
            (side == "LONG" and current_price <= sl_price)
            or (side == "SHORT" and current_price >= sl_price)
        )
        if hit:
            logger.info(
                f"분할 TP SL 도달 ({side}): "
                f"${current_price:,.2f} vs ${sl_price:,.2f}{be_tag}"
            )
            return "SL"
        return None

    @staticmethod
    def _check_split_tp_levels(
        state: dict, side: str, current_price: float
    ) -> str | None:
        """분할 TP 레벨 도달 체크 헬퍼."""
        levels = state.get("levels", [])
        for i, level in enumerate(levels):
            if level["hit"]:
                continue

            tp_price = level["price"]
            is_last = i == len(levels) - 1

            reached = (
                (side == "LONG" and current_price >= tp_price)
                or (side == "SHORT" and current_price <= tp_price)
            )
            if reached:
                if is_last:
                    logger.info(
                        f"분할 TP 최종 도달: "
                        f"${current_price:,.2f} vs ${tp_price:,.2f}"
                    )
                    return "TP"
                logger.info(
                    f"분할 TP{i+1} 도달: "
                    f"${current_price:,.2f} vs ${tp_price:,.2f}"
                )
                return f"SPLIT_TP{i+1}"

            # 가격 순서 상 이 레벨 미달이면 이후도 미달
            break

        return None

    async def execute_partial_close(
        self, tp_level_index: int, current_price: float
    ) -> dict | None:
        """분할 TP 부분 청산 실행.

        Args:
            tp_level_index: TP 레벨 인덱스 (0-based)
            current_price: 현재 가격

        Returns:
            주문 결과 또는 None
        """
        if not self.current_position:
            return None

        state = self.current_position.get("split_tp_state")
        if not state:
            return None

        levels = state.get("levels", [])
        if tp_level_index >= len(levels):
            return None

        level = levels[tp_level_index]
        if level["hit"]:
            return None

        side = self.current_position.get("side") or self.current_position.get("signal")
        entry_price = self.current_position["entry_price"]
        close_side = "SELL" if side == "LONG" else "BUY"

        close_qty = round(state["original_quantity"] * level["ratio"], 3)

        # 최소 주문 수량 미만이면 hit 마크하고 스킵
        if close_qty < self.MIN_ORDER_QTY:
            logger.warning(
                f"분할 TP{tp_level_index+1}: 수량 {close_qty} < "
                f"최소 {self.MIN_ORDER_QTY}, 스킵 (hit 마크)"
            )
            level["hit"] = True
            return None

        try:
            order = await self.client.create_market_order(
                symbol=self.config.symbol,
                side=close_side,
                quantity=close_qty,
            )
        except Exception as e:
            logger.error(f"분할 TP{tp_level_index+1} 부분 청산 실패: {e}")
            return None

        # State 업데이트
        level["hit"] = True
        state["remaining_quantity"] = round(
            state["remaining_quantity"] - close_qty, 3
        )

        # PnL 누적
        if side == "LONG":
            partial_pnl = (current_price - entry_price) * close_qty
        else:
            partial_pnl = (entry_price - current_price) * close_qty

        # 수수료 추정 차감
        _fee_rate = getattr(self.config, "estimated_fee_rate", 0.0008)
        if _fee_rate > 0:
            partial_pnl -= close_qty * current_price * _fee_rate

        state["accumulated_pnl_usd"] += partial_pnl

        logger.info(
            f"분할 TP{tp_level_index+1} 부분 청산: "
            f"{close_qty} @ ${current_price:,.2f}, "
            f"PnL=${partial_pnl:+,.2f}, "
            f"누적=${state['accumulated_pnl_usd']:+,.2f}, "
            f"잔여={state['remaining_quantity']}"
        )

        # TP1 후 SL을 break-even으로 이동
        if tp_level_index == 0 and not state.get("sl_moved_to_be"):
            await self._move_sl_to_breakeven()

        return order

    async def _move_sl_to_breakeven(self) -> bool:
        """SL을 break-even (진입가)으로 이동.

        기존 SL을 취소하고 진입가에 새 SL을 배치합니다.

        Returns:
            True if successful
        """
        if not self.current_position:
            return False

        state = self.current_position.get("split_tp_state")
        if not state:
            return False

        side = self.current_position.get("side") or self.current_position.get("signal")
        entry_price = self.current_position["entry_price"]
        close_side = "SELL" if side == "LONG" else "BUY"
        remaining_qty = state["remaining_quantity"]

        # 기존 SL 주문 취소
        try:
            await self.client.cancel_all_open_orders(self.config.symbol)
        except Exception as e:
            logger.warning(f"BE SL 이동: 기존 주문 취소 실패: {e}")
            return False

        # 새 SL을 진입가로 배치
        try:
            await self.client.create_stop_market_order(
                symbol=self.config.symbol,
                side=close_side,
                quantity=remaining_qty,
                stop_price=entry_price,
            )
        except Exception as e:
            logger.warning(f"BE SL 배치 실패 (원래 SL 유효할 수 있음): {e}")
            return False

        self.current_position["sl_price"] = entry_price
        state["sl_moved_to_be"] = True

        logger.info(
            f"SL → break-even 이동 완료: ${entry_price:,.2f}, "
            f"잔여 수량={remaining_qty}"
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
