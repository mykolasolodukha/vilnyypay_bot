-- upgrade --
CREATE TABLE "group__admin"
(
    "group_id" INT    NOT NULL REFERENCES "group" ("id") ON DELETE CASCADE,
    "user_id"  BIGINT NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE
);

-- Set default group admins
INSERT INTO "group__admin" ("group_id", "user_id")
SELECT "id", "created_by_user_id"
FROM "group";

-- downgrade --
DROP TABLE IF EXISTS "group__admin";
