CREATE TABLE marko_shadow_cycle_records (
    record_id text PRIMARY KEY,
    request_id text NOT NULL UNIQUE,
    packet_id text NOT NULL UNIQUE,
    knowledge_cutoff timestamptz NOT NULL,
    journal_state text NOT NULL,
    journal_head_hash text NOT NULL,
    payload jsonb NOT NULL,
    payload_hash text NOT NULL CHECK (length(payload_hash) = 64),
    persisted_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT marko_shadow_cycle_record_id_check CHECK (record_id ~ '^[0-9a-f]{64}$'),
    CONSTRAINT marko_shadow_cycle_journal_hash_check CHECK (
        journal_head_hash ~ '^[0-9a-f]{64}$'
    ),
    CONSTRAINT marko_shadow_cycle_state_check CHECK (
        journal_state IN ('scheduled', 'blocked', 'draft', 'reviewed', 'reconciled')
    ),
    CONSTRAINT marko_shadow_cycle_request_fk FOREIGN KEY (request_id)
        REFERENCES marko_shadow_run_requests (request_id),
    CONSTRAINT marko_shadow_cycle_packet_fk FOREIGN KEY (packet_id)
        REFERENCES marko_decision_packets (packet_id),
    CONSTRAINT marko_shadow_cycle_payload_identity_check CHECK (
        payload ->> 'schema' = 'marko.shadow_cycle_record'
        AND (payload ->> 'version')::integer = 1
        AND payload #>> '{payload,record_id}' = record_id
        AND payload #>> '{payload,request_ref,request_id}' = request_id
        AND payload #>> '{payload,decision_packet_ref,packet_id}' = packet_id
        AND (payload #>> '{payload,knowledge_cutoff}')::timestamptz = knowledge_cutoff
        AND payload #>> '{payload,journal,events,-1,state}' = journal_state
        AND payload #>> '{payload,journal,events,-1,content_hash}' = journal_head_hash
    )
);

CREATE INDEX marko_shadow_cycle_cutoff_idx
    ON marko_shadow_cycle_records (knowledge_cutoff, request_id);

CREATE TRIGGER marko_shadow_cycle_records_immutable
    BEFORE UPDATE OR DELETE ON marko_shadow_cycle_records
    FOR EACH ROW EXECUTE FUNCTION marko_forbid_mutation();

REVOKE UPDATE, DELETE, TRUNCATE ON TABLE marko_shadow_cycle_records FROM PUBLIC;
