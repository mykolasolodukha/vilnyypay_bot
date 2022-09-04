-- upgrade --
ALTER TABLE "group_user" RENAME TO "group__user";
-- downgrade --
ALTER TABLE "group__user" RENAME TO "group_user";
