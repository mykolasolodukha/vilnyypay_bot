"""The `aiogram` states module."""

from aiogram.dispatcher.filters.state import State, StatesGroup


class Registration(StatesGroup):
    """The states that a user can be in during the registration process."""

    share_phone_number = State()
    share_first_name = State()
    share_last_name = State()
    confirm_coliving = State()
    enter_coliving_name = State()


class CreatePayment(StatesGroup):
    """The states that a user can be in during the payment creation process."""

    enter_group = State()
    enter_amount = State()
    enter_comment = State()
    enter_due_date = State()


class GroupSettings(StatesGroup):
    """The states that allows a user to change their group."""

    select_group = State()


class BankAccountSettings(StatesGroup):
    """The states that allows a user to change their bank account."""

    select_bank_account = State()


class ProfileSettings(StatesGroup):
    """The states that allows a user to change their profile."""

    enter_first_name = State()
    enter_last_name = State()


class Settings(StatesGroup):
    """The states that a user can be in during the settings process."""

    select_settings_type = State()
