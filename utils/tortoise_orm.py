"""The `tortoise-orm` configuration module."""

import ssl

from tortoise import expand_db_url, Tortoise

from settings import settings


def get_tortoise_config():
    """Get the configuration for the `tortoise-orm`."""
    ctx = ssl.create_default_context(cafile="")
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    db = expand_db_url(settings.DATABASE_URL)
    db["credentials"]["ssl"] = ctx

    tortoise_config = {
        "connections": {"default": db},
        "apps": {
            "bot": {
                "models": [
                    "models",
                    "aerich.models",
                ],
                "default_connection": "default",
            }
        },
    }
    return tortoise_config


async def init():
    """Initialize the `tortoise-orm`."""
    # Init database connection
    await Tortoise.init(config=get_tortoise_config())
    # Generate the schema
    await Tortoise.generate_schemas()


async def shutdown():
    """Shutdown the `tortoise-orm`."""
    await Tortoise.close_connections()


# Used by aerich.ini
TORTOISE_ORM_CONFIG = get_tortoise_config()
