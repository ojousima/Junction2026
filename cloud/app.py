"""Heat Pump Doctor, cloud side: the homeowner's phone dashboard + web push alerts.

Runs on Aiven Runtime next to the Aiven PostgreSQL the UNO Q writes to. All diagnosis
happens on the edge (python/health.py on the board); this app only shows the latest
status per component and pushes a notification when a component turns "alert".

Environment:
  DATABASE_URL       Aiven PostgreSQL service URI (injected by the Runtime integration).
                     Without it the app runs in DEMO mode with simulated data.
  AIVEN_CA_CERT      optional: project CA certificate (PEM text) for verified TLS
  VAPID_PUBLIC_KEY   web push keys, generate once with:  python app.py --gen-vapid
  VAPID_PRIVATE_KEY
  VAPID_SUBJECT      contact for push services, e.g. mailto:team@example.com
  PUSH_POLL_SECONDS  how often new alerts are checked (default 15)
"""
import base64
import ipaddress
import json
import os
import sys
import tempfile
import threading
import time
import uuid
from contextlib import asynccontextmanager, closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

STATIC = Path(__file__).parent / "static"
COMPONENTS = ["coil", "fan", "compressor", "defrost"]
ONLINE_S = 10 * 60
DB_URL = os.environ.get("DATABASE_URL", "").strip()
DEMO = not DB_URL
VAPID_PUBLIC = os.environ.get("VAPID_PUBLIC_KEY", "").strip()
VAPID_PRIVATE = os.environ.get("VAPID_PRIVATE_KEY", "").strip()
VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "mailto:admin@example.com").strip()
POLL_S = float(os.environ.get("PUSH_POLL_SECONDS", "15"))
PUSH_SERVICE_HOSTS = {
    "fcm.googleapis.com",
    "updates.push.services.mozilla.com",
    "web.push.apple.com",
}



@asynccontextmanager
async def lifespan(_app):
    print(f"Heat Pump Doctor cloud: {'DEMO mode' if DEMO else 'PostgreSQL'}, "
          f"push {'on' if VAPID_PRIVATE else 'off (no VAPID keys)'}", flush=True)
    threading.Thread(target=push_loop, daemon=True).start()
    yield


app = FastAPI(title="Heat Pump Doctor", lifespan=lifespan)


# --- Storage: PostgreSQL, or in-memory demo -----------------------------------------
class Postgres:
    def __init__(self, url):
        import psycopg2
        import psycopg2.extras
        self.pg, self.extras = psycopg2, psycopg2.extras
        self.kwargs = {}
        ca = os.environ.get("AIVEN_CA_CERT", "").strip()
        if ca:  # verified TLS when the CA is provided; otherwise the URI's sslmode applies
            f = tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False)
            f.write(ca + "\n")
            f.close()
            self.kwargs = {"sslmode": "verify-full", "sslrootcert": f.name}
        self.url = url
        self.run("""
            CREATE SCHEMA IF NOT EXISTS cloud;
            CREATE TABLE IF NOT EXISTS cloud.push_subscriptions (
                endpoint TEXT PRIMARY KEY, device_id UUID NOT NULL, subscription JSONB NOT NULL,
                created TIMESTAMPTZ NOT NULL DEFAULT now());
            CREATE TABLE IF NOT EXISTS cloud.alert_state (
                device_id UUID NOT NULL, component TEXT NOT NULL, level TEXT NOT NULL,
                time TIMESTAMPTZ NOT NULL, PRIMARY KEY (device_id, component));""")

    def run(self, sql, args=(), fetch=False):
        with closing(self.pg.connect(self.url, connect_timeout=10, **self.kwargs)) as conn:
            with conn, conn.cursor(cursor_factory=self.extras.RealDictCursor) as cur:
                cur.execute(sql, args)
                return cur.fetchall() if fetch else None

    def devices(self):
        return [r["device_id"] for r in self.run(
            "SELECT DISTINCT device_id::text FROM sensors.health_status "
            "WHERE time > now() - interval '30 days'", fetch=True)]

    def latest(self, device):
        rows = self.run("""SELECT DISTINCT ON (component) component, level, message, time
                           FROM sensors.health_status WHERE device_id = %s
                           ORDER BY component, time DESC""", (device,), fetch=True)
        return {r["component"]: {"level": r["level"], "text": r["message"], "time": r["time"]} for r in rows}

    def subscribe(self, device, sub):
        self.run("""INSERT INTO cloud.push_subscriptions (endpoint, device_id, subscription)
                    VALUES (%s, %s, %s) ON CONFLICT (endpoint) DO UPDATE
                    SET device_id = EXCLUDED.device_id, subscription = EXCLUDED.subscription""",
                 (sub["endpoint"], device, json.dumps(sub)))

    def unsubscribe(self, endpoint):
        self.run("DELETE FROM cloud.push_subscriptions WHERE endpoint = %s", (endpoint,))

    def subscriptions(self, device=None):
        rows = self.run("SELECT device_id::text, subscription FROM cloud.push_subscriptions"
                        + (" WHERE device_id = %s" if device else ""), (device,) if device else (), fetch=True)
        return [(r["device_id"], r["subscription"]) for r in rows]

    def alert_state(self, device):
        return {r["component"]: r["level"] for r in self.run(
            "SELECT component, level FROM cloud.alert_state WHERE device_id = %s", (device,), fetch=True)}

    def set_alert_state(self, device, component, level):
        self.run("""INSERT INTO cloud.alert_state VALUES (%s, %s, %s, now())
                    ON CONFLICT (device_id, component) DO UPDATE SET level = EXCLUDED.level, time = now()""",
                 (device, component, level))


class Demo:
    """Simulated heat pump so the dashboard and push can be shown without the board.

    Every 90 s it walks through: all OK -> coil getting dirty -> fan alert -> OK.
    """
    DEVICE = "00000000-0000-5000-8000-000000000001"
    SCRIPT = [
        {"coil": "ok", "fan": "ok", "compressor": "ok", "defrost": "ok"},
        {"coil": "watch", "fan": "ok", "compressor": "ok", "defrost": "watch"},
        {"coil": "watch", "fan": "alert", "compressor": "ok", "defrost": "watch"},
    ]
    TEXT = {
        ("coil", "ok"): "Coil clean", ("coil", "watch"): "Coil getting dirty: plan a cleaning",
        ("fan", "ok"): "Fan OK", ("fan", "alert"): "Fan problem: check for ice, leaves or a loose part",
        ("compressor", "ok"): "Compressor OK",
        ("defrost", "ok"): "Defrost OK", ("defrost", "watch"): "Frost weather: defrost is working hard",
    }

    def __init__(self):
        self.subs, self.alerts = {}, {}

    def devices(self):
        return [self.DEVICE]

    def latest(self, device):
        if device != self.DEVICE:
            return {}
        step = self.SCRIPT[int(time.time() // 90) % len(self.SCRIPT)]
        now = datetime.now(timezone.utc)
        return {c: {"level": lv, "text": self.TEXT[(c, lv)], "time": now} for c, lv in step.items()}

    def subscribe(self, device, sub):
        self.subs[sub["endpoint"]] = (device, sub)

    def unsubscribe(self, endpoint):
        self.subs.pop(endpoint, None)

    def subscriptions(self, device=None):
        return [v for v in self.subs.values() if device is None or v[0] == device]

    def alert_state(self, device):
        return dict(self.alerts.get(device, {}))

    def set_alert_state(self, device, component, level):
        self.alerts.setdefault(device, {})[component] = level


store = Demo() if DEMO else Postgres(DB_URL)


def valid_device(device):
    try:
        return str(uuid.UUID(device))
    except (ValueError, TypeError):
        raise HTTPException(400, "unknown device")


# --- Status API -------------------------------------------------------------------
@app.get("/api/devices")
def api_devices():
    return {"devices": store.devices(), "demo": DEMO}


@app.get("/api/status/{device}")
def api_status(device: str):
    device = valid_device(device)
    latest = store.latest(device)
    if not latest:
        raise HTTPException(404, "no data from this device yet")
    last = max(c["time"] for c in latest.values())
    age = (datetime.now(timezone.utc) - last).total_seconds()
    order = ["unknown", "ok", "watch", "alert"]
    known = [c["level"] for c in latest.values() if c["level"] != "unknown"]
    return {
        "device": device, "demo": DEMO,
        "last_seen": last.isoformat(), "age_s": round(age), "online": age < ONLINE_S,
        "overall": max(known, key=order.index) if known else "unknown",
        "components": {c: {"level": latest[c]["level"], "text": latest[c]["text"]}
                       for c in COMPONENTS if c in latest},
    }


# --- Web push ---------------------------------------------------------------------
def send_push(sub, payload):
    """Send one notification; return sent, expired, or retry."""
    if not valid_push_endpoint(sub.get("endpoint")):
        print("push rejected: unapproved endpoint", flush=True)
        return "expired"

    from pywebpush import WebPushException, webpush

    try:
        with push_requests_session() as session:
            webpush(subscription_info=sub, data=json.dumps(payload), vapid_private_key=VAPID_PRIVATE,
                    vapid_claims={"sub": VAPID_SUBJECT}, ttl=3600, requests_session=session)
        return "sent"
    except WebPushException as e:
        status = getattr(e.response, "status_code", None)
        print(f"push failed ({status}): {e}", flush=True)
        return "expired" if status in (404, 410) else "retry"


def valid_push_endpoint(endpoint):
    if not isinstance(endpoint, str):
        return False
    try:
        parsed = urlsplit(endpoint)
        host = parsed.hostname
        port = parsed.port
    except ValueError:
        return False
    if (parsed.scheme != "https" or not host or parsed.username or parsed.password
            or port not in (None, 443)):
        return False
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return False
    return host.lower() in PUSH_SERVICE_HOSTS


def push_requests_session():
    import requests

    class NoRedirectSession(requests.Session):
        def request(self, method, url, **kwargs):
            kwargs["allow_redirects"] = False
            return super().request(method, url, **kwargs)

    return NoRedirectSession()


def push_alert(device, component, text, pending):
    """Attempt an alert for pending recipients; return True when all are handled."""
    key = (device, component)
    if key not in pending:
        pending[key] = {
            sub["endpoint"]: sub for _, sub in store.subscriptions(device)
        }

    payload = {"title": "Heat pump: action needed", "body": text,
               "device": device, "tag": f"{device}-{component}"}
    for endpoint, sub in list(pending[key].items()):
        result = send_push(sub, payload)
        if result == "expired":
            store.unsubscribe(endpoint)
        if result in ("sent", "expired"):
            del pending[key][endpoint]

    if pending[key]:
        return False
    del pending[key]
    return True


@app.get("/api/push/key")
def api_push_key():
    return {"publicKey": VAPID_PUBLIC or None}


@app.post("/api/push/subscribe")
async def api_subscribe(req: Request):
    body = await req.json()
    sub, device = body.get("subscription") or {}, valid_device(body.get("device"))
    if not valid_push_endpoint(sub.get("endpoint")) or "keys" not in sub:
        raise HTTPException(400, "bad subscription")
    store.subscribe(device, sub)
    return {"ok": True}


@app.post("/api/push/unsubscribe")
async def api_unsubscribe(req: Request):
    store.unsubscribe((await req.json()).get("endpoint", ""))
    return {"ok": True}


@app.post("/api/push/test")
async def api_push_test(req: Request):
    device = valid_device((await req.json()).get("device"))
    if not VAPID_PRIVATE:
        raise HTTPException(503, "push not configured")
    n = 0
    for _, sub in store.subscriptions(device):
        result = send_push(sub, {"title": "Heat Pump Doctor", "body": "Test: alerts are working.",
                                 "device": device, "tag": "test"})
        if result == "sent":
            n += 1
        elif result == "expired":
            store.unsubscribe(sub["endpoint"])
    return {"sent": n}


def push_loop():
    """Push when a component becomes 'alert' (once per transition, not every poll)."""
    pending = {}
    while True:
        try:
            for device in {d for d, _ in store.subscriptions()}:
                latest, seen = store.latest(device), store.alert_state(device)
                for comp, c in latest.items():
                    if c["level"] == seen.get(comp):
                        continue
                    if c["level"] == "alert" and VAPID_PRIVATE:
                        if push_alert(device, comp, c["text"], pending):
                            store.set_alert_state(device, comp, c["level"])
                    else:
                        pending.pop((device, comp), None)
                        store.set_alert_state(device, comp, c["level"])
        except Exception as e:  # keep the loop alive through DB hiccups
            print(f"push loop error: {e}", flush=True)
        time.sleep(POLL_S)


# --- Static app (installable web app) -----------------------------------------------
@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/sw.js")
def service_worker():
    return FileResponse(STATIC / "sw.js", media_type="text/javascript",
                        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"})


@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(STATIC / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/icon.svg")
def icon():
    return FileResponse(STATIC / "icon.svg", media_type="image/svg+xml")


@app.get("/icon-192.png")
def icon_png():
    return FileResponse(STATIC / "icon-192.png", media_type="image/png")


def gen_vapid():
    """Print a new VAPID key pair as environment variables."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    key = ec.generate_private_key(ec.SECP256R1())
    b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()  # noqa: E731
    priv = key.private_numbers().private_value.to_bytes(32, "big")
    pub = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    print(f"VAPID_PUBLIC_KEY={b64(pub)}\nVAPID_PRIVATE_KEY={b64(priv)}")


if __name__ == "__main__" and "--gen-vapid" in sys.argv:
    gen_vapid()
