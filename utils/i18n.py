"""All the utilities around localizations."""

import babel


def custom_gettext(key: str, user_locale: babel.core.Locale) -> str:
    """
    Get the translation for the key in the user's locale.

    This is basically a workaround for the fact that `i18n.gettext` doesn't support passing a
    `babel.core.Locale` instance as the `locale` argument, and defaulting to the `i18n.default`
    locale if the user's locale is not supported.
    """
    from main import i18n

    return i18n.gettext(
        key,
        locale=(
            _locale_language
            if (_locale_language := user_locale.language) in i18n.locales
            else i18n.default
        ),
    )


__all__ = ["custom_gettext"]
