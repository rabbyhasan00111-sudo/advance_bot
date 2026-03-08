#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════════════════╗
║                                                                       ║
║              ██████╗  █████╗ ███████╗ ██████╗██╗  ██╗                ║
║              ██╔══██╗██╔══██╗██╔════╝██╔════╝██║  ██║                ║
║              ██║  ██║███████║███████╗██║     ███████║                ║
║              ██║  ██║██╔══██║╚════██║██║     ╚════██║                ║
║              ██████╔╝██║  ██║███████║╚██████╗     ██║                ║
║              ╚═════╝ ╚═╝  ╚═╝╚══════╝ ╚═════╝     ╚═╝                ║
║                                                                       ║
║     ██████╗ ██████╗  ██████╗ ██╗  ██╗██╗   ██╗███████╗               ║
║     ██╔══██╗██╔══██╗██╔═══██╗╚██╗██╔╝██║   ██║██╔════╝               ║
║     ██████╔╝██████╔╝██║   ██║ ╚███╔╝ ██║   ██║███████╗               ║
║     ██╔═══╝ ██╔══██╗██║   ██║ ██╔██╗ ██║   ██║╚════██║               ║
║     ██║     ██║  ██║╚██████╔╝██╔╝ ██╗╚██████╔╝███████║               ║
║     ╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝               ║
║                                                                       ║
║                     ⚡ NEXT-GEN HOSTING BOT ⚡                        ║
║                          Version 3.0.0 CYBER                          ║
║                         By: @shuvohassan00                            ║
║                                                                       ║
╚═══════════════════════════════════════════════════════════════════════╝

                    🛡️ GADGET PREMIUM HOST 🛡️
                 A Next-Generation Telegram Bot
                    Hosting Platform Built with
                      aiogram 3.x + SQLite + asyncio

"""

import asyncio
import logging
import sys
import os
import signal
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart, Command

# Import configuration
from config import (
    BOT_TOKEN, BRAND_NAME, BRAND_VERSION, OWNER_ID,
    LOGGING_CONFIG, DATA_DIR, USER_FILES_DIR, LOGS_DIR
)

# Import database
from database import db

# Import handlers
from handlers.admin import admin_router
from handlers.user import user_router
from handlers.hosting import hosting_router

# Import services
from services.process_manager import process_manager

# Import utilities
from utils.helpers import ServerMonitor

# ═══════════════════════════════════════════════════════════════
# 📝 LOGGING SETUP
# ═══════════════════════════════════════════════════════════════

def setup_logging():
    """Configure logging"""
    # Create logs directory
    os.makedirs(LOGS_DIR, exist_ok=True)
    
    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(
                os.path.join(LOGS_DIR, "bot.log"),
                encoding='utf-8'
            )
        ]
    )
    
    # Set specific loggers
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    
    return logging.getLogger("gadget_host")


logger = setup_logging()


# ═══════════════════════════════════════════════════════════════
# 🤖 BOT INSTANCE
# ═══════════════════════════════════════════════════════════════

async def create_bot() -> tuple[Bot, Dispatcher]:
    """Create bot and dispatcher instances"""
    
    # Validate token
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("❌ BOT_TOKEN not set! Please set it in config.py or environment variable.")
        sys.exit(1)
    
    # Create bot instance
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
            link_preview_is_disabled=True
        )
    )
    
    # Create dispatcher
    dp = Dispatcher()
    
    # Register routers
    dp.include_router(admin_router)
    dp.include_router(user_router)
    dp.include_router(hosting_router)
    
    logger.info("✅ Bot and dispatcher created")
    
    return bot, dp


# ═══════════════════════════════════════════════════════════════
# 🚀 STARTUP SEQUENCE
# ═══════════════════════════════════════════════════════════════

async def on_startup(bot: Bot):
    """Execute on bot startup"""
    
    # Print startup banner
    print("""
╔═══════════════════════════════════════════════════════════════╗
║         🛡️ GADGET PREMIUM HOST v3.0.0 🛡️                      ║
║              Starting up...                                   ║
╚═══════════════════════════════════════════════════════════════╝
""")
    
    logger.info("=" * 50)
    logger.info(f"🚀 {BRAND_NAME} v{BRAND_VERSION}")
    logger.info("=" * 50)
    
    # Initialize database
    logger.info("📊 Initializing database...")
    await db.initialize()
    logger.info("✅ Database ready")
    
    # Initialize process manager
    logger.info("🔄 Initializing process manager...")
    await process_manager.initialize()
    logger.info("✅ Process manager ready")
    
    # Create necessary directories
    for directory in [DATA_DIR, USER_FILES_DIR, LOGS_DIR]:
        os.makedirs(directory, exist_ok=True)
    logger.info("📁 Directories verified")
    
    # Get bot info
    me = await bot.get_me()
    logger.info(f"🤖 Bot: @{me.username} ({me.id})")
    logger.info(f"👤 Owner ID: {OWNER_ID}")
    
    # Get server info
    stats = ServerMonitor.get_full_stats()
    logger.info(f"🖥️ Server: CPU {stats['cpu_percent']:.1f}%, RAM {stats['ram_percent']:.1f}%")
    logger.info(f"⏰ Uptime: {stats['uptime']}")
    
    # Notify owner
    try:
        await bot.send_message(
            OWNER_ID,
            f"""
🚀 <b>{BRAND_NAME} STARTED!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

⏰ <b>Time:</b> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

<b>📊 Server Status:</b>
┃ CPU: {stats['cpu_percent']:.1f}%
┃ RAM: {stats['ram_used']:.1f}/{stats['ram_total']:.1f} GB
┃ Disk: {stats['disk_percent']:.1f}%
┃ Uptime: {stats['uptime']}

<b>✅ All systems operational!</b>
""",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Could not notify owner: {e}")
    
    logger.info("=" * 50)
    logger.info("🎯 Bot is ready! Listening for updates...")
    logger.info("=" * 50)
    
    print("""
╔═══════════════════════════════════════════════════════════════╗
║                    ✅ BOT ONLINE ✅                           ║
║                                                               ║
║   Bot is now running and listening for messages!              ║
║   Press Ctrl+C to stop.                                       ║
╚═══════════════════════════════════════════════════════════════╝
""")


async def on_shutdown(bot: Bot):
    """Execute on bot shutdown"""
    
    logger.info("=" * 50)
    logger.info("🛑 Shutting down...")
    
    # Notify owner
    try:
        await bot.send_message(
            OWNER_ID,
            f"""
🛑 <b>{BRAND_NAME} STOPPED!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━

⏰ <b>Time:</b> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

<i>Bot is shutting down...</i>
""",
            parse_mode="HTML"
        )
    except:
        pass
    
    # Close database
    await db.close()
    logger.info("📊 Database closed")
    
    logger.info("👋 Goodbye!")
    logger.info("=" * 50)


# ═══════════════════════════════════════════════════════════════
# 🔄 MAIN EVENT LOOP
# ═══════════════════════════════════════════════════════════════

async def main():
    """Main entry point"""
    
    # Create bot and dispatcher
    bot, dp = await create_bot()
    
    # Register startup and shutdown handlers
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Start polling
    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            handle_signals=False
        )
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        await on_shutdown(bot)
        await bot.session.close()


# ═══════════════════════════════════════════════════════════════
# 🎯 ENTRY POINT
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    try:
        # Run the bot
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
