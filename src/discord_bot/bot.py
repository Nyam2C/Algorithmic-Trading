"""
Discord Bot for Trading Bot Remote Control

Provides slash commands for monitoring and controlling the trading bot
"""
import discord
from discord import app_commands
from datetime import datetime
from loguru import logger
from typing import Optional


class TradingBotClient(discord.Client):
    """Discord client for trading bot control"""

    def __init__(self, bot_state: dict, trade_db=None):
        """
        Initialize Discord bot client

        Args:
            bot_state: Shared state dictionary with trading bot
            trade_db: TradeHistoryDB instance (optional)
        """
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)

        self.tree = app_commands.CommandTree(self)
        self.bot_state = bot_state
        self.trade_db = trade_db
        self.setup_commands()

    def setup_commands(self):
        """Register slash commands"""

        @self.tree.command(name="status", description="봇 실행 상태 및 현재 포지션 확인")
        async def status(interaction: discord.Interaction):
            """Show bot status and current position"""
            await interaction.response.defer()

            try:
                # Get bot state
                is_running = self.bot_state.get("is_running", False)
                uptime = self.bot_state.get("uptime", "N/A")
                current_price = self.bot_state.get("current_price", 0)
                last_signal = self.bot_state.get("last_signal", "WAIT")
                last_signal_time = self.bot_state.get("last_signal_time", "N/A")

                # Get position
                position = self.bot_state.get("position")

                # Build embed
                embed = discord.Embed(
                    title="🤖 Bot Status",
                    color=0x00FF00 if is_running else 0xFF0000
                )

                embed.add_field(
                    name="⚡ Status",
                    value="Running" if is_running else "Stopped",
                    inline=True
                )
                embed.add_field(
                    name="⏰ Uptime",
                    value=uptime,
                    inline=True
                )
                embed.add_field(
                    name="💰 Symbol",
                    value=self.bot_state.get("symbol", "BTCUSDT"),
                    inline=True
                )
                embed.add_field(
                    name="📊 Current Price",
                    value=f"${current_price:,.2f}",
                    inline=True
                )

                # Position info
                if position and position.get("side"):
                    side = position.get("side")
                    emoji = "🟢" if side == "LONG" else "🔴"
                    embed.add_field(
                        name="📍 Position",
                        value=f"{emoji} {side}",
                        inline=True
                    )
                else:
                    embed.add_field(
                        name="📍 Position",
                        value="None",
                        inline=True
                    )

                embed.add_field(
                    name="🔄 Last Signal",
                    value=f"{last_signal} ({last_signal_time})",
                    inline=False
                )
                embed.add_field(
                    name="📈 Strategy",
                    value="Rule-Based (RSI + MA)",
                    inline=False
                )

                await interaction.followup.send(embed=embed)
                logger.info(f"Discord command /status executed by {interaction.user}")

            except Exception as e:
                logger.error(f"Error in /status command: {e}")
                await interaction.followup.send(
                    f"❌ Error getting bot status: {str(e)}",
                    ephemeral=True
                )

        @self.tree.command(name="position", description="현재 포지션 상세 정보")
        async def position(interaction: discord.Interaction):
            """Show detailed position information"""
            await interaction.response.defer()

            try:
                position = self.bot_state.get("position")

                if not position or not position.get("side"):
                    embed = discord.Embed(
                        title="📍 No Position",
                        description="⏸️ Waiting for signal...",
                        color=0xFFFF00
                    )
                    embed.add_field(
                        name="🔄 Last Signal",
                        value=self.bot_state.get("last_signal", "WAIT"),
                        inline=False
                    )
                    await interaction.followup.send(embed=embed)
                    return

                # Build position details
                side = position.get("side")
                entry_price = position.get("entry_price", 0)
                size = position.get("size", 0)
                leverage = position.get("leverage", 15)
                duration = position.get("duration", "N/A")

                tp_price = position.get("tp_price", 0)
                sl_price = position.get("sl_price", 0)
                timecut_remaining = position.get("timecut_remaining", "N/A")

                current_price = self.bot_state.get("current_price", 0)
                pnl_usd = position.get("pnl_usd", 0)
                pnl_pct = position.get("pnl_pct", 0)

                emoji = "🟢" if side == "LONG" else "🔴"
                color = 0x00FF00 if side == "LONG" else 0xFF0000

                embed = discord.Embed(
                    title=f"📍 Current Position",
                    color=color
                )

                embed.add_field(
                    name=f"{emoji} Side",
                    value=side,
                    inline=True
                )
                embed.add_field(
                    name="💵 Entry",
                    value=f"${entry_price:,.2f}",
                    inline=True
                )
                embed.add_field(
                    name="📊 Size",
                    value=f"{size:.4f} BTC ({leverage}x)",
                    inline=True
                )
                embed.add_field(
                    name="⏱️ Duration",
                    value=duration,
                    inline=True
                )
                embed.add_field(
                    name="🎯 TP",
                    value=f"${tp_price:,.2f} (+0.4%)",
                    inline=True
                )
                embed.add_field(
                    name="🛑 SL",
                    value=f"${sl_price:,.2f} (-0.4%)",
                    inline=True
                )
                embed.add_field(
                    name="⏰ Timecut",
                    value=f"{timecut_remaining} remaining",
                    inline=False
                )

                pnl_emoji = "💰" if pnl_usd > 0 else "📉"
                embed.add_field(
                    name=f"{pnl_emoji} Current PnL",
                    value=f"${pnl_usd:+.2f} ({pnl_pct:+.2f}%)",
                    inline=False
                )

                await interaction.followup.send(embed=embed)
                logger.info(f"Discord command /position executed by {interaction.user}")

            except Exception as e:
                logger.error(f"Error in /position command: {e}")
                await interaction.followup.send(
                    f"❌ Error getting position: {str(e)}",
                    ephemeral=True
                )

        @self.tree.command(name="stats", description="거래 통계 (최근 24시간)")
        async def stats(interaction: discord.Interaction, hours: int = 24):
            """Show trading statistics"""
            await interaction.response.defer()

            try:
                if not self.trade_db:
                    await interaction.followup.send(
                        "❌ Trade database not available",
                        ephemeral=True
                    )
                    return

                # Get statistics
                stats_data = await self.trade_db.get_statistics(hours=hours)

                if stats_data["total_trades"] == 0:
                    embed = discord.Embed(
                        title=f"📊 No Trades (Last {hours}h)",
                        description="No completed trades in this period",
                        color=0xFFFF00
                    )
                    await interaction.followup.send(embed=embed)
                    return

                # Build embed
                embed = discord.Embed(
                    title=f"📊 Trading Statistics",
                    description=f"Last {hours} hours",
                    color=0x00FF00 if stats_data["total_pnl"] > 0 else 0xFF0000
                )

                embed.add_field(
                    name="🎯 Total Trades",
                    value=str(stats_data["total_trades"]),
                    inline=True
                )
                embed.add_field(
                    name="✅ Winners",
                    value=f"{stats_data['winners']} ({stats_data['win_rate']:.1f}%)",
                    inline=True
                )
                embed.add_field(
                    name="❌ Losers",
                    value=str(stats_data["losers"]),
                    inline=True
                )

                pnl_emoji = "💰" if stats_data["total_pnl"] > 0 else "📉"
                embed.add_field(
                    name=f"{pnl_emoji} Total PnL",
                    value=f"${stats_data['total_pnl']:+.2f}",
                    inline=False
                )
                embed.add_field(
                    name="📈 Best Trade",
                    value=f"+{stats_data['best_trade']:.2f}%",
                    inline=True
                )
                embed.add_field(
                    name="📉 Worst Trade",
                    value=f"{stats_data['worst_trade']:.2f}%",
                    inline=True
                )
                embed.add_field(
                    name="🟢 LONG",
                    value=f"{stats_data['long_trades']} trades",
                    inline=True
                )
                embed.add_field(
                    name="🔴 SHORT",
                    value=f"{stats_data['short_trades']} trades",
                    inline=True
                )

                await interaction.followup.send(embed=embed)
                logger.info(f"Discord command /stats executed by {interaction.user}")

            except Exception as e:
                logger.error(f"Error in /stats command: {e}")
                await interaction.followup.send(
                    f"❌ Error getting statistics: {str(e)}",
                    ephemeral=True
                )

        @self.tree.command(name="history", description="최근 거래 내역")
        async def history(interaction: discord.Interaction, count: int = 5):
            """Show recent trade history"""
            await interaction.response.defer()

            try:
                if not self.trade_db:
                    await interaction.followup.send(
                        "❌ Trade database not available",
                        ephemeral=True
                    )
                    return

                # Limit count
                count = min(count, 10)

                # Get recent trades
                trades = await self.trade_db.get_recent_trades(limit=count)

                if not trades:
                    embed = discord.Embed(
                        title="📜 No Trade History",
                        description="No completed trades found",
                        color=0xFFFF00
                    )
                    await interaction.followup.send(embed=embed)
                    return

                # Build embed
                embed = discord.Embed(
                    title=f"📜 Recent Trades (Last {len(trades)})",
                    color=0x00BFFF
                )

                for i, trade in enumerate(trades, 1):
                    side = trade["side"]
                    emoji = "🟢" if side == "LONG" else "🔴"
                    entry = trade["entry_price"]
                    exit_p = trade["exit_price"]
                    exit_reason = trade["exit_reason"]
                    pnl_usd = trade["pnl_usd"]
                    pnl_pct = trade["pnl_pct"]

                    # Time ago
                    exit_time = trade["exit_time"]
                    time_diff = datetime.now() - exit_time.replace(tzinfo=None)
                    hours_ago = int(time_diff.total_seconds() / 3600)
                    mins_ago = int((time_diff.total_seconds() % 3600) / 60)

                    if hours_ago > 0:
                        time_ago = f"{hours_ago}h {mins_ago}m ago"
                    else:
                        time_ago = f"{mins_ago}m ago"

                    pnl_emoji = "💰" if pnl_usd > 0 else "📉"

                    value = (
                        f"{emoji} **{side}** | Entry: ${entry:,.2f} → Exit: ${exit_p:,.2f} ({exit_reason})\n"
                        f"{pnl_emoji} PnL: ${pnl_usd:+.2f} ({pnl_pct:+.2f}%) | {time_ago}"
                    )

                    embed.add_field(
                        name=f"{i}️⃣ Trade #{trade['id']}",
                        value=value,
                        inline=False
                    )

                await interaction.followup.send(embed=embed)
                logger.info(f"Discord command /history executed by {interaction.user}")

            except Exception as e:
                logger.error(f"Error in /history command: {e}")
                await interaction.followup.send(
                    f"❌ Error getting trade history: {str(e)}",
                    ephemeral=True
                )

        @self.tree.command(name="stop", description="봇 일시 정지 (새 포지션 진입 중지)")
        async def stop(interaction: discord.Interaction):
            """Pause the trading bot"""
            await interaction.response.defer()

            try:
                # Set bot state to paused
                self.bot_state["is_paused"] = True
                self.bot_state["paused_by"] = str(interaction.user)
                self.bot_state["paused_at"] = datetime.now()

                embed = discord.Embed(
                    title="⏸️ Bot Paused",
                    description="Trading bot has been paused",
                    color=0xFFFF00
                )

                embed.add_field(
                    name="🛑 New positions",
                    value="Disabled",
                    inline=True
                )
                embed.add_field(
                    name="📍 Existing positions",
                    value="Active (TP/SL still working)",
                    inline=True
                )
                embed.add_field(
                    name="⚠️ Resume",
                    value="Use `/start` to resume trading",
                    inline=False
                )
                embed.add_field(
                    name="👤 Paused by",
                    value=str(interaction.user),
                    inline=True
                )

                await interaction.followup.send(embed=embed)
                logger.warning(f"Bot paused by {interaction.user}")

            except Exception as e:
                logger.error(f"Error in /stop command: {e}")
                await interaction.followup.send(
                    f"❌ Error pausing bot: {str(e)}",
                    ephemeral=True
                )

        @self.tree.command(name="start", description="봇 재시작 (정상 거래 재개)")
        async def start(interaction: discord.Interaction):
            """Resume the trading bot"""
            await interaction.response.defer()

            try:
                # Check if bot was paused
                was_paused = self.bot_state.get("is_paused", False)

                # Set bot state to active
                self.bot_state["is_paused"] = False
                self.bot_state["resumed_by"] = str(interaction.user)
                self.bot_state["resumed_at"] = datetime.now()

                embed = discord.Embed(
                    title="▶️ Bot Resumed",
                    description="Trading bot is now active",
                    color=0x00FF00
                )

                embed.add_field(
                    name="✅ Trading",
                    value="Enabled",
                    inline=True
                )
                embed.add_field(
                    name="🔄 Next signal",
                    value="Will be generated in next loop",
                    inline=True
                )
                embed.add_field(
                    name="👤 Resumed by",
                    value=str(interaction.user),
                    inline=False
                )

                if was_paused:
                    paused_by = self.bot_state.get("paused_by", "Unknown")
                    paused_at = self.bot_state.get("paused_at")
                    if paused_at:
                        pause_duration = datetime.now() - paused_at
                        hours = int(pause_duration.total_seconds() / 3600)
                        mins = int((pause_duration.total_seconds() % 3600) / 60)
                        embed.add_field(
                            name="⏱️ Pause duration",
                            value=f"{hours}h {mins}m (paused by {paused_by})",
                            inline=False
                        )

                await interaction.followup.send(embed=embed)
                logger.info(f"Bot resumed by {interaction.user}")

            except Exception as e:
                logger.error(f"Error in /start command: {e}")
                await interaction.followup.send(
                    f"❌ Error resuming bot: {str(e)}",
                    ephemeral=True
                )

        @self.tree.command(name="emergency", description="🚨 긴급 청산 (현재 포지션 즉시 청산 + 봇 정지)")
        async def emergency(interaction: discord.Interaction):
            """Emergency close current position and pause bot"""
            await interaction.response.defer()

            try:
                position = self.bot_state.get("position")

                if not position or not position.get("side"):
                    embed = discord.Embed(
                        title="⚠️ No Position to Close",
                        description="No open position found",
                        color=0xFFFF00
                    )
                    await interaction.followup.send(embed=embed)
                    return

                # Set emergency flag
                self.bot_state["emergency_close"] = True
                self.bot_state["emergency_by"] = str(interaction.user)
                self.bot_state["emergency_at"] = datetime.now()

                # Also pause the bot
                self.bot_state["is_paused"] = True

                side = position.get("side")
                entry_price = position.get("entry_price", 0)
                size = position.get("size", 0)

                embed = discord.Embed(
                    title="🚨 Emergency Close Initiated",
                    description="Position will be closed at market price",
                    color=0xFF0000
                )

                emoji = "🟢" if side == "LONG" else "🔴"
                embed.add_field(
                    name=f"{emoji} Position",
                    value=f"{side} @ ${entry_price:,.2f}",
                    inline=True
                )
                embed.add_field(
                    name="📊 Size",
                    value=f"{size:.4f} BTC",
                    inline=True
                )
                embed.add_field(
                    name="⚠️ Action",
                    value="Market close in next loop",
                    inline=False
                )
                embed.add_field(
                    name="⏸️ Bot Status",
                    value="Paused (use `/start` to resume)",
                    inline=False
                )
                embed.add_field(
                    name="👤 Initiated by",
                    value=str(interaction.user),
                    inline=True
                )

                await interaction.followup.send(embed=embed)
                logger.critical(f"Emergency close initiated by {interaction.user}")

            except Exception as e:
                logger.error(f"Error in /emergency command: {e}")
                await interaction.followup.send(
                    f"❌ Error initiating emergency close: {str(e)}",
                    ephemeral=True
                )

        @self.tree.command(name="ping", description="봇 응답 확인")
        async def ping(interaction: discord.Interaction):
            """Check if bot is responding"""
            await interaction.response.send_message("🏓 Pong!", ephemeral=True)
            logger.info(f"Discord command /ping executed by {interaction.user}")

    async def on_ready(self):
        """Called when bot is ready"""
        logger.info(f"Discord bot logged in as {self.user}")
        logger.info(f"Bot is in {len(self.guilds)} guild(s)")

        # Sync commands
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} command(s)")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")

    async def on_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handle command errors"""
        logger.error(f"Command error: {error}")
        await interaction.response.send_message(
            f"❌ Command error: {str(error)}",
            ephemeral=True
        )


async def start_discord_bot(token: str, bot_state: dict, trade_db=None):
    """
    Start Discord bot

    Args:
        token: Discord bot token
        bot_state: Shared state dictionary with trading bot
        trade_db: TradeHistoryDB instance (optional)
    """
    client = TradingBotClient(bot_state=bot_state, trade_db=trade_db)

    try:
        await client.start(token)
    except Exception as e:
        logger.error(f"Discord bot error: {e}")
        raise
