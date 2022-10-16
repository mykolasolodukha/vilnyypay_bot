-- upgrade --
CREATE TABLE "group__admin"
(
    "group_id" INT    NOT NULL REFERENCES "group" ("id") ON DELETE CASCADE,
    "user_id"  BIGINT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE
);
-- downgrade --
DROP TABLE IF EXISTS "group__admin";
