-- End-user health summary published by the UNO Q (python/health.py via python/telemetry.py).
-- One row per component per upload; the cloud dashboard reads the latest row per component.
CREATE TABLE IF NOT EXISTS sensors.health_status (
    device_id UUID NOT NULL,          -- UUIDv5 of heat-pump-doctor/<serial>/heatpump-1
    time TIMESTAMPTZ NOT NULL,
    component TEXT NOT NULL,          -- coil | fan | compressor | defrost | local_ip
    level TEXT NOT NULL,              -- unknown | ok | watch | alert
    message TEXT NOT NULL,            -- health text, or the LAN address for local_ip
    PRIMARY KEY (device_id, component, time)
);
-- The board's writer may only insert; the dashboard only reads.
GRANT INSERT ON sensors.health_status TO sensor_writer;
