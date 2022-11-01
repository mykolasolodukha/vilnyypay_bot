-- upgrade --
CREATE TABLE IF NOT EXISTS "settings"
(
    "id"                            SERIAL      NOT NULL PRIMARY KEY,
    "date_added"                    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "date_updated"                  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "monobank_account_to_pay_to_id" VARCHAR(22) REFERENCES "monobank_account" ("id") ON DELETE CASCADE,
    "user_id"                       BIGINT      NOT NULL UNIQUE REFERENCES "user" ("id") ON DELETE CASCADE
);
COMMENT ON TABLE "settings" IS 'The model for the user''s settings.';

-- Insert default settings for all users, set `monobank_account_to_pay_to_id` to the first `monobank_account` there is
INSERT INTO "settings" ("user_id", "monobank_account_to_pay_to_id")
SELECT "id", (SELECT "id" FROM "monobank_account" ORDER BY "date_added" LIMIT 1)
FROM "user";

-- downgrade --
DROP TABLE IF EXISTS "settings";
