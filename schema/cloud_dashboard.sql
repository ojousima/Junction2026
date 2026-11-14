-- Run as a database administrator after creating the cloud_dashboard service user.
CREATE SCHEMA IF NOT EXISTS cloud;

CREATE TABLE IF NOT EXISTS cloud.push_subscriptions (
    endpoint TEXT PRIMARY KEY,
    device_id UUID NOT NULL,
    subscription JSONB NOT NULL,
    created TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cloud.alert_state (
    device_id UUID NOT NULL,
    component TEXT NOT NULL,
    level TEXT NOT NULL,
    time TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (device_id, component)
);

GRANT USAGE ON SCHEMA sensors, cloud TO cloud_dashboard;
GRANT SELECT ON sensors.health_status TO cloud_dashboard;
GRANT SELECT, INSERT, UPDATE, DELETE ON cloud.push_subscriptions TO cloud_dashboard;
GRANT SELECT, INSERT, UPDATE ON cloud.alert_state TO cloud_dashboard;
