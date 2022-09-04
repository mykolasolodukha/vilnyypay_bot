"""The main module of the application."""

import aiogram
import emoji
from aiogram.contrib.middlewares.i18n import I18nMiddleware
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import any_state

import states
from filters.auth import AuthFilter
from middlewares.message_logging_middleware import MessagesLoggingMiddleware
from models import Group, Profile, User
from settings import settings
from utils import tortoise_orm
from utils.loguru_logging import logger
from utils.redis_storage import redis_storage
from utils.tortoise_orm import flatten_tortoise_model

bot = aiogram.Bot(settings.TELEGRAM_BOT_TOKEN)
dp = aiogram.Dispatcher(bot, storage=redis_storage)

# region Filters
dp.bind_filter(
    AuthFilter,
    exclude_event_handlers=[
        dp.errors_handlers,
        dp.poll_handlers,
        dp.poll_answer_handlers,
    ],
)

# endregion


# region Middlewares
dp.middleware.setup(aiogram.contrib.middlewares.logging.LoggingMiddleware())
dp.middleware.setup(MessagesLoggingMiddleware())

i18n = I18nMiddleware("messages", default="uk")
dp.middleware.setup(i18n)
_ = i18n.gettext
__ = i18n.lazy_gettext


# endregion


@dp.message_handler(
    aiogram.filters.CommandStart(), state=aiogram.dispatcher.filters.state.any_state
)
async def start(message: aiogram.types.Message, state: FSMContext):
    """`/start` command handler."""
    logger.debug(f"Received /start command: {message.text=}")

    # Reset the state since the user has just clicked the start button
    await state.reset_state(with_data=False)

    if (start_payload := message.get_args()) and start_payload.startswith("group-"):
        logger.debug(f"Received start payload: {start_payload=}")

        if (group_id := start_payload.split("-")[1]) and group_id.isdigit():
            await state.update_data(group_uid_to_add_to=int(start_payload.split("-")[1]))

            logger.debug(f"User has been invited to the group: {group_id=}")
        else:
            logger.warning(f"Invalid start payload: {start_payload=}")

    await states.Registration.share_phone_number.set()

    return await message.answer(
        emoji.emojize(_("start.welcome")),
        reply_markup=aiogram.types.ReplyKeyboardMarkup(
            resize_keyboard=True, one_time_keyboard=True
        ).add(
            aiogram.types.KeyboardButton(
                _("start.button.share_phone_number"), request_contact=True
            ),
        ),
    )


# region Registration


@dp.message_handler(
    state=states.Registration.share_phone_number, content_types=aiogram.types.ContentType.CONTACT
)
async def registration_save_phone_number(message: aiogram.types.Message, user: User):
    """Save the phone number of the user."""
    logger.debug(f"Received phone number: {message.contact.phone_number=}")

    if user.phone_number:
        return await message.answer(
            emoji.emojize(_("registration.phone_number.already_set")),
            reply_markup=aiogram.types.ReplyKeyboardRemove(),
        )

    if not message.contact.user_id == message.from_user.id:
        return await message.answer(emoji.emojize(_("registration.phone_number.not_from_user")))

    user.phone_number = message.contact.phone_number
    await user.save()

    await states.Registration.share_full_name.set()

    return await message.answer(
        emoji.emojize(_("registration.share_full_name")),
        reply_markup=aiogram.types.ReplyKeyboardRemove(),
    )


@dp.message_handler(
    state=states.Registration.share_full_name, content_types=aiogram.types.ContentType.TEXT
)
async def registration_save_full_name(
    message: aiogram.types.Message, state: FSMContext, user: User
):
    """Create a user's profile and save the full name of the user."""
    logger.debug(f"Received full name: {message.text=}")

    if not (user_profile := await user.profile):
        user_profile = await Profile.create(user=user, full_name=message.text)
        logger.debug(f"Created a new profile for the user: {user_profile.pk=}")
    else:
        logger.warning(f"User already has a profile: {user_profile.pk=}, {user.pk=}")

    if group_uid_to_add_to := (await state.get_data()).get("group_uid_to_add_to"):
        if group := await Group.get_or_none(uid=group_uid_to_add_to):
            await states.Registration.confirm_coliving.set()

            # noinspection StrFormat
            return await message.answer(
                emoji.emojize(
                    _("registration.confirm_coliving").format(
                        **(
                            flatten_tortoise_model(group, separator="__", prefix="group__")
                            | flatten_tortoise_model(
                                user_profile, separator="__", prefix="user__profile__"
                            )
                        )
                    )
                ),
                reply_markup=aiogram.types.ReplyKeyboardMarkup(
                    resize_keyboard=True, one_time_keyboard=True
                ).add(
                    aiogram.types.KeyboardButton(_("yes")),
                    aiogram.types.KeyboardButton(_("no")),
                ),
            )
        else:
            logger.warning(f"Group not found: {group_uid_to_add_to=}")

            # noinspection StrFormat
            return await message.answer(
                emoji.emojize(
                    _("registration.group_not_found").format(
                        group_uid_to_add_to=group_uid_to_add_to
                    )
                ),
                reply_markup=aiogram.types.ReplyKeyboardRemove(),
            )
    else:
        logger.error(f"Group UID to add to not found in the FSM context: {await state.get_data()=}")

        return await message.answer(
            emoji.emojize(_("registration.group_uuid_not_found")),
            reply_markup=aiogram.types.ReplyKeyboardRemove(),
        )


@dp.message_handler(
    state=states.Registration.confirm_coliving, content_types=aiogram.types.ContentType.TEXT
)
async def registration_confirm_coliving(
    message: aiogram.types.Message, state: aiogram.dispatcher.FSMContext, user: User
):
    """Check if the user has confirmed the coliving name, otherwise raise a `SupportTicket`."""
    if message.text == _("yes"):
        # Actually add the user to the group
        if group_uid_to_add_to := (await state.get_data()).get("group_uid_to_add_to"):
            logger.debug(f"Adding the user to the group: {group_uid_to_add_to=}")

            if group := await Group.get_or_none(uid=group_uid_to_add_to):
                await user.groups.add(group)
                logger.debug(f"Added the user to the group: {group.pk=}, {user.pk=}")

                await state.finish()

                # noinspection StrFormat
                return await message.answer(
                    emoji.emojize(
                        _("registration.complete").format(
                            **(
                                flatten_tortoise_model(
                                    await user.profile, separator="__", prefix="user__profile__"
                                )
                                | flatten_tortoise_model(group, separator="__", prefix="group__")
                            )
                        )
                    ),
                    reply_markup=aiogram.types.ReplyKeyboardRemove(),
                )
            else:
                logger.warning(f"Group not found: {group_uid_to_add_to=}")

                # noinspection StrFormat
                return await message.answer(
                    emoji.emojize(
                        _("registration.group_not_found").format(
                            group_uid_to_add_to=group_uid_to_add_to
                        )
                    ),
                    reply_markup=aiogram.types.ReplyKeyboardRemove(),
                )

    elif message.text == _("no"):
        await states.Registration.enter_coliving_name.set()
        return await message.answer(
            emoji.emojize(_("registration.enter_coliving_name")),
            reply_markup=aiogram.types.ReplyKeyboardRemove(),
        )
    else:
        return await message.answer(emoji.emojize(_("no_such_option")))


@dp.message_handler(
    state=states.Registration.enter_coliving_name, content_types=aiogram.types.ContentType.TEXT
)
async def registration_save_coliving_name(
    message: aiogram.types.Message, state: aiogram.dispatcher.FSMContext, user: User
):
    """Save the coliving name of the user."""
    logger.debug(f"Received coliving name: {message.text=}")

    # TODO: [9/2/2022 by Mykola] Implement the SupportTicket system.

    if settings.ADMIN_ID:
        await bot.send_message(
            settings.ADMIN_ID,
            f"User {user.id=} has entered the coliving name: `{message.text=}`",
        )

    await state.finish()
    return await message.answer(emoji.emojize(_("registration.complete")))


# endregion


# region Admin commands
@dp.message_handler(commands=["groups_stats"], state=aiogram.filters.state.any_state)
async def groups_stats(message: aiogram.types.Message, user: User):
    """Show the statistics of the groups."""
    logger.debug(f"Received the command: {message.text=}")

    if not user.is_admin:
        return await message.answer(emoji.emojize(_("no_permission")))

    if not (groups := await Group.all()):
        return await message.answer(emoji.emojize(_("no_groups")))

    stats = [
        f"<b>{group.name:<10}</b> ({group.uid}): <b>{await group.users.all().count()}</b> users"
        for group in groups
    ]

    return await message.answer(
        "".join([f"<b>Groups stats</b>\n\n", "<pre>", "\n".join(stats), "</pre>"]),
        parse_mode=aiogram.types.ParseMode.HTML,
    )


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
