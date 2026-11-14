# Telemetry database contract

The existing simulator documents `sensors.measurements` as follows. This is the
repository's documented contract, not a live database inspection:

```sql
CREATE TABLE sensors.measurements (
    sensor_id UUID NOT NULL,
    time TIMESTAMPTZ NOT NULL,
    temperature DOUBLE PRECISION,
    humidity DOUBLE PRECISION
);
```

Each row contains one physical sensor's temperature in degrees Celsius and
relative humidity in percent, at the UTC acquisition time. The existing
simulator uses two fixed UUIDs; the real board uses a different, stable UUID.
There is currently one physical Thermo. No second temperature is invented.

The sensor ID is UUIDv5 (`NAMESPACE_URL`) of
`heat-pump-doctor/<hardware-serial>/thermo-1`, using the Linux SoC serial at
`/sys/devices/soc0/serial_number`. The connected UNO Q exposes this path
inside its App Lab container. The publisher reports an error and does not send
if it cannot read the serial; it does not fall back to a shared default. The
derived UUID is an identifier, not authentication or a secret.

The separate [telemetry_metrics.sql](telemetry_metrics.sql) is a proposed
schema for future audio and video analytics, with one row per scalar data
point and primary key `(sensor_id, time, metric)`. It is not required by the
current temperature publisher and should not be applied until that integration
is implemented and reviewed. The publisher's audio and video functions are
placeholders: they send no values.

At each upload interval the app sends the latest new Thermo sample, not every
one-second sample. Missing/failed sensors produce no fabricated values. Each
upload is one database transaction. A failed upload is logged and the latest
available sample is retried at the next interval; newer samples can replace it,
and there is no durable offline queue. The existing measurements table has no
documented unique constraint: an ambiguous commit or restart can duplicate a
temperature row. The sensor clock must be correct.
