#!/usr/bin/env python3
"""Sensor simulator for the sensors.measurements table on Aiven Postgres.

Two simulated outdoor sensors, each a mean-reverting random walk (OU process):
  - sensor A tends toward -5 C and 75 % RH
  - sensor B tends toward -9 C and the RH the same air mass would have at -9 C
    (same absolute humidity, saturation vapour pressure ratio, clamped <= 100 %)

Both sensors report one row per interval (default 60 s), in one INSERT.

The sensors.measurements table must already exist; this script only inserts.

Usage:
  PG_CONNINFO="postgresql://user:pass@host:port/db?sslmode=require" \
      python3 tools/simulator.py [--interval 60] [--dry-run]

  --dry-run   print rows instead of inserting (no database needed)
"""
import argparse
import math
import random
import time
import uuid
from datetime import datetime, timezone

# Stable IDs so every run reports as the same two sensors.
SENSOR_A = uuid.uuid5(uuid.NAMESPACE_URL, "https://github.com/ojousima/Junction2026/sim/outdoor-a")
SENSOR_B = uuid.uuid5(uuid.NAMESPACE_URL, "https://github.com/ojousima/Junction2026/sim/outdoor-b")

THETA = 0.1          # mean-reversion speed per step
SIGMA_T = 0.15       # temperature walk noise, C per step
SIGMA_RH = 0.6       # humidity walk noise, % per step

TARGET_A_T, TARGET_A_RH = -5.0, 75.0
TARGET_B_T = -9.0


def svp_magnus(temp_c):
    """Saturation vapour pressure over water (Pa), Magnus formula."""
    return 610.94 * math.exp(17.625 * temp_c / (temp_c + 243.04))


# RH at -9 C for the air mass that is at 75 % RH at -5 C. Clamped at 100 %:
# that air mass is near saturation at -9 C, i.e. frost-forming conditions.
TARGET_B_RH = min(100.0, TARGET_A_RH * svp_magnus(TARGET_A_T) / svp_magnus(TARGET_B_T))


class Sensor:
    """Mean-reverting random walk around (target_t, target_rh)."""

    def __init__(self, sensor_id, target_t, target_rh):
        self.sensor_id = sensor_id
        self.target_t = target_t
        self.target_rh = target_rh
        self.t = target_t + random.gauss(0, 1.0)
        self.rh = target_rh + random.gauss(0, 3.0)

    def step(self):
        self.t += THETA * (self.target_t - self.t) + random.gauss(0, SIGMA_T)
        self.rh += THETA * (self.target_rh - self.rh) + random.gauss(0, SIGMA_RH)
        self.rh = max(0.0, min(100.0, self.rh))
        return (str(self.sensor_id), datetime.now(timezone.utc),
                round(self.t, 2), round(self.rh, 1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--interval", type=float, default=60.0, help="seconds between samples (default 60)")
    ap.add_argument("--dry-run", action="store_true", help="print rows, don't touch the database")
    args = ap.parse_args()
    if not math.isfinite(args.interval) or args.interval <= 0:
        ap.error("--interval must be a positive, finite number")

    print(f"sensor A {SENSOR_A} -> ({TARGET_A_T} C, {TARGET_A_RH} %RH)")
    print(f"sensor B {SENSOR_B} -> ({TARGET_B_T} C, {TARGET_B_RH:.1f} %RH)")

    conn = None
    if not args.dry_run:
        import os
        import psycopg2
        conninfo = os.environ.get("PG_CONNINFO")
        if not conninfo:
            raise SystemExit("PG_CONNINFO env var not set (or use --dry-run)")
        print("connecting to database...")
        try:
            conn = psycopg2.connect(conninfo, connect_timeout=10)
        except Exception as exc:
            raise SystemExit(f"connection failed: {exc}")
        conn.autocommit = True
        print("connected")

    sensors = [Sensor(SENSOR_A, TARGET_A_T, TARGET_A_RH),
               Sensor(SENSOR_B, TARGET_B_T, TARGET_B_RH)]

    try:
        while True:
            rows = [s.step() for s in sensors]
            for r in rows:
                print(f"{r[1].isoformat()}  {r[0][:8]}…  {r[2]:6.2f} C  {r[3]:5.1f} %")
            if not args.dry_run:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO sensors.measurements (sensor_id, time, temperature, humidity)"
                        " VALUES (%s, %s, %s, %s), (%s, %s, %s, %s)", rows[0] + rows[1])
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    main()
