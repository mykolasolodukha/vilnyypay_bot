"""The main module of the application."""
import aiogram

from settings import settings
from utils.logging import logger

bot = aiogram.Bot(settings.TELEGRAM_BOT_TOKEN)
dp = aiogram.Dispatcher(bot)


@dp.message_handler(aiogram.filters.CommandStart())
async def start(message: aiogram.types.Message):
    """`/start` command handler."""
    logger.info(f"Received /start command: {message.text=} from {message.from_user.to_python()=}")
    me = await bot.get_me()
    await message.answer(
        f"Hi! I'm the {me.full_name} bot. Send me a message and I'll reply to you."
    )


if __name__ == "__main__":
    aiogram.executor.start_polling(dp)
