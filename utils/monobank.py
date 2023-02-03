"""A module with all the Monobank integration logic."""
import asyncio
import typing

import aiohttp
import arrow
import stringcase
import tortoise

from models import MonobankAccount, MonobankAccountStatement, MonobankClient
from utils.loguru_logging import logger


async def pull_all_account_statements(
    monobank_account_id: str,
    continue_terminated: bool = False,
    new_account_statement_callback: typing.Callable[
        [MonobankAccountStatement], typing.Awaitable[typing.Any]
    ]
    | None = None,
) -> None:
    """Pull all account statements for the account with the given ID."""
    logger.info(f"Pulling all account statements for account `{monobank_account_id}`")
    logger.debug(f"Using {continue_terminated=}")

    monobank_account = await MonobankAccount.get(id=monobank_account_id)

    monobank_client: MonobankClient = await monobank_account.monobank_client

    _pull_statements_up_to_time: arrow.Arrow = arrow.utcnow()

    if continue_terminated:
        _oldest_statement = (
            await MonobankAccountStatement.filter(monobank_account=monobank_account)
            .order_by("time")
            .first()
        )
        if _oldest_statement:
            _pull_statements_up_to_time = arrow.Arrow.fromdatetime(_oldest_statement.time)

    while True:
        _pull_statements_from_time = _pull_statements_up_to_time.shift(months=-1)
        logger.debug(
            f"Pulling statements from {_pull_statements_from_time} to {_pull_statements_up_to_time}"
        )

        # Save the time of the API call to avoid hitting the "429 Too Many Requests" error
        _api_call_time: arrow.Arrow = arrow.utcnow()
        logger.debug(f"API call time: {_api_call_time}")

        # Pull statements
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.monobank.ua/personal/statement/{monobank_account.id}/"
                f"{_pull_statements_from_time.int_timestamp}/"
                # -1 second to avoid pulling the same statement twice
                f"{_pull_statements_up_to_time.int_timestamp - 1}",
                headers={"X-Token": monobank_client.token},
            ) as response:
                pulled_account_statements: list[dict] = await response.json()

                # If there are no statements and the last statement creates a balance
                #  equal to its amount, then we've pulled all the statements
                # NB: This has not been tested yet
                if not pulled_account_statements:
                    _last_statement = (
                        await MonobankAccountStatement.filter(monobank_account=monobank_account)
                        .order_by("-time")
                        .first()
                    )
                    if _last_statement and _last_statement.balance == _last_statement.amount:
                        logger.info("All done!")
                        return
                    logger.warning("No statements were pulled, but we're not done yet.")

                for pulled_account_statement in pulled_account_statements:
                    try:
                        account_statement = await MonobankAccountStatement.create(
                            monobank_account=monobank_account,
                            **{
                                stringcase.snakecase(key): value
                                for key, value in pulled_account_statement.items()
                            },
                        )
                        logger.info(
                            f"Created account statement with ID `{account_statement.id}` "
                            f"for account `{monobank_account.id}`"
                        )
                        if new_account_statement_callback:
                            await new_account_statement_callback(account_statement)
                    except tortoise.exceptions.IntegrityError:  # Statement already exists
                        # pass
                        logger.info("All done!")
                        return  # We've pulled all the new statements

        _pull_statements_up_to_time = min(
            _pull_statements_from_time, arrow.Arrow.fromdatetime(account_statement.time)
        )

        # Sleep to make sure we don't send more than 1 request per 60 seconds
        _time_to_sleep: float = (_api_call_time.shift(seconds=60) - arrow.utcnow()).total_seconds()
        logger.debug(f"Sleeping for {_time_to_sleep} seconds")
        await asyncio.sleep(_time_to_sleep if _time_to_sleep > 0 else 0)


async def main():
    """Pull all account statements. Used for testing."""
    # Initial setup
    from main import on_startup

    await on_startup()

    # Get the first `MonobankAccount` and pull all its statements
    monobank_account = await MonobankAccount.all().order_by("date_added").first()
    await pull_all_account_statements(monobank_account.id, continue_terminated=False)


if __name__ == "__main__":
    asyncio.run(main())
