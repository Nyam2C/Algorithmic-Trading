"""
Trading executor for opening and closing positions
"""
from typing import Dict, Optional
from datetime import datetime, timedelta
from binance.enums import (
    SIDE_BUY,
    SIDE_SELL,
)
from loguru import logger


class TradingExecutor:
    """Execute trades on Binance Futures"""

    def __init__(self, binance_client, config):
        """
        Initialize trading executor

        Args:
            binance_client: BinanceTestnetClient instance
            config: TradingConfig instance
        """
        self.client = binance_client
        self.config = config
        self.current_position: Optional[Dict] = None

        logger.info("Trading executor initialized")

    async def setup_leverage(self) -> bool:
        """
        Set leverage for the trading symbol

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

    def _calculate_position_size(self, current_price: float) -> float:
        """
        Calculate position size based on configuration

        Args:
            current_price: Current market price

        Returns:
            Position quantity in base asset
        """
        # Get account balance
        # For MVP, we'll use a simplified calculation
        # In Sprint 2, we'll fetch real balance from exchange

        # Calculate position value in USDT
        capital = 1000.0  # Simplified for Sprint 1 (will get from balance in Sprint 2)
        position_value = capital * self.config.position_size_pct * self.config.leverage

        # Calculate quantity
        quantity = position_value / current_price

        # Round to appropriate precision (BTC = 3 decimals)
        quantity = round(quantity, 3)

        logger.info(
            f"Position size calculated: {quantity} @ ${current_price:,.2f} "
            f"= ${position_value:,.2f} (with {self.config.leverage}x leverage)"
        )

        return quantity

    async def open_position(
        self, signal: str, current_price: float
    ) -> Optional[Dict]:
        """
        Open a new position based on signal

        Args:
            signal: "LONG" or "SHORT"
            current_price: Current market price

        Returns:
            Order details or None if failed
        """
        try:
            # Check if we already have a position
            existing_position = await self.client.get_position(self.config.symbol)
            if existing_position:
                logger.warning(
                    f"Already have a {existing_position['side']} position, skipping"
                )
                return None

            # Setup leverage
            await self.setup_leverage()

            # Calculate position size
            quantity = self._calculate_position_size(current_price)

            # Determine order side
            side = SIDE_BUY if signal == "LONG" else SIDE_SELL

            # Create market order
            logger.info(f"Opening {signal} position: {side} {quantity} {self.config.symbol}")
            order = await self.client.create_market_order(
                symbol=self.config.symbol,
                side=side,
                quantity=quantity,
            )

            # Store position info with entry time
            self.current_position = {
                "signal": signal,
                "side": side,
                "quantity": quantity,
                "entry_price": current_price,
                "order_id": order["orderId"],
                "entry_time": datetime.now(),  # Add entry time for timecut
            }

            logger.info(
                f"Position opened: {signal} {quantity} @ ${current_price:,.2f}"
            )

            return order

        except Exception as e:
            logger.error(f"Failed to open position: {e}")
            return None

    async def close_position(self) -> Optional[Dict]:
        """
        Close current position

        Returns:
            Order details or None if failed
        """
        try:
            # Check if we have a position
            position = await self.client.get_position(self.config.symbol)
            if not position:
                logger.info("No position to close")
                return None

            # Close position
            logger.info(
                f"Closing position: {position['side']} {abs(position['position_amt'])}"
            )
            order = await self.client.close_position(self.config.symbol)

            # Clear stored position
            self.current_position = None

            logger.info("Position closed successfully")
            return order

        except Exception as e:
            logger.error(f"Failed to close position: {e}")
            return None

    async def get_position(self) -> Optional[Dict]:
        """
        Get current position from exchange

        Returns:
            Position info or None if no position
        """
        try:
            position = await self.client.get_position(self.config.symbol)
            return position
        except Exception as e:
            logger.error(f"Failed to get position: {e}")
            return None

    async def has_position(self) -> bool:
        """
        Check if we currently have an open position

        Returns:
            True if has position, False otherwise
        """
        position = await self.get_position()
        return position is not None

    def calculate_pnl_pct(self, entry_price: float, current_price: float, side: str) -> float:
        """
        Calculate PnL percentage

        Args:
            entry_price: Entry price
            current_price: Current price
            side: "LONG" or "SHORT"

        Returns:
            PnL percentage
        """
        if side == "LONG":
            pnl_pct = ((current_price - entry_price) / entry_price) * 100
        else:  # SHORT
            pnl_pct = ((entry_price - current_price) / entry_price) * 100

        return pnl_pct

    async def check_tp_sl(self, position: Dict, current_price: float) -> Optional[str]:
        """
        Check if TP or SL should be triggered

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
                logger.info(f"Take profit triggered: {pnl_pct*100:.2f}% >= {self.config.take_profit_pct*100:.2f}%")
                return "TP"

            # Check SL
            if pnl_pct <= -self.config.stop_loss_pct:
                logger.info(f"Stop loss triggered: {pnl_pct*100:.2f}% <= -{self.config.stop_loss_pct*100:.2f}%")
                return "SL"

            return None

        except Exception as e:
            logger.error(f"Failed to check TP/SL: {e}")
            return None

    def check_timecut(self, position: Dict) -> bool:
        """
        Check if position should be closed due to timecut (2 hours)

        Args:
            position: Position info with entry_time

        Returns:
            True if timecut should be triggered
        """
        try:
            if "entry_time" not in position:
                logger.warning("Position does not have entry_time, skipping timecut check")
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
