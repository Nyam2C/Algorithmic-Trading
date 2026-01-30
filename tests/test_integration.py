"""
Quick integration test for Discord Bot + PostgreSQL
"""
import asyncio
from src.config import get_config
from src.storage.trade_history import TradeHistoryDB


async def test_integration():
    """Test Discord bot configuration and PostgreSQL connection"""
    print("=" * 60)
    print("Discord Bot + PostgreSQL Integration Test")
    print("=" * 60)

    # Load config
    config = get_config()
    print("\n1. Configuration loaded:")
    print(f"   Symbol: {config.symbol}")
    print(f"   Leverage: {config.leverage}x")
    print(f"   Discord Bot Token: {'✓ Set' if config.discord_bot_token and config.discord_bot_token != 'your_bot_token_here' else '✗ Not set'}")
    print(f"   Database URL: {'✓ Set' if config.database_url else '✗ Not set'}")

    # Test PostgreSQL connection
    if config.database_url:
        print("\n2. Testing PostgreSQL connection...")
        try:
            trade_db = TradeHistoryDB(config.database_url)
            await trade_db.connect()
            print("   ✓ PostgreSQL connected successfully")

            # Test query
            stats = await trade_db.get_statistics(hours=24)
            print(f"   ✓ Stats query successful: {stats['total_trades']} trades in last 24h")

            await trade_db.disconnect()
            print("   ✓ PostgreSQL disconnected")
        except Exception as e:
            print(f"   ✗ PostgreSQL error: {e}")
    else:
        print("\n2. PostgreSQL test skipped (DATABASE_URL not set)")

    # Discord bot token check
    if config.discord_bot_token and config.discord_bot_token != "your_bot_token_here":
        print("\n3. Discord Bot Configuration:")
        print("   ✓ Discord bot token is set")
        print("   ℹ To test Discord bot, run the main bot with: python -m src.main")
        print("   ℹ Then use /ping command in Discord to verify")
    else:
        print("\n3. Discord Bot Configuration:")
        print("   ✗ Discord bot token not set")
        print("   ℹ Set DISCORD_BOT_TOKEN in .env to enable Discord commands")

    print("\n" + "=" * 60)
    print("Integration test complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_integration())
