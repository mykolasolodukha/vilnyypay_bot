-- upgrade --
CREATE TABLE IF NOT EXISTS "profile"
(
    "id"           SERIAL      NOT NULL PRIMARY KEY,
    "date_added"   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "date_updated" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "full_name"    TEXT        NOT NULL,
    "user_id"      BIGINT      NOT NULL UNIQUE REFERENCES "user" ("id") ON DELETE CASCADE
);
COMMENT ON TABLE "profile" IS 'The model for the user''s profile.';
-- downgrade --
DROP TABLE IF EXISTS "profile";
