"""The middleware to log all the incoming messages into the database."""
import typing

from aiogram import types
from aiogram.dispatcher.middlewares import BaseMiddleware

from models import Message, User
from utils.loguru_logging import logger


class MessagesLoggingMiddleware(BaseMiddleware):
    """The middleware class, inherited from `BaseMiddleware`."""

    async def on_pre_process_message(self, msg: types.Message, *_, **__):
        """Save the message into the database _before_ processing it."""
        user_data: dict = msg.from_user.to_python()
        try:
            # Create a user first, if not exist. Otherwise, we are unable to create a message
            # with a foreign key.
            user, created = await User.get_or_create(id=user_data.pop("id"), defaults=user_data)

            if created:
                if payload := msg.get_args():
                    user.start_payload = payload
                    await user.save()
                logger.info(
                    f"New user [ID:{user.pk}] [USERNAME:@{user.username}] "
                    f"with {user.start_payload=}"
                )
            else:
                await user.update_from_dict(msg.from_user.to_python()).save()

        except Exception as e:
            logger.error(f"Exception in {self.__class__.__name__}: {e} ({e.__class__}")
            raise e

        message = await Message.create(
            **msg.to_python(),
            user=user,
            chat_id=msg.chat.id,
            content_type=msg.content_type,
        )
        logger.info(
            f"Logged message [ID:{message.message_id}] in chat [{msg.chat.type}:{msg.chat.id}]"
        )
