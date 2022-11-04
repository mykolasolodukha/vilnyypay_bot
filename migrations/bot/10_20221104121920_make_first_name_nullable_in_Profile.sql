-- upgrade --
ALTER TABLE "profile" ALTER COLUMN "first_name" DROP NOT NULL;
-- downgrade --
ALTER TABLE "profile" ALTER COLUMN "first_name" SET NOT NULL;
