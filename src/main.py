"""
High-Win Survival System - Main Entry Point
Sprint 1: Paper Trading MVP
"""
import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime

import aiohttp
from loguru import logger

# Import our modules
from src.config import get_config
from src.exchange.binance import BinanceTestnetClient
from src.data.indicators import analyze_market
from src.ai.gemini import GeminiSignalGenerator
from src.ai.rule_based import RuleBasedSignalGenerator
from src.ai.signals import (
    parse_signal,
    validate_signal,
    should_enter_trade,
    get_signal_emoji,
    get_signal_color,
)
from src.trading.executor import TradingExecutor


def setup_logging():
    """
    Configure structured JSON logging for Loki/Promtail
    """
    # Remove default logger
    logger.remove()

    # Create logs directory
    Path("logs").mkdir(exist_ok=True)

    # JSON formatter for file logging (Loki/Promtail)
    def json_formatter(record):
        log_entry = {
            "timestamp": record["time"].isoformat(),
            "level": record["level"].name,
            "message": record["message"],
            "module": record["name"],
            "function": record["function"],
            "line": record["line"],
        }

        # Add extra fields if present
        if record["extra"]:
            log_entry.update(record["extra"])

        return json.dumps(log_entry)

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
        format=json_formatter,
        level="DEBUG",
        rotation="100 MB",
        retention="30 days",
        compression="zip",
    )

    # Error-only logger (error.log)
    logger.add(
        "logs/error.log",
        format=json_formatter,
        level="ERROR",
        rotation="10 MB",
        retention="30 days",
        compression="zip",
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
    signal_generator = RuleBasedSignalGenerator(
        rsi_oversold=45.0,  # 35 → 45 (more signals)
        rsi_overbought=55.0,  # 65 → 55 (more signals)
        volume_threshold=0.3,  # 1.2 → 0.3 (lower volume requirement)
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

            # 4. Check current position
            logger.info("Step 4: Checking position...")
            current_position = await executor.get_position()
            has_position = current_position is not None

            if has_position:
                logger.info(
                    f"Current position: {current_position['side']} "
                    f"{abs(current_position['position_amt'])} @ "
                    f"${current_position['entry_price']:,.2f}"
                )

                # Check Timecut first
                if executor.current_position and executor.check_timecut(executor.current_position):
                    exit_reason = "TIMECUT"
                    logger.info("Exit condition met: TIMECUT")

                    # Close position
                    order = await executor.close_position()

                    if order:
                        # Calculate PnL
                        entry_price = current_position["entry_price"]
                        pnl_pct = executor.calculate_pnl_pct(
                            entry_price, current_price, current_position["side"]
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
                exit_reason = await executor.check_tp_sl(current_position, current_price)
                if exit_reason:
                    logger.info(f"Exit condition met: {exit_reason}")

                    # Close position
                    order = await executor.close_position()

                    if order:
                        # Calculate PnL
                        entry_price = current_position["entry_price"]
                        pnl_pct = executor.calculate_pnl_pct(
                            entry_price, current_price, current_position["side"]
                        )

                        # Send Discord notification
                        await send_discord_embed(
                            webhook_url=config.discord_webhook_url,
                            title=f"{'✅' if exit_reason == 'TP' else '❌'} Position Closed - {exit_reason}",
                            description=f"**{current_position['side']}** position closed",
                            color=0x00FF00 if exit_reason == "TP" else 0xFF0000,
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

            if should_enter_trade(signal, has_position):
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
