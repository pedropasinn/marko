ALTER TABLE marko_decision_packets
    DROP CONSTRAINT marko_decision_packets_payload_identity_check;

ALTER TABLE marko_decision_packets
    ADD CONSTRAINT marko_decision_packets_payload_identity_check CHECK (
        payload ->> 'schema' = 'marko.decision_packet'
        AND (payload ->> 'version')::integer IN (1, 2, 3)
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
