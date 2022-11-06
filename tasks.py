"""All the asynchronous tasks are defined here."""
import base64
import datetime
import typing

import aiogram
import arrow
import babel
import emoji

from models import GroupPayment, Paycheck, User
from settings import settings
from utils.i18n import custom_gettext as _
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


def _generate_payment_link(
    receiver: str, iban: str, amount: int, edrpou: str, comment: str
) -> str:
    """
    Generate a payment link.

    According to https://bank.gov.ua/admin_uploads/law/01022021_11.pdf?v=4.
    """
    base64_data = base64.b64encode(
        (
            f"BCD\n"  # service code
            f"002\n"  # version
            f"2\n"  # encoding: 1 - Windows-1251, 2 - UTF-8
            f"UCT\n"  # function code: UTC for "Ukrainian Credit Transfer"
            f"\n"  # BIC: Bank Identifier Code (not used)
            f"{receiver}\n"  # receiver name
            f"{iban}\n"  # IBAN
            f"UAH{amount / 100:.2f}\n"  # amount
            f"{edrpou}\n"  # receiver tax id
            f"\n"  # RFU (not used, reserved for future use)
            f"\n"  # Reference to RFU (not used, reserved for future use)
            f"{comment}\n"  # comment
        ).encode("utf-8")
    )

    return f"https://bank.gov.ua/qr/{base64_data.decode('utf-8')}"


async def generate_link_from_paycheck(paycheck: Paycheck) -> str:
    """Generate a payment link from the paycheck."""
    # Create the payment's comment message
    # TODO: [11/6/2022 by Mykola] DRY when it comes to the comment message in the payment message
    #  and the payment link
    _comment = paycheck.comment

    # TODO: [11/6/2022 by Mykola] Remove the need to do multiple fetches
    await paycheck.fetch_related("generated_from_group_payment__group")
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


async def _send_paycheck_to_user(paycheck: Paycheck) -> None:
    """Send a paycheck to the user."""
    from main import bot

    await paycheck.fetch_related(
        "for_user__settings__monobank_account_to_pay_to", "generated_from_group_payment__group"
    )

    user: User = paycheck.for_user
    _user_locale = babel.core.Locale.parse(user.language_code, sep="-")

    payment_template_data = {
        key: formatter(value) if (formatter := PAYMENT_FORMATTERS.get(key)) else value
        for key, value in flatten_tortoise_model(
            paycheck, separator="__", prefix="paycheck__"
        ).items()
    }

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


async def send_group_payment(group_payment_id: int) -> None:
    """Send a group payment to the group users."""
    group_payment = await GroupPayment.get(id=group_payment_id)

    # Send the group payment to the group users
    for user in await (await group_payment.group).users.all():
        if await Paycheck.exists(generated_from_group_payment=group_payment, for_user=user):
            continue

        paycheck: Paycheck = await _generate_paycheck_for_user(group_payment, user)
        await _send_paycheck_to_user(paycheck)
