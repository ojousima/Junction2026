-- Proposed future audio/video schema; not used by the current publisher.
CREATE TABLE sensors.telemetry_metrics (
    sensor_id UUID NOT NULL,
    time TIMESTAMPTZ NOT NULL,
    metric TEXT NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    unit TEXT NOT NULL,
    PRIMARY KEY (sensor_id, time, metric)
);
