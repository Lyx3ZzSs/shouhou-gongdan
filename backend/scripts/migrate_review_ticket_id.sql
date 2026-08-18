BEGIN;

ALTER TABLE public.workorder_review
    ADD COLUMN IF NOT EXISTS ticket_id BIGINT;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'ticket' AND column_name = 'ticket_no'
    ) AND EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'workorder_review' AND column_name = 'ticket_no'
    ) THEN
        IF EXISTS (
            SELECT 1
            FROM public.workorder_review wr
            LEFT JOIN public.ticket t ON t.ticket_no = wr.ticket_no
            WHERE wr.ticket_id IS NULL
            GROUP BY wr.ticket_no
            HAVING count(t.id) <> 1
        ) THEN
            RAISE EXCEPTION '存在无法唯一映射 ticket.id 的审核记录，请先修复 ticket_no 数据';
        END IF;

        UPDATE public.workorder_review wr
        SET ticket_id = t.id
        FROM public.ticket t
        WHERE wr.ticket_id IS NULL AND wr.ticket_no = t.ticket_no;
    END IF;

    IF EXISTS (SELECT 1 FROM public.workorder_review WHERE ticket_id IS NULL) THEN
        RAISE EXCEPTION '存在无法关联 ticket.id 的审核记录，请先补齐 ticket_id';
    END IF;
END $$;

ALTER TABLE public.workorder_review
    ALTER COLUMN ticket_id SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS workorder_review_ticket_id_key
    ON public.workorder_review (ticket_id);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'workorder_review_ticket_id_fkey'
          AND conrelid = 'public.workorder_review'::regclass
    ) THEN
        ALTER TABLE public.workorder_review
            ADD CONSTRAINT workorder_review_ticket_id_fkey
            FOREIGN KEY (ticket_id) REFERENCES public.ticket (id);
    END IF;
END $$;

ALTER TABLE public.workorder_review
    DROP COLUMN IF EXISTS ticket_no;

COMMIT;
