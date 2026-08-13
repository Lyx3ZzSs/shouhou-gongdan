BEGIN;

CREATE TABLE IF NOT EXISTS public.review_submission (
    idempotency_key VARCHAR(128) PRIMARY KEY,
    workorder_id    VARCHAR(64)  NOT NULL,
    session_id      VARCHAR(64)  NOT NULL,
    decision        VARCHAR(16)  NOT NULL,
    request_hash    VARCHAR(64)  NOT NULL,
    response_data   JSONB        NOT NULL,
    operator_id     VARCHAR(64)  NOT NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_submission_session UNIQUE (workorder_id, session_id)
);
CREATE INDEX IF NOT EXISTS idx_submission_workorder ON public.review_submission (workorder_id);

COMMIT;
