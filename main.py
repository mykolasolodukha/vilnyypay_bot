"""The main module of the application."""
import functools

import aiogram
import arrow
import emoji
from aiogram.contrib.middlewares.i18n import I18nMiddleware
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import any_state

import states
from filters.auth import AuthFilter
from middlewares.message_logging_middleware import MessagesLoggingMiddleware
from models import Group, GroupPayment, Profile, User
from settings import settings
from tasks import send_group_payment
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
_ = functools.partial(i18n.gettext, locale="uk")
__ = functools.partial(i18n.lazy_gettext, locale="uk")


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

    await states.Registration.share_first_name.set()

    return await message.answer(
        emoji.emojize(_("registration.share_first_name")),
        reply_markup=aiogram.types.ReplyKeyboardRemove(),
    )


@dp.message_handler(
    state=states.Registration.share_first_name, content_types=aiogram.types.ContentType.TEXT
)
async def registration_save_first_name(
    message: aiogram.types.Message, state: FSMContext, user: User
):
    """Save the first name of the user."""
    logger.debug(f"Received first name: {message.text=}")

    # Get user's profile and set the first name
    profile = await user.profile
    profile.first_name = message.text
    await profile.save()

    await states.Registration.share_last_name.set()

    return await message.answer(
        emoji.emojize(_("registration.share_last_name")),
        reply_markup=aiogram.types.ReplyKeyboardRemove(),
    )


@dp.message_handler(
    state=states.Registration.share_last_name, content_types=aiogram.types.ContentType.TEXT
)
async def registration_save_last_name(
    message: aiogram.types.Message, state: FSMContext, user: User
):
    """Save the last name of the user."""
    logger.debug(f"Received last name: {message.text=}")

    if not (user_profile := await user.profile):
        logger.error(f"User doesn't have a profile: {user.pk=}")
        return await message.answer(emoji.emojize(_("registration.error")))

    user_profile.last_name = message.text
    await user_profile.save()

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


# region User settings
@dp.message_handler(commands=["settings"], state=aiogram.filters.state.any_state)
async def settings(message: aiogram.types.Message):
    """Show the settings menu to the user."""
    logger.debug(f"Received the command: {message.text=}")

    await states.Settings.select_settings_type.set()

    return await message.answer(
        emoji.emojize(_("settings")),
        reply_markup=aiogram.types.ReplyKeyboardMarkup(
            resize_keyboard=True, row_width=1, one_time_keyboard=True
        ).add(
            aiogram.types.KeyboardButton(_("settings.groups")),
            aiogram.types.KeyboardButton(_("settings.profile")),
            aiogram.types.KeyboardButton(_("settings.primary_bank_account")),
        ),
    )


# region Groups settings


@dp.message_handler(
    state=states.Settings.select_settings_type,
    content_types=aiogram.types.ContentType.TEXT,
    text=__("settings.groups"),
)
async def select_group_settings(message: aiogram.types.Message):
    """Select the group settings type."""
    logger.debug(f"Received the text: {message.text=}")

    await states.GroupSettings.select_group.set()

    return await message.answer(
        emoji.emojize(_("settings.select_new_group")),
        reply_markup=aiogram.types.ReplyKeyboardMarkup(
            resize_keyboard=True, row_width=3, one_time_keyboard=True
        ).add(*[aiogram.types.KeyboardButton(group.name) for group in await Group.all()]),
    )


@dp.message_handler(
    state=states.GroupSettings.select_group, content_types=aiogram.types.ContentType.TEXT
)
async def select_group(message: aiogram.types.Message, state: FSMContext, user: User):
    """Select the group."""
    logger.debug(f"Received the text: {message.text=}")

    if group := await Group.get_or_none(name=message.text):
        # Remove the user from all the groups and add him to the new one
        await user.groups.clear()
        await user.groups.add(group)

        await state.finish()

        # noinspection StrFormat
        return await message.answer(
            emoji.emojize(
                _("settings.group_selected").format(
                    **flatten_tortoise_model(group, separator="__", prefix="group__")
                )
            ),
            reply_markup=aiogram.types.ReplyKeyboardRemove(),
        )
    else:
        return await message.answer(emoji.emojize(_("settings.group_not_found")))


# endregion


# region Profile settings
@dp.message_handler(
    state=states.Settings.select_settings_type,
    content_types=aiogram.types.ContentType.TEXT,
    text=__("settings.profile"),
)
async def select_profile_settings(message: aiogram.types.Message, state: FSMContext):
    """Select the profile settings type."""
    logger.debug(f"Received the text: {message.text=}")

    # TODO: [3/10/2023 by Mykola] Add Profile settings.

    await state.finish()

    return await message.answer(
        emoji.emojize(_("settings.not_implemented")),
        reply_markup=aiogram.types.ReplyKeyboardRemove(),
    )


# endregion


# region Primary bank account settings


@dp.message_handler(
    state=states.Settings.select_settings_type,
    content_types=aiogram.types.ContentType.TEXT,
    text=__("settings.primary_bank_account"),
)
async def select_primary_bank_account_settings(message: aiogram.types.Message, state: FSMContext):
    """Select the profile settings type."""
    logger.debug(f"Received the text: {message.text=}")

    # TODO: [3/10/2023 by Mykola] Add Primary bank account settings.

    await state.finish()

    return await message.answer(
        emoji.emojize(_("settings.not_implemented")),
        reply_markup=aiogram.types.ReplyKeyboardRemove(),
    )


# endregion


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


@dp.message_handler(commands=["create_group_payment"], state=aiogram.filters.state.any_state)
async def create_group_payment(message: aiogram.types.Message, user: User):
    """Create a payment for the group."""
    logger.debug(f"Received the command: {message.text=}")

    # TODO: [10/16/2022 by Mykola] Make a decorator for the admin commands.
    if not user.is_admin:
        return await message.answer(emoji.emojize(_("no_permission")))

    if not (groups := await Group.filter(admins__id=user.id)):
        return await message.answer(emoji.emojize(_("no_groups")))

    await states.CreatePayment.enter_group.set()

    return await message.answer(
        emoji.emojize(_("admin.create_group_payment.enter_group")),
        reply_markup=aiogram.types.ReplyKeyboardMarkup(
            resize_keyboard=True, one_time_keyboard=True
        ).add(
            *(
                # TODO: [10/19/2022 by Mykola] Make them more distinct in the keyboard.
                aiogram.types.KeyboardButton(group.name)
                for group in groups
            ),
        ),
    )


@dp.message_handler(
    state=states.CreatePayment.enter_group, content_types=aiogram.types.ContentType.TEXT
)
async def create_group_payment_enter_group(
    message: aiogram.types.Message, state: aiogram.dispatcher.FSMContext, user: User
):
    """Save the group name and ask for the payment amount."""
    logger.debug(f"Received the group name: {message.text=}")

    if not (group := await Group.filter(admins__id=user.id, name=message.text).first()):
        return await message.answer(emoji.emojize(_("no_such_group")))

    await state.update_data(group_payment__group_id=group.pk)

    await states.CreatePayment.enter_amount.set()

    return await message.answer(
        # NB: The `amount` must be specified in the smallest currency unit.
        emoji.emojize(_("admin.create_group_payment.enter_amount")),
        reply_markup=aiogram.types.ReplyKeyboardRemove(),
    )


@dp.message_handler(
    state=states.CreatePayment.enter_amount, content_types=aiogram.types.ContentType.TEXT
)
async def create_group_payment_enter_amount(
    message: aiogram.types.Message, state: aiogram.dispatcher.FSMContext, user: User
):
    """Save the payment amount and ask for the payment comment."""
    logger.debug(f"Received the payment amount: {message.text=}")

    if message.text.isdigit():
        amount = int(message.text) * 100
    else:
        try:
            amount_major_units, amount_minor_units = (int(part) for part in message.text.split("."))
        except ValueError:
            return await message.answer(
                emoji.emojize(_("admin.create_group_payment.invalid_amount"))
            )

        if (amount_major_units <= 0 and amount_minor_units <= 0) or len(
            str(amount_minor_units)
        ) != 2:
            return await message.answer(
                emoji.emojize(_("admin.create_group_payment.invalid_amount"))
            )

        # FIXME: [11/4/2022 by Mykola] The `f"{amount_major_units:02}"` doesn't work here.
        amount = int(f"{amount_major_units}{amount_minor_units:02}")

    await state.update_data(group_payment__amount=amount)

    await states.CreatePayment.enter_comment.set()

    return await message.answer(
        emoji.emojize(_("admin.create_group_payment.enter_comment")),
        reply_markup=aiogram.types.ReplyKeyboardRemove(),
    )


@dp.message_handler(
    state=states.CreatePayment.enter_comment, content_types=aiogram.types.ContentType.TEXT
)
async def create_group_payment_enter_comment(
    message: aiogram.types.Message, state: aiogram.dispatcher.FSMContext, user: User
):
    """Save the payment comment and ask for the payment's due date."""
    logger.debug(f"Received the payment comment: {message.text=}")

    await state.update_data(group_payment__comment=message.text)

    await states.CreatePayment.enter_due_date.set()

    return await message.answer(
        # NB: The `due_date` must be specified in the format `DD.MM.YYYY` or `DD MM YYYY`.
        emoji.emojize(_("admin.create_group_payment.enter_due_date")),
        reply_markup=aiogram.types.ReplyKeyboardRemove(),
    )


@dp.message_handler(
    state=states.CreatePayment.enter_due_date, content_types=aiogram.types.ContentType.TEXT
)
async def create_group_payment_enter_due_date(
    message: aiogram.types.Message, state: aiogram.dispatcher.FSMContext, user: User
):
    """Save the payment's due date and create a `models.GroupPayment`."""
    logger.debug(f"Received the payment's due date: {message.text=}")

    try:
        due_date = arrow.get(message.text.replace(" ", "."), "DD.MM.YYYY").date()
    except ValueError:
        return await message.answer(emoji.emojize(_("admin.create_group_payment.invalid_due_date")))

    if due_date < arrow.now().date():
        # TODO: [10/19/2022 by Mykola] What if a payment is due today?
        return await message.answer(emoji.emojize(_("admin.create_group_payment.invalid_due_date")))

    await state.update_data(group_payment__due_date=due_date.isoformat())

    user_state_data = await state.get_data()

    group_payment_data = {
        key.removeprefix("group_payment__"): value
        for key, value in user_state_data.items()
        if key.startswith("group_payment__")
    }

    group_payment = await GroupPayment.create(**group_payment_data, created_by=user)

    await state.finish()

    # TODO: [11/1/2022 by Mykola] Do this in a separate worker.
    await send_group_payment(group_payment.pk)

    # noinspection StrFormat
    return await message.answer(
        emoji.emojize(
            _("admin.create_group_payment.success").format(
                **flatten_tortoise_model(group_payment, separator="__", prefix="group_payment__")
            )
        ),
        reply_markup=aiogram.types.ReplyKeyboardRemove(),
    )


# endregion


# region Startup and shutdown callbacks
async def on_startup(*__, **___):
    """Startup the bot."""
    logger.info(f"Starting up the https://t.me/{(await bot.get_me()).username} bot...")

    logger.debug("Initializing the database connection...")
    await tortoise_orm.init()

    logger.debug("Setting the bot's commands...")
    await bot.set_my_commands(
        [
            aiogram.types.BotCommand("start", _("bot_command.start")),
            # TODO: [3/10/2023 by Mykola] Add the `help` command.
            # aiogram.types.BotCommand("help", _("bot_command.help")),
            aiogram.types.BotCommand("settings", _("bot_command.settings")),
        ]
    )

    logger.info("Startup complete.")


async def on_shutdown(*__, **___):
    """Shutdown the bot."""
    logger.info("Shutting down...")

    logger.debug("Closing the database connection...")
    await tortoise_orm.shutdown()

    logger.info("Shutdown complete.")


# endregion

if __name__ == "__main__":
    aiogram.executor.start_polling(dp, on_startup=on_startup, on_shutdown=on_shutdown)
