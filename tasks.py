"""All the asynchronous tasks are defined here."""
import datetime
import typing

import aiogram
import arrow
import babel

from models import GroupPayment, Paycheck, User
from settings import settings
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
    from main import bot, i18n

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
        i18n.gettext(
            "tasks.notification.payment_created",
            locale=(
                _locale_language
                if (_locale_language := _user_locale.language) in i18n.locales
                else i18n.default
            ),
        ).format(**payment_template_data),
        reply_markup=aiogram.types.ReplyKeyboardRemove(),
        parse_mode=aiogram.types.ParseMode.HTML,
    )


async def send_group_payment(group_payment_id: int) -> None:
    """Send a group payment to the group users."""
    group_payment = await GroupPayment.get(id=group_payment_id)

    # Send the group payment to the group users
    for user in await (await group_payment.group).users.all():
        paycheck: Paycheck = await _generate_paycheck_for_user(group_payment, user)
        await _send_paycheck_to_user(paycheck)
