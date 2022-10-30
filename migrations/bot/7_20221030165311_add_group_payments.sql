-- upgrade --
CREATE TABLE IF NOT EXISTS "group_payment"
(
    "id"           SERIAL      NOT NULL PRIMARY KEY,
    "date_added"   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "date_updated" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "amount"       INT         NOT NULL,
    "comment"      TEXT        NOT NULL,
    "due_date"     TIMESTAMPTZ NOT NULL,
    "creator_id"   BIGINT      NOT NULL REFERENCES "user" ("id") ON DELETE CASCADE,
    "group_id"     INT         NOT NULL REFERENCES "group" ("id") ON DELETE CASCADE
);
COMMENT ON TABLE "group_payment" IS 'The model for the group payment.';;
ALTER TABLE "paycheck"
    ADD "generated_from_group_payment_id" INT;
ALTER TABLE "paycheck"
    ADD CONSTRAINT "fk_paycheck_group_pa_07966bdb" FOREIGN KEY ("generated_from_group_payment_id") REFERENCES "group_payment" ("id") ON DELETE CASCADE;
-- downgrade --
ALTER TABLE "paycheck"
    DROP CONSTRAINT "fk_paycheck_group_pa_07966bdb";
ALTER TABLE "paycheck"
    DROP COLUMN "generated_from_group_payment_id";
DROP TABLE IF EXISTS "group_payment";
