BEGIN;

ALTER TABLE public.workorder_review
    ADD COLUMN IF NOT EXISTS lock_fencing_token BIGINT NOT NULL DEFAULT 0;

COMMIT;
