"""All the tasks that are run periodically."""
import asyncio

from tasks import monitor_paychecks


async def main():
    """Run all the tasks."""
    # Initial setup for the worker
    from main import on_startup

    await on_startup()

    await monitor_paychecks()
    # In the future, we can add more tasks here


if __name__ == "__main__":
    asyncio.run(main())
