DO $$
DECLARE constraint_name text;
BEGIN
    SELECT conname INTO constraint_name
    FROM pg_constraint
    WHERE conrelid = 'public.workorder_review'::regclass
      AND contype = 'c'
      AND pg_get_constraintdef(oid) LIKE '%sync_status%';
    IF constraint_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE public.workorder_review DROP CONSTRAINT %I', constraint_name);
    END IF;
END $$;

ALTER TABLE public.workorder_review
    ADD CONSTRAINT workorder_review_sync_status_check
    CHECK (sync_status IN ('pending', 'syncing', 'synced', 'failed', 'uncertain'));
