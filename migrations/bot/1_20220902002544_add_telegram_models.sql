-- upgrade --
CREATE TABLE IF NOT EXISTS "user"
(
    "date_added"      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "date_updated"    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "id"              BIGINT      NOT NULL PRIMARY KEY,
    "username"        VARCHAR(32),
    "first_name"      TEXT,
    "last_name"       TEXT,
    "phone_number"    VARCHAR(14),
    "language_code"   VARCHAR(2),
    "is_bot"          BOOL        NOT NULL DEFAULT FALSE,
    "start_payload"   TEXT,
    "is_active"       BOOL        NOT NULL DEFAULT TRUE,
    "has_bot_blocked" BOOL        NOT NULL DEFAULT FALSE,
    "is_beta"         BOOL        NOT NULL DEFAULT FALSE,
    "is_deleted"      BOOL        NOT NULL DEFAULT FALSE,
    "is_admin"        BOOL        NOT NULL DEFAULT FALSE,
    "is_staff_member" BOOL        NOT NULL DEFAULT FALSE
);
COMMENT ON TABLE "user" IS 'The model for the Telegram user.';
CREATE TABLE IF NOT EXISTS "message"
(
    "id"           SERIAL      NOT NULL PRIMARY KEY,
    "date_added"   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "date_updated" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "message_id"   INT         NOT NULL,
    "chat_id"      BIGINT,
    "content_type" TEXT,
    "text"         TEXT,
    "date"         TIMESTAMPTZ NOT NULL,
    "user_id"      BIGINT      NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE
);
COMMENT ON TABLE "message" IS 'The model for the Telegram message.';;
-- downgrade --
DROP TABLE IF EXISTS "message";
DROP TABLE IF EXISTS "user";
