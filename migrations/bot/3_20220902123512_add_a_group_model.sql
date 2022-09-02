-- upgrade --
CREATE TABLE IF NOT EXISTS "group"
(
    "id"                 SERIAL      NOT NULL PRIMARY KEY,
    "date_added"         TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "date_updated"       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "name"               TEXT        NOT NULL,
    "uid"                VARCHAR(4)  NOT NULL UNIQUE,
    "created_by_user_id" BIGINT      NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE
);
COMMENT ON TABLE "group" IS 'The model for the group of users.';;
CREATE TABLE "group_user"
(
    "user_id"  BIGINT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE,
    "group_id" INT    NOT NULL REFERENCES "group" ("id") ON DELETE CASCADE
);
-- downgrade --
DROP TABLE IF EXISTS "group_user";
DROP TABLE IF EXISTS "group";
