CREATE TABLE marko_shadow_run_requests (
    request_id text PRIMARY KEY,
    schedule_id text NOT NULL,
    scheduled_for timestamptz NOT NULL,
    knowledge_cutoff timestamptz NOT NULL,
    payload jsonb NOT NULL,
    payload_hash text NOT NULL CHECK (length(payload_hash) = 64),
    persisted_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT marko_shadow_requests_id_check CHECK (
        request_id ~ '^[0-9a-f]{64}$' AND btrim(schedule_id) <> ''
    ),
    CONSTRAINT marko_shadow_requests_cutoff_check CHECK (
        knowledge_cutoff <= scheduled_for
    ),
    CONSTRAINT marko_shadow_requests_payload_identity_check CHECK (
        payload ->> 'schema' = 'marko.shadow_run_request'
        AND (payload ->> 'version')::integer = 1
        AND payload #>> '{payload,request_id}' = request_id
        AND payload #>> '{payload,schedule_id}' = schedule_id
        AND (payload #>> '{payload,scheduled_for}')::timestamptz = scheduled_for
        AND (payload #>> '{payload,knowledge_cutoff}')::timestamptz = knowledge_cutoff
    )
);

CREATE INDEX marko_shadow_requests_schedule_idx
    ON marko_shadow_run_requests (scheduled_for, request_id);

CREATE TRIGGER marko_shadow_run_requests_immutable
    BEFORE UPDATE OR DELETE ON marko_shadow_run_requests
    FOR EACH ROW EXECUTE FUNCTION marko_forbid_mutation();

ALTER TABLE marko_decision_packets
    DROP CONSTRAINT marko_decision_packets_payload_identity_check;

ALTER TABLE marko_decision_packets
    ADD COLUMN shadow_request_id text NULL,
    ADD COLUMN knowledge_cutoff timestamptz NULL,
    ADD CONSTRAINT marko_decision_packets_shadow_pair_check CHECK (
        (shadow_request_id IS NULL) = (knowledge_cutoff IS NULL)
        AND (knowledge_cutoff IS NULL OR knowledge_cutoff <= created_at)
    ),
    ADD CONSTRAINT marko_decision_packets_shadow_request_fk FOREIGN KEY (shadow_request_id)
        REFERENCES marko_shadow_run_requests (request_id),
    ADD CONSTRAINT marko_decision_packets_payload_identity_check CHECK (
        payload ->> 'schema' = 'marko.decision_packet'
        AND (payload ->> 'version')::integer IN (1, 2)
        AND payload #>> '{payload,packet_id}' = packet_id
        AND (payload #>> '{payload,created_at}')::timestamptz = created_at
        AND (
            (payload ->> 'version')::integer = 1
            OR (
                payload #>> '{payload,shadow_request_id}' IS NOT DISTINCT FROM shadow_request_id
                AND (payload #>> '{payload,knowledge_cutoff}')::timestamptz
                    IS NOT DISTINCT FROM knowledge_cutoff
            )
        )
    );

CREATE INDEX marko_decision_packets_shadow_request_idx
    ON marko_decision_packets (shadow_request_id)
    WHERE shadow_request_id IS NOT NULL;

REVOKE UPDATE, DELETE, TRUNCATE ON TABLE marko_shadow_run_requests FROM PUBLIC;
