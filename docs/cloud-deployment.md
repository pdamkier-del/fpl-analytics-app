# FPL shared mobile and desktop cloud deployment

Status: *cloud bridge-preview backend* only. It serves existing static forecasts;
it does NOT run the locked MM -> PM/vFinal -> TS -> chip models. Never claim that
the forecast has been updated without a full, validated model run.

## Render deployment

1. Connect GitHub repository to Render and create a **Blueprint** from
   `render.yaml` on branch `cloud-shared-backend-20261010`.
2. Provide `FPL_APP_USER` and a unique random `FPL_APP_PASSWORD` of at least
   20 characters using Render's secret environment fields. **Do not commit credentials.**
3. Confirm the Starter plan and persistent 1 GB disk pricing before creating
   the service. SSL/HTTPS is provided by Render.
4. Open the service's `https://...` address in Safari or on desktop.
   Log in with the configured credentials and use the same address on both devices.
5. On iPhone, Safari Share -> Add to Home Screen. Use the cloud URL rather than
   GitHub Pages if you need squad synchronization.

All existing desktop bridge data are kept. The durable SQLite squad database
is stored in the attached disk at `/data/users.sqlite3`. Keep backups and do
not replace the disk during re-deploys.

Security: basic auth is required on every page and API endpoint. Only use HTTPS.
No FPL credentials are needed or supported. There is one shared user; sharing the
password shares the squad. Model configuration edits are disabled on cloud.
For production, replace Basic auth with session-based auth, CSRF protection,
rate limiting, security monitoring and tested backup restoration.

Legacy desktop `start_app.py` still runs locally and stores its separate
`user/squad.json`. To share the same squad between devices, open the cloud URL
on the desktop instead of the local localhost URL.

## Limitations and required next release
- Official data, injury updates and projected starting XIs require a scheduled
  source pipeline and independent freshness checks.
- Actual locked forecast generation and immutable version checks must be
  implemented and certified before enabling POST /api/forecast/refresh.
- Authenticated requests to POST /api/forecast/refresh currently fail closed (503).
- Backend optimizer endpoints use the existing preview/bridge, not locked TS.
- The snapshot shipped in source must not be described as live.
- Check memory requirements with real model samples before choosing a larger plan.
