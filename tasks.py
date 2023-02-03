"""All the asynchronous tasks are defined here."""
import asyncio
import base64
import datetime
import random
import re
import typing
from uuid import UUID

import aiogram
import aiogram.utils.exceptions
import arrow
import babel
import emoji

from models import GroupPayment, MonobankAccount, MonobankAccountStatement, Paycheck, User
from settings import settings
from utils.i18n import custom_gettext as _
from utils.loguru_logging import logger
from utils.monobank import pull_all_account_statements
from utils.tortoise_orm import flatten_tortoise_model

# noinspection StrFormat
PAYMENT_FORMATTERS: dict[str, typing.Callable[[int | datetime.datetime], str | int]] = {
    "paycheck__amount": lambda amount: amount / 100,
    "paycheck__generated_from_group_payment__due_date": lambda due_date: arrow.Arrow.fromdatetime(
        due_date
    )
    .to(settings.TIMEZONE)
    .format("DD.MM.YYYY"),
}


def _generate_payment_link(receiver: str, iban: str, amount: int, edrpou: str, comment: str) -> str:
    """
    Generate a payment link.

    According to https://bank.gov.ua/admin_uploads/law/01022021_11.pdf?v=4.
    """
    base64_data = base64.b64encode(
        (
            f"BCD\n"  # service code
            f"002\n"  # version
            f"2\n"  # encoding: 1 - UTF-8, 2 - Windows-1251
            f"UCT\n"  # function code: UTC for "Ukrainian Credit Transfer"
            f"\n"  # BIC: Bank Identifier Code (not used)
            f"{receiver}\n"  # receiver name
            f"{iban}\n"  # IBAN
            f"UAH{amount / 100:.2f}\n"  # amount
            f"{edrpou}\n"  # receiver tax id
            f"\n"  # RFU (not used, reserved for future use)
            f"\n"  # Reference to RFU (not used, reserved for future use)
            f"{comment}\n"  # comment
        ).encode("windows-1251")
    )

    qr_data = base64_data.decode("utf-8").replace("+", "-").replace("/", "_").replace("=", "")
    return f"https://bank.gov.ua/qr/{qr_data}"


async def generate_link_from_paycheck(paycheck: Paycheck) -> str:
    """Generate a payment link from the paycheck."""
    # Create the payment's comment message
    # TODO: [11/6/2022 by Mykola] DRY when it comes to the comment message in the payment message
    #  and the payment link
    _comment = paycheck.comment

    # TODO: [11/6/2022 by Mykola] Remove the need to do multiple fetches
    await paycheck.fetch_related("generated_from_group_payment__group", "to_account")
    if paycheck.generated_from_group_payment:
        _comment += f" [{paycheck.generated_from_group_payment.group.name}]"

    _comment += f" [{paycheck.id}]"

    # Generate a payment link
    return _generate_payment_link(
        receiver=paycheck.to_account.name,
        iban=paycheck.to_account.iban,
        amount=paycheck.amount,
        edrpou=paycheck.to_account.edrpou,
        comment=f"{paycheck.comment} [{paycheck.generated_from_group_payment.group.name}] [{paycheck.id}]",
    )


async def _generate_paycheck_for_user(group_payment: GroupPayment, user: User) -> Paycheck:
    """Generate a paycheck for the user."""
    return await Paycheck.create(
        for_user=user,
        to_account=await (await user.settings).monobank_account_to_pay_to,
        amount=group_payment.amount,
        currency_symbol="UAH",
        currency_code=980,
        comment=group_payment.comment,
        generated_from_group_payment=group_payment,
    )


async def _get_payment_template_data(paycheck: Paycheck) -> dict[str, typing.Any]:
    """Get the data for the payment template."""
    await paycheck.fetch_related(
        "for_user__settings__monobank_account_to_pay_to", "generated_from_group_payment__group"
    )

    payment_template_data = {
        key: formatter(value) if (formatter := PAYMENT_FORMATTERS.get(key)) else value
        for key, value in flatten_tortoise_model(
            paycheck, separator="__", prefix="paycheck__"
        ).items()
    }

    return payment_template_data


async def _send_paycheck_to_user(paycheck: Paycheck) -> None:
    """Send a paycheck to the user."""
    from main import bot

    payment_template_data = await _get_payment_template_data(paycheck)

    user: User = paycheck.for_user
    _user_locale = babel.core.Locale.parse(user.language_code, sep="-")

    try:
        # noinspection StrFormat
        await bot.send_message(
            user.id,
            emoji.emojize(
                # FIXME: [11/6/2022 by Mykola] This might not work with `pybabel extract`
                _("tasks.notifications.payment_created.message", _user_locale).format(
                    **payment_template_data
                )
            ),
            reply_markup=aiogram.types.InlineKeyboardMarkup().add(
                aiogram.types.InlineKeyboardButton(
                    text=emoji.emojize(
                        _("tasks.notifications.payment_created.pay_button", _user_locale)
                    ),
                    url=await generate_link_from_paycheck(paycheck),
                )
            ),
            parse_mode=aiogram.types.ParseMode.HTML,
        )
    except aiogram.utils.exceptions.BotBlocked:
        logger.info(f"Bot blocked by the {user.id=} ({user.username=})")

        logger.debug(f"Setting {user.id=} ({user.username=}) as inactive...")
        user.is_active = False
        await user.save(update_fields=["is_active"])


async def send_group_payment(group_payment_id: int) -> None:
    """Send a group payment to the group users."""
    group_payment = await GroupPayment.get(id=group_payment_id)

    # Send the group payment to the group users
    for user in await (await group_payment.group).users.all():
        if await Paycheck.exists(generated_from_group_payment=group_payment, for_user=user):
            continue

        paycheck: Paycheck = await _generate_paycheck_for_user(group_payment, user)
        await _send_paycheck_to_user(paycheck)


async def send_payment_received_message(paycheck_id: UUID) -> aiogram.types.Message:
    """Send a message to the user that the payment has been received."""
    from main import bot

    paycheck = await Paycheck.get(id=paycheck_id)

    payment_template_data = await _get_payment_template_data(paycheck)

    user: User = paycheck.for_user
    _user_locale = babel.core.Locale.parse(user.language_code, sep="-")

    # noinspection StrFormat
    return await bot.send_message(
        user.id,
        emoji.emojize(
            _("tasks.notifications.payment_received.message", _user_locale).format(
                **payment_template_data
            )
        ),
        parse_mode=aiogram.types.ParseMode.HTML,
    )


async def process_new_account_statement(account_statement: MonobankAccountStatement) -> None:
    """
    Process new account statement.

    Also, make the `Paycheck.is_paid` field `True` if the statement meets the requirements.
    """
    # Check if there is a UUID in the `account_statement.description`
    uuid_in_square_brackets_pattern: re.Pattern = re.compile(
        r"\[(?P<uuid>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\]"
    )
    match: re.Match | None = uuid_in_square_brackets_pattern.search(account_statement.comment)
    if not match:
        logger.error(
            f"Received a statement without a UUID in the comment: {account_statement.comment=}"
        )

    # Get the `Paycheck` by the UUID
    paycheck: Paycheck = await Paycheck.get(id=UUID(match.group("uuid")))

    # Check if the `Paycheck` is already paid
    if paycheck.is_paid:
        logger.error(f"Paycheck {paycheck.id=} is already paid")
        return

    # Set the `Paycheck.is_paid` field to `True`
    paycheck.is_paid = True
    await paycheck.save()

    # Send a message to the user that the payment has been received
    await send_payment_received_message(paycheck.id)


async def monitor_paychecks() -> None:
    """Monitor the paychecks."""
    # NB: This _might not_ work when there are multiple `MonobankAccount`s and/or multiple
    #  `MonobankClient`s processing at once, for multiple reasons:
    #  1. The "429 Too Many Requests" error might be raised by Monobank API
    #  2. Monobank might consider this a non-private usage of their API
    #   (one must apply for a commercial access).

    while True:
        # Pull all account statements from Monobank for all the `MonobankAccount`s
        await asyncio.gather(
            *(
                pull_all_account_statements(
                    monobank_account.id,
                    new_account_statement_callback=process_new_account_statement,
                )
                # for monobank_account in await MonobankAccount.all()
                # TODO: [2/3/2023 by Mykola] Make it work for multiple `MonobankAccount`s
                for monobank_account in [await MonobankAccount.all().order_by("date_added").first()]
            )
        )

        # Sleep for a random time between 1 and 2 minutes
        await asyncio.sleep(random.randint(60, 60 * 2))
