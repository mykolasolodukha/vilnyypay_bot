"""The main module of the application."""
import aiogram

from settings import settings
from utils import tortoise_orm
from utils.logging import logger
from utils.redis_storage import redis_storage

bot = aiogram.Bot(settings.TELEGRAM_BOT_TOKEN)
dp = aiogram.Dispatcher(bot, storage=redis_storage)


# region Handlers
@dp.message_handler(aiogram.filters.CommandStart())
async def start(message: aiogram.types.Message):
    """`/start` command handler."""
    logger.info(f"Received /start command: {message.text=} from {message.from_user.to_python()=}")
    me = await bot.get_me()
    return await message.answer(
        f"Hi! I'm the {me.full_name} bot. Send me a message and I'll reply to you."
    )


# endregion


# region Startup and shutdown callbacks
async def on_startup(*_, **__):
    """Startup the bot."""
    logger.info(f"Starting up the https://t.me/{(await bot.get_me()).username} bot...")

    logger.debug("Initializing the database connection...")
    await tortoise_orm.init()

    logger.info("Startup complete.")


async def on_shutdown(*_, **__):
    """Shutdown the bot."""
    logger.info("Shutting down...")

    logger.debug("Closing the database connection...")
    await tortoise_orm.shutdown()

    logger.info("Shutdown complete.")


# endregion

if __name__ == "__main__":
    aiogram.executor.start_polling(dp, on_startup=on_startup, on_shutdown=on_shutdown)
