ALTER TABLE marko_activities
    ADD CONSTRAINT marko_activities_payload_identity_check CHECK (
        payload ->> 'schema' = 'marko.activity'
        AND (payload ->> 'version')::integer = 1
        AND payload #>> '{payload,activity_id}' = activity_id
        AND (payload #>> '{payload,effective_at}')::timestamptz = effective_at
        AND (payload #>> '{payload,recorded_at}')::timestamptz = recorded_at
        AND (payload #>> '{payload,sequence}')::bigint = sequence
    );

ALTER TABLE marko_observations
    ADD CONSTRAINT marko_observations_payload_identity_check CHECK (
        payload ->> 'schema' = 'marko.observation'
        AND (payload ->> 'version')::integer = 1
        AND payload #>> '{payload,observation_id}' = observation_id
        AND payload #>> '{payload,series_id}' = series_id
        AND (payload #>> '{payload,times,effective_at}')::timestamptz = effective_at
        AND (payload #>> '{payload,times,available_at}')::timestamptz = available_at
        AND payload #>> '{payload,vintage_id}' = vintage_id
        AND payload #> '{payload,dimensions}' = dimensions
    );

ALTER TABLE marko_model_runs
    ADD CONSTRAINT marko_model_runs_payload_identity_check CHECK (
        payload ->> 'schema' = 'marko.model_run'
        AND (payload ->> 'version')::integer = 1
        AND payload #>> '{payload,run_id}' = run_id
        AND (payload #>> '{payload,created_at}')::timestamptz = created_at
    );

ALTER TABLE marko_decision_packets
    ADD CONSTRAINT marko_decision_packets_payload_identity_check CHECK (
        payload ->> 'schema' = 'marko.decision_packet'
        AND (payload ->> 'version')::integer = 1
        AND payload #>> '{payload,packet_id}' = packet_id
        AND (payload #>> '{payload,created_at}')::timestamptz = created_at
    );

REVOKE UPDATE, DELETE, TRUNCATE ON TABLE
    marko_activities,
    marko_observations,
    marko_model_runs,
    marko_decision_packets
FROM PUBLIC;
