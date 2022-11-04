-- upgrade --
ALTER TABLE "profile"
    RENAME COLUMN "full_name" TO "first_name";
ALTER TABLE "profile"
    ADD "last_name" TEXT;
-- downgrade --
ALTER TABLE "profile"
    RENAME COLUMN "first_name" TO "full_name";
ALTER TABLE "profile"
    DROP COLUMN "last_name";
