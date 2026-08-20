CREATE TABLE marko_activities (
    activity_id text PRIMARY KEY,
    effective_at timestamptz NOT NULL,
    recorded_at timestamptz NOT NULL,
    sequence bigint NOT NULL CHECK (sequence >= 0),
    payload jsonb NOT NULL,
    payload_hash text NOT NULL CHECK (length(payload_hash) = 64),
    persisted_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX marko_activities_order_idx
    ON marko_activities (effective_at, recorded_at, sequence, activity_id);

CREATE TABLE marko_observations (
    observation_id text PRIMARY KEY,
    series_id text NOT NULL,
    effective_at timestamptz NOT NULL,
    available_at timestamptz NOT NULL,
    vintage_id text NOT NULL,
    dimensions jsonb NOT NULL,
    payload jsonb NOT NULL,
    payload_hash text NOT NULL CHECK (length(payload_hash) = 64),
    persisted_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX marko_observations_pit_idx
    ON marko_observations (series_id, available_at, effective_at);

CREATE TABLE marko_model_runs (
    run_id text PRIMARY KEY,
    created_at timestamptz NOT NULL,
    payload jsonb NOT NULL,
    payload_hash text NOT NULL CHECK (length(payload_hash) = 64),
    persisted_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX marko_model_runs_created_idx ON marko_model_runs (created_at, run_id);

CREATE TABLE marko_decision_packets (
    packet_id text PRIMARY KEY,
    created_at timestamptz NOT NULL,
    payload jsonb NOT NULL,
    payload_hash text NOT NULL CHECK (length(payload_hash) = 64),
    persisted_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX marko_decision_packets_created_idx
    ON marko_decision_packets (created_at, packet_id);

CREATE FUNCTION marko_forbid_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'Marko persistence is append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER marko_activities_immutable
    BEFORE UPDATE OR DELETE ON marko_activities
    FOR EACH ROW EXECUTE FUNCTION marko_forbid_mutation();

CREATE TRIGGER marko_observations_immutable
    BEFORE UPDATE OR DELETE ON marko_observations
    FOR EACH ROW EXECUTE FUNCTION marko_forbid_mutation();

CREATE TRIGGER marko_model_runs_immutable
    BEFORE UPDATE OR DELETE ON marko_model_runs
    FOR EACH ROW EXECUTE FUNCTION marko_forbid_mutation();

CREATE TRIGGER marko_decision_packets_immutable
    BEFORE UPDATE OR DELETE ON marko_decision_packets
    FOR EACH ROW EXECUTE FUNCTION marko_forbid_mutation();
