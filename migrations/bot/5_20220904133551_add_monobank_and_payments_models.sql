-- upgrade --
CREATE TABLE IF NOT EXISTS "monobank_client"
(
    "id"           SERIAL      NOT NULL PRIMARY KEY,
    "date_added"   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "date_updated" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "token"        TEXT        NOT NULL,
    "client_id"    TEXT,
    "name"         TEXT,
    "web_hook_url" TEXT,
    "permissions"  VARCHAR(4)  NOT NULL,
    "user_id"      BIGINT      NOT NULL UNIQUE REFERENCES "user" ("id") ON DELETE CASCADE
);
COMMENT ON TABLE "monobank_client" IS 'The model for the Monobank client.';;
CREATE TABLE IF NOT EXISTS "monobank_account"
(
    "date_added"         TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "date_updated"       TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "id"                 VARCHAR(22)  NOT NULL PRIMARY KEY,
    "send_id"            VARCHAR(10),
    "currency_code"      SMALLINT     NOT NULL,
    "cashback_type"      VARCHAR(255) NOT NULL,
    "balance"            BIGINT       NOT NULL,
    "credit_limit"       BIGINT       NOT NULL,
    "masked_pan"         VARCHAR(16),
    "type"               VARCHAR(16)  NOT NULL,
    "iban"               VARCHAR(29)  NOT NULL,
    "monobank_client_id" INT          NOT NULL REFERENCES "monobank_client" ("id") ON DELETE CASCADE
);
COMMENT ON TABLE "monobank_account" IS 'The model for the Monobank account.';;
CREATE TABLE IF NOT EXISTS "paycheck"
(
    "date_added"      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "date_updated"    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "id"              UUID        NOT NULL PRIMARY KEY,
    "comment"         TEXT        NOT NULL,
    "amount"          INT         NOT NULL,
    "currency_symbol" VARCHAR(3)  NOT NULL,
    "currency_code"   SMALLINT    NOT NULL,
    "is_paid"         BOOL        NOT NULL DEFAULT FALSE,
    "for_user_id"     BIGINT      NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE,
    "to_account_id"   VARCHAR(22) REFERENCES "monobank_account" ("id") ON DELETE SET NULL
);
COMMENT ON TABLE "paycheck" IS 'The model for the paycheck.';;
CREATE TABLE IF NOT EXISTS "monobank_account_statement"
(
    "date_added"          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "date_updated"        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "id"                  VARCHAR(16) NOT NULL PRIMARY KEY,
    "time"                TIMESTAMPTZ NOT NULL,
    "description"         TEXT        NOT NULL,
    "comment"             TEXT,
    "mcc"                 INT         NOT NULL,
    "original_mcc"        INT         NOT NULL,
    "amount"              INT         NOT NULL,
    "operation_amount"    INT         NOT NULL,
    "currency_code"       INT         NOT NULL,
    "commission_rate"     INT         NOT NULL,
    "cashback_amount"     INT         NOT NULL,
    "balance"             INT         NOT NULL,
    "hold"                BOOL        NOT NULL,
    "receipt_id"          VARCHAR(255),
    "invoice_id"          VARCHAR(255),
    "counterEdrpou"       VARCHAR(255),
    "counterIban"         VARCHAR(255),
    "monobank_account_id" VARCHAR(22) NOT NULL REFERENCES "monobank_account" ("id") ON DELETE CASCADE,
    "paycheck_id"         UUID REFERENCES "paycheck" ("id") ON DELETE CASCADE
);
COMMENT ON TABLE "monobank_account_statement" IS 'The model for the Monobank account statement.';;
-- downgrade --
DROP TABLE IF EXISTS "monobank_account";
DROP TABLE IF EXISTS "monobank_account_statement";
DROP TABLE IF EXISTS "monobank_client";
DROP TABLE IF EXISTS "paycheck";
