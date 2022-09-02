# [VilnyyPay Bot](https://t.me/vilnyypay_bot?start=readme)

A bot for managing payments for a network of Vilnyy co-livings.

## How to use?

* Create your Telegram bot using the [BotFather bot](https://telegram.me/botfather).
* Add the Telegram bot token to the `.env` file.
* Create a Postgres database and a Redis database.
* Using the `.env.example` file as an example, create an `.env` file and add there the following variables:
    - the Telegram bot token;
    - the URL of the Postgres database;
    - the URL of the Redis database;
* Install the dependencies:
    ```shell
    make env
    ```
* Compile the locales:
    ```shell
    pybabel compile --directory ./locales
    ```
* Run the bot using
    ```shell
    make run
    ```

## How to update the literals (the bot's messages)?

The project uses [POEditor](https://poeditor.com/) to manage locales.
Here is [the Project's page](https://poeditor.com/projects/view?id=557099) in POEditor.

### To update the locales after you add/change literals in Python files:

* Extract the identifiers/terms using
    ```shell
    pybabel extract --input-dirs . --output ./locales/messages.pot
    ```
* Import the identifiers/terms into POEditor.
* Translate the identifiers/terms into the desired languages.
* Update the locales/translations (see below).

### To update locales/translations:

* Go to the [project page](https://poeditor.com/projects/view?id=557099).
* [Optional] Make the changes in the project.
* Select the language you want to export.
* Export the `.mo` file and save it as `./locales/$YOUR_LANGUAGE/LC_MESSAGES/messages.po` file.
* Compile the locales using
    ```shell
    pybabel compile --directory ./locales
    ```

**NB: More info on how to use locales can be found in
the [`aiogram`'s documentation](https://docs.aiogram.dev/en/dev-3.x/utils/i18n.html#deal-with-babel).**

---
#### TODO:

* Ask for an email address to send invoices to. 