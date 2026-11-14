"""Publish sampled sensor readings to PostgreSQL without blocking acquisition."""

import math
import os
import time
import uuid
from contextlib import closing
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import execute_values


def hardware_serial():
    serial = Path("/sys/devices/soc0/serial_number").read_text(encoding="ascii").strip()
    if not serial:
        raise ValueError("hardware serial is empty")
    return serial


def sensor_id(serial, source):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"heat-pump-doctor/{serial}/{source}"))


def build_rows(state, sample_times, sent_times, serial):
    """Return the latest unsent Thermo reading."""
    measurements = []
    included = {}
    timestamp = sample_times.get("thermo")
    if (timestamp is not None and timestamp != sent_times.get("thermo")
            and state["temp_c"] is not None and state["rh"] is not None):
        measurements.append((sensor_id(serial, "thermo-1"), timestamp,
                             state["temp_c"], state["rh"]))
        included["thermo"] = timestamp

    return measurements, included


def audio_metrics():
    """Placeholder: audio telemetry is not implemented."""
    return []


def video_metrics():
    """Placeholder: video telemetry is not implemented."""
    return []


def run(snapshot):
    load_dotenv(Path(__file__).with_name(".env"), override=False)
    conninfo = os.environ.get("PG_CONNINFO")
    if not conninfo:
        print("telemetry disabled: PG_CONNINFO is not configured", flush=True)
        return

    ca_file = os.environ.get("PGSSLROOTCERT", "").strip()
    if not ca_file:
        print("telemetry configuration error: set PGSSLROOTCERT", flush=True)
        return
    try:
        serial = hardware_serial()
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"telemetry configuration error: cannot read hardware serial: {exc}", flush=True)
        return
    ca_path = Path(ca_file).expanduser()
    if not ca_path.is_absolute():
        ca_path = Path(__file__).parent / ca_path
    if not ca_path.is_file():
        print("telemetry configuration error: PGSSLROOTCERT file not found", flush=True)
        return
    try:
        interval = float(os.environ.get("TELEMETRY_INTERVAL_SECONDS", "60"))
        if not math.isfinite(interval) or interval <= 0:
            raise ValueError
    except ValueError:
        print("telemetry configuration error: TELEMETRY_INTERVAL_SECONDS must be positive and finite",
              flush=True)
        return

    sent_times = {}
    print(f"telemetry enabled: publishing latest samples every {interval:g} seconds", flush=True)
    while True:
        state, sample_times = snapshot()
        measurements, included = build_rows(state, sample_times, sent_times, serial)
        if measurements:
            try:
                with closing(psycopg2.connect(conninfo, connect_timeout=10, sslmode="verify-full",
                                              sslrootcert=str(ca_path))) as conn:
                    with conn:
                        with conn.cursor() as cur:
                            execute_values(cur, "INSERT INTO sensors.measurements "
                                           "(sensor_id, time, temperature, humidity) VALUES %s",
                                           measurements)
                sent_times.update(included)
                print(f"telemetry published: {len(measurements)} measurements", flush=True)
            except (psycopg2.Error, OSError) as exc:
                print(f"telemetry publish failed; retrying latest samples in {interval:g}s: {exc}",
                      flush=True)
        time.sleep(interval)
