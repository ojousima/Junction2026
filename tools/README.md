# tools/

Dev-side utilities (run on your laptop, not on the UNO Q).

## simulator.py

Fake sensor feed for the `sensors.measurements` table on Aiven Postgres.
Two simulated outdoor sensors, each a mean-reverting random walk:

| Sensor | UUID | Tends toward |
|---|---|---|
| A | `64d342b4-3a03-5845-8475-a6122e591c23` | −5 °C, 75 % RH |
| B | `fe8cf164-302d-5e18-b336-9c26956aec73` | −9 °C, ~100 % RH (same air mass, clamped at saturation) |

The table must already exist — the simulator only inserts:

```sql
CREATE TABLE sensors.measurements (
    sensor_id UUID NOT NULL,
    time TIMESTAMPTZ NOT NULL,
    temperature DOUBLE PRECISION,
    humidity DOUBLE PRECISION
);
```

### Usage

```bash
pip install -r requirements-dev.txt   # psycopg2-binary
export PG_CONNINFO="postgresql://user:pass@host:port/dbname?sslmode=require"

python3 tools/simulator.py            # one sample per sensor per minute
python3 tools/simulator.py --interval 5   # faster, for testing
python3 tools/simulator.py --dry-run      # print rows, no database needed
```

### Troubleshooting

- `connection failed: timeout expired` → host unreachable, check with
  `nc -vz <host> <port>` (firewall/VPN/wifi issue, not the script).
- `connection failed: ...SSL...` / auth error → check the `PG_CONNINFO` URI.
- `permission denied for table measurements` → the DB user needs INSERT rights;
  ask whoever provisioned the schema.

Never commit `PG_CONNINFO` — it contains the password.

## fetch_audio.py

Downloads public machine-sound data (CANDAS fan imbalance, MIMII fan, RWTH heat pump
stimuli, ESC-50 background noise) into `data/audio/` as 16 kHz mono WAV for Edge
Impulse. Standard library plus `ffmpeg`. Layout, licenses and upload commands:
see [data/audio/README.md](../data/audio/README.md).

```bash
python3 tools/fetch_audio.py                # everything, about 2.5 GB download
python3 tools/fetch_audio.py --only candas  # one source
```
