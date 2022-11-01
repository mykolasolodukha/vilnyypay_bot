"""The models used in the application."""

from __future__ import annotations

import typing
import uuid

from tortoise import fields

from utils.tortoise_orm import Model


class BaseModel(Model):
    """The base model for all models."""

    date_added = fields.DatetimeField(auto_now_add=True)
    date_updated = fields.DatetimeField(auto_now=True)

    class Meta:
        """The metaclass for the base model."""

        abstract = True


# region Telegram models
class User(BaseModel):
    """
    The model for the Telegram user.

    This model stores all the information about the user.
    It is also used to store all the authentication-related information.
    """

    id = fields.BigIntField(pk=True, generated=False)

    username = fields.CharField(max_length=32, null=True)

    first_name = fields.TextField(null=True)
    last_name = fields.TextField(null=True)

    phone_number = fields.CharField(max_length=14, null=True)
    language_code = fields.CharField(max_length=2, null=True)
    is_bot = fields.BooleanField(default=False)

    start_payload = fields.TextField(null=True)

    is_active = fields.BooleanField(default=True)
    has_bot_blocked = fields.BooleanField(default=False)
    is_beta = fields.BooleanField(default=False)
    is_deleted = fields.BooleanField(default=False)

    is_admin = fields.BooleanField(default=False)
    is_staff_member = fields.BooleanField(default=False)

    messages: fields.ReverseRelation[Message]

    profile: fields.BackwardOneToOneRelation[Profile]
    settings: fields.BackwardOneToOneRelation[Settings]

    groups: fields.ManyToManyRelation[Group]
    admin_in_groups: fields.ManyToManyRelation[Group]
    created_group_payments: fields.ReverseRelation[GroupPayment]

    received_paychecks: fields.ReverseRelation[Paycheck]

    monobank_client: fields.BackwardOneToOneRelation[MonobankClient]
    created_groups: fields.ReverseRelation[Group]

    @property
    def full_name(self):
        """Get the full name of the user."""
        if not self.last_name:
            return self.first_name

        return f"{self.first_name} {self.last_name}"


class Message(BaseModel):
    """The model for the Telegram message."""

    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "bot.User", related_name="messages"
    )

    message_id = fields.IntField()
    chat_id = fields.BigIntField(null=True)

    content_type = fields.TextField(null=True)
    text = fields.TextField(null=True)

    date = fields.DatetimeField()


# endregion


# region User-related models
class Profile(BaseModel):
    """The model for the user's profile."""

    user: fields.OneToOneRelation[User] = fields.OneToOneField("bot.User", related_name="profile")

    full_name = fields.TextField()


class Settings(BaseModel):
    """The model for the user's settings."""

    user: fields.OneToOneRelation[User] = fields.OneToOneField("bot.User", related_name="settings")

    monobank_account_to_pay_to: fields.ForeignKeyRelation[MonobankAccount] = fields.ForeignKeyField(
        "bot.MonobankAccount", related_name="paying_users_settings", null=True
    )


# endregion


class Group(BaseModel):
    """The model for the group of users."""

    name = fields.TextField()
    uid = fields.CharField(max_length=4, unique=True)

    # TODO: [10/27/2022 by Mykola] Rename `.users` to `.members`
    users: fields.ManyToManyRelation[User] = fields.ManyToManyField(
        "bot.User", through="group__user", related_name="groups"
    )
    admins: fields.ManyToManyRelation[User] = fields.ManyToManyField(
        "bot.User", through="group__admin", related_name="admin_in_groups"
    )

    created_by_user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "bot.User", related_name="created_groups"
    )
    payments: fields.ReverseRelation[GroupPayment]


# region Monobank models
class MonobankClient(BaseModel):
    """The model for the Monobank client."""

    user: fields.OneToOneRelation[User] = fields.OneToOneField(
        "bot.User", related_name="monobank_client"
    )

    token = fields.TextField()

    client_id = fields.TextField(null=True)
    name = fields.TextField(null=True)
    web_hook_url = fields.TextField(null=True)
    permissions = fields.CharField(max_length=4)

    monobank_accounts: fields.ReverseRelation[MonobankAccount]


class MonobankAccount(BaseModel):
    """The model for the Monobank account."""

    monobank_client: fields.ForeignKeyRelation[MonobankClient] = fields.ForeignKeyField(
        "bot.MonobankClient", related_name="monobank_accounts"
    )

    id = fields.CharField(max_length=22, pk=True)
    send_id = fields.CharField(max_length=10, null=True)
    currency_code = fields.SmallIntField()
    cashback_type = fields.CharField(max_length=255)
    balance = fields.BigIntField()
    credit_limit = fields.BigIntField()
    masked_pan = fields.CharField(max_length=16, null=True)
    type: typing.Literal[
        "black", "white", "platinum", "iron", "fop", "yellow", "eAid"
    ] = fields.CharField(max_length=16)
    iban = fields.CharField(max_length=29)

    account_statements: fields.ReverseRelation[MonobankAccountStatement]

    paying_users_settings: fields.ReverseRelation[Settings]

    paychecks: fields.ReverseRelation[Paycheck]

    def __str__(self):
        """
        Get the human-readable representation of the account.

        NB: In case of a "fop" account, the masked PAN is unavailable, so we use the IBAN instead.
        """
        return f"{self.masked_pan or self.iban} ({self.balance / 100} {self.currency_code})"


class MonobankAccountStatement(BaseModel):
    """The model for the Monobank account statement."""

    monobank_account: fields.ForeignKeyRelation[MonobankAccount] = fields.ForeignKeyField(
        "bot.MonobankAccount", related_name="account_statements"
    )

    id = fields.CharField(max_length=16, pk=True)
    time = fields.DatetimeField()

    description = fields.TextField()
    comment = fields.TextField(null=True, default=None)

    mcc = fields.IntField()
    original_mcc = fields.IntField()

    amount = fields.IntField()
    operation_amount = fields.IntField()
    currency_code = fields.IntField()
    commission_rate = fields.IntField()
    cashback_amount = fields.IntField()

    balance = fields.IntField()

    hold = fields.BooleanField()

    receipt_id = fields.CharField(max_length=255, null=True, default=None)
    invoice_id = fields.CharField(max_length=255, null=True, default=None)

    # The following fields exist only if `MonobankAccount.type == "fop"`
    counterEdrpou = fields.CharField(max_length=255, null=True, default=None)
    counterIban = fields.CharField(max_length=255, null=True, default=None)

    # The `paycheck` field would be populated after an `AccountStatement` matched with a `Paycheck`,
    # basically meaning that "this particular `AccountStatement`(-s) is a result of someone paying
    # this particular `Paycheck`"
    paycheck: fields.ForeignKeyNullableRelation[Paycheck] = fields.ForeignKeyField(
        "bot.Paycheck", related_name="paid_account_statements", null=True, default=None
    )


# endregion


# region Payments models
class Paycheck(BaseModel):
    """
    The model for the paycheck.

    A Paycheck is at the core of the bot's functionality. It is created for a user and then , after
    the user has paid it, matched with the corresponding account statements.
    """

    for_user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "bot.User", related_name="received_paychecks"
    )
    to_account: fields.ForeignKeyRelation[MonobankAccount] = fields.ForeignKeyField(
        "bot.MonobankAccount", related_name="paychecks", on_delete=fields.SET_NULL, null=True
    )

    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    comment = fields.TextField()

    amount = fields.IntField()
    currency_symbol = fields.CharField(max_length=3)
    currency_code = fields.SmallIntField()

    is_paid = fields.BooleanField(default=False)
    generated_from_group_payment: fields.ForeignKeyNullableRelation[
        GroupPayment
    ] = fields.ForeignKeyField(
        "bot.GroupPayment", related_name="generated_paychecks", null=True, default=None
    )

    paid_account_statements: fields.ReverseRelation[MonobankAccountStatement]


class GroupPayment(BaseModel):
    """
    The model for the group payment.

    This allows saving the group payments to the database, generating `Paycheck`s, and keeping
    track of them after.
    """

    group: fields.ForeignKeyRelation[Group] = fields.ForeignKeyField(
        "bot.Group", related_name="payments"
    )

    amount = fields.IntField()
    comment = fields.TextField()  # TODO: [10/19/2022 by Mykola] Allow nullable comments
    due_date = fields.DatetimeField()

    creator: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "bot.User", related_name="created_group_payments"
    )

    generated_paychecks: fields.ReverseRelation[Paycheck]


# endregion
