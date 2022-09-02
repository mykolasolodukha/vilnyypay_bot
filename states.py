"""The `aiogram` states module."""

from aiogram.dispatcher.filters.state import State, StatesGroup


class Registration(StatesGroup):
    """The states that a user can be in during the registration process."""

    share_phone_number = State()
    share_full_name = State()
    confirm_coliving = State()
    enter_coliving_name = State()
