-- upgrade --
ALTER TABLE "group_payment"
    DROP CONSTRAINT "fk_group_pa_user_abc30bc5";
ALTER TABLE "group_payment"
    RENAME COLUMN "creator_id" TO "created_by_id";
ALTER TABLE "group_payment"
    ADD CONSTRAINT "fk_group_pa_user_5a4364bc" FOREIGN KEY ("created_by_id") REFERENCES "user" ("id") ON DELETE CASCADE;
-- downgrade --
ALTER TABLE "group_payment"
    DROP CONSTRAINT "fk_group_pa_user_5a4364bc";
ALTER TABLE "group_payment"
    RENAME COLUMN "created_by_id" TO "creator_id";
ALTER TABLE "group_payment"
    ADD CONSTRAINT "fk_group_pa_user_abc30bc5" FOREIGN KEY ("creator_id") REFERENCES "user" ("id") ON DELETE CASCADE;
