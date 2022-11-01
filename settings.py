"""The module for the settings of the application."""
import pydantic


class Settings(pydantic.BaseSettings):
    """Settings for the Telegram bot."""

    TELEGRAM_BOT_TOKEN: str

    DATABASE_URL: pydantic.PostgresDsn
    REDIS_URL: pydantic.RedisDsn

    ADMIN_ID: int | None = None

    TIMEZONE: str = "Europe/Kiev"

    class Config:
        """Configuration for the settings."""

        env_file = ".env"


settings = Settings()
