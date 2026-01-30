"""
High-Win Survival System - Main Entry Point
Sprint 1: Paper Trading MVP
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

import aiohttp
from loguru import logger

# Import our modules
from src.config import get_config
from src.exchange.binance import BinanceTestnetClient
from src.data.indicators import analyze_market
from src.ai.rule_based import RuleBasedSignalGenerator
from src.ai.signals import (
    validate_signal,
    should_enter_trade,
    get_signal_emoji,
    get_signal_color,
)
from src.trading.executor import TradingExecutor
from src.discord_bot.bot import start_discord_bot
from src.storage.trade_history import TradeHistoryDB


def setup_logging():
    """
    Configure structured JSON logging for Loki/Promtail
    """
    # Remove default logger
    logger.remove()

    # Create logs directory
    Path("logs").mkdir(exist_ok=True)

    # Console logger (human-readable)
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
        colorize=True,
    )

    # JSON file logger (bot.log) - for Promtail
    logger.add(
        "logs/bot.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        rotation="100 MB",
        retention="30 days",
        compression="zip",
        serialize=False,  # Use simple format instead of JSON to avoid errors
    )

    # Error-only logger (error.log)
    logger.add(
        "logs/error.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="ERROR",
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        serialize=False,
    )


async def send_discord_embed(
    webhook_url: str, title: str, description: str, color: int, fields: list | None = None
) -> bool:
    """
    Send Discord embed message

    Args:
        webhook_url: Discord webhook URL
        title: Embed title
        description: Embed description
        color: Embed color (int)
        fields: List of field dicts (optional)

    Returns:
        True if successful
    """
    if not webhook_url:
        logger.warning("DISCORD_WEBHOOK_URL not set")
        return False

    embed = {
        "title": title,
        "description": description,
        "color": color,
        "timestamp": datetime.utcnow().isoformat(),
    }

    if fields:
        embed["fields"] = fields

    payload = {"embeds": [embed], "username": "Trading Bot"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload) as resp:
                if resp.status == 204:
                    logger.debug("Discord embed sent successfully")
                    return True
                else:
                    logger.error(f"Discord webhook failed: {resp.status}")
                    return False
    except Exception as e:
        logger.error(f"Discord webhook error: {e}")
        return False


async def trading_loop():
    """Main trading loop"""
    logger.info("=" * 60)
    logger.info("High-Win Survival System - Starting")
    logger.info("=" * 60)

    # Load configuration
    config = get_config()

    # Initialize shared bot state for Discord bot
    bot_state = {
        "is_running": True,
        "is_paused": False,
        "emergency_close": False,
        "uptime_start": datetime.now(),
        "current_price": 0,
        "last_signal": "WAIT",
        "last_signal_time": None,
        "position": None,
        "symbol": config.symbol,
        "leverage": config.leverage,
    }

    # Initialize PostgreSQL database
    trade_db = None
    if config.database_url:
        try:
            trade_db = TradeHistoryDB(config.database_url)
            await trade_db.connect()
            logger.info("PostgreSQL trade history database connected")
        except Exception as e:
            logger.error(f"Failed to connect to trade database: {e}")
            logger.warning("Continuing without trade history database")
    else:
        logger.warning("DATABASE_URL not set - trade history will not be saved")

    # Start Discord bot in background
    discord_task = None
    if config.discord_bot_token and config.discord_bot_token != "your_bot_token_here":
        try:
            discord_task = asyncio.create_task(
                start_discord_bot(
                    token=config.discord_bot_token,
                    bot_state=bot_state,
                    trade_db=trade_db
                )
            )
            logger.info("Discord bot started in background")
        except Exception as e:
            logger.error(f"Failed to start Discord bot: {e}")
            logger.warning("Continuing without Discord bot")
    else:
        logger.warning("DISCORD_BOT_TOKEN not set - Discord commands disabled")

    # Initialize clients
    binance = BinanceTestnetClient(
        api_key=config.binance_api_key,
        secret_key=config.binance_secret_key,
        testnet=config.binance_testnet,
    )

    # Use rule-based signal generator (temporary fallback)
    # gemini = GeminiSignalGenerator(
    #     api_key=config.gemini_api_key,
    #     model=config.gemini_model,
    #     temperature=config.gemini_temperature,
    # )
    # PRODUCTION MODE: Standard parameters for reliable signal generation
    signal_generator = RuleBasedSignalGenerator(
        rsi_oversold=35.0,      # RSI 35 이하에서 LONG 신호
        rsi_overbought=65.0,    # RSI 65 이상에서 SHORT 신호
        volume_threshold=1.2,   # 평균 대비 1.2배 이상 거래량 필요
    )

    executor = TradingExecutor(binance_client=binance, config=config)

    # Send startup notification
    await send_discord_embed(
        webhook_url=config.discord_webhook_url,
        title="🤖 Bot Started",
        description=f"**{config.bot_name}** started successfully\n⚠️ Using **Rule-Based** signals (Gemini API unavailable)",
        color=0x00FF00,
        fields=[
            {"name": "Symbol", "value": config.symbol, "inline": True},
            {"name": "Leverage", "value": f"{config.leverage}x", "inline": True},
            {
                "name": "Mode",
                "value": "Testnet" if config.binance_testnet else "LIVE",
                "inline": True,
            },
            {"name": "Signal Method", "value": "Rule-Based (RSI + MA)", "inline": False},
        ],
    )

    logger.info("Initialization complete")
    logger.info(f"Trading {config.symbol} with {config.leverage}x leverage")
    logger.info(f"Loop interval: {config.loop_interval_seconds} seconds")

    # Main loop
    loop_count = 0
    while True:
        try:
            loop_count += 1
            logger.info(f"\n{'='*60}")
            logger.info(f"Loop #{loop_count} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"{'='*60}")

            # 1. Fetch market data
            logger.info("Step 1: Fetching market data...")
            current_price = await binance.get_current_price(config.symbol)
            klines = await binance.get_klines(config.symbol, limit=24)
            ticker_24h = await binance.get_ticker_24h(config.symbol)

            # 2. Calculate indicators
            logger.info("Step 2: Calculating indicators...")
            market_data = analyze_market(klines, ticker_24h, current_price)

            # 3. Generate signal (rule-based)
            logger.info("Step 3: Generating signal (rule-based)...")
            signal = signal_generator.get_signal(market_data)

            if not validate_signal(signal):
                logger.warning(f"Invalid signal '{signal}', defaulting to WAIT")
                signal = "WAIT"

            # Log signal with structured data for Grafana
            logger.bind(
                event="SIGNAL",
                signal=signal,
                price=current_price,
                rsi=market_data.get("rsi"),
                ma_7=market_data.get("ma_7"),
                ma_25=market_data.get("ma_25"),
                volume_ratio=market_data.get("volume_ratio"),
            ).info(f"Signal: {get_signal_emoji(signal)} {signal}")

            # Update bot state for Discord bot
            bot_state["current_price"] = current_price
            bot_state["last_signal"] = signal
            bot_state["last_signal_time"] = datetime.now()
            bot_state["market_data"] = market_data

            # 4. Check for emergency close command
            if bot_state.get("emergency_close", False):
                logger.warning("Emergency close triggered by Discord command!")
                current_position = await executor.get_position()
                if current_position:
                    order = await executor.close_position()
                    if order:
                        entry_price = current_position["entry_price"]
                        pnl_pct = executor.calculate_pnl_pct(
                            entry_price, current_price, current_position["side"]
                        )
                        pnl_usd = (current_price - entry_price) * current_position["position_amt"] * config.leverage

                        # Record to database
                        if trade_db and executor.current_position and executor.current_position.get("trade_id"):
                            entry_time = executor.current_position.get("entry_time", datetime.now())
                            duration = int((datetime.now() - entry_time).total_seconds() / 60)
                            await trade_db.add_exit(
                                trade_id=executor.current_position["trade_id"],
                                exit_time=datetime.now(),
                                exit_price=current_price,
                                exit_reason="MANUAL",
                                pnl=pnl_usd,
                                pnl_pct=pnl_pct,
                                duration_minutes=duration
                            )

                        await send_discord_embed(
                            webhook_url=config.discord_webhook_url,
                            title="🚨 Emergency Close",
                            description=f"**{current_position['side']}** position closed via emergency command",
                            color=0xFF0000,
                            fields=[
                                {"name": "Entry Price", "value": f"${entry_price:,.2f}", "inline": True},
                                {"name": "Exit Price", "value": f"${current_price:,.2f}", "inline": True},
                                {"name": "PnL", "value": f"{pnl_pct:+.2f}%", "inline": True},
                            ],
                        )
                bot_state["emergency_close"] = False
                bot_state["is_paused"] = True
                logger.info("Bot paused after emergency close")
                continue

            # 5. Check current position
            logger.info("Step 4: Checking position...")
            current_position = await executor.get_position()
            has_position = current_position is not None

            # Update bot state with position info
            bot_state["position"] = current_position

            if has_position and current_position is not None:
                logger.info(
                    f"Current position: {current_position['side']} "
                    f"{abs(current_position['position_amt'])} @ "
                    f"${current_position['entry_price']:,.2f}"
                )

                # Check Timecut first
                if executor.current_position and executor.check_timecut(executor.current_position):
                    logger.info("Exit condition met: TIMECUT")

                    # Close position
                    order = await executor.close_position()

                    if order:
                        # Calculate PnL
                        entry_price = current_position["entry_price"]
                        pnl_pct = executor.calculate_pnl_pct(
                            entry_price, current_price, current_position["side"]
                        )
                        pnl_usd = (current_price - entry_price) * current_position["position_amt"] * config.leverage

                        # Record to database
                        if trade_db and executor.current_position and executor.current_position.get("trade_id"):
                            entry_time = executor.current_position.get("entry_time", datetime.now())
                            duration = int((datetime.now() - entry_time).total_seconds() / 60)
                            await trade_db.add_exit(
                                trade_id=executor.current_position["trade_id"],
                                exit_time=datetime.now(),
                                exit_price=current_price,
                                exit_reason="TIME_CUT",
                                pnl=pnl_usd,
                                pnl_pct=pnl_pct,
                                duration_minutes=duration
                            )

                        # Send Discord notification
                        await send_discord_embed(
                            webhook_url=config.discord_webhook_url,
                            title="⏰ Position Closed - TIMECUT",
                            description=f"**{current_position['side']}** position closed due to timecut (2 hours)",
                            color=0xFFA500,  # Orange color
                            fields=[
                                {
                                    "name": "Entry Price",
                                    "value": f"${entry_price:,.2f}",
                                    "inline": True,
                                },
                                {
                                    "name": "Exit Price",
                                    "value": f"${current_price:,.2f}",
                                    "inline": True,
                                },
                                {
                                    "name": "PnL",
                                    "value": f"{pnl_pct:+.2f}%",
                                    "inline": True,
                                },
                                {
                                    "name": "Reason",
                                    "value": "Time limit reached (2 hours)",
                                    "inline": False,
                                },
                            ],
                        )
                    continue  # Skip TP/SL check and signal execution

                # Check TP/SL
                tp_sl_reason = await executor.check_tp_sl(current_position, current_price)
                if tp_sl_reason:
                    logger.info(f"Exit condition met: {tp_sl_reason}")

                    # Close position
                    order = await executor.close_position()

                    if order:
                        # Calculate PnL
                        entry_price = current_position["entry_price"]
                        pnl_pct = executor.calculate_pnl_pct(
                            entry_price, current_price, current_position["side"]
                        )
                        pnl_usd = (current_price - entry_price) * current_position["position_amt"] * config.leverage

                        # Record to database
                        if trade_db and executor.current_position and executor.current_position.get("trade_id"):
                            entry_time = executor.current_position.get("entry_time", datetime.now())
                            duration = int((datetime.now() - entry_time).total_seconds() / 60)
                            await trade_db.add_exit(
                                trade_id=executor.current_position["trade_id"],
                                exit_time=datetime.now(),
                                exit_price=current_price,
                                exit_reason=tp_sl_reason,
                                pnl=pnl_usd,
                                pnl_pct=pnl_pct,
                                duration_minutes=duration
                            )

                        # Send Discord notification
                        await send_discord_embed(
                            webhook_url=config.discord_webhook_url,
                            title=f"{'✅' if tp_sl_reason == 'TP' else '❌'} Position Closed - {tp_sl_reason}",
                            description=f"**{current_position['side']}** position closed",
                            color=0x00FF00 if tp_sl_reason == "TP" else 0xFF0000,
                            fields=[
                                {
                                    "name": "Entry Price",
                                    "value": f"${entry_price:,.2f}",
                                    "inline": True,
                                },
                                {
                                    "name": "Exit Price",
                                    "value": f"${current_price:,.2f}",
                                    "inline": True,
                                },
                                {
                                    "name": "PnL",
                                    "value": f"{pnl_pct:+.2f}%",
                                    "inline": True,
                                },
                            ],
                        )
            else:
                logger.info("No current position")

            # 5. Execute signal
            logger.info("Step 5: Executing signal...")

            # Check if bot is paused
            if bot_state.get("is_paused", False):
                logger.info("Bot is paused - skipping signal execution")
            elif should_enter_trade(signal, has_position):
                logger.info(f"Entering {signal} trade...")

                # Open position
                order = await executor.open_position(signal, current_price)

                if order:
                    # Log trade execution with structured data
                    logger.bind(
                        event="TRADE_OPENED",
                        signal=signal,
                        side=signal,
                        price=current_price,
                        quantity=order.get("origQty", 0),
                        order_id=order.get("orderId"),
                    ).info(f"Trade opened: {signal} @ ${current_price:,.2f}")

                    # Calculate TP/SL prices
                    if signal == "LONG":
                        tp_price = current_price * (1 + config.take_profit_pct)
                        sl_price = current_price * (1 - config.stop_loss_pct)
                    else:  # SHORT
                        tp_price = current_price * (1 - config.take_profit_pct)
                        sl_price = current_price * (1 + config.stop_loss_pct)

                    # Record to database
                    if trade_db and executor.current_position:
                        trade_id = await trade_db.add_entry(
                            entry_time=datetime.now(),
                            entry_price=current_price,
                            side=signal,
                            quantity=float(order.get("origQty", 0)),
                            leverage=config.leverage,
                            symbol=config.symbol
                        )
                        # Store trade_id in executor for later use
                        executor.current_position["trade_id"] = trade_id
                        logger.info(f"Trade entry recorded in database: ID={trade_id}")

                    # Send Discord notification
                    await send_discord_embed(
                        webhook_url=config.discord_webhook_url,
                        title=f"{get_signal_emoji(signal)} Position Opened - {signal}",
                        description=f"**{signal}** position opened",
                        color=get_signal_color(signal),
                        fields=[
                            {
                                "name": "Entry Price",
                                "value": f"${current_price:,.2f}",
                                "inline": True,
                            },
                            {
                                "name": "TP Target",
                                "value": f"${tp_price:,.2f} (+{config.take_profit_pct*100:.2f}%)",
                                "inline": True,
                            },
                            {
                                "name": "SL Target",
                                "value": f"${sl_price:,.2f} (-{config.stop_loss_pct*100:.2f}%)",
                                "inline": True,
                            },
                            {
                                "name": "RSI",
                                "value": f"{market_data['rsi']:.2f}",
                                "inline": True,
                            },
                            {
                                "name": "Leverage",
                                "value": f"{config.leverage}x",
                                "inline": True,
                            },
                        ],
                    )
            else:
                logger.info(f"Signal: {signal} - No action taken")

            # 6. Wait for next iteration
            logger.info(f"\nWaiting {config.loop_interval_seconds} seconds...")
            await asyncio.sleep(config.loop_interval_seconds)

        except KeyboardInterrupt:
            logger.info("\nShutting down gracefully...")

            # Cleanup
            bot_state["is_running"] = False

            # Disconnect from database
            if trade_db:
                await trade_db.disconnect()

            # Cancel Discord bot task
            if discord_task and not discord_task.done():
                discord_task.cancel()
                try:
                    await discord_task
                except asyncio.CancelledError:
                    logger.info("Discord bot task cancelled")

            await send_discord_embed(
                webhook_url=config.discord_webhook_url,
                title="🛑 Bot Stopped",
                description=f"**{config.bot_name}** stopped by user",
                color=0xFF0000,
            )
            break

        except Exception as e:
            logger.error(f"Error in trading loop: {e}", exc_info=True)
            await send_discord_embed(
                webhook_url=config.discord_webhook_url,
                title="⚠️ Error",
                description=f"Error in trading loop: {str(e)}",
                color=0xFFA500,
            )
            # Wait before retrying
            await asyncio.sleep(60)


async def main():
    """Entry point"""
    try:
        await trading_loop()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)


if __name__ == "__main__":
    # Setup structured JSON logging
    setup_logging()

    # Run the bot
    asyncio.run(main())
