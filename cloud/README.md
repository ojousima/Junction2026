# Cloud dashboard (homeowner's phone)

One screen, four answers: **Coil cleanliness, Fan, Compressor, Defrost**, each OK /
Watch / Action with one plain sentence, plus a push notification on the phone when
something needs action. All diagnosis runs on the UNO Q (`python/health.py`); the board
writes one row per component to `sensors.health_status` in Aiven PostgreSQL through the
existing telemetry thread. This app only reads the latest rows and sends web push.

```
UNO Q (edge)                          Aiven
python/health.py  ── telemetry ──▶    PostgreSQL sensors.health_status
                                          │
                                      Runtime: cloud/app.py ──▶ phone (installable web app)
                                          └── web push on "alert" (VAPID)
```

## Run locally

Without `DATABASE_URL` the app runs in **demo mode** with a simulated heat pump that
walks through OK, then "getting dirty", then a fan alert every 90 s.

```bash
cd cloud
pip install -r requirements.txt
python app.py --gen-vapid > vapid.env        # once; keep the private key secret
set -a; . ./vapid.env; set +a
uvicorn app:app --port 8080                  # open http://localhost:8080
```

## Deploy on Aiven Runtime

1. **Database table** (once, as an admin on the Aiven PostgreSQL):
   run [`../schema/health_status.sql`](../schema/health_status.sql). The board's
   `sensor_writer` may only insert. The app creates its own `cloud` schema
   (push subscriptions, alert state) at startup, so its database user needs
   `CREATE` on the database and `SELECT` on `sensors.health_status`.
2. **Deploy** in the Aiven Console: Runtime > Deploy application > this GitHub repo,
   branch `main`, build path `cloud/`, Containerfile `cloud/Containerfile`, port
   `8080` (HTTP). Aiven serves it over HTTPS on its public URL.
3. **Connect PostgreSQL**: add the PostgreSQL service as an integration. Runtime injects
   the connection string as `DATABASE_URL`.
4. **Environment variables**:
   - `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` (mark as Secret) from `python app.py --gen-vapid`
   - `VAPID_SUBJECT`: a contact URI for push services, e.g. `mailto:<team address>`
   - optional `AIVEN_CA_CERT`: the project CA certificate (PEM) for verified TLS;
     without it the connection uses the URI's `sslmode` (encrypted, not verified)
   - optional `PUSH_POLL_SECONDS` (default 15)
5. Redeploys are manual: "Deploy latest commit" after merging changes.

Health check: `GET /healthz`.

## Using it

- Open the app URL on the phone. With one heat pump it opens straight to it; the URL
  becomes `/?d=<device id>`. Bookmark or share that link.
- **Alerts**: tap "Turn on alerts" and allow notifications. On iPhone (iOS 16.4+) first
  add the page to the Home Screen (Share > Add to Home Screen) and open it from there;
  Safari only allows web push for installed apps. "Send a test alert" checks the chain.
- A push is sent once when a component turns **Action** (alert). Watch-level changes
  and recoveries only show on the dashboard. The board publishes every
  `TELEMETRY_INTERVAL_SECONDS` (default 60 s), and the app checks every
  `PUSH_POLL_SECONDS`, so an alert reaches the phone within about 1-2 minutes.
- "Sensor offline" shows when the board has not reported for 10 minutes.

## Limits (hackathon scope)

- No login: anyone with the device link sees that heat pump's four statuses. The ID is a
  random-looking UUID derived from the board serial, not a secret. Add authentication
  before real customers.
- No rate limiting on the subscribe and test-push endpoints.
- Defrost uses frost weather (Thermo) and, once the camera publishes it, an icing score
  (`state["icing"]`, 0..1). Until then it can say "Watch" in frost weather but never "Action".
