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
                                      Runtime: infra/aiven/cloud/app.py ──▶ phone (installable web app)
                                          └── web push on "alert" (VAPID)
```

## Run locally

Without `DATABASE_URL` the app runs in **demo mode** with a simulated heat pump that
walks through OK, then "getting dirty", then a fan alert every 90 s.

```bash
cd infra/aiven/cloud
pip install -r requirements.txt
python app.py --gen-vapid > vapid.env        # once; keep the private key secret
set -a; . ./vapid.env; set +a
uvicorn app:app --port 8080                  # open http://localhost:8080
```

## Deploy on Aiven Runtime

1. **Database tables** (once, as an admin on the Aiven PostgreSQL):
   run [`../../../schema/health_status.sql`](../../../schema/health_status.sql), create an Aiven
   service user named `cloud_dashboard`, then run
   [`../../../schema/cloud_dashboard.sql`](../../../schema/cloud_dashboard.sql). The board's
   `sensor_writer` may only insert health rows; the dashboard user can read health
   rows and manage its own subscriptions and alert state, without schema or database
   creation privileges.
2. **Deploy** in the Aiven Console: Runtime > Deploy application > this GitHub repo,
   branch `main`, build path `infra/aiven/cloud/`, Containerfile
   `infra/aiven/cloud/Containerfile`, port
   `8080` (HTTP). Aiven serves it over HTTPS on its public URL.
   For an existing application, update both paths before redeploying a revision
   that includes this move.
3. **Connect PostgreSQL**: add the PostgreSQL service as an integration, select the
   `cloud_dashboard` user and map its connection string to `DATABASE_URL`. Runtime injects the base64-encoded project CA
   as `PROJECT_CA_CERT`; the app uses it to verify the server certificate and hostname.
4. **Environment variables**:
   - `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` (mark as Secret) from `python app.py --gen-vapid`
   - `VAPID_SUBJECT`: a contact URI for push services, e.g. `mailto:<team address>`
   - optional `AIVEN_CA_CERT`: the project CA certificate as PEM text; overrides
     `PROJECT_CA_CERT`. If neither is set, the connection uses the URI's `sslmode`,
     which may not verify the server certificate.
   - optional `PUSH_POLL_SECONDS` (default 5)
5. Redeploys are manual: "Deploy latest commit" after merging changes.

On PostgreSQL startup, logs identify which CA variable is selected and whether its
value has PEM markers and line breaks, without printing certificate or credential
contents. If the environment editor cannot accept multiline PEM, put the base64-encoded
complete PEM in `PROJECT_CA_CERT` and remove `AIVEN_CA_CERT`, which takes precedence.

Health check: `GET /healthz`.

## Using it

- Open the app URL on the phone. With one heat pump it opens straight to it; the URL
  becomes `/?d=<device id>`. Bookmark or share that link.
- **Alerts**: tap "Turn on alerts" and allow notifications. On iPhone (iOS 16.4+) first
  add the page to the Home Screen (Share > Add to Home Screen) and open it from there;
  Safari only allows web push for installed apps. "Send a test alert" checks the chain.
- A push is sent once when a component turns **Action** (alert). Watch-level changes
  and recoveries only show on the dashboard. Defaults are set for the demo: the board
  publishes every `TELEMETRY_INTERVAL_SECONDS` (5 s), the app checks for alerts every
  `PUSH_POLL_SECONDS` (5 s) and the open page refreshes every 5 s, so a change shows on
  the phone within about 10 s. For long unattended runs raise the board interval
  (e.g. 60 s) to keep the database small.
- "Sensor offline" shows when the board has not reported for 10 minutes.
- The status API includes `local_ip`, the board's most recently reported Wi-Fi IPv4
  address, or `null` if unavailable. The dashboard does not display it.

## Limits (hackathon scope)

- No login: anyone with the device link sees that heat pump's four statuses. The ID is a
  random-looking UUID derived from the board serial, not a secret. Add authentication
  before real customers. The status API also exposes the board's local IP address.
- No rate limiting on the subscribe and test-push endpoints.
- Defrost uses frost weather (Thermo) and, once the camera publishes it, an icing score
  (`state["icing"]`, 0..1). Until then it can say "Watch" in frost weather but never "Action".
